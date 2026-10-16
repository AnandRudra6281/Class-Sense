from app.core.config import Settings


def test_settings_default_values():
    s = Settings(_env_file=None)
    assert s.PROJECT_NAME == "ClassSense"
    assert s.API_V1_PREFIX == "/api/v1"
    assert s.MISTRAL_LLM_MODEL == "mistral-large-latest"
    assert s.MISTRAL_VOXTRAL_MODEL == "voxtral-mini-latest"
    assert s.MISTRAL_EMBED_MODEL == "mistral-embed"
    assert s.ASR_PROVIDER == "faster_whisper"
    assert s.LLM_PROVIDER == "mistral"
    assert s.EMBEDDING_PROVIDER == "mistral"
    assert isinstance(s.CORS_ORIGINS, list)
    assert len(s.CORS_ORIGINS) > 0


def test_settings_cors_parsing():
    s = Settings(_env_file=None, CORS_ORIGINS='["http://example.com", "http://localhost:3000"]')
    assert "http://example.com" in s.CORS_ORIGINS
    assert "http://localhost:3000" in s.CORS_ORIGINS
