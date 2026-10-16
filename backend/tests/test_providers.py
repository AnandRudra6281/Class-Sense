from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import BaseModel, Field
from app.core.errors import LLMValidationError, ProviderDisabledError
from app.providers.asr.openai_whisper import OpenAIWhisperASR
from app.providers.asr.sarvam_ai import SarvamAIASR
from app.providers.embeddings.mistral_embed import MistralEmbeddingProvider
from app.providers.llm.mistral_llm import MistralLLMProvider


class SampleOutputSchema(BaseModel):
    title: str
    score: float = Field(ge=0.0, le=1.0)
    keywords: list[str]


@pytest.mark.asyncio
async def test_adapters_disabled_without_keys():
    openai_provider = OpenAIWhisperASR()
    assert openai_provider.is_enabled() is False
    with pytest.raises(ProviderDisabledError) as exc_info:
        await openai_provider.transcribe(Path("dummy.wav"))
    assert "OPENAI_API_KEY" in str(exc_info.value)

    sarvam_provider = SarvamAIASR()
    assert sarvam_provider.is_enabled() is False
    with pytest.raises(ProviderDisabledError) as exc_info:
        await sarvam_provider.transcribe(Path("dummy.wav"))
    assert "SARVAM_API_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mistral_llm_structured_success():
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"title": "Neural Networks", "score": 0.85, "keywords": ["weights", "biases"]}'
    mock_response = MagicMock(choices=[mock_choice])
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)

    llm = MistralLLMProvider(client=mock_client)
    res = await llm.generate_structured(
        prompt="Explain Neural Networks",
        response_model=SampleOutputSchema,
    )
    assert isinstance(res, SampleOutputSchema)
    assert res.title == "Neural Networks"
    assert res.score == 0.85
    assert "weights" in res.keywords
    assert mock_client.chat.complete_async.call_count == 1


@pytest.mark.asyncio
async def test_mistral_llm_retry_once_on_validation_failure():
    mock_client = MagicMock()
    
    # Attempt 1: Invalid schema (missing required fields 'title' and 'keywords')
    mock_choice_fail = MagicMock()
    mock_choice_fail.message.content = '{"score": 2.5}'  # score out of range, title missing
    response_fail = MagicMock(choices=[mock_choice_fail])

    # Attempt 2 (Retry): Valid schema
    mock_choice_success = MagicMock()
    mock_choice_success.message.content = '{"title": "Recovered Concept", "score": 0.9, "keywords": ["fixed"]}'
    response_success = MagicMock(choices=[mock_choice_success])

    mock_client.chat.complete_async = AsyncMock(side_effect=[response_fail, response_success])

    llm = MistralLLMProvider(client=mock_client)
    res = await llm.generate_structured(
        prompt="Explain concept",
        response_model=SampleOutputSchema,
    )

    assert mock_client.chat.complete_async.call_count == 2
    assert res.title == "Recovered Concept"
    assert res.score == 0.9


@pytest.mark.asyncio
async def test_mistral_llm_fails_job_after_retry_failure():
    mock_client = MagicMock()

    # Both attempts return invalid JSON
    mock_choice_fail = MagicMock()
    mock_choice_fail.message.content = '{"invalid_schema": true}'
    response_fail = MagicMock(choices=[mock_choice_fail])

    mock_client.chat.complete_async = AsyncMock(side_effect=[response_fail, response_fail])

    llm = MistralLLMProvider(client=mock_client)
    with pytest.raises(LLMValidationError) as exc_info:
        await llm.generate_structured(
            prompt="Explain concept",
            response_model=SampleOutputSchema,
        )

    assert mock_client.chat.complete_async.call_count == 2
    assert "Validation failed after retry" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_mistral_embedding_provider():
    mock_client = MagicMock()
    mock_item1 = MagicMock(embedding=[0.1, 0.2, 0.3])
    mock_item2 = MagicMock(embedding=[0.4, 0.5, 0.6])
    mock_client.embeddings.create_async = AsyncMock(
        return_value=MagicMock(data=[mock_item1, mock_item2])
    )

    embed_provider = MistralEmbeddingProvider(client=mock_client)
    embeddings = await embed_provider.embed_texts(["hello", "world"])
    assert len(embeddings) == 2
    assert embeddings[0] == [0.1, 0.2, 0.3]
    assert embeddings[1] == [0.4, 0.5, 0.6]


@pytest.mark.asyncio
async def test_gemini_llm_structured_success():
    from app.providers.llm.gemini_llm import GeminiLLMProvider
    mock_client = MagicMock()
    mock_response = MagicMock(text='{"title": "Backpropagation", "score": 0.95, "keywords": ["chain rule"]}')
    mock_client.models.generate_content.return_value = mock_response

    llm = GeminiLLMProvider(client=mock_client)
    res = await llm.generate_structured(
        prompt="Explain Backpropagation",
        response_model=SampleOutputSchema,
    )
    assert res.title == "Backpropagation"
    assert res.score == 0.95
    assert "chain rule" in res.keywords


@pytest.mark.asyncio
async def test_gemini_llm_retry_once_on_validation_failure():
    from app.providers.llm.gemini_llm import GeminiLLMProvider
    mock_client = MagicMock()
    # Attempt 1 returns invalid json/schema
    mock_fail = MagicMock(text='{"bad_key": 123}')
    # Attempt 2 returns valid schema
    mock_success = MagicMock(text='{"title": "Fixed Schema", "score": 0.8, "keywords": ["recovered"]}')
    mock_client.models.generate_content.side_effect = [mock_fail, mock_success]

    llm = GeminiLLMProvider(client=mock_client)
    res = await llm.generate_structured(
        prompt="Explain",
        response_model=SampleOutputSchema,
    )
    assert mock_client.models.generate_content.call_count == 2
    assert res.title == "Fixed Schema"
    assert res.score == 0.8


@pytest.mark.asyncio
async def test_gemini_embedding_provider():
    from app.providers.embeddings.gemini_embed import GeminiEmbeddingProvider
    mock_client = MagicMock()
    mock_resp1 = MagicMock(embedding=MagicMock(values=[0.11, 0.22, 0.33]))
    mock_resp2 = MagicMock(embedding=MagicMock(values=[0.44, 0.55, 0.66]))
    mock_client.models.embed_content.side_effect = [mock_resp1, mock_resp2]

    embed_provider = GeminiEmbeddingProvider(client=mock_client)
    res = await embed_provider.embed_texts(["first", "second"])
    assert len(res) == 2
    assert res[0] == [0.11, 0.22, 0.33]
    assert res[1] == [0.44, 0.55, 0.66]
