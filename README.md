# Matt

Matt is a small financial research assistant that checks live market data, recent reporting, SEC
filings, and company fundamentals before it answers. Its sources and MCP tool calls stay visible so
you can inspect where a claim came from.

Live app: [signaldesk-a8gf.onrender.com](https://signaldesk-a8gf.onrender.com)

Matt is built for research, not trade execution or personalized investment advice. Prices may be
delayed, and every answer should be checked against the linked source material.

## How it works

```text
Question
   │
   ▼
Research agent ──► MCP client ──► read-only finance tools
                                      ├── Market snapshot
                                      ├── Financial news
                                      ├── SEC submissions
                                      └── SEC company facts
   │
   ▼
Cited brief + sources + tool trace
```

The model decides which tools it needs, while the MCP server owns data retrieval. Tool use is
bounded, and when the tool budget is reached Matt produces a final brief from the evidence already
collected rather than continuing indefinitely.

## Features

- Live market snapshots with timestamps and short-period price changes
- Recent financial news with publisher and publication metadata
- SEC filings and commonly reported XBRL company facts
- Inline `[S#]` citations linked to the original sources
- An inspectable MCP trace showing tool inputs and returned source IDs
- Groq and OpenAI support through a provider-compatible Responses API
- Per-visitor quotas, a shared daily limit, bounded tool use, and response caching
- A saved example that does not consume model quota
- FastAPI, Docker, tests, linting, and Render deployment configuration

## Run locally

Requirements: Python 3.11+ and a Groq API key or OpenAI API key.

```bash
git clone https://github.com/willyko1/FinanceNewsLLM.git
cd FinanceNewsLLM
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Create a key at [GroqCloud](https://console.groq.com/keys), add it to `.env`, and run:

```bash
make dev
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). API documentation is available at
`/docs`, and `/api/health` reports the provider and discovered MCP tools.

The free default uses Groq with `openai/gpt-oss-120b`. To use OpenAI, set
`AI_PROVIDER=openai`, `OPENAI_API_KEY`, and your preferred `AI_MODEL` in `.env`.

## MCP tools

| Tool | Returns |
| --- | --- |
| `get_market_snapshot` | Price, timestamp, exchange, currency, and 1D/5D/1M changes |
| `search_finance_news` | Headlines, publishers, publication times, and article links |
| `get_recent_sec_filings` | Recent 10-K, 10-Q, 8-K, 20-F, and 6-K filings |
| `get_company_facts` | Commonly reported SEC XBRL financial metrics |

Run the MCP server independently with:

```bash
matt-mcp
```

## Tests

```bash
make lint
make test
make eval  # uses live data and the configured model provider
```

The evaluations check source selection, citations, and the research-only disclaimer. They test
grounding behavior rather than hard-coded financial conclusions because the underlying data changes.

## Deployment

`render.yaml` and the `Dockerfile` describe a free Render web service. Set `GROQ_API_KEY` and
`SEC_USER_AGENT` as private environment variables in Render; do not commit either value.

The public configuration allows three live investigations per visitor per rolling day and 100
investigations globally. Those limits and the response cache are in memory, which is appropriate for
one demo instance but should be moved to a shared store before scaling to multiple replicas.

## Data sources and limitations

- Market data comes from Yahoo Finance and may be delayed.
- News discovery uses Google News RSS; the original publishers remain linked.
- Filings and fundamentals come from the official SEC EDGAR APIs.
- Matt does not connect to brokerage accounts or execute trades.
- Public financial and news feeds can be incomplete or temporarily unavailable.

## License

MIT
