from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ClassSense global application settings."""

    # Project metadata
    PROJECT_NAME: str = "ClassSense"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database Configuration (SQLite default, PostgreSQL via env)
    DATABASE_URL: str = "sqlite+aiosqlite:///./classsense.db"

    # Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = Field(default_factory=lambda: Path("./uploads"))
    CHROMA_PERSIST_DIR: Path = Field(default_factory=lambda: Path("./chroma_db"))

    @property
    def raw_upload_dir(self) -> Path:
        p = self.UPLOAD_DIR / "raw"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def audio_upload_dir(self) -> Path:
        p = self.UPLOAD_DIR / "audio"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Mistral AI
    MISTRAL_API_KEY: str = ""
    MISTRAL_LLM_MODEL: str = "mistral-large-latest"
    MISTRAL_VOXTRAL_MODEL: str = "voxtral-mini-latest"
    MISTRAL_EMBED_MODEL: str = "mistral-embed"

    # Google Gemini (Supported Alternative)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_LLM_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"

    # Provider Selection ("mistral" default, "gemini" optional adapter, "auto")
    LLM_PROVIDER: str = "mistral"
    EMBEDDING_PROVIDER: str = "mistral"

    # ASR Provider Configuration ("faster_whisper" default, "mistral_voxtral", "gemini_audio" optional, "auto")
    ASR_PROVIDER: str = "faster_whisper"
    FASTER_WHISPER_MODEL: str = "base"
    AUDIO_CHUNK_DURATION_SECONDS: float = 300.0
    AUDIO_CHUNK_OVERLAP_SECONDS: float = 5.0

    # Confusion Engine Configuration (30-60s sliding windows, signal + LLM weights)
    CONFUSION_WINDOW_SIZE_SECONDS: float = 45.0
    CONFUSION_WINDOW_STEP_SECONDS: float = 15.0
    CONFUSION_SIGNAL_WEIGHT: float = 0.40
    CONFUSION_LLM_WEIGHT: float = 0.60
    CONFUSION_MIN_SCORE: float = 0.35

    # Report & Pedagogical Pacing Bands (words per minute)
    WPM_BAND_SLOW_MAX: float = 110.0
    WPM_BAND_FAST_MIN: float = 180.0

    # Provider Resilience & Concurrency Configuration
    PROVIDER_CALL_TIMEOUT_SECONDS: float = 60.0
    PROVIDER_MAX_CONCURRENCY: int = 3
    PROVIDER_MAX_RETRIES: int = 3

    # Upload Limits
    MAX_UPLOAD_MB: int = 500

    # Optional Providers (Disabled unless keys provided)
    OPENAI_API_KEY: Optional[str] = None
    SARVAM_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=[
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent.parent.parent / ".env"),
            ".env",
        ],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                pass
        return v if isinstance(v, list) else ["*"]

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def resolve_sqlite_url(cls, v: str) -> str:
        if v.startswith("sqlite") and ":///." in v:
            prefix, rel_path = v.split(":///.", 1)
            base_dir = Path(__file__).resolve().parent.parent.parent
            clean_rel = rel_path.lstrip("/\\")
            abs_path = (base_dir / clean_rel).resolve().as_posix()
            return f"{prefix}:///{abs_path}"
        return v

    @field_validator("UPLOAD_DIR", "CHROMA_PERSIST_DIR", mode="after")
    @classmethod
    def resolve_relative_paths(cls, v: Path) -> Path:
        if not v.is_absolute():
            base_dir = Path(__file__).resolve().parent.parent.parent
            return (base_dir / v).resolve()
        return v


settings = Settings()
