import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger("classsense.api.lectures")

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppException, MediaProcessingError, ResourceNotFoundError
from app.models.confusion import ConfusionEvent
from app.models.evidence import Evidence
from app.models.intervention import Intervention
from app.models.catchup import StudentCatchUp
from app.models.quiz import QuizQuestion
from app.models.lecture import Lecture
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.report import Report
from app.models.topic import Topic
from app.models.transcript import TranscriptSegment
from app.schemas.common import ApiResponse
from app.schemas.domain import (
    ConfusionEventSchema,
    EvidenceSchema,
    InterventionSchema,
    MisconceptionSchema,
    PrerequisiteNodeSchema,
)
from app.schemas.lecture import (
    ConfusionAnalysisJobResponse,
    IngestJobResponse,
    InterventionJobResponse,
    LectureCreate,
    LectureDetailResponse,
    LectureResponse,
    MisconceptionExtractionJobResponse,
    PrerequisiteTracingJobResponse,
    ReportJobResponse,
    TopicSegmentationJobResponse,
    TranscribeRequest,
    TranscribeResponse,
    YouTubeIngestRequest,
)
from app.schemas.report import (
    ReportExportResponse,
    ReportResponse,
)
from app.schemas.student import (
    StudentCatchUpJobResponse,
    StudentCatchUpResponse,
    QuizQuestionResponse,
    TutorChatRequest,
    TutorChatResponse,
)
from app.schemas.job import JobResponse
from app.schemas.topic import TopicSchema
from app.schemas.transcript import TranscriptSegmentSchema
from app.services.confusion_service import confusion_service
from app.services.coordinates import compute_coordinates
from app.services.ingestion_service import ingestion_service
from app.services.intervention_service import intervention_service
from app.services.misconception_service import misconception_service
from app.services.pipeline_service import pipeline_service
from app.services.prerequisite_service import prerequisite_service
from app.services.report_service import report_service
from app.services.socratic_tutor_service import socratic_tutor_service
from app.services.student_catchup_service import student_catchup_service
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
    auto_analyze: bool = Form(False),
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

    # Save to disk with streaming size limit enforcement
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    total_bytes = 0
    try:
        with open(target_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    buffer.close()
                    if target_path.exists():
                        target_path.unlink(missing_ok=True)
                    raise AppException(
                        message=f"Uploaded file exceeds maximum allowed size of {settings.MAX_UPLOAD_MB}MB.",
                        code="PAYLOAD_TOO_LARGE",
                        status_code=413,
                        details={"max_upload_mb": settings.MAX_UPLOAD_MB, "bytes_received": total_bytes},
                    )
                buffer.write(chunk)
    except AppException:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise MediaProcessingError(f"Failed to write uploaded file to disk: {str(e)}")

    # Verify the file with ffprobe before creating the job and reject non-media
    from app.services.audio_extractor import AudioExtractor
    extractor = AudioExtractor()
    try:
        metadata = await extractor.probe_metadata(target_path)
        if not metadata.get("has_audio") and metadata.get("duration_seconds", 0) <= 0:
            if target_path.exists():
                target_path.unlink(missing_ok=True)
            raise AppException(
                message=f"Uploaded file '{filename}' does not contain valid audio or video streams.",
                code="NON_MEDIA_FILE",
                status_code=400,
                details={"filename": filename},
            )
    except MediaProcessingError as mpe:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise AppException(
            message=f"Uploaded file '{filename}' failed media validation: {str(mpe)}",
            code="INVALID_MEDIA_FILE",
            status_code=400,
            details={"filename": filename, "error": str(mpe)},
        )

    lecture, job, analyze_job = await ingestion_service.create_upload_job(
        db=db,
        media_path=target_path,
        filename=filename,
        custom_title=title,
        auto_analyze=auto_analyze,
    )

    # Dispatch async background worker
    background_tasks.add_task(ingestion_service.run_ingestion_pipeline, job.id)

    return ApiResponse(
        data=IngestJobResponse(
            lecture_id=lecture.id,
            job_id=job.id,
            status=job.status,
            title=lecture.title,
            analyze_job_id=analyze_job.id if analyze_job else None,
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

    lecture, job, analyze_job = await ingestion_service.create_youtube_job(
        db=db,
        url=payload.url,
        custom_title=payload.title,
        auto_analyze=payload.auto_analyze,
    )

    # Dispatch async background worker
    background_tasks.add_task(ingestion_service.run_ingestion_pipeline, job.id)

    return ApiResponse(
        data=IngestJobResponse(
            lecture_id=lecture.id,
            job_id=job.id,
            status=job.status,
            title=lecture.title,
            analyze_job_id=analyze_job.id if analyze_job else None,
        )
    )


@router.post("/{lecture_id}/analyze", response_model=ApiResponse[JobResponse])
async def trigger_full_analysis(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    resume: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers the unified one-click 8-stage pedagogy analysis pipeline:
    transcribe -> segment topics -> confusion analysis -> misconceptions ->
    prerequisites -> interventions -> student catch-up -> report.
    If resume=True, skips already-completed stages and resumes from the first incomplete/failed stage.
    """
    job = await pipeline_service.create_pipeline_job(db=db, lecture_id=lecture_id, resume=resume)
    background_tasks.add_task(pipeline_service.run_full_pipeline, job.id)
    return ApiResponse(data=JobResponse.model_validate(job))


@router.delete("/{lecture_id}", response_model=ApiResponse[dict])
async def delete_lecture(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """Deletes a lecture record, associated ChromaDB vectors, and media/derived audio files from disk."""
    stmt = select(Lecture).where(Lecture.id == lecture_id)
    res = await db.execute(stmt)
    lecture = res.scalar_one_or_none()
    if not lecture:
        raise ResourceNotFoundError("Lecture", lecture_id)

    # 1. Clean up associated vectors from ChromaDB
    try:
        from app.services.vector_store import VectorStoreService
        vs = VectorStoreService()
        deleted_vectors = vs.delete_by_lecture(lecture_id)
        logger.info(f"Deleted {deleted_vectors} ChromaDB vector(s) for lecture '{lecture_id}'.")
    except Exception as c_err:
        logger.warning(f"Failed to remove ChromaDB vectors for lecture '{lecture_id}': {c_err}")

    # 2. Clean up media and derived audio files from disk
    files_to_remove = set()
    for path_str in [lecture.media_path, lecture.audio_path]:
        if path_str:
            files_to_remove.add(Path(path_str))

    # Also search audio and raw directories for derived audio files matching lecture_id or file stems
    stems = {f.stem for f in files_to_remove if f}
    stems.add(lecture_id)
    for directory in [settings.audio_upload_dir, settings.raw_upload_dir]:
        if directory.exists():
            for p in directory.glob("*"):
                if p.is_file() and any(stem in p.name for stem in stems if stem):
                    files_to_remove.add(p)

    for p in files_to_remove:
        if p.exists() and p.is_file():
            try:
                p.unlink()
            except OSError as oe:
                logger.warning(f"Failed to delete derived media/audio file {p}: {oe}")

    # 3. Delete lecture record from SQLite
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
    Triggers structured LLM extraction of potential misconceptions (inferred from lecture speech) and root cause prerequisite gaps.
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
    Retrieve all potential misconceptions (inferred from lecture speech) and root cause gaps for a lecture.
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


@router.post("/{lecture_id}/generate-interventions", response_model=ApiResponse[InterventionJobResponse])
async def trigger_intervention_generation(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers structured LLM generation of teacher interventions (actionable recap, diagnostic questions, pacing).
    """
    job = await intervention_service.create_intervention_job(db=db, lecture_id=lecture_id)
    background_tasks.add_task(intervention_service.run_intervention_pipeline, job.id)
    return ApiResponse(
        data=InterventionJobResponse(
            job_id=job.id,
            lecture_id=lecture_id,
            status=job.status,
        )
    )


@router.get("/{lecture_id}/interventions", response_model=ApiResponse[List[InterventionSchema]])
async def get_lecture_interventions(
    lecture_id: str,
    target_type: Optional[str] = "teacher",
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all synthesized interventions (teacher or student) for a lecture.
    """
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    query = select(Intervention).where(Intervention.lecture_id == lecture_id)
    if target_type:
        query = query.where(Intervention.target_type == target_type)
    query = query.order_by(Intervention.created_at.asc())

    res = await db.execute(query)
    interventions = res.scalars().all()
    return ApiResponse(data=[InterventionSchema.model_validate(inv) for inv in interventions])


@router.post("/{lecture_id}/generate-catchup", response_model=ApiResponse[StudentCatchUpJobResponse])
async def trigger_student_catchup_generation(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers structured LLM generation of student catch-up modules and progressive-hint practice quizzes.
    """
    job = await student_catchup_service.create_catchup_job(db=db, lecture_id=lecture_id)
    background_tasks.add_task(student_catchup_service.run_catchup_pipeline, job.id)
    return ApiResponse(
        data=StudentCatchUpJobResponse(
            job_id=job.id,
            lecture_id=lecture_id,
            status=job.status,
        )
    )


@router.get("/{lecture_id}/catchup", response_model=ApiResponse[List[StudentCatchUpResponse]])
async def get_lecture_student_catchup(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all synthesized student catch-up modules and nested diagnostic quiz questions for a lecture.
    """
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt = (
        select(StudentCatchUp)
        .where(StudentCatchUp.lecture_id == lecture_id)
        .options(selectinload(StudentCatchUp.quiz_questions))
        .order_by(StudentCatchUp.created_at.asc())
    )
    res = await db.execute(stmt)
    catchups = res.scalars().all()

    response_items = []
    for cu in catchups:
        quiz_items = [
            QuizQuestionResponse(
                id=q.id,
                catchup_id=q.catchup_id,
                question=q.question,
                options=q.options,
                correct_option_index=q.correct_option_index,
                hints=q.hints,
                explanation=q.explanation,
                coordinates=q.coordinates,
            )
            for q in cu.quiz_questions
        ]
        response_items.append(
            StudentCatchUpResponse(
                id=cu.id,
                lecture_id=cu.lecture_id,
                topic_id=cu.topic_id,
                title=cu.title,
                summary=cu.summary,
                concrete_analogy=cu.concrete_analogy,
                key_takeaways=cu.key_takeaways,
                quiz_questions=quiz_items,
                coordinates=cu.coordinates,
            )
        )

    return ApiResponse(data=response_items)


@router.post("/{lecture_id}/tutor/chat", response_model=ApiResponse[TutorChatResponse])
async def socratic_tutor_chat(
    lecture_id: str,
    payload: TutorChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Interactive Socratic dialogue endpoint for students with transcript grounding and suggested follow-ups.
    """
    response = await socratic_tutor_service.chat(
        lecture_id=lecture_id,
        message=payload.message,
        db=db,
        history=payload.history,
        catchup_id=payload.catchup_id,
    )
    return ApiResponse(data=response)


@router.post("/{lecture_id}/generate-report", response_model=ApiResponse[ReportJobResponse])
async def trigger_report_generation(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers structured LLM generation of a comprehensive Pedagogy Quality & Cognitive Audit Report.
    """
    job = await report_service.create_report_job(db=db, lecture_id=lecture_id)
    background_tasks.add_task(report_service.run_report_pipeline, job.id)
    return ApiResponse(
        data=ReportJobResponse(
            job_id=job.id,
            lecture_id=lecture_id,
            status=job.status,
        )
    )


@router.get("/{lecture_id}/reports", response_model=ApiResponse[List[ReportResponse]])
async def get_lecture_reports(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all synthesized pedagogy audit reports for a lecture.
    """
    stmt_lec = select(Lecture).where(Lecture.id == lecture_id)
    res_lec = await db.execute(stmt_lec)
    if not res_lec.scalar_one_or_none():
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt = select(Report).where(Report.lecture_id == lecture_id).order_by(Report.created_at.desc())
    res = await db.execute(stmt)
    reports = res.scalars().all()
    return ApiResponse(data=[ReportResponse.model_validate(r) for r in reports])


@router.get("/{lecture_id}/reports/{report_id}/export", response_model=ApiResponse[ReportExportResponse])
async def export_lecture_report(
    lecture_id: str,
    report_id: str,
    format: Optional[str] = "markdown",
    db: AsyncSession = Depends(get_db),
):
    """
    Export pedagogy audit report formatted as Markdown or structured JSON.
    """
    stmt_l = select(Lecture).where(Lecture.id == lecture_id)
    res_l = await db.execute(stmt_l)
    lecture = res_l.scalar_one_or_none()
    if not lecture:
        raise ResourceNotFoundError("Lecture", lecture_id)

    stmt_r = select(Report).where(Report.id == report_id, Report.lecture_id == lecture_id)
    res_r = await db.execute(stmt_r)
    report = res_r.scalar_one_or_none()
    if not report:
        raise ResourceNotFoundError("Report", report_id)

    safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in lecture.title)

    if format == "json":
        report_data = ReportResponse.model_validate(report).model_dump(mode="json")
        content_str = json.dumps(report_data, indent=2)
        filename = f"ClassSense_Audit_{safe_title}.json"
    else:
        content_str = report_service.export_report_markdown(report, lecture)
        filename = f"ClassSense_Audit_{safe_title}.md"

    return ApiResponse(
        data=ReportExportResponse(
            report_id=report.id,
            lecture_id=lecture.id,
            format=format or "markdown",
            content=content_str,
            filename=filename,
        )
    )
