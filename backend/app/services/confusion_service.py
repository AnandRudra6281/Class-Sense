import logging
from typing import Awaitable, Callable, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppException, ResourceNotFoundError, format_exception_error
from app.db.session import async_session_factory
from app.models.confusion import ConfusionEvent
from app.models.evidence import Evidence
from app.models.job import Job
from app.models.lecture import Lecture
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.schemas.confusion import LLMWindowConfusionAnalysis
from app.services.coordinates import compute_coordinates
from app.services.provider_factory import get_llm_provider
from app.services.signal_engine import WindowSignalMetrics, signal_engine

logger = logging.getLogger("classsense.confusion_service")


class ConfusionService:
    """
    Orchestrates sliding-window confusion signal analysis, structured LLM cognitive validation,
    exact substring quote verification with retry-once, and persistent Evidence generation.
    """

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

    @staticmethod
    def validate_quote_substring(quote: str, window_text: str, max_words: int = 30) -> bool:
        """Verifies whether quote (ignoring surrounding quotes/whitespace) is BOTH an exact substring of window_text and at most max_words (max 30 words)."""
        if not quote or not window_text:
            return False
        clean_q = quote.strip().strip('"\'')
        if not clean_q:
            return False
        if clean_q not in window_text:
            return False
        word_count = len(clean_q.split())
        if word_count > max_words:
            return False
        return True

    async def _evaluate_window_llm(
        self,
        window: WindowSignalMetrics,
    ) -> Optional[LLMWindowConfusionAnalysis]:
        """
        Executes an LLM pass in JSON mode with exact substring and max-length (<= 30 words) validation and one retry.
        If validation fails after retry, logs reason and returns None (drops event).
        """
        llm = get_llm_provider()

        system_prompt = (
            "You are an expert pedagogical analyst detecting moments of cognitive hesitation, student confusion, "
            "or instructor friction during lectures. Analyze the provided window transcript.\n"
            "CRITICAL REQUIREMENT: 'evidence_quote' MUST BE THE SHORTEST VERBATIM EXCERPT supporting the score "
            "(maximum 30 words, 1-2 sentences) and MUST BE AN EXACT SUBSTRING of the transcript below. "
            "Do NOT paraphrase, alter words, add punctuation, or exceed 30 words."
        )

        prompt = (
            f"Lecture Excerpt (Window [{window.start_time:.1f}s - {window.end_time:.1f}s]):\n"
            f"\"\"\"{window.text}\"\"\"\n\n"
            f"Acoustic Signals in this window:\n"
            f"- Speech rate anomaly z: {window.wpm_anomaly_z:.2f} (WPM: {window.wpm:.1f})\n"
            f"- Pause density: {window.pause_density:.2f}\n"
            f"- Disfluency ratio: {window.disfluency_ratio:.2f}\n"
            f"- Repetition ratio: {window.repetition_ratio:.2f}\n"
            f"- Question density: {window.question_density:.2f}\n"
            f"- Student response gap: {window.student_response_gap:.2f}\n"
            f"- Primary signal: {window.primary_signal}\n\n"
            "Evaluate whether this window exhibits cognitive friction or misunderstanding. Return a JSON object with:\n"
            "- confusion_score: float in [0.0, 1.0]\n"
            "- ai_confidence: float in [0.0, 1.0]\n"
            "- evidence_quote: shortest verbatim excerpt (max 30 words, 1-2 sentences) directly supporting the score, exact substring of the text above\n"
            "- rationale: pedagogical explanation of the hesitation or difficulty"
        )

        try:
            analysis = await llm.generate_structured(
                prompt=prompt,
                response_model=LLMWindowConfusionAnalysis,
                system_prompt=system_prompt,
            )
        except Exception as e:
            logger.warning(f"Initial LLM window evaluation failed for window {window.window_id}: {e}. Retrying once...")
            try:
                analysis = await llm.generate_structured(
                    prompt=prompt,
                    response_model=LLMWindowConfusionAnalysis,
                    system_prompt=system_prompt,
                )
            except Exception as re_err:
                logger.error(f"LLM window evaluation failed on retry for window {window.window_id}: {re_err}")
                return None

        # Validate exact substring AND max length <= 30 words
        if self.validate_quote_substring(analysis.evidence_quote, window.text, max_words=30):
            return analysis

        # Retry once on quote mismatch or length breach
        words_in_quote = len(analysis.evidence_quote.strip().strip('"\'').split())
        fail_reason = (
            f"exceeded max length of 30 words ({words_in_quote} words)"
            if words_in_quote > 30
            else "is NOT an exact substring of window transcript"
        )
        logger.warning(
            f"Window {window.window_id}: LLM quote '{analysis.evidence_quote}' {fail_reason}. "
            f"Retrying LLM once for shortest verbatim excerpt (max 30 words)..."
        )

        retry_prompt = (
            f"Your previous evidence_quote was rejected because it {fail_reason}.\n"
            f"Transcript:\n\"\"\"{window.text}\"\"\"\n\n"
            "You MUST select the SHORTEST verbatim excerpt (maximum 30 words, 1-2 sentences) "
            "that appears verbatim as an EXACT substring in the transcript above. "
            "Do NOT alter even a single character and do NOT exceed 30 words."
        )

        try:
            retry_analysis = await llm.generate_structured(
                prompt=retry_prompt,
                response_model=LLMWindowConfusionAnalysis,
                system_prompt=system_prompt,
            )
            if self.validate_quote_substring(retry_analysis.evidence_quote, window.text, max_words=30):
                return retry_analysis
            else:
                retry_words = len(retry_analysis.evidence_quote.strip().strip('"\'').split())
                retry_reason = (
                    f"exceeded 30 words ({retry_words} words)"
                    if retry_words > 30
                    else "is NOT an exact substring of the transcript"
                )
                logger.warning(
                    f"Window {window.window_id}: Retry evidence_quote '{retry_analysis.evidence_quote}' "
                    f"{retry_reason}. Dropping confusion event for this window with logged reason."
                )
                return None
        except Exception as re_err:
            logger.warning(
                f"Window {window.window_id}: LLM retry failed ({re_err}). Dropping confusion event for this window."
            )
            return None

    async def analyze_confusion_for_lecture(
        self,
        lecture_id: str,
        db: AsyncSession,
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
    ) -> List[ConfusionEvent]:
        """
        Runs 30-60s sliding window acoustic and linguistic signal analysis,
        flags high-friction windows, runs structured LLM cognitive validation,
        validates exact verbatim substring evidence, and persists ConfusionEvent and Evidence records.
        """
        stmt_l = select(Lecture).where(Lecture.id == lecture_id)
        res_l = await db.execute(stmt_l)
        lecture = res_l.scalar_one_or_none()
        if not lecture:
            raise ResourceNotFoundError("Lecture", lecture_id)

        stmt_s = (
            select(TranscriptSegment)
            .where(TranscriptSegment.lecture_id == lecture.id)
            .order_by(TranscriptSegment.start_time.asc())
        )
        res_s = await db.execute(stmt_s)
        segments = list(res_s.scalars().all())

        if not segments:
            raise AppException("No transcript segments found to analyze.", code="TRANSCRIPT_EMPTY", status_code=400)

        if progress_callback:
            await progress_callback(10)

        stmt_t = (
            select(Topic)
            .where(Topic.lecture_id == lecture.id)
            .order_by(Topic.start_time.asc())
        )
        res_t = await db.execute(stmt_t)
        topics = list(res_t.scalars().all())

        # 1. Sliding Window Signal Extraction (30-60s windows)
        w_size = getattr(settings, "CONFUSION_WINDOW_SIZE_SECONDS", 45.0)
        w_step = getattr(settings, "CONFUSION_WINDOW_STEP_SECONDS", 15.0)

        logger.info(f"Running sliding window analysis ({w_size}s windows, {w_step}s step) on lecture {lecture.id}...")
        windows = signal_engine.analyze_lecture_windows(
            segments,
            window_size=w_size,
            step=w_step,
        )

        # 2. Identify Flagged Windows (Zero flagged windows is valid for calm speech)
        flagged_windows = [w for w in windows if w.is_flagged]
        logger.info(f"Identified {len(flagged_windows)} flagged window(s) for LLM cognitive friction analysis.")

        # 3. Clean up prior confusion events for idempotency
        await db.execute(delete(ConfusionEvent).where(ConfusionEvent.lecture_id == lecture.id))

        created_events: List[ConfusionEvent] = []
        lecture_duration = lecture.duration_seconds if lecture.duration_seconds > 0 else 1.0

        w_signal = getattr(settings, "CONFUSION_SIGNAL_WEIGHT", 0.40)
        w_llm = getattr(settings, "CONFUSION_LLM_WEIGHT", 0.60)
        min_score = getattr(settings, "CONFUSION_MIN_SCORE", 0.35)
        total_flagged = max(1, len(flagged_windows))

        for idx, win in enumerate(flagged_windows):
            # 4. LLM Pass with exact substring validation and retry
            llm_eval = await self._evaluate_window_llm(win)
            
            # Real per-item progress update
            pct = int(10 + 80 * ((idx + 1) / total_flagged))
            if progress_callback:
                try:
                    await progress_callback(pct)
                except Exception:
                    pass

            if not llm_eval:
                logger.info(f"Window {win.window_id} ({win.start_time}s - {win.end_time}s) dropped due to quote validation failure.")
                continue

            # 5. Combine Signal and LLM scores with configurable weights
            fused_score = (w_signal * win.signal_score) + (w_llm * llm_eval.confusion_score)
            fused_score = round(min(1.0, max(0.0, fused_score)), 3)

            # Event gating: only persist events whose fused score >= CONFUSION_MIN_SCORE
            if fused_score < min_score:
                logger.info(
                    f"Window {win.window_id} fused score {fused_score:.3f} < CONFUSION_MIN_SCORE ({min_score}). "
                    f"Skipping event persistence."
                )
                continue

            # Determine topic depth
            topic_depth = 0
            for t in topics:
                if t.start_time <= win.start_time <= t.end_time:
                    topic_depth = t.depth
                    break

            coords = compute_coordinates(
                start_time=win.start_time,
                lecture_duration=lecture_duration,
                confusion_score=fused_score,
                topic_depth=topic_depth,
            )

            # Map primary signal to readable explanation
            signal_desc = {
                "disfluency": f"Pronounced speech disfluency and hesitation ({int(win.disfluency_ratio * 100)}% filler ratio)",
                "repetition": f"Lexical backtrack repetition ({int(win.repetition_ratio * 100)}% repetition ratio)",
                "pause_density": f"Unusual cognitive silence gaps ({int(win.pause_density * 100)}% pause density)",
                "speech_rate": f"Sharp speech rate deceleration or rush ({win.wpm_anomaly_z:.1f}σ WPM anomaly)",
                "question_density": f"High density of concept check inquiries ({win.question_count} questions in window)",
                "student_response_gap": f"Prolonged response hesitation ({win.max_response_gap_seconds:.1f}s wait-time)",
            }.get(win.primary_signal, "Cognitive hesitation detected")

            misconception_text = f"{signal_desc}: {llm_eval.rationale}"
            verbatim_quote = llm_eval.evidence_quote.strip().strip('"\'')

            signals_dict = {
                "wpm": win.wpm,
                "wpm_anomaly_z": win.wpm_anomaly_z,
                "pause_density": win.pause_density,
                "disfluency_ratio": win.disfluency_ratio,
                "repetition_ratio": win.repetition_ratio,
                "question_density": win.question_density,
                "student_response_gap": win.student_response_gap,
                "type_token_ratio": win.type_token_ratio,
                "acoustic_friction_score": win.signal_score,
                "signal_score": win.signal_score,
                "llm_confusion_score": llm_eval.confusion_score,
                "ai_confidence": llm_eval.ai_confidence,
                "composite_score": fused_score,
                "primary_signal": win.primary_signal,
                "weights": {"signal": w_signal, "llm": w_llm},
                "baseline_status": win.baseline_status,
                "method_metadata": {
                    "baseline_status": win.baseline_status,
                    "min_score_threshold": min_score,
                },
            }

            confusion_event = ConfusionEvent(
                lecture_id=lecture.id,
                segment_id=win.segment_ids[0] if win.segment_ids else None,
                timestamp_start=win.start_time,
                timestamp_end=win.end_time,
                confusion_score=fused_score,
                misconception_text=misconception_text,
                evidence_text=verbatim_quote,
                signals=signals_dict,
                coordinates=coords.model_dump(),
            )
            db.add(confusion_event)
            await db.flush()
            created_events.append(confusion_event)

            # Persist Evidence record
            evidence_item = Evidence(
                confusion_id=confusion_event.id,
                quote=verbatim_quote,
                signal_type=win.primary_signal,
                confidence=llm_eval.ai_confidence,
                timestamp_start=win.start_time,
                timestamp_end=win.end_time,
                coordinates=coords.model_dump(),
            )
            db.add(evidence_item)

        # Update topic coordinates with mean confusion
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

        await db.commit()
        logger.info(f"Created {len(created_events)} confusion event(s) and evidence records for lecture {lecture.id}.")
        return created_events

    async def run_confusion_pipeline(self, job_id: str) -> None:
        """Background worker that executes sliding-window signal analysis and persists ConfusionEvents."""
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
                job.status = "running"
                job.progress_pct = 25
                await db.commit()

                created_events = await self.analyze_confusion_for_lecture(
                    lecture_id=lecture.id,
                    db=db,
                    job_id=job.id,
                )

                job.status = "done"
                job.progress_pct = 100
                job.result = {
                    "lecture_id": lecture.id,
                    "confusion_events_count": len(created_events),
                }
                await db.commit()
                logger.info(f"Confusion analysis job {job.id} completed: {len(created_events)} events.")

            except Exception as e:
                logger.error(f"Confusion analysis job {job.id} failed: {e}", exc_info=True)
                await db.rollback()

                try:
                    res_j_err = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j_err.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = format_exception_error(e)
                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error for job {job_id}: {ex}")


confusion_service = ConfusionService()
