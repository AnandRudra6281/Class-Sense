import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppException, ResourceNotFoundError
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.intervention import Intervention
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.report import Report
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.schemas.report import LLMReportPayload, ReportExportResponse
from app.services.job_service import JobService
from app.services.provider_factory import get_llm_provider

logger = logging.getLogger("classsense.services.report")

REPORT_SYSTEM_PROMPT = """You are an executive pedagogical auditor and chief academic quality consultant for universities and online learning institutions.
Your mission is to produce an authoritative, comprehensive, and data-driven Pedagogy Quality & Cognitive Audit Report for an analyzed lecture.

Given:
- Lecture metadata and overall duration
- Topic breakdown and structural outline
- Computed speech pacing metrics (WPM, pause density, hesitation spikes)
- Detected student cognitive friction clusters and struggle moments
- Diagnosed misconceptions and traced prerequisite gaps

Synthesize a structured `LLMReportPayload` containing:
1. `title`: Professional report title (e.g. "Pedagogical Quality & Cognitive Audit: Machine Learning Dynamics").
2. `executive_summary`: 2 to 3 substantive paragraphs analyzing the instructional effectiveness of the lecture, precisely identifying cognitive bottlenecks, evaluating how pacing and terminology contributed to mental model strain, and highlighting successful segments.
3. `key_recommendations`: 3 to 5 prioritized, high-impact instructional adjustments for the instructor and curriculum designers (e.g., scaffolding adjustments, real-world analogies, diagnostic checkpoints).

Always output strictly valid JSON conforming to the schema.
"""


