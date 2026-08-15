from finresearch.agent import _extract_sources, _normalize_citations


def test_extract_sources_from_tool_payload():
    payload = {
        "source": {"title": "Quote", "url": "https://example.com/quote"},
        "articles": [{"title": "News", "url": "https://example.com/news"}],
        "filings": [{"title": "10-Q", "url": "https://example.com/filing"}],
    }
    assert [source["title"] for source in _extract_sources(payload)] == ["Quote", "News", "10-Q"]


def test_normalizes_provider_citation_brackets():
    assert _normalize_citations("Price is current【S1】.") == "Price is current[S1]."
