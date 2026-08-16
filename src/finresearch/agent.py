from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from openai import AsyncOpenAI

from .config import settings
from .mcp_client import MCPFinanceClient, finance_mcp_client

SYSTEM_PROMPT = """
You are SignalDesk, an evidence-first financial research analyst. Research the user's question
using the available tools before answering. For company-specific questions, normally inspect
market movement, recent news, recent SEC filings, and company facts. Use multiple searches if
the first query is insufficient.

Evidence rules:
- Cite every current, numerical, or company-specific factual claim with [S#].
- Source IDs are assigned in tool-result order. Only cite IDs present in the tool results.
- Prefer SEC filings for issuer-reported facts. Distinguish reported facts from your inference.
- State when price data may be delayed and when evidence is missing or conflicting.
- Never invent a price, date, filing, headline, source, or citation.
- Do not issue personalized buy/sell instructions or predict returns. Discuss scenarios, risks,
  catalysts, and what evidence would change the analysis.

Answer format:
1. A direct 2-3 sentence answer.
2. "What the evidence says" with compact bullets.
3. "Risks & what to watch" with compact bullets.
4. End with: "Research only — not personalized investment advice."
""".strip()

FINAL_SYNTHESIS_PROMPT = """
Tool collection is complete. Produce the final answer now using only the evidence already in the
conversation. Do not request or call any more tools. If the available evidence is incomplete, say
so explicitly instead of inventing facts. Preserve the required answer format and citations.
""".strip()


@dataclass
class Source:
    id: str
    title: str
    url: str
    publisher: str
    published_at: str | None = None


@dataclass
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    status: str = "complete"
    source_ids: list[str] = field(default_factory=list)


def _extract_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(payload.get("source"), dict):
        found.append(payload["source"])
    for key in ("articles", "filings"):
        for item in payload.get(key, []) or []:
            if isinstance(item, dict) and item.get("url"):
                found.append(item)
    return found


def _normalize_citations(text: str) -> str:
    """Normalize common model citation variants for the UI's [S#] links."""
    return text.replace("【S", "[S").replace("】", "]")


class ResearchAgent:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        key = api_key or settings.ai_api_key
        if not key:
            expected = "GROQ_API_KEY" if settings.ai_provider == "groq" else "OPENAI_API_KEY"
            raise ValueError(f"{expected} is not configured")
        self.client = AsyncOpenAI(api_key=key, base_url=base_url or settings.ai_base_url)
        self.model = model or settings.ai_model
        self.provider = settings.ai_provider

    async def research(self, question: str) -> dict[str, Any]:
        async with finance_mcp_client() as mcp:
            return await self._run(question, mcp)

    def _result(
        self,
        answer: str,
        sources: list[Source],
        traces: list[ToolTrace],
    ) -> dict[str, Any]:
        return {
            "answer": _normalize_citations(answer),
            "sources": [source.__dict__ for source in sources],
            "trace": [trace.__dict__ for trace in traces],
            "model": self.model,
            "generated_at": datetime.now(UTC).isoformat(),
            "provider": self.provider,
        }

    async def _run(self, question: str, mcp: MCPFinanceClient) -> dict[str, Any]:
        tools = await mcp.openai_tools()
        input_items: list[Any] = [{"role": "user", "content": question}]
        traces: list[ToolTrace] = []
        sources: list[Source] = []
        source_by_url: dict[str, str] = {}

        for _ in range(settings.max_tool_rounds):
            response = await self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=input_items,
                tools=tools,
                reasoning={"effort": "low"},
            )
            calls = [item for item in response.output if item.type == "function_call"]
            input_items.extend(response.output)
            if not calls:
                return self._result(response.output_text, sources, traces)

            for call in calls:
                if len(traces) >= settings.max_tool_calls:
                    raise RuntimeError(
                        f"Research exceeded the maximum of {settings.max_tool_calls} tool calls"
                    )
                arguments = json.loads(call.arguments)
                payload = await mcp.call(call.name, arguments)
                trace = ToolTrace(name=call.name, arguments=arguments)
                for raw_source in _extract_sources(payload):
                    url = raw_source.get("url", "")
                    if not url:
                        continue
                    source_id = source_by_url.get(url)
                    if not source_id:
                        source_id = f"S{len(sources) + 1}"
                        source_by_url[url] = source_id
                        sources.append(
                            Source(
                                id=source_id,
                                title=(
                                    raw_source.get("title")
                                    or raw_source.get("description")
                                    or url
                                ),
                                url=url,
                                publisher=raw_source.get("publisher", "Unknown"),
                                published_at=(
                                    raw_source.get("published_at")
                                    or raw_source.get("filed_at")
                                ),
                            )
                        )
                    trace.source_ids.append(source_id)
                traces.append(trace)
                payload["citation_ids"] = trace.source_ids
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(payload, default=str),
                    }
                )

        # Some models keep asking for more tools even after enough evidence has been collected.
        # A final tools-disabled pass converts that evidence into an answer instead of surfacing a
        # budget-limit error to the user.
        final_response = await self.client.responses.create(
            model=self.model,
            instructions=f"{SYSTEM_PROMPT}\n\n{FINAL_SYNTHESIS_PROMPT}",
            input=input_items,
            reasoning={"effort": "low"},
        )
        return self._result(final_response.output_text, sources, traces)
