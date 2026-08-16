from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .sources import (
    company_facts,
    market_snapshot,
    recent_sec_filings,
)
from .sources import search_finance_news as search_news_source

mcp = FastMCP(
    "Matt Financial Data",
    instructions="Read-only, timestamped market, news, and SEC evidence for financial research.",
)


@mcp.tool()
async def get_market_snapshot(ticker: str) -> dict:
    """Get delayed quote data and 1-day, 5-day, and 1-month price changes for a ticker."""
    return await market_snapshot(ticker)


@mcp.tool()
async def search_finance_news(query: str, days: int = 7, limit: int = 8) -> dict:
    """Search recent financial news. Returns headlines, publishers, timestamps, and URLs."""
    return await search_news_source(query, days=days, limit=limit)


@mcp.tool()
async def get_recent_sec_filings(ticker: str, limit: int = 6) -> dict:
    """Get recent material SEC filings (10-K, 10-Q, 8-K, 20-F, 6-K) with primary-document URLs."""
    return await recent_sec_filings(ticker, limit=limit)


@mcp.tool()
async def get_company_facts(ticker: str) -> dict:
    """Get the latest commonly reported GAAP metrics from SEC XBRL company facts."""
    return await company_facts(ticker)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
