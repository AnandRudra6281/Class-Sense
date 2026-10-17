import json
import logging
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from mistralai.client import Mistral
from app.core.config import settings
from app.core.errors import LLMValidationError, ProviderDisabledError
from app.providers.base import LLMProvider
from app.providers.resilience import execute_with_resilience

logger = logging.getLogger("classsense.llm.mistral")

T = TypeVar("T", bound=BaseModel)


class MistralLLMProvider(LLMProvider):
    """Mistral LLM Provider with strict JSON Mode, Pydantic validation, and one-time retry recovery."""

    def __init__(self, client: Optional[Mistral] = None):
        self._client = client

    @property
    def name(self) -> str:
        return "mistral"

    def is_enabled(self) -> bool:
        key = (settings.MISTRAL_API_KEY or "").strip()
        return bool(key and not key.startswith("your_") and key != "your_mistral_api_key_here")

    def _get_client(self) -> Mistral:
        if self._client:
            return self._client
        if not self.is_enabled():
            raise ProviderDisabledError("Mistral LLM", "MISTRAL_API_KEY")
        return Mistral(api_key=settings.MISTRAL_API_KEY)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        client = self._get_client()
        model_name = settings.MISTRAL_LLM_MODEL

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async def _call():
            return await client.chat.complete_async(
                model=model_name,
                messages=messages,
                temperature=0.2,
            )

        response = await execute_with_resilience(_call, call_name=f"mistral_llm.generate_text({model_name})")

        return response.choices[0].message.content or ""

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        """Call Mistral in JSON Mode, validate with Pydantic, retry once on validation failure, then fail cleanly."""
        client = self._get_client()
        model_name = settings.MISTRAL_LLM_MODEL
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)

        base_system_prompt = (
            "You are an expert pedagogical AI analyzing lectures. "
            "You MUST output valid JSON matching this JSON Schema:\n"
            f"{schema_json}\n"
            "Return ONLY the JSON object. Do not include markdown formatting or commentary."
        )
        if system_prompt:
            base_system_prompt = f"{system_prompt}\n\n{base_system_prompt}"

        messages = [
            {"role": "system", "content": base_system_prompt},
            {"role": "user", "content": prompt},
        ]

        # Construct json_schema response_format
        try:
            from mistralai.extra import response_format_from_pydantic_model
            resp_format = response_format_from_pydantic_model(response_model)
        except Exception:
            resp_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema(),
                    "strict": True,
                },
            }

        # First Attempt
        raw_output = ""
        try:
            logger.info(f"Calling Mistral LLM ({model_name}) with json_schema mode for {response_model.__name__}...")

            async def _attempt1():
                return await client.chat.complete_async(
                    model=model_name,
                    messages=messages,
                    response_format=resp_format,
                    temperature=0.1,
                )

            response = await execute_with_resilience(_attempt1, call_name=f"mistral_llm.generate_structured({response_model.__name__})")
            raw_output = response.choices[0].message.content or ""
            return response_model.model_validate_json(raw_output)

        except (ValidationError, json.JSONDecodeError, Exception) as first_err:
            logger.warning(
                f"Attempt 1 for {response_model.__name__} failed: {first_err}. Attempting 1 automatic retry with error feedback..."
            )

            # Retry once with explicit error feedback
            retry_messages = [
                {"role": "system", "content": base_system_prompt},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw_output},
                {
                    "role": "user",
                    "content": (
                        f"CRITICAL: Your previous response failed schema validation with error:\n{str(first_err)}\n\n"
                        f"Please rectify the errors and return valid JSON adhering strictly to this schema:\n{schema_json}"
                    ),
                },
            ]

            try:
                async def _attempt2():
                    return await client.chat.complete_async(
                        model=model_name,
                        messages=retry_messages,
                        response_format=resp_format,
                        temperature=0.0,
                    )

                retry_response = await execute_with_resilience(
                    _attempt2,
                    call_name=f"mistral_llm.generate_structured_retry({response_model.__name__})",
                )
                retry_raw_output = retry_response.choices[0].message.content or ""
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
