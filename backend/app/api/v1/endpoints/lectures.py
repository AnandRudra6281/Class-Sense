import os
import re
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import MediaProcessingError, ResourceNotFoundError
from app.models.lecture import Lecture
from app.schemas.common import ApiResponse
from app.schemas.lecture import (
    IngestJobResponse,
    LectureCreate,
    LectureDetailResponse,
    LectureResponse,
    YouTubeIngestRequest,
)
from app.services.coordinates import compute_coordinates
from app.services.ingestion_service import ingestion_service
from app.services.youtube_downloader import youtube_downloader

router = APIRouter()

ALLOWED_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm",
    ".wav", ".mp3", ".m4a", ".flac", ".ogg"
}


@router.get("", response_model=ApiResponse[List[LectureResponse]])
async def list_lectures(db: AsyncSession = Depends(get_db)):
    """List all ingested lectures sorted by most recent."""
    stmt = select(Lecture).order_by(Lecture.created_at.desc())
    result = await db.execute(stmt)
    lectures = result.scalars().all()
    return ApiResponse(data=[LectureResponse.model_validate(lec) for lec in lectures])


@router.get("/{lecture_id}", response_model=ApiResponse[LectureDetailResponse])
async def get_lecture_detail(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve full detail of a lecture including segments, topics, confusion points, and interventions."""
    stmt = (
        select(Lecture)
        .where(Lecture.id == lecture_id)
        .options(
            selectinload(Lecture.segments),
            selectinload(Lecture.topics),
            selectinload(Lecture.confusion_events),
            selectinload(Lecture.interventions),
        )
    )
    result = await db.execute(stmt)
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise ResourceNotFoundError("Lecture", lecture_id)

    return ApiResponse(data=LectureDetailResponse.model_validate(lecture))


@router.post("/upload", response_model=ApiResponse[IngestJobResponse])
async def upload_lecture_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Direct upload endpoint for lecture video or audio files.
    Initiates persisted background ingestion pipeline and returns job and lecture IDs.
    """
    filename = file.filename or "upload.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise MediaProcessingError(
            f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            details={"filename": filename, "extension": ext},
        )

    # Sanitize filename
    safe_stem = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", Path(filename).stem)
    stored_filename = f"{uuid.uuid4().hex[:12]}_{safe_stem}{ext}"
    target_path = settings.raw_upload_dir / stored_filename

    # Save to disk
    try:
        with open(target_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise MediaProcessingError(f"Failed to write uploaded file to disk: {str(e)}")

    lecture, job = await ingestion_service.create_upload_job(
        db=db,
        media_path=target_path,
        filename=filename,
        custom_title=title,
    )

    # Dispatch async background worker
    background_tasks.add_task(ingestion_service.run_ingestion_pipeline, job.id)

    return ApiResponse(
        data=IngestJobResponse(
            lecture_id=lecture.id,
            job_id=job.id,
            status=job.status,
            title=lecture.title,
        )
    )


@router.post("/youtube", response_model=ApiResponse[IngestJobResponse])
async def ingest_youtube_lecture(
    payload: YouTubeIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest lecture from a YouTube video URL.
    Validates URL format, initiates background stream download and extraction, and returns job and lecture IDs.
    """
    if not youtube_downloader.is_valid_url(payload.url):
        raise MediaProcessingError(
            f"Invalid YouTube URL: '{payload.url}'. Must be a standard youtube.com/watch or youtu.be link.",
            details={"url": payload.url},
        )

    lecture, job = await ingestion_service.create_youtube_job(
        db=db,
        url=payload.url,
        custom_title=payload.title,
    )

    # Dispatch async background worker
    background_tasks.add_task(ingestion_service.run_ingestion_pipeline, job.id)

    return ApiResponse(
        data=IngestJobResponse(
            lecture_id=lecture.id,
            job_id=job.id,
            status=job.status,
            title=lecture.title,
        )
    )


@router.delete("/{lecture_id}", response_model=ApiResponse[dict])
async def delete_lecture(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """Deletes a lecture record and its associated audio/media files from disk."""
    stmt = select(Lecture).where(Lecture.id == lecture_id)
    res = await db.execute(stmt)
    lecture = res.scalar_one_or_none()
    if not lecture:
        raise ResourceNotFoundError("Lecture", lecture_id)

    # Clean up physical files safely
    for path_str in [lecture.media_path, lecture.audio_path]:
        if path_str:
            p = Path(path_str)
            if p.exists() and p.is_file():
                try:
                    p.unlink()
                except OSError:
                    pass

    await db.delete(lecture)
    await db.commit()

    return ApiResponse(data={"deleted": True, "lecture_id": lecture_id})


@router.post("", response_model=ApiResponse[LectureResponse])
async def create_lecture_scaffold(
    payload: LectureCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a manual lecture metadata scaffold."""
    coords = compute_coordinates(0.0, 1.0, 0.0, 0)
    lecture = Lecture(
        title=payload.title,
        source_type=payload.source_type,
        source_url=payload.source_url,
        duration_seconds=0.0,
        status="pending",
        coordinates=coords.model_dump(),
    )
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return ApiResponse(data=LectureResponse.model_validate(lecture))
