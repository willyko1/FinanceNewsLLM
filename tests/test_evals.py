import pytest

from finresearch.evaluation import evaluate_result, select_cases, validate_cases


def _case():
    return {
        "id": "market_research",
        "question": "What changed at Apple?",
        "required_tools": ["get_market_snapshot"],
        "minimum_sources": 1,
        "minimum_citations": 1,
    }


def _result():
    return {
        "answer": (
            "Apple moved after its update [S1]. "
            "Research only — not personalized investment advice."
        ),
        "sources": [{"id": "S1", "url": "https://example.com"}],
        "trace": [
            {
                "name": "get_market_snapshot",
                "arguments": {"ticker": "AAPL"},
                "source_ids": ["S1"],
            }
        ],
    }


def test_evaluate_result_accepts_grounded_answer():
    evaluation = evaluate_result(_case(), _result())

    assert evaluation["passed"] is True
    assert all(evaluation["checks"].values())
    assert evaluation["metrics"]["citation_count"] == 1


def test_evaluate_result_rejects_unresolved_citation_and_trace_source():
    result = _result()
    result["answer"] = result["answer"].replace("[S1]", "[S2]")
    result["trace"][0]["source_ids"] = ["S3"]

    evaluation = evaluate_result(_case(), result)

    assert evaluation["passed"] is False
    assert evaluation["checks"]["citations_resolve"] is False
    assert evaluation["checks"]["trace_sources_resolve"] is False


def test_validate_cases_rejects_unknown_tools():
    case = _case()
    case["required_tools"] = ["trade_stock"]

    with pytest.raises(ValueError, match="unknown tools"):
        validate_cases([case])


def test_validate_cases_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="Duplicate eval case id"):
        validate_cases([_case(), _case()])


def test_select_cases_preserves_file_order():
    first = _case()
    second = {**_case(), "id": "filing_research"}

    assert select_cases([first, second], ["filing_research"])[0]["id"] == "filing_research"


def test_select_cases_rejects_unknown_id():
    with pytest.raises(ValueError, match="Unknown eval case ids"):
        select_cases([_case()], ["missing"])
