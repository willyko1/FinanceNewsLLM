from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import AuthenticationError, RateLimitError
from pydantic import BaseModel, Field

from .agent import ResearchAgent
from .config import settings
from .mcp_client import finance_mcp_client

STATIC_DIR = Path(__file__).parent / "static"
DEMO_PATH = Path(__file__).parent / "demo" / "sample_research.json"
DAY_SECONDS = 86_400

app = FastAPI(
    title="Matt API",
    description="Evidence-first financial research using an MCP tool server.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class DailyRateLimiter:
    """Small in-memory quota guard suitable for a single portfolio container."""

    def __init__(self, per_client: int, global_limit: int):
        self.per_client = per_client
        self.global_limit = global_limit
        self._clients: dict[str, deque[float]] = defaultdict(deque)
        self._global: deque[float] = deque()
        self._lock = asyncio.Lock()

    @staticmethod
    def _trim(bucket: deque[float], now: float) -> None:
        while bucket and now - bucket[0] >= DAY_SECONDS:
            bucket.popleft()

    async def acquire(self, client_id: str) -> tuple[int, int]:
        now = time.time()
        async with self._lock:
            client_bucket = self._clients[client_id]
            self._trim(client_bucket, now)
            self._trim(self._global, now)
            if len(client_bucket) >= self.per_client:
                retry_after = max(1, int(DAY_SECONDS - (now - client_bucket[0])))
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "This demo allows three live investigations per visitor each day. "
                        "The zero-cost example remains available."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            if len(self._global) >= self.global_limit:
                retry_after = max(1, int(DAY_SECONDS - (now - self._global[0])))
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Matt reached today's shared demo quota. "
                        "The zero-cost example remains available."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            client_bucket.append(now)
            self._global.append(now)
            return self.per_client - len(client_bucket), self.global_limit - len(self._global)


rate_limiter = DailyRateLimiter(
    per_client=settings.requests_per_day_per_ip,
    global_limit=settings.global_requests_per_day,
)
research_semaphore = asyncio.Semaphore(2)
response_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class ResearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)


def _leaf_exception(error: BaseException) -> BaseException:
    """Unwrap errors raised while the MCP stdio task group is shutting down."""
    if isinstance(error, BaseExceptionGroup) and error.exceptions:
        return _leaf_exception(error.exceptions[0])
    return error


def _public_error_message(error: BaseException) -> tuple[int, str]:
    cause = _leaf_exception(error)
    if isinstance(cause, AuthenticationError):
        return 401, "The configured AI provider rejected the API key."
    if isinstance(cause, RateLimitError):
        code = getattr(cause, "code", None)
        if code in {"credit_balance_exhausted", "insufficient_quota"}:
            return (
                402,
                "The configured AI provider has no credits remaining.",
            )
        return (
            429,
            "The free AI-provider quota is temporarily unavailable. Try the zero-cost example.",
        )
    return 502, f"Research failed: {cause}"


def _client_id(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    try:
        async with finance_mcp_client() as mcp:
            tools = [tool["name"] for tool in await mcp.openai_tools()]
        mcp_status = "connected"
    except Exception as exc:
        tools = []
        mcp_status = f"error: {exc}"
    return {
        "status": "ok",
        "mcp": mcp_status,
        "tools": tools,
        "provider": settings.ai_provider,
        "model": settings.ai_model,
        "ai_configured": bool(settings.ai_api_key),
        "live_requests_per_visitor_per_day": settings.requests_per_day_per_ip,
    }


@app.get("/api/demo")
async def demo() -> dict:
    """Return a static, dated research trace without consuming an AI request."""
    return json.loads(DEMO_PATH.read_text())


@app.post("/api/research")
async def research(request: ResearchRequest, http_request: Request, response: Response) -> dict:
    if not settings.ai_api_key:
        expected = "GROQ_API_KEY" if settings.ai_provider == "groq" else "OPENAI_API_KEY"
        raise HTTPException(
            status_code=503,
            detail=f"Add {expected} to .env, then restart Matt.",
        )
    cache_key = " ".join(request.question.lower().split())
    cached = response_cache.get(cache_key)
    if cached and time.time() - cached[0] < settings.response_cache_seconds:
        response.headers["X-Matt-Cache"] = "HIT"
        return cached[1]

    remaining, global_remaining = await rate_limiter.acquire(_client_id(http_request))
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-Global-RateLimit-Remaining"] = str(global_remaining)
    try:
        async with research_semaphore:
            result = await asyncio.wait_for(
                ResearchAgent().research(request.question),
                timeout=settings.research_timeout,
            )
        response_cache[cache_key] = (time.time(), result)
        response.headers["X-Matt-Cache"] = "MISS"
        return result
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Research timed out. Try a narrower question."
        ) from exc
    except Exception as exc:
        status, detail = _public_error_message(exc)
        raise HTTPException(status_code=status, detail=detail) from exc


def run() -> None:
    uvicorn.run("finresearch.web:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
