import json
import logging
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from google import genai
from google.genai import types
from app.core.config import settings
from app.core.errors import LLMValidationError, ProviderDisabledError
from app.providers.base import LLMProvider

logger = logging.getLogger("classsense.llm.gemini")

T = TypeVar("T", bound=BaseModel)


class GeminiLLMProvider(LLMProvider):
    """Google Gemini LLM Provider with structured JSON Mode, Pydantic validation, and one-time retry recovery."""

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client

    @property
    def name(self) -> str:
        return "gemini"

    def is_enabled(self) -> bool:
        key = settings.GEMINI_API_KEY or ""
        return bool(key.strip() and key != "your_gemini_api_key_here")

    def _get_client(self) -> genai.Client:
        if self._client:
            return self._client
        if not self.is_enabled():
            raise ProviderDisabledError("Gemini LLM", "GEMINI_API_KEY")
        return genai.Client(api_key=settings.GEMINI_API_KEY)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        client = self._get_client()
        model_name = settings.GEMINI_LLM_MODEL

        config = types.GenerateContentConfig(
            temperature=0.2,
            system_instruction=system_prompt if system_prompt else None,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        return response.text or ""

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        """Call Gemini in JSON Mode, validate with Pydantic, retry once on validation failure, then fail cleanly."""
        client = self._get_client()
        model_name = settings.GEMINI_LLM_MODEL
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)

        base_system_prompt = (
            "You are an expert pedagogical AI analyzing lectures. "
            "You MUST output valid JSON matching this JSON Schema:\n"
            f"{schema_json}\n"
            "Return ONLY the JSON object. Do not include markdown fences or commentary."
        )
        if system_prompt:
            base_system_prompt = f"{system_prompt}\n\n{base_system_prompt}"

        config = types.GenerateContentConfig(
            temperature=0.1,
            system_instruction=base_system_prompt,
            response_mime_type="application/json",
        )

        raw_output = ""
        try:
            logger.info(f"Calling Gemini LLM ({model_name}) with JSON mode for {response_model.__name__}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            raw_output = response.text or ""
            return response_model.model_validate_json(raw_output)

        except (ValidationError, json.JSONDecodeError, Exception) as first_err:
            logger.warning(
                f"Attempt 1 for {response_model.__name__} via Gemini failed: {first_err}. Attempting 1 automatic retry with error feedback..."
            )

            # Retry once with explicit error context
            retry_prompt = (
                f"Original Task:\n{prompt}\n\n"
                f"Your previous response:\n{raw_output}\n\n"
                f"CRITICAL: Your response failed schema validation with error:\n{str(first_err)}\n\n"
                f"Please rectify all errors and return valid JSON adhering strictly to this schema:\n{schema_json}"
            )

            try:
                retry_response = client.models.generate_content(
                    model=model_name,
                    contents=retry_prompt,
                    config=config,
                )
                retry_raw_output = retry_response.text or ""
                return response_model.model_validate_json(retry_raw_output)

            except ValidationError as final_val_err:
                logger.error(f"Attempt 2 failed validation for {response_model.__name__}: {final_val_err}")
                raise LLMValidationError(
                    message=f"Validation failed after retry for {response_model.__name__}",
                    validation_errors=final_val_err.errors(),
                    raw_output=retry_raw_output,
                )
            except Exception as final_err:
                logger.error(f"Attempt 2 failed with unexpected error for {response_model.__name__}: {final_err}")
                raise LLMValidationError(
                    message=f"Execution failed after retry for {response_model.__name__}: {str(final_err)}",
                    validation_errors=str(final_err),
                    raw_output=retry_raw_output if "retry_raw_output" in locals() else raw_output,
                )
