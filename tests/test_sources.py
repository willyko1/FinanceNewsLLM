from finresearch.sources import _latest_annual_or_quarterly, _pct, _ticker


def test_ticker_normalization_and_validation():
    assert _ticker(" brk.b ") == "BRK.B"


def test_percent_change():
    assert _pct(110, 100) == 10.0
    assert _pct(10, 0) is None


def test_latest_fact_prefers_most_recent_filing():
    units = {
        "USD": [
            {"form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "val": 10},
            {"form": "10-Q", "filed": "2025-05-01", "end": "2025-03-31", "val": 12},
            {"form": "8-K", "filed": "2025-06-01", "end": "2025-05-31", "val": 99},
        ]
    }
    assert _latest_annual_or_quarterly(units)["val"] == 12
