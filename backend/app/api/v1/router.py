from fastapi import APIRouter
from app.api.v1.endpoints import health, jobs, lectures

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(lectures.router, prefix="/lectures", tags=["Lectures"])
