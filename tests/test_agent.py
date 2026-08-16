from dataclasses import replace
from types import SimpleNamespace

import pytest

from finresearch import agent as agent_module
from finresearch.agent import ResearchAgent, _extract_sources, _normalize_citations


def test_extract_sources_from_tool_payload():
    payload = {
        "source": {"title": "Quote", "url": "https://example.com/quote"},
        "articles": [{"title": "News", "url": "https://example.com/news"}],
        "filings": [{"title": "10-Q", "url": "https://example.com/filing"}],
    }
    assert [source["title"] for source in _extract_sources(payload)] == ["Quote", "News", "10-Q"]


def test_normalizes_provider_citation_brackets():
    assert _normalize_citations("Price is current【S1】.") == "Price is current[S1]."


class FakeResponses:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= 2:
            tool_call = SimpleNamespace(
                type="function_call",
                name="get_market_snapshot",
                arguments='{"ticker": "AAPL"}',
                call_id=f"call-{len(self.calls)}",
            )
            return SimpleNamespace(output=[tool_call], output_text="")
        return SimpleNamespace(output=[], output_text="Price is supported【S1】.")


class FakeMCPClient:
    async def openai_tools(self):
        return [{"type": "function", "name": "get_market_snapshot", "parameters": {}}]

    async def call(self, name, arguments):
        assert name == "get_market_snapshot"
        assert arguments == {"ticker": "AAPL"}
        return {
            "source": {
                "title": "AAPL market data",
                "url": "https://example.com/aapl",
                "publisher": "Example",
            }
        }


@pytest.mark.asyncio
async def test_tool_round_limit_forces_final_synthesis(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "settings",
        replace(agent_module.settings, max_tool_rounds=2, max_tool_calls=4),
    )
    research_agent = ResearchAgent(api_key="test-key", model="test-model")
    fake_responses = FakeResponses()
    research_agent.client = SimpleNamespace(responses=fake_responses)

    result = await research_agent._run("What is happening with Apple?", FakeMCPClient())

    assert result["answer"] == "Price is supported[S1]."
    assert result["sources"][0]["id"] == "S1"
    assert len(result["trace"]) == 2
    assert len(fake_responses.calls) == 3
    assert "tools" in fake_responses.calls[0]
    assert "tools" not in fake_responses.calls[-1]
    assert "Do not request or call any more tools" in fake_responses.calls[-1]["instructions"]
