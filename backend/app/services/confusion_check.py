from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.confusion import ConfusionEvent
from app.models.job import Job


async def has_confusion_analysis_run(db: AsyncSession, lecture_id: str) -> bool:
    """Checks whether confusion analysis has completed or is in progress for a lecture."""
    # 1. Any confusion events exist?
    ev_stmt = select(ConfusionEvent.id).where(ConfusionEvent.lecture_id == lecture_id).limit(1)
    ev_res = await db.execute(ev_stmt)
    if ev_res.scalar_one_or_none():
        return True

    # 2. Has a confusion analysis job or lecture pipeline finished or currently active?
    job_stmt = select(Job).where(Job.job_type.in_(["confusion_analysis", "lecture_pipeline"]))
    job_res = await db.execute(job_stmt)
    for j in job_res.scalars().all():
        if j.payload and j.payload.get("lecture_id") == lecture_id:
            if j.job_type == "confusion_analysis" and j.status in ["done", "running"]:
                return True
            if j.job_type == "lecture_pipeline":
                stages = j.payload.get("stages", {})
                conf_stage = stages.get("confusion", {})
                if conf_stage.get("status") in ["done", "running"] or j.status in ["running", "done"]:
                    return True
    return False
