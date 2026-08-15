import pytest
from fastapi import HTTPException
from httpx import Request, Response
from openai import AuthenticationError, RateLimitError

from finresearch.web import DailyRateLimiter, _leaf_exception, _public_error_message


def _response(status: int) -> Response:
    return Response(status, request=Request("POST", "https://api.openai.com/v1/responses"))


def test_unwraps_nested_exception_group():
    cause = ValueError("specific failure")
    wrapped = ExceptionGroup("task group", [ExceptionGroup("session", [cause])])
    assert _leaf_exception(wrapped) is cause


def test_explains_exhausted_api_credits():
    error = RateLimitError(
        "No credits",
        response=_response(429),
        body={"code": "credit_balance_exhausted"},
    )
    assert _public_error_message(error) == (
        402,
        "The configured AI provider has no credits remaining.",
    )


def test_explains_invalid_api_key():
    error = AuthenticationError("Invalid key", response=_response(401), body=None)
    status, message = _public_error_message(error)
    assert status == 401
    assert "rejected" in message


@pytest.mark.asyncio
async def test_daily_rate_limiter_enforces_per_client_quota():
    limiter = DailyRateLimiter(per_client=1, global_limit=10)
    assert await limiter.acquire("visitor-a") == (0, 9)
    with pytest.raises(HTTPException) as error:
        await limiter.acquire("visitor-a")
    assert error.value.status_code == 429
    assert "three live investigations" in error.value.detail


@pytest.mark.asyncio
async def test_daily_rate_limiter_enforces_global_quota():
    limiter = DailyRateLimiter(per_client=5, global_limit=1)
    await limiter.acquire("visitor-a")
    with pytest.raises(HTTPException) as error:
        await limiter.acquire("visitor-b")
    assert error.value.status_code == 429
    assert "shared demo quota" in error.value.detail
