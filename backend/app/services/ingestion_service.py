import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ResourceNotFoundError
from app.db.session import async_session_factory
from app.models.job import Job
from app.models.lecture import Lecture
from app.services.audio_extractor import audio_extractor
from app.services.youtube_downloader import youtube_downloader

logger = logging.getLogger("classsense.ingestion")


class IngestionService:
    """Manages creation, execution, and progress tracking of lecture ingestion jobs."""

    async def create_upload_job(
        self,
        db: AsyncSession,
        media_path: Path,
        filename: str,
        custom_title: Optional[str] = None,
    ) -> Tuple[Lecture, Job]:
        """Creates initial Lecture and Job records for an uploaded file."""
        title = custom_title.strip() if custom_title and custom_title.strip() else Path(filename).stem.replace("_", " ").title()

        lecture = Lecture(
            title=title,
            source_type="upload",
            media_path=str(media_path),
            status="queued",
            duration_seconds=0.0,
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lecture)
        await db.flush()

        job = Job(
            job_type="lecture_ingestion",
            status="queued",
            progress_pct=0,
            payload={
                "lecture_id": lecture.id,
                "source_type": "upload",
                "file_path": str(media_path),
                "original_filename": filename,
            },
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(lecture)
        await db.refresh(job)

        logger.info(f"Created upload ingestion job {job.id} for lecture {lecture.id}")
        return lecture, job

    async def create_youtube_job(
        self,
        db: AsyncSession,
        url: str,
        custom_title: Optional[str] = None,
    ) -> Tuple[Lecture, Job]:
        """Creates initial Lecture and Job records for a YouTube URL."""
        video_id = youtube_downloader.extract_video_id(url) or "video"
        title = custom_title.strip() if custom_title and custom_title.strip() else f"YouTube Lecture ({video_id})"

        lecture = Lecture(
            title=title,
            source_type="youtube",
            source_url=url.strip(),
            status="queued",
            duration_seconds=0.0,
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(lecture)
        await db.flush()

        job = Job(
            job_type="lecture_ingestion",
            status="queued",
            progress_pct=0,
            payload={
                "lecture_id": lecture.id,
                "source_type": "youtube",
                "url": url.strip(),
            },
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        db.add(job)
        await db.commit()
        await db.refresh(lecture)
        await db.refresh(job)

        logger.info(f"Created YouTube ingestion job {job.id} for lecture {lecture.id}")
        return lecture, job

    async def run_ingestion_pipeline(self, job_id: str) -> None:
        """
        Background worker executing media ingestion, metadata inspection,
        and ffmpeg 16kHz mono audio extraction.
        """
        async with async_session_factory() as db:
            # 1. Fetch Job
            res = await db.execute(select(Job).where(Job.id == job_id))
            job = res.scalar_one_or_none()
            if not job:
                logger.error(f"Ingestion job {job_id} not found in database.")
                return

            lecture_id = job.payload.get("lecture_id") if job.payload else None
            res_lec = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
            lecture = res_lec.scalar_one_or_none()
            if not lecture:
                job.status = "failed"
                job.error_message = f"Associated lecture {lecture_id} not found."
                await db.commit()
                return

            try:
                # Step 1: Mark Running (15%)
                job.status = "running"
                job.progress_pct = 15
                lecture.status = "processing"
                await db.commit()

                source_type = job.payload.get("source_type")
                media_path: Optional[Path] = None
                known_duration: float = 0.0

                if source_type == "youtube":
                    # Step 2: Download YouTube stream (15% -> 45%)
                    url = job.payload.get("url")
                    logger.info(f"Downloading YouTube media from {url}...")
                    yt_res = await youtube_downloader.download_media(url)
                    media_path = Path(yt_res["file_path"])
                    known_duration = yt_res.get("duration_seconds", 0.0)

                    lecture.media_path = str(media_path)
                    # If lecture title was default, replace with real video title
                    if lecture.title.startswith("YouTube Lecture (") and yt_res.get("title"):
                        lecture.title = yt_res["title"]

                    job.progress_pct = 45
                    await db.commit()
                else:
                    # Upload source: media file already on disk
                    file_path_str = job.payload.get("file_path")
                    media_path = Path(file_path_str)
                    if not media_path.exists():
                        raise FileNotFoundError(f"Uploaded file does not exist on disk: {media_path}")
                    job.progress_pct = 40
                    await db.commit()

                # Step 3: Probe Metadata & Duration (40% -> 60%)
                logger.info(f"Probing media metadata for {media_path}...")
                metadata = await audio_extractor.probe_metadata(media_path)
                duration = metadata.get("duration_seconds") or known_duration
                job.progress_pct = 60
                await db.commit()

                # Step 4: Extract 16kHz Mono WAV via ffmpeg (60% -> 85%)
                logger.info(f"Extracting 16kHz mono WAV from {media_path}...")
                audio_path = await audio_extractor.extract_16k_mono_wav(media_path)
                job.progress_pct = 85
                await db.commit()

                # Step 5: Finalize Lecture & Job (85% -> 100%)
                lecture.duration_seconds = max(0.1, float(duration))
                lecture.audio_path = str(audio_path)
                lecture.status = "ready"
                lecture.coordinates = {"x": 0.0, "y": 0.0, "z": 0.0}

                job.status = "done"
                job.progress_pct = 100
                job.result = {
                    "lecture_id": lecture.id,
                    "audio_path": str(audio_path),
                    "media_path": str(media_path),
                    "duration_seconds": lecture.duration_seconds,
                    "sample_rate": 16000,
                    "channels": 1,
                }
                await db.commit()
                logger.info(f"Ingestion job {job.id} completed successfully for lecture {lecture.id}")

            except Exception as e:
                logger.error(f"Ingestion job {job.id} failed: {e}", exc_info=True)
                await db.rollback()

                # Re-fetch or update within clean transaction
                try:
                    res_j = await db.execute(select(Job).where(Job.id == job_id))
                    j_err = res_j.scalar_one_or_none()
                    if j_err:
                        j_err.status = "failed"
                        j_err.error_message = str(e)

                    res_l = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
                    l_err = res_l.scalar_one_or_none()
                    if l_err:
                        l_err.status = "failed"

                    await db.commit()
                except Exception as ex:
                    logger.critical(f"Failed to persist error state for job {job_id}: {ex}")


ingestion_service = IngestionService()
