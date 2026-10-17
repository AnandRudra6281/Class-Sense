import asyncio
import time
import pytest
from app.core.errors import AppException
from app.providers.resilience import (
    execute_with_resilience,
    get_provider_semaphore,
    reset_provider_semaphore,
)


@pytest.mark.asyncio
async def test_provider_call_timeout_fails_with_clear_message():
    """Verify that a hanging/slow provider call times out and fails with a clear message."""
    call_count = 0

    async def slow_provider():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.5)
        return "finished"

    with pytest.raises(AppException) as exc_info:
        await execute_with_resilience(
            slow_provider,
            call_name="test_llm.generate",
            timeout_seconds=0.05,
            max_attempts=2,
            base_backoff_seconds=0.01,
        )

    assert exc_info.value.code == "PROVIDER_TIMEOUT"
    assert "timed out after 0.05s across 2 attempt(s)" in exc_info.value.message
    assert call_count == 2


@pytest.mark.asyncio
async def test_provider_call_backoff_on_429_success_on_retry():
    """Verify that 429 rate-limiting triggers exponential backoff and succeeds on retry."""
    call_count = 0

    async def rate_limited_provider():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("429 Too Many Requests: Rate limit exceeded")
        return {"status": "ok", "content": "resilient answer"}

    t0 = time.perf_counter()
    res = await execute_with_resilience(
        rate_limited_provider,
        call_name="test_llm.rate_limit",
        timeout_seconds=2.0,
        max_attempts=3,
        base_backoff_seconds=0.05,
    )
    elapsed = time.perf_counter() - t0

    assert call_count == 3
    assert res["status"] == "ok"
    assert res["content"] == "resilient answer"
    # Backoff delay took place
    assert elapsed >= 0.1


@pytest.mark.asyncio
async def test_provider_call_exhausted_transient_error_fails():
    """Verify that persistent 503 errors fail with clear error after max attempts."""
    call_count = 0

    async def failing_503_provider():
        nonlocal call_count
        call_count += 1
        raise Exception("503 Service Unavailable: overloaded")

    with pytest.raises(AppException) as exc_info:
        await execute_with_resilience(
            failing_503_provider,
            call_name="test_asr.transcribe",
            timeout_seconds=2.0,
            max_attempts=3,
            base_backoff_seconds=0.02,
        )

    assert exc_info.value.code == "PROVIDER_TRANSIENT_EXHAUSTED"
    assert "failed after 3 attempts due to transient error" in exc_info.value.message
    assert call_count == 3


@pytest.mark.asyncio
async def test_global_semaphore_limits_concurrency():
    """Verify global semaphore limits concurrent provider calls."""
    reset_provider_semaphore(concurrency=2)

    active_tasks = 0
    max_active_tasks = 0

    async def worker():
        nonlocal active_tasks, max_active_tasks
        active_tasks += 1
        if active_tasks > max_active_tasks:
            max_active_tasks = active_tasks
        await asyncio.sleep(0.08)
        active_tasks -= 1
        return True

    tasks = [
        execute_with_resilience(worker, call_name=f"worker_{i}", timeout_seconds=2.0)
        for i in range(5)
    ]
    results = await asyncio.gather(*tasks)

    assert all(results)
    assert max_active_tasks <= 2, f"Expected concurrency <= 2, got {max_active_tasks}"

    # Reset semaphore back to default
    reset_provider_semaphore()


@pytest.mark.asyncio
async def test_non_transient_error_fails_immediately():
    """Verify non-transient errors (e.g. ValueError, bad inputs) fail immediately without retries."""
    call_count = 0

    async def bad_argument_provider():
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid prompt parameters")

    with pytest.raises(ValueError) as exc_info:
        await execute_with_resilience(
            bad_argument_provider,
            call_name="test_llm.bad_args",
            max_attempts=3,
        )

    assert "Invalid prompt parameters" in str(exc_info.value)
    assert call_count == 1
