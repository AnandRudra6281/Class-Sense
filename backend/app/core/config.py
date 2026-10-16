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
    GEMINI_LLM_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBED_MODEL: str = "text-embedding-004"

    # Provider Selection ("mistral" default, "gemini" optional adapter, "auto")
    LLM_PROVIDER: str = "mistral"
    EMBEDDING_PROVIDER: str = "mistral"

    # ASR Provider Configuration ("faster_whisper" default, "mistral_voxtral", "gemini_audio" optional, "auto")
    ASR_PROVIDER: str = "faster_whisper"
    FASTER_WHISPER_MODEL: str = "base"

    # Optional Providers (Disabled unless keys provided)
    OPENAI_API_KEY: Optional[str] = None
    SARVAM_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
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


settings = Settings()
