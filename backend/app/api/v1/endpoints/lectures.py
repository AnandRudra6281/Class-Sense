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
from app.models.confusion import ConfusionEvent
from app.models.evidence import Evidence
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.schemas.common import ApiResponse
from app.schemas.domain import (
    ConfusionEventSchema,
    EvidenceSchema,
    MisconceptionSchema,
    PrerequisiteNodeSchema,
)
from app.schemas.lecture import (
    ConfusionAnalysisJobResponse,
    IngestJobResponse,
    LectureCreate,
    LectureDetailResponse,
    LectureResponse,
    MisconceptionExtractionJobResponse,
    PrerequisiteTracingJobResponse,
    TopicSegmentationJobResponse,
    TranscribeRequest,
    TranscribeResponse,
    YouTubeIngestRequest,
)
from app.schemas.topic import TopicSchema
from app.schemas.transcript import TranscriptSegmentSchema
from app.services.confusion_service import confusion_service
from app.services.coordinates import compute_coordinates
from app.services.ingestion_service import ingestion_service
from app.services.misconception_service import misconception_service
from app.services.prerequisite_service import prerequisite_service
from app.services.topic_segmentation_service import topic_segmentation_service
from app.services.transcription_service import transcription_service
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


@router.post("/{lecture_id}/transcribe", response_model=ApiResponse[TranscribeResponse])
async def trigger_lecture_transcription(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    payload: Optional[TranscribeRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Launch asynchronous word/segment timestamped speech-to-text transcription for an ingested lecture.
    """
    req_provider = payload.provider if payload and payload.provider else "auto"
    req_lang = payload.language if payload else None

    job = await transcription_service.create_transcription_job(
        db=db,
        lecture_id=lecture_id,
        provider_name=req_provider,
        language=req_lang,
    )

    background_tasks.add_task(transcription_service.run_transcription_pipeline, job.id)

    return ApiResponse(
        data=TranscribeResponse(
            job_id=job.id,
            lecture_id=lecture_id,
            status=job.status,
        )
    )


@router.get("/{lecture_id}/transcript", response_model=ApiResponse[List[TranscriptSegmentSchema]])
async def get_lecture_transcript(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve word-aligned transcript segments for a lecture ordered chronologically.
    """
    # Check if lecture exists
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt = (
        select(TranscriptSegment)
        .where(TranscriptSegment.lecture_id == lecture_id)
        .order_by(TranscriptSegment.start_time.asc())
    )
    res = await db.execute(stmt)
    segments = res.scalars().all()
    return ApiResponse(data=[TranscriptSegmentSchema.model_validate(seg) for seg in segments])


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


@router.post("/{lecture_id}/segment-topics", response_model=ApiResponse[TopicSegmentationJobResponse])
async def trigger_topic_segmentation(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers asynchronous LLM topic outline segmentation for an ingested and transcribed lecture.
    """
    job = await topic_segmentation_service.create_segmentation_job(db=db, lecture_id=lecture_id)
    background_tasks.add_task(topic_segmentation_service.run_topic_segmentation_pipeline, job.id)
    return ApiResponse(
        data=TopicSegmentationJobResponse(
            job_id=job.id,
            lecture_id=lecture_id,
            status=job.status,
        )
    )


@router.get("/{lecture_id}/topics", response_model=ApiResponse[List[TopicSchema]])
async def get_lecture_topics(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve hierarchical pedagogical topics for a lecture.
    """
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt = select(Topic).where(Topic.lecture_id == lecture_id).order_by(Topic.start_time.asc())
    res = await db.execute(stmt)
    topics = res.scalars().all()
    return ApiResponse(data=[TopicSchema.model_validate(t) for t in topics])


@router.post("/{lecture_id}/analyze-signals", response_model=ApiResponse[ConfusionAnalysisJobResponse])
async def trigger_signal_analysis(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Run empirical acoustic and linguistic confusion signal analysis over lecture transcript segments.
    """
    job = await confusion_service.create_analysis_job(db=db, lecture_id=lecture_id)
    background_tasks.add_task(confusion_service.run_confusion_pipeline, job.id)
    return ApiResponse(
        data=ConfusionAnalysisJobResponse(
            job_id=job.id,
            lecture_id=lecture_id,
            status=job.status,
        )
    )


@router.get("/{lecture_id}/confusion-events", response_model=ApiResponse[List[ConfusionEventSchema]])
async def get_lecture_confusion_events(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all detected cognitive friction and confusion events for a lecture.
    """
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt = (
        select(ConfusionEvent)
        .where(ConfusionEvent.lecture_id == lecture_id)
        .order_by(ConfusionEvent.timestamp_start.asc())
    )
    res = await db.execute(stmt)
    events = res.scalars().all()
    return ApiResponse(data=[ConfusionEventSchema.model_validate(e) for e in events])


@router.get("/{lecture_id}/evidence", response_model=ApiResponse[List[EvidenceSchema]])
async def get_lecture_evidence(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all grounding acoustic and transcript evidence items associated with confusion events.
    """
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt = (
        select(Evidence)
        .join(ConfusionEvent, Evidence.confusion_id == ConfusionEvent.id)
        .where(ConfusionEvent.lecture_id == lecture_id)
        .order_by(Evidence.timestamp_start.asc())
    )
    res = await db.execute(stmt)
    evidence_items = res.scalars().all()
    return ApiResponse(data=[EvidenceSchema.model_validate(ev) for ev in evidence_items])


@router.post("/{lecture_id}/extract-misconceptions", response_model=ApiResponse[MisconceptionExtractionJobResponse])
async def trigger_misconception_extraction(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers structured LLM diagnostic extraction of student misconceptions and root cause prerequisite gaps.
    """
    job = await misconception_service.create_extraction_job(db=db, lecture_id=lecture_id)
    background_tasks.add_task(misconception_service.run_misconception_pipeline, job.id)
    return ApiResponse(
        data=MisconceptionExtractionJobResponse(
            job_id=job.id,
            lecture_id=lecture_id,
            status=job.status,
        )
    )


@router.get("/{lecture_id}/misconceptions", response_model=ApiResponse[List[MisconceptionSchema]])
async def get_lecture_misconceptions(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all diagnosed student misconceptions and root cause gaps for a lecture.
    """
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt = (
        select(Misconception)
        .join(ConfusionEvent, Misconception.confusion_id == ConfusionEvent.id)
        .where(ConfusionEvent.lecture_id == lecture_id)
        .order_by(ConfusionEvent.timestamp_start.asc(), Misconception.cognitive_load_score.desc())
    )
    res = await db.execute(stmt)
    misconceptions = res.scalars().all()
    return ApiResponse(data=[MisconceptionSchema.model_validate(m) for m in misconceptions])


@router.post("/{lecture_id}/trace-prerequisites", response_model=ApiResponse[PrerequisiteTracingJobResponse])
async def trigger_prerequisite_tracing(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers structured LLM and vector retrieval prerequisite tracing for a lecture's confusion events.
    """
    job = await prerequisite_service.create_tracing_job(db=db, lecture_id=lecture_id)
    background_tasks.add_task(prerequisite_service.run_prerequisite_pipeline, job.id)
    return ApiResponse(
        data=PrerequisiteTracingJobResponse(
            job_id=job.id,
            lecture_id=lecture_id,
            status=job.status,
        )
    )


@router.get("/{lecture_id}/prerequisites", response_model=ApiResponse[List[PrerequisiteNodeSchema]])
async def get_lecture_prerequisites(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all traced prerequisite knowledge graph nodes for a lecture.
    """
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt = (
        select(PrerequisiteNode)
        .join(ConfusionEvent, PrerequisiteNode.confusion_id == ConfusionEvent.id)
        .where(ConfusionEvent.lecture_id == lecture_id)
        .order_by(ConfusionEvent.timestamp_start.asc(), PrerequisiteNode.depth.asc())
    )
    res = await db.execute(stmt)
    nodes = res.scalars().all()
    return ApiResponse(data=[PrerequisiteNodeSchema.model_validate(n) for n in nodes])
