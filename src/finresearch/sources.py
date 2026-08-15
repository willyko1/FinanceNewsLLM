from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus

import httpx

from .config import settings

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class DataSourceError(RuntimeError):
    pass


def _ticker(value: str) -> str:
    clean = value.strip().upper()
    if not TICKER_PATTERN.fullmatch(clean):
        raise ValueError("Ticker must contain 1-10 letters, numbers, dots, or hyphens")
    return clean


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _pct(new: float, old: float) -> float | None:
    return round((new / old - 1) * 100, 2) if old else None


async def market_snapshot(ticker: str) -> dict[str, Any]:
    symbol = _ticker(ticker)
    params = {"interval": "1d", "range": "1mo", "events": "div,splits"}
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        response = await client.get(
            YAHOO_CHART_URL.format(ticker=symbol),
            params=params,
            headers={"User-Agent": "Mozilla/5.0 SignalDesk/1.0"},
        )
        response.raise_for_status()
    try:
        result = response.json()["chart"]["result"][0]
        meta = result["meta"]
        timestamps = result.get("timestamp", [])
        closes = result["indicators"]["quote"][0]["close"]
        points = [(ts, close) for ts, close in zip(timestamps, closes, strict=False) if close]
        current = float(meta.get("regularMarketPrice") or points[-1][1])
    except (KeyError, IndexError, TypeError) as exc:
        raise DataSourceError(f"No market data returned for {symbol}") from exc

    previous = float(
        meta.get("chartPreviousClose") or (points[-2][1] if len(points) > 1 else current)
    )
    five_day_base = float(points[-6][1]) if len(points) >= 6 else float(points[0][1])
    month_base = float(points[0][1])
    currency = meta.get("currency", "USD")
    exchange = meta.get("fullExchangeName") or meta.get("exchangeName")
    market_time = meta.get("regularMarketTime")
    as_of = datetime.fromtimestamp(market_time, UTC).isoformat() if market_time else _now()
    source_url = f"https://finance.yahoo.com/quote/{quote_plus(symbol)}"

    return {
        "ticker": symbol,
        "company": meta.get("longName") or meta.get("shortName") or symbol,
        "price": round(current, 4),
        "currency": currency,
        "exchange": exchange,
        "as_of": as_of,
        "change_1d_percent": _pct(current, previous),
        "change_5d_percent": _pct(current, five_day_base),
        "change_1m_percent": _pct(current, month_base),
        "range_52w": {
            "low": meta.get("fiftyTwoWeekLow"),
            "high": meta.get("fiftyTwoWeekHigh"),
        },
        "source": {
            "title": f"{symbol} market data",
            "url": source_url,
            "publisher": "Yahoo Finance",
            "published_at": as_of,
        },
        "retrieved_at": _now(),
    }


async def search_finance_news(query: str, days: int = 7, limit: int = 8) -> dict[str, Any]:
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("News query cannot be empty")
    days = max(1, min(days, 30))
    limit = max(1, min(limit, 15))
    params = {"q": f"{clean_query} when:{days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"}
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        response = await client.get(
            GOOGLE_NEWS_URL,
            params=params,
            headers={"User-Agent": "Mozilla/5.0 SignalDesk/1.0"},
        )
        response.raise_for_status()

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        raise DataSourceError("News provider returned malformed XML") from exc

    articles = []
    for item in root.findall("./channel/item")[:limit]:
        source_node = item.find("source")
        title = item.findtext("title", "Untitled")
        publisher = source_node.text if source_node is not None and source_node.text else "Unknown"
        articles.append(
            {
                "title": title,
                "url": item.findtext("link", ""),
                "publisher": publisher,
                "published_at": item.findtext("pubDate"),
            }
        )
    return {"query": clean_query, "window_days": days, "articles": articles, "retrieved_at": _now()}


@lru_cache(maxsize=1)
def _cached_ticker_map(raw_items: tuple[tuple[str, str, str], ...]) -> dict[str, dict[str, str]]:
    return {ticker: {"cik": cik, "title": title} for ticker, cik, title in raw_items}


async def _sec_ticker_map() -> dict[str, dict[str, str]]:
    headers = {"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"}
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        response = await client.get(SEC_TICKERS_URL, headers=headers)
        response.raise_for_status()
    raw = response.json()
    items = tuple(
        (row["ticker"].upper(), str(row["cik_str"]), row["title"])
        for row in raw.values()
    )
    return _cached_ticker_map(items)


