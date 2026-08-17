from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from finresearch.agent import ResearchAgent
from finresearch.evaluation import KNOWN_TOOLS, evaluate_result, select_cases, validate_cases

CASES_PATH = Path(__file__).parent / "cases.json"


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text())
    validate_cases(cases)
    return cases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Matt's behavioral research evaluations")
    parser.add_argument("--case", action="append", dest="case_ids", help="Run one case by id")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path")
    parser.add_argument("--validate", action="store_true", help="Validate cases without using AI")
    parser.add_argument("--list", action="store_true", help="List available case ids")
    return parser


async def run_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    agent = ResearchAgent()
    for case in cases:
        started = time.monotonic()
        try:
            research = await agent.research(case["question"])
            evaluated = evaluate_result(case, research)
            evaluated["duration_seconds"] = round(time.monotonic() - started, 2)
            evaluated["model"] = research.get("model")
            evaluated["provider"] = research.get("provider")
            results.append(evaluated)
        except Exception as exc:
            results.append(
                {
                    "id": case["id"],
                    "passed": False,
                    "duration_seconds": round(time.monotonic() - started, 2),
                    "error": str(exc),
                }
            )

    passed = sum(result["passed"] for result in results)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {"passed": passed, "failed": len(results) - passed, "total": len(results)},
        "results": results,
    }


def main() -> None:
    args = build_parser().parse_args()
    cases = load_cases()
    if args.list:
        print("\n".join(case["id"] for case in cases))
        return
    if args.validate:
        print(f"Validated {len(cases)} eval cases and {len(KNOWN_TOOLS)} tool names.")
        return

    selected = select_cases(cases, args.case_ids)
    report = asyncio.run(run_cases(selected))
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n")
    if report["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
