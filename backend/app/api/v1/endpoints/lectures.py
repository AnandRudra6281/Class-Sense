from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.errors import ResourceNotFoundError
from app.models.lecture import Lecture
from app.schemas.common import ApiResponse
from app.schemas.lecture import LectureCreate, LectureDetailResponse, LectureResponse
from app.services.coordinates import compute_coordinates

router = APIRouter()


@router.get("", response_model=ApiResponse[List[LectureResponse]])
async def list_lectures(db: AsyncSession = Depends(get_db)):
    """List all ingested lectures."""
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
            selectinload(Lecture.confusion_points),
            selectinload(Lecture.interventions),
        )
    )
    result = await db.execute(stmt)
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise ResourceNotFoundError("Lecture", lecture_id)

    return ApiResponse(data=LectureDetailResponse.model_validate(lecture))


@router.post("", response_model=ApiResponse[LectureResponse])
async def create_lecture_scaffold(
    payload: LectureCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new lecture record."""
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
