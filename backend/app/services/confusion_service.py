import logging
from typing import List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppException, ResourceNotFoundError
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.evidence import Evidence
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.services.coordinates import compute_coordinates
from app.services.signal_engine import SegmentSignalMetrics, signal_engine

logger = logging.getLogger("classsense.confusion_service")


class ConfusionService:
    """Service orchestrating empirical acoustic/linguistic confusion signal analysis and evidence persistence."""

    async def create_analysis_job(self, db: AsyncSession, lecture_id: str) -> Job:
        """Validates lecture transcripts and creates a persisted confusion signal analysis Job."""
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        res = await db.execute(stmt)
        lecture = res.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        stmt_seg = select(TranscriptSegment).where(TranscriptSegment.lecture_id == lecture_id).limit(1)
        res_seg = await db.execute(stmt_seg)
        if not res_seg.scalar_one_or_none():
            raise AppException(
                f"Lecture '{lecture.title}' has no transcript segments. Transcribe the lecture before analyzing signals.",
                code="TRANSCRIPT_MISSING",
                status_code=400,
            )

        job = Job(
            job_type="confusion_analysis",
            status="queued",
            progress_pct=0,
            payload={"lecture_id": lecture.id},
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created confusion signal analysis job {job.id} for lecture {lecture.id}")
        return job

    async def run_confusion_pipeline(self, job_id: str) -> None:
        """Background worker that runs the signal engine, clusters friction moments, and persists ConfusionEvents and Evidence."""
        async with async_session_factory() as db:
            res_j = await db.execute(select(Job).where(Job.id == job_id))
            job = res_j.scalar_one_or_none()
            if not job:
                return

            lecture_id = job.payload.get("lecture_id") if job.payload else None
            res_l = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
            lecture = res_l.scalar_one_or_none()
            if not lecture:
                job.status = "failed"
                job.error_message = f"Lecture {lecture_id} not found."
                await db.commit()
                return

            try:
                # Step 1: Initialize (20%)
                job.status = "running"
                job.progress_pct = 20
                await db.commit()

                # Fetch all transcript segments
                stmt_s = (
                    select(TranscriptSegment)
                    .where(TranscriptSegment.lecture_id == lecture.id)
                    .order_by(TranscriptSegment.start_time.asc())
                )
                res_s = await db.execute(stmt_s)
                segments = list(res_s.scalars().all())

                if not segments:
                    raise AppException("No transcript segments found to analyze.", code="TRANSCRIPT_EMPTY", status_code=400)

                # Fetch existing topics to determine pedagogical depth
                stmt_t = (
                    select(Topic)
                    .where(Topic.lecture_id == lecture.id)
                    .order_by(Topic.start_time.asc())
                )
                res_t = await db.execute(stmt_t)
                topics = list(res_t.scalars().all())

                # Step 2: Compute Empirical Signals (40%)
                job.progress_pct = 40
                await db.commit()

                logger.info(f"Running signal engine on {len(segments)} segments for lecture {lecture.id}...")
                metrics_list: List[SegmentSignalMetrics] = signal_engine.analyze_lecture(segments)
                metrics_by_seg_id = {m.segment_id: m for m in metrics_list}

                # Step 3: Identify Confusion Spikes and Group into Moments (60%)
                job.progress_pct = 60
                await db.commit()

                spikes = [m for m in metrics_list if m.is_confusion_spike]

                # If no strict spike, pick the top 2 highest friction segments if above threshold
                if not spikes and metrics_list:
                    sorted_by_friction = sorted(metrics_list, key=lambda m: m.acoustic_friction_score, reverse=True)
                    spikes = [m for m in sorted_by_friction[:2] if m.acoustic_friction_score >= 0.25]

                # Cluster adjacent spikes (within 8 seconds of each other)
                clusters: List[List[SegmentSignalMetrics]] = []
                for s in spikes:
                    if not clusters:
                        clusters.append([s])
                    else:
                        last_cluster = clusters[-1]
                        if s.start_time - last_cluster[-1].end_time <= 8.0:
                            last_cluster.append(s)
                        else:
                            clusters.append([s])

                # Step 4: Clear existing ConfusionEvents and Evidence for this lecture and persist new ones (80%)
                job.progress_pct = 80
                await db.commit()

                # Clean prior events for this lecture
                await db.execute(delete(ConfusionEvent).where(ConfusionEvent.lecture_id == lecture.id))

                created_events: List[ConfusionEvent] = []
                created_evidence_count = 0
                lecture_duration = lecture.duration_seconds if lecture.duration_seconds > 0 else 1.0

                for cluster in clusters:
                    first_m = cluster[0]
                    last_m = cluster[-1]
                    t_start = first_m.start_time
                    t_end = last_m.end_time

                    # Segment map
                    cluster_seg_ids = {m.segment_id for m in cluster}
                    cluster_segments = [seg for seg in segments if seg.id in cluster_seg_ids]

                    # Aggregate composite score
                    avg_friction = sum(m.acoustic_friction_score for m in cluster) / len(cluster)
                    max_z = max(m.wpm_anomaly_z for m in cluster)
                    max_pause = max(m.pause_density for m in cluster)
                    max_disfluency = max(m.disfluency_ratio for m in cluster)

                    # Determine dominant signal
                    dominant_signal = first_m.primary_signal

                    # Find topic depth at this timestamp
                    topic_depth = 0
                    for t in topics:
                        if t.start_time <= t_start <= t.end_time:
                            topic_depth = t.depth
                            break

                    coords = compute_coordinates(
                        start_time=t_start,
                        lecture_duration=lecture_duration,
                        confusion_score=avg_friction,
                        topic_depth=topic_depth,
                    )

                    combined_text = " ".join(seg.text for seg in cluster_segments)
                    evidence_preview = combined_text[:300] + ("..." if len(combined_text) > 300 else "")

                    # Human-readable misconception diagnosis
                    signal_desc = {
                        "disfluency": f"Pronounced speech disfluency and hesitation ({int(max_disfluency * 100)}% disfluency ratio)",
                        "pause_density": f"Unusual cognitive silence gaps ({int(max_pause * 100)}% pause density)",
                        "acoustic_wpm": f"Sharp speech rate deceleration or rush ({max_z:.1f}σ WPM anomaly)",
                        "semantic": "Cognitive friction detected in explanation delivery",
                    }.get(dominant_signal, "Cognitive hesitation")

                    misconception_text = f"{signal_desc} during concept presentation."

                    signals_dict = {
                        "wpm_anomaly_z": round(max_z, 2),
                        "pause_density": round(max_pause, 3),
                        "disfluency_ratio": round(max_disfluency, 3),
                        "acoustic_friction_score": round(avg_friction, 3),
                        "primary_signal": dominant_signal,
                        "cluster_segments_count": len(cluster),
                    }

                    confusion_event = ConfusionEvent(
                        lecture_id=lecture.id,
                        segment_id=cluster_segments[0].id if cluster_segments else None,
                        timestamp_start=t_start,
                        timestamp_end=t_end,
                        confusion_score=round(avg_friction, 3),
                        misconception_text=misconception_text,
                        evidence_text=evidence_preview,
                        signals=signals_dict,
                        coordinates=coords.model_dump(),
                    )
                    db.add(confusion_event)
                    await db.flush()
                    created_events.append(confusion_event)

                    # Create grounding Evidence for each segment in the cluster
                    for seg in cluster_segments:
                        seg_metric = metrics_by_seg_id.get(seg.id)
                        seg_conf = seg_metric.acoustic_friction_score if seg_metric else avg_friction
                        seg_signal = seg_metric.primary_signal if seg_metric else dominant_signal

                        evidence_item = Evidence(
                            confusion_id=confusion_event.id,
                            quote=seg.text,
                            signal_type=seg_signal,
                            confidence=round(min(1.0, max(0.1, seg_conf)), 2),
                            timestamp_start=seg.start_time,
                            timestamp_end=seg.end_time,
                            coordinates=coords.model_dump(),
                        )
                        db.add(evidence_item)
                        created_evidence_count += 1

                # Step 5: Update Topic y-coordinates with mean confusion density
                if topics and created_events:
                    for topic in topics:
                        overlapping_events = [
                            e for e in created_events
                            if not (e.timestamp_end < topic.start_time or e.timestamp_start > topic.end_time)
                        ]
                        if overlapping_events:
                            mean_conf = sum(e.confusion_score for e in overlapping_events) / len(overlapping_events)
                            topic_coords = dict(topic.coordinates) if topic.coordinates else {"x": 0.0, "y": 0.0, "z": 0.0}
                            topic_coords["y"] = round(mean_conf * 100.0, 2)
                            topic.coordinates = topic_coords

                job.status = "done"
                job.progress_pct = 100
                job.result = {
                    "lecture_id": lecture.id,
                    "confusion_events_count": len(created_events),
                    "evidence_items_count": created_evidence_count,
                    "analyzed_segments_count": len(segments),
                }

                await db.commit()
                logger.info(
                    f"Confusion analysis job {job.id} completed: "
                    f"{len(created_events)} events, {created_evidence_count} evidence records."
                )

            except Exception as e:
                logger.error(f"Confusion analysis job {job.id} failed: {e}", exc_info=True)
                await db.rollback()

                try:
                    res_j = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = str(e)
                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error for job {job_id}: {ex}")


confusion_service = ConfusionService()