async def _sec_identity(ticker: str) -> tuple[str, str, str]:
    symbol = _ticker(ticker)
    identity = (await _sec_ticker_map()).get(symbol)
    if not identity:
        raise DataSourceError(f"SEC CIK not found for ticker {symbol}")
    return symbol, identity["cik"].zfill(10), identity["title"]


async def recent_sec_filings(ticker: str, limit: int = 6) -> dict[str, Any]:
    symbol, cik, company = await _sec_identity(ticker)
    limit = max(1, min(limit, 20))
    headers = {"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"}
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        response = await client.get(SEC_SUBMISSIONS_URL.format(cik=cik), headers=headers)
        response.raise_for_status()
    recent = response.json().get("filings", {}).get("recent", {})
    accepted = recent.get("acceptanceDateTime", [])
    filings = []
    allowed = {"10-K", "10-Q", "8-K", "20-F", "6-K"}
    for index, form in enumerate(recent.get("form", [])):
        if form not in allowed:
            continue
        accession = recent["accessionNumber"][index]
        accession_compact = accession.replace("-", "")
        document = recent["primaryDocument"][index]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_compact}/{document}"
        filings.append(
            {
                "form": form,
                "filed_at": recent["filingDate"][index],
                "accepted_at": accepted[index] if index < len(accepted) else None,
                "description": recent.get(
                    "primaryDocDescription", [""] * len(recent["form"])
                )[index],
                "accession_number": accession,
                "title": f"{company} {form} filed {recent['filingDate'][index]}",
                "url": url,
                "publisher": "U.S. SEC",
            }
        )
        if len(filings) >= limit:
            break
    return {
        "ticker": symbol,
        "company": company,
        "cik": cik,
        "filings": filings,
        "retrieved_at": _now(),
    }


FACT_LABELS = {
    "Revenues": "Revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
    "NetIncomeLoss": "Net income",
    "Assets": "Total assets",
    "Liabilities": "Total liabilities",
    "StockholdersEquity": "Stockholders' equity",
    "EarningsPerShareDiluted": "Diluted EPS",
    "CashAndCashEquivalentsAtCarryingValue": "Cash and equivalents",
}


def _latest_annual_or_quarterly(units: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    values = next(iter(units.values()), [])
    candidates = [v for v in values if v.get("form") in {"10-K", "10-Q"} and v.get("filed")]
    if not candidates:
        return None
    return max(candidates, key=lambda value: (value.get("filed", ""), value.get("end", "")))


async def company_facts(ticker: str) -> dict[str, Any]:
    symbol, cik, company = await _sec_identity(ticker)
    headers = {"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"}
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        response = await client.get(SEC_FACTS_URL.format(cik=cik), headers=headers)
        response.raise_for_status()
    us_gaap = response.json().get("facts", {}).get("us-gaap", {})
    metrics: dict[str, Any] = {}
    used_labels: set[str] = set()
    for fact_name, label in FACT_LABELS.items():
        if label in used_labels or fact_name not in us_gaap:
            continue
        latest = _latest_annual_or_quarterly(us_gaap[fact_name].get("units", {}))
        if latest:
            metrics[label] = {
                "value": latest.get("val"),
                "unit": next(iter(us_gaap[fact_name].get("units", {})), None),
                "period_end": latest.get("end"),
                "filed_at": latest.get("filed"),
                "form": latest.get("form"),
                "fiscal_year": latest.get("fy"),
                "fiscal_period": latest.get("fp"),
            }
            used_labels.add(label)
    url = f"https://www.sec.gov/edgar/browse/?CIK={int(cik)}&owner=exclude"
    return {
        "ticker": symbol,
        "company": company,
        "metrics": metrics,
        "source": {"title": f"{company} company facts", "url": url, "publisher": "U.S. SEC"},
        "retrieved_at": _now(),
    }


async def research_bundle(ticker: str, days: int = 7) -> dict[str, Any]:
    """Fetch the standard evidence set concurrently; useful for demos and evals."""
    market, news, filings, facts = await asyncio.gather(
        market_snapshot(ticker),
        search_finance_news(f"{ticker} stock", days=days),
        recent_sec_filings(ticker),
        company_facts(ticker),
    )
    return {"market": market, "news": news, "filings": filings, "facts": facts}
