from __future__ import annotations

import re
from typing import Any

KNOWN_TOOLS = {
    "get_company_facts",
    "get_market_snapshot",
    "get_recent_sec_filings",
    "search_finance_news",
}
DISCLAIMER = "not personalized investment advice"


def validate_cases(cases: Any) -> None:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Eval cases must be a non-empty JSON list")

    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"Eval case {index} must be an object")
        missing = {
            "id",
            "question",
            "required_tools",
            "minimum_sources",
            "minimum_citations",
        } - case.keys()
        if missing:
            raise ValueError(f"Eval case {index} is missing: {', '.join(sorted(missing))}")

        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"Eval case {index} has an invalid id")
        if case_id in seen_ids:
            raise ValueError(f"Duplicate eval case id: {case_id}")
        seen_ids.add(case_id)

        if not isinstance(case["question"], str) or len(case["question"].strip()) < 5:
            raise ValueError(f"Eval case {case_id} has an invalid question")
        if not isinstance(case["required_tools"], list) or not all(
            isinstance(tool, str) for tool in case["required_tools"]
        ):
            raise ValueError(f"Eval case {case_id} has invalid required_tools")
        unknown_tools = set(case["required_tools"]) - KNOWN_TOOLS
        if unknown_tools:
            raise ValueError(
                f"Eval case {case_id} references unknown tools: {', '.join(sorted(unknown_tools))}"
            )
        for key in ("minimum_sources", "minimum_citations"):
            if not isinstance(case[key], int) or case[key] < 0:
                raise ValueError(f"Eval case {case_id} has an invalid {key}")


def evaluate_result(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("answer", "")
    sources = result.get("sources", [])
    traces = result.get("trace", [])
    called_tools = {trace.get("name") for trace in traces}
    source_ids = {source.get("id") for source in sources if source.get("id")}
    citation_ids = set(re.findall(r"\[(S\d+)\]", answer))
    trace_source_ids = {
        source_id
        for trace in traces
        for source_id in trace.get("source_ids", [])
        if source_id
    }

    checks = {
        "answer_present": bool(answer.strip()),
        "required_tools": set(case["required_tools"]).issubset(called_tools),
        "minimum_sources": len(source_ids) >= case["minimum_sources"],
        "minimum_citations": len(citation_ids) >= case["minimum_citations"],
        "citations_resolve": citation_ids.issubset(source_ids),
        "trace_sources_resolve": trace_source_ids.issubset(source_ids),
        "has_disclaimer": DISCLAIMER in answer.lower(),
    }
    return {
        "id": case["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": {
            "called_tools": sorted(tool for tool in called_tools if tool),
            "source_count": len(source_ids),
            "citation_count": len(citation_ids),
        },
    }


def select_cases(cases: list[dict[str, Any]], case_ids: list[str] | None) -> list[dict[str, Any]]:
    if not case_ids:
        return cases
    requested = set(case_ids)
    available = {case["id"] for case in cases}
    unknown = requested - available
    if unknown:
        raise ValueError(f"Unknown eval case ids: {', '.join(sorted(unknown))}")
    return [case for case in cases if case["id"] in requested]
