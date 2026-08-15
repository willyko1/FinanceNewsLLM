from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from finresearch.agent import ResearchAgent


async def main() -> None:
    cases = json.loads((Path(__file__).parent / "cases.json").read_text())
    results = []
    for case in cases:
        try:
            result = await ResearchAgent().research(case["question"])
            called = {trace["name"] for trace in result["trace"]}
            citations = set(re.findall(r"\[S\d+\]", result["answer"]))
            checks = {
                "required_tools": set(case["requires_tools"]).issubset(called),
                "minimum_sources": len(result["sources"]) >= case["minimum_sources"],
                "has_citations": bool(citations),
                "has_disclaimer": "not personalized investment advice" in result["answer"].lower(),
            }
            results.append({"id": case["id"], "passed": all(checks.values()), "checks": checks})
        except Exception as exc:
            results.append({"id": case["id"], "passed": False, "error": str(exc)})
    print(json.dumps(results, indent=2))
    if not all(result["passed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
