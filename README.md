# Matt

[![CI](https://github.com/willyko1/FinanceNewsLLM/actions/workflows/ci.yml/badge.svg)](https://github.com/willyko1/FinanceNewsLLM/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-315b4c)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-315b4c)](LICENSE)

Matt is a financial research assistant that checks live market data, recent reporting, SEC filings,
and company fundamentals before answering. Every brief includes its source links and the MCP tool
trace used to produce it.

**Why I built it:** Matt started as a simple RAG prototype for summarizing financial news. I found
that news retrieval alone was not enough for questions involving current prices, SEC filings, or
company-reported financials, so I rebuilt it around an MCP-based research agent that gathers
evidence from multiple sources before answering.

**Live app:** [signaldesk-a8gf.onrender.com](https://signaldesk-a8gf.onrender.com)

Matt is a research tool, not a trading system. It does not execute trades or provide personalized
investment advice, and market data may be delayed.

## What it does

- Retrieves current market snapshots and short-period price changes
- Searches recent company reporting with publisher and publication metadata
- Reads recent SEC filings and commonly reported XBRL company facts
- Links current and numerical claims to inline `[S#]` citations
- Shows each MCP tool call, its inputs, and the source IDs it returned
- Supports Groq and OpenAI through a provider-compatible Responses API
- Bounds tool use, concurrency, per-visitor usage, and shared demo usage
- Includes a saved investigation that does not consume model quota

## Request path

```text
Browser / API
     │
     ▼
FastAPI ──► research agent ──► MCP client ──stdio──► finance MCP server
                                                      ├── Yahoo market data
                                                      ├── Google News RSS
                                                      └── SEC EDGAR APIs
     │
     ▼
Cited brief + source list + MCP trace
```

The model chooses which read-only tools it needs, while the MCP server owns data retrieval. Tool use
is capped. If a model reaches the tool-round limit, Matt synthesizes the evidence already collected
instead of continuing indefinitely.

## Run locally

Requirements: Python 3.11+ and either a Groq or OpenAI API key.

```bash
git clone https://github.com/willyko1/FinanceNewsLLM.git
cd FinanceNewsLLM
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Add your provider key to `.env`, then start the application:

```bash
make dev
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive API documentation is available at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `AI_PROVIDER` | `groq` | Model provider: `groq` or `openai` |
| `AI_MODEL` | `openai/gpt-oss-120b` | Provider model identifier |
| `GROQ_API_KEY` | — | Required when `AI_PROVIDER=groq` |
| `OPENAI_API_KEY` | — | Required when `AI_PROVIDER=openai` |
| `SEC_USER_AGENT` | example contact | Contact identifier requested by SEC EDGAR |
| `REQUEST_TIMEOUT_SECONDS` | `20` | Upstream data request timeout |
| `RESEARCH_TIMEOUT_SECONDS` | `90` | Maximum duration of one investigation |
| `MAX_TOOL_ROUNDS` | `4` | Maximum model/tool iterations |
| `MAX_TOOL_CALLS` | `12` | Maximum tool calls per investigation |
| `REQUESTS_PER_DAY_PER_IP` | `3` | Public per-visitor quota |
| `GLOBAL_REQUESTS_PER_DAY` | `100` | Shared public quota |
| `RESPONSE_CACHE_SECONDS` | `600` | Successful-response cache duration |

Never commit `.env` or an API key. Set `SEC_USER_AGENT` to a real project name and contact email
before making sustained requests to EDGAR.

## API

Check provider and MCP connectivity:

```bash
curl http://127.0.0.1:8000/api/health
```

Run an investigation:

```bash
curl -X POST http://127.0.0.1:8000/api/research \
  -H 'Content-Type: application/json' \
  -d '{"question":"What changed in Apple’s latest filing?"}'
```

Load the zero-cost saved example:

```bash
curl http://127.0.0.1:8000/api/demo
```

## MCP tools

| Tool | Returns |
| --- | --- |
| `get_market_snapshot` | Price, timestamp, exchange, currency, and 1D/5D/1M changes |
| `search_finance_news` | Headlines, publishers, publication times, and article links |
| `get_recent_sec_filings` | Recent 10-K, 10-Q, 8-K, 20-F, and 6-K filings |
| `get_company_facts` | Commonly reported SEC XBRL financial metrics |

Run the stdio MCP server independently with `matt-mcp`.

## Evaluation

Unit tests are deterministic and do not require network access or a model key:

```bash
make lint
make test
make eval-validate
```

`make eval-validate` checks the eval-case schema and tool names. CI runs this offline validation but
does not spend model quota.

The behavioral eval suite uses live data and the configured provider:

```bash
make eval
```

Run one case or save a machine-readable report:

```bash
python evals/run.py --case filing_research
python evals/run.py --output eval-report.json
python evals/run.py --list
```

Each case checks required tool selection, minimum source and citation counts, citation resolution,
trace/source consistency, and the research-only disclaimer. The suite evaluates grounding behavior
rather than fixed financial conclusions because prices, headlines, and filings change over time.

## Project layout

```text
src/finresearch/
├── agent.py          model orchestration and citation assembly
├── mcp_client.py     stdio MCP client adapter
├── mcp_server.py     read-only finance tool definitions
├── sources.py        Yahoo, Google News, and SEC clients
├── web.py            FastAPI routes, quotas, cache, and timeouts
├── static/           browser interface
└── demo/             saved zero-cost investigation
evals/                live behavioral cases and evaluator
tests/                deterministic unit tests
```

## Deployment

The `Dockerfile` and `render.yaml` define the public Render service. Configure `GROQ_API_KEY` and
`SEC_USER_AGENT` as private Render environment variables. The included limits are appropriate for a
single demo instance; move quotas and caching to a shared store before running multiple replicas.

## Data sources and limitations

- Market data comes from Yahoo Finance and may be delayed.
- News discovery uses Google News RSS; original publishers remain linked.
- Filings and fundamentals come from official SEC EDGAR APIs.
- Public feeds may be incomplete, rate-limited, or temporarily unavailable.
- Model-generated analysis can still be wrong; verify decisions against primary sources.

## License

[MIT](LICENSE)