class ReportService:
    """Service orchestrating empirical quantitative metric computation and LLM executive audit report synthesis."""

    async def create_report_job(self, db: AsyncSession, lecture_id: str) -> Job:
        """Validates lecture and creates a queued report generation Job."""
        stmt = select(Lecture).where(Lecture.id == lecture_id)
        res = await db.execute(stmt)
        lecture = res.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        job = Job(
            job_type="report_generation",
            status="queued",
            progress_pct=0,
            payload={"lecture_id": lecture.id},
            coordinates={"x": 50.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created report generation job {job.id} for lecture {lecture.id}")
        return job

    async def run_report_pipeline(self, job_id: str) -> None:
        """Background worker that computes metrics and generates the audit report."""
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

            job.status = "running"
            job.progress_pct = 20
            await db.commit()

            try:
                report = await self.generate_report_for_lecture(
                    lecture_id=lecture.id,
                    db=db,
                    job_id=job.id,
                )
                logger.info(f"Report generation pipeline completed: created report {report.id} for job {job.id}.")
            except Exception as e:
                logger.error(f"Report generation job {job.id} failed: {e}", exc_info=True)
                try:
                    res_j_err = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j_err.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = str(e)
                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error for job {job_id}: {ex}")

    async def generate_report_for_lecture(
        self,
        lecture_id: str,
        db: AsyncSession,
        job_id: Optional[str] = None,
    ) -> Report:
        """Computes empirical metrics and generates an LLM pedagogical quality audit report."""
        logger.info(f"Starting report generation for lecture {lecture_id}...")

        try:
            # 1. Fetch lecture with all associated data
            stmt_l = (
                select(Lecture)
                .where(Lecture.id == lecture_id)
                .options(
                    selectinload(Lecture.segments),
                    selectinload(Lecture.topics),
                    selectinload(Lecture.confusion_events).selectinload(ConfusionEvent.misconceptions),
                    selectinload(Lecture.interventions),
                )
            )
            res_l = await db.execute(stmt_l)
            lecture = res_l.scalar_one_or_none()
            if not lecture:
                raise AppException(f"Lecture '{lecture_id}' not found.", code="LECTURE_NOT_FOUND", status_code=404)

            # Fetch prerequisites count
            confusion_ids = [e.id for e in lecture.confusion_events]
            prereq_count = 0
            prereq_nodes: List[PrerequisiteNode] = []
            if confusion_ids:
                stmt_p = select(PrerequisiteNode).where(PrerequisiteNode.confusion_id.in_(confusion_ids))
                res_p = await db.execute(stmt_p)
                prereq_nodes = list(res_p.scalars().all())
                prereq_count = len(prereq_nodes)

            if job_id:
                await JobService.update_job_progress(job_id, 40, db)

            # 2. Compute Empirical Quantitative Metrics
            total_segments = len(lecture.segments)
            confusion_spikes = len(lecture.confusion_events)
            total_duration = float(lecture.duration_seconds)

            confusion_density = (
                min(1.0, round(confusion_spikes / max(1, total_segments), 3))
                if total_segments > 0
                else (0.5 if confusion_spikes > 0 else 0.0)
            )

            avg_confusion_score = (
                round(sum(e.confusion_score for e in lecture.confusion_events) / max(1, confusion_spikes), 2)
                if confusion_spikes > 0
                else 0.0
            )

            all_misconceptions = [m for e in lecture.confusion_events for m in e.misconceptions]
            critical_misconceptions = sum(1 for m in all_misconceptions if m.severity == "critical")

            # Speech rate and pauses
            total_words = sum(len(s.text.split()) for s in lecture.segments)
            speaking_minutes = sum((s.end_time - s.start_time) for s in lecture.segments) / 60.0
            avg_wpm = (
                round(total_words / max(0.1, speaking_minutes), 1)
                if speaking_minutes > 0.05
                else (round((total_words / max(1.0, total_duration)) * 60.0, 1) if total_duration > 0 else 135.0)
            )

            hesitation_pause_count = sum(
                1
                for e in lecture.confusion_events
                if (e.signals.get("pause_density", 0) > 0.20 or e.signals.get("wpm_anomaly_z", 0) > 1.5)
            )

            metrics: Dict[str, Any] = {
                "total_duration_seconds": round(total_duration, 1),
                "total_segments": total_segments,
                "total_topics": len(lecture.topics),
                "confusion_spikes": confusion_spikes,
                "confusion_density": confusion_density,
                "avg_confusion_score": avg_confusion_score,
                "total_misconceptions": len(all_misconceptions),
                "critical_misconceptions": critical_misconceptions,
                "traced_prerequisites": prereq_count,
                "avg_wpm": avg_wpm,
                "hesitation_pause_count": hesitation_pause_count,
                "pedagogy_quality_score": round(max(0.0, (1.0 - (confusion_density * 0.7 + (avg_confusion_score * 0.3))) * 100), 1),
            }

            if job_id:
                await JobService.update_job_progress(job_id, 65, db)

            # 3. Assemble Prompt & Call LLM in Structured JSON Mode
            misc_summary = [f"- {m.name} (Severity: {m.severity}, Load: {m.cognitive_load_score:.2f}): {m.apparent_reason}" for m in all_misconceptions]
            prereq_summary = [f"- {p.concept_name}: {p.gap_description}" for p in prereq_nodes]
            topic_summary = [f"- {t.title} ({t.start_time:.0f}s - {t.end_time:.0f}s)" for t in lecture.topics]

            prompt = (
                f"Lecture Title: {lecture.title}\n"
                f"Duration: {total_duration:.1f}s | Pacing: {avg_wpm} WPM | Segments: {total_segments}\n\n"
                f"--- Quantitative Cognitive Metrics ---\n"
                f"- Confusion Density: {confusion_density * 100:.1f}%\n"
                f"- Confusion Spikes: {confusion_spikes} (Avg Score: {avg_confusion_score:.2f})\n"
                f"- Hesitation Pauses: {hesitation_pause_count}\n"
                f"- Quality Score: {metrics['pedagogy_quality_score']}/100\n\n"
                f"--- Topic Outline ---\n"
                + ("\n".join(topic_summary) if topic_summary else "No topics segmented")
                + "\n\n--- Diagnosed Student Misconceptions ---\n"
                + ("\n".join(misc_summary) if misc_summary else "No misconceptions diagnosed")
                + "\n\n--- Traced Prerequisite Gaps ---\n"
                + ("\n".join(prereq_summary) if prereq_summary else "No prerequisites traced")
                + "\n\nGenerate the structured executive audit report."
            )

            llm = get_llm_provider()
            logger.info(f"Synthesizing audit report via LLM for lecture {lecture_id}...")
            response: LLMReportPayload = await llm.generate_structured(
                prompt=prompt,
                response_model=LLMReportPayload,
                system_prompt=REPORT_SYSTEM_PROMPT,
            )
            if not response or not response.key_recommendations:
                raise AppException(
                    f"LLM returned invalid or empty audit report for lecture {lecture_id}.",
                    code="REPORT_GENERATION_FAILED",
                    status_code=502,
                )

            if job_id:
                await JobService.update_job_progress(job_id, 85, db)

            # 4. Remove previous reports for idempotency
            await db.execute(delete(Report).where(Report.lecture_id == lecture_id))

            # 5. Persist Report with Deterministic 3D Coordinates
            coord_y = round(confusion_density * 100.0, 2)
            report_id = str(uuid.uuid4())
            report = Report(
                id=report_id,
                lecture_id=lecture_id,
                title=response.title,
                executive_summary=response.executive_summary,
                confusion_density=confusion_density,
                key_recommendations=response.key_recommendations,
                metrics=metrics,
                export_format="json",
                coordinates={"x": 50.0, "y": coord_y, "z": 0.0},
            )
            db.add(report)
            await db.commit()
            await db.refresh(report)

            if job_id:
                await JobService.update_job_status(job_id, "done", 100, db)

            logger.info(f"Successfully generated and persisted pedagogy report {report.id} for lecture {lecture_id}.")
            return report

        except AppException:
            if job_id:
                await JobService.update_job_status(job_id, "failed", 0, db)
            await db.rollback()
            raise
        except Exception as exc:
            logger.error(f"Report generation failed: {exc}", exc_info=True)
            if job_id:
                await JobService.update_job_status(job_id, "failed", 0, db)
            await db.rollback()
            raise AppException(
                message=f"Report generation failed: {str(exc)}",
                code="REPORT_GENERATION_FAILED",
                status_code=500,
                details={"error": str(exc)},
            )

    def export_report_markdown(self, report: Report, lecture: Lecture) -> str:
        """Formats report as a clean, publication-ready Markdown audit document."""
        metrics = report.metrics or {}
        recs = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(report.key_recommendations))

        md = f"""# {report.title}
*ClassSense Automated Pedagogical & Cognitive Audit*

**Lecture:** {lecture.title}
**Duration:** {metrics.get('total_duration_seconds', 0)} seconds ({round(metrics.get('total_duration_seconds', 0) / 60, 1)} minutes)
**Audit Date:** {report.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if hasattr(report, 'created_at') and report.created_at else 'N/A'}
**Overall Pedagogical Quality Score:** {metrics.get('pedagogy_quality_score', 'N/A')}/100

---

## 1. Executive Summary
{report.executive_summary}

---

## 2. Quantitative Cognitive Metrics
| Metric | Value | Reference Benchmark |
| :--- | :--- | :--- |
| **Confusion Density** | {round(report.confusion_density * 100, 1)}% | < 15.0% Optimal |
| **Cognitive Friction Spikes** | {metrics.get('confusion_spikes', 0)} | Lower is better |
| **Average Confusion Score** | {metrics.get('avg_confusion_score', 0.0)} / 1.00 | < 0.40 Nominal |
| **Diagnosed Misconceptions** | {metrics.get('total_misconceptions', 0)} ({metrics.get('critical_misconceptions', 0)} Critical) | Target zero critical |
| **Traced Prerequisite Gaps** | {metrics.get('traced_prerequisites', 0)} | Foundational anchors |
| **Average Pacing (WPM)** | {metrics.get('avg_wpm', 130)} WPM | 120 - 150 WPM Recommended |
| **Hesitation Pause Spikes** | {metrics.get('hesitation_pause_count', 0)} | Significant acoustic stalls |
| **Pedagogical 3D Coordinate** | ({report.coordinates.get('x', 50)}, {report.coordinates.get('y', 0)}, {report.coordinates.get('z', 0)}) | System space anchor |

---

## 3. Prioritized Instructional Recommendations
{recs}

---
*Report generated automatically by ClassSense Engine (Structured JSON Mode & Empirical Signal Analysis).*
"""
        return md


report_service = ReportService()
