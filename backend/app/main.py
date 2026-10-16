import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.errors import register_exception_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logger = logging.getLogger("classsense.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up ClassSense Backend...")
    # Ensure directories exist
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize database tables
    await init_db()
    logger.info("ClassSense Backend initialized successfully.")
    yield
    logger.info("Shutting down ClassSense Backend...")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="ClassSense: AI Teaching Assistant finding confusion points & prerequisite gaps in lectures.",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register error handlers with standard envelope
    register_exception_handlers(app)

    # Mount API routes under /api/v1
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
