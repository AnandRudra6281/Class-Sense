import asyncio
import logging
import random
from typing import Awaitable, Callable, Optional, TypeVar
from app.core.config import settings
from app.core.errors import AppException

logger = logging.getLogger("classsense.resilience")

T = TypeVar("T")

# Lazy global semaphore for limiting concurrent provider calls
_GLOBAL_PROVIDER_SEMAPHORE: Optional[asyncio.Semaphore] = None


def get_provider_semaphore() -> asyncio.Semaphore:
    """Return the global concurrency semaphore for provider API calls."""
    global _GLOBAL_PROVIDER_SEMAPHORE
    if _GLOBAL_PROVIDER_SEMAPHORE is None:
        _GLOBAL_PROVIDER_SEMAPHORE = asyncio.Semaphore(settings.PROVIDER_MAX_CONCURRENCY)
    return _GLOBAL_PROVIDER_SEMAPHORE


def reset_provider_semaphore(concurrency: Optional[int] = None) -> asyncio.Semaphore:
    """Reset or reconfigure the global semaphore (primarily for testing)."""
    global _GLOBAL_PROVIDER_SEMAPHORE
    _GLOBAL_PROVIDER_SEMAPHORE = asyncio.Semaphore(
        concurrency if concurrency is not None else settings.PROVIDER_MAX_CONCURRENCY
    )
    return _GLOBAL_PROVIDER_SEMAPHORE


def is_transient_error(err: Exception) -> bool:
    """Check whether an error is transient (e.g., 429 rate limit, 503 unavailable, network disconnect)."""
    if isinstance(err, asyncio.TimeoutError):
        return True
    status = getattr(err, "status_code", None) or getattr(err, "code", None)
    if status in (429, 502, 503, 504):
        return True

    err_str = str(err).lower()
    transient_markers = [
        "429",
        "503",
        "502",
        "504",
        "rate limit",
        "rate_limit",
        "quota",
        "resource_exhausted",
        "resourceexhausted",
        "temporarily unavailable",
        "service unavailable",
        "server disconnected",
        "connection reset",
        "overloaded",
    ]
    return any(marker in err_str for marker in transient_markers)


async def execute_with_resilience(
    coro_factory: Callable[[], Awaitable[T]],
    call_name: str = "provider_call",
    timeout_seconds: Optional[float] = None,
    max_attempts: Optional[int] = None,
    base_backoff_seconds: float = 0.25,
) -> T:
    """
    Executes a provider operation with:
    - Global concurrency limit via asyncio.Semaphore
    - Configurable per-call timeout (fails the call if exceeded)
    - Exponential backoff with jitter on 429, 503, and timeouts (up to max_attempts)
    """
    timeout = timeout_seconds if timeout_seconds is not None else settings.PROVIDER_CALL_TIMEOUT_SECONDS
    attempts = max_attempts if max_attempts is not None else settings.PROVIDER_MAX_RETRIES
    semaphore = get_provider_semaphore()

    for attempt in range(1, attempts + 1):
        try:
            async with semaphore:
                return await asyncio.wait_for(coro_factory(), timeout=timeout)
        except asyncio.TimeoutError as te:
            logger.warning(
                f"[{call_name}] Timed out after {timeout}s (attempt {attempt}/{attempts})."
            )
            if attempt == attempts:
                raise AppException(
                    message=f"Provider call '{call_name}' timed out after {timeout}s across {attempts} attempt(s).",
                    code="PROVIDER_TIMEOUT",
                    status_code=504,
                ) from te
            backoff = min(base_backoff_seconds * (2 ** (attempt - 1)) + random.uniform(0.01, 0.1), 5.0)
            await asyncio.sleep(backoff)
        except Exception as exc:
            if isinstance(exc, AppException) and exc.code == "PROVIDER_TIMEOUT":
                raise
            if is_transient_error(exc):
                logger.warning(
                    f"[{call_name}] Transient error ({exc}) on attempt {attempt}/{attempts}."
                )
                if attempt == attempts:
                    raise AppException(
                        message=f"Provider call '{call_name}' failed after {attempts} attempts due to transient error: {str(exc)}",
                        code="PROVIDER_TRANSIENT_EXHAUSTED",
                        status_code=503,
                    ) from exc
                backoff = min(base_backoff_seconds * (2 ** (attempt - 1)) + random.uniform(0.01, 0.1), 5.0)
                await asyncio.sleep(backoff)
            else:
                # Non-transient errors (schema errors, validation, auth) fail without retry loops
                raise
