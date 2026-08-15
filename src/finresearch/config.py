from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    ai_provider: str = os.getenv("AI_PROVIDER", "openai").lower()
    ai_model: str = os.getenv("AI_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6-terra"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    sec_user_agent: str = os.getenv(
        "SEC_USER_AGENT", "SignalDesk portfolio project research@example.com"
    )
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    research_timeout: float = float(os.getenv("RESEARCH_TIMEOUT_SECONDS", "90"))
    max_tool_rounds: int = int(os.getenv("MAX_TOOL_ROUNDS", "4"))
    max_tool_calls: int = int(os.getenv("MAX_TOOL_CALLS", "12"))
    requests_per_day_per_ip: int = int(os.getenv("REQUESTS_PER_DAY_PER_IP", "3"))
    global_requests_per_day: int = int(os.getenv("GLOBAL_REQUESTS_PER_DAY", "100"))
    response_cache_seconds: int = int(os.getenv("RESPONSE_CACHE_SECONDS", "600"))

    @property
    def ai_api_key(self) -> str | None:
        if self.ai_provider == "groq":
            return self.groq_api_key
        return self.openai_api_key

    @property
    def ai_base_url(self) -> str | None:
        if self.ai_provider == "groq":
            return "https://api.groq.com/openai/v1"
        return None


settings = Settings()
