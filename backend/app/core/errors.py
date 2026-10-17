import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("classsense.errors")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorEnvelope(BaseModel):
    success: bool = False
    data: Optional[Any] = None
    error: ErrorDetail
    meta: dict = Field(default_factory=lambda: {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": str(uuid.uuid4())
    })


class AppException(Exception):
    """Base exception for ClassSense domain and business errors."""
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class ProviderDisabledError(AppException):
    def __init__(self, provider_name: str, key_name: str):
        super().__init__(
            message=f"Provider '{provider_name}' is disabled because '{key_name}' is not configured.",
            code="PROVIDER_DISABLED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": provider_name, "required_key": key_name}
        )


class LLMValidationError(AppException):
    def __init__(self, message: str, validation_errors: Any = None, raw_output: Optional[str] = None):
        super().__init__(
            message=f"LLM output validation failed: {message}",
            code="LLM_VALIDATION_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"validation_errors": validation_errors, "raw_output": raw_output}
        )


class JobNotFoundError(AppException):
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job with ID '{job_id}' was not found.",
            code="JOB_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"job_id": job_id}
        )


class ResourceNotFoundError(AppException):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} with ID '{resource_id}' was not found.",
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class MediaProcessingError(AppException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEDIA_PROCESSING_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AudioExtractionError(AppException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="AUDIO_EXTRACTION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


def build_error_response(status_code: int, code: str, message: str, details: Optional[Any] = None) -> JSONResponse:
    envelope = ErrorEnvelope(
        success=False,
        data=None,
        error=ErrorDetail(code=code, message=message, details=details),
        meta={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": str(uuid.uuid4())
        }
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"AppException: {exc.code} - {exc.message} (status: {exc.status_code})")
        return build_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(f"HTTPException: {exc.status_code} - {exc.detail}")
        code = "HTTP_ERROR"
        if exc.status_code == 404:
            code = "NOT_FOUND"
        elif exc.status_code == 401:
            code = "UNAUTHORIZED"
        elif exc.status_code == 403:
            code = "FORBIDDEN"
        return build_error_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
            details=None
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
        return build_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Request body or query parameter validation failed.",
            details=exc.errors()
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
        return build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred.",
            details=str(exc) if getattr(settings_module(), "DEBUG", False) else None
        )


def settings_module():
    from app.core.config import settings
    return settings


def format_exception_error(exc: BaseException) -> str:
    """Formats an exception into a non-empty error message for job persistence.
    When exc has no message or str(exc) is empty, returns '<ExceptionClass>: <repr or traceback summary>'.
    Never returns an empty string.
    """
    cls_name = exc.__class__.__name__
    msg = str(exc).strip()
    if not msg:
        rep = repr(exc).strip()
        if rep:
            return f"{cls_name}: {rep}"
        return f"{cls_name}: {cls_name}()"
    if not msg.startswith(cls_name):
        return f"{cls_name}: {msg}"
    return msg
