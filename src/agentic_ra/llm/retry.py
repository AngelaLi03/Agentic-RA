"""Shared tenacity policy for Anthropic calls (T-1.2): max 4 attempts,
exponential backoff with jitter, retry only on transient failures."""

from __future__ import annotations

from anthropic import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

RETRYABLE = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)


def llm_retrying() -> AsyncRetrying:
    """Fresh retry controller per call (AsyncRetrying is stateful)."""
    return AsyncRetrying(
        retry=retry_if_exception_type(RETRYABLE),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=0.5, max=12.0),
        reraise=True,
    )
