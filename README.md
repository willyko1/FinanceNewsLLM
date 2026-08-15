# SignalDesk

**Financial research, with receipts.** SignalDesk is an evidence-first research agent that uses the Model Context Protocol (MCP) to investigate live market data, recent financial news, SEC filings, and company fundamentals before answering.

It is intentionally a research tool—not a stock picker. Current and numerical claims are linked to the evidence used, tool activity remains visible, and the agent separates reported facts from its interpretation.

## Why this project exists

Generic finance chatbots can sound confident without showing whether an answer came from a filing, a stale article, or model memory. SignalDesk makes the research process inspectable:

```text
Question
   │
   ▼
Provider-compatible Responses API ─────► MCP client
                                             │ stdio
                                             ▼
                                   SignalDesk MCP server
                                   ├── Market snapshot
                                   ├── Financial news
                                   ├── SEC submissions
                                   └── SEC company facts
                                             │
                                             ▼
                              Timestamped evidence + source URLs
   │
   ▼
Cited brief + research trace + uncertainty
```

## Product features

- Four real read-only MCP tools: market snapshots, news search, recent SEC filings, and SEC XBRL facts
- Multi-step tool orchestration with the OpenAI Responses API
- Inline `[S#]` evidence citations linked to a source inspector
- Visible MCP tool trace, inputs, timestamps, and evidence provenance
- Guardrails against personalized buy/sell instructions and unsupported claims
- Responsive web interface plus generated FastAPI API documentation
- Automated unit tests and a small behavioral evaluation suite
- Docker and one-command local setup
- Public-demo safeguards: per-visitor and shared quotas, bounded tool rounds, concurrency limits,
  short-lived response caching, and a zero-cost saved investigation

## Quick start

Requirements: Python 3.11+ and a free Groq API key (or an OpenAI API key).

```bash
git clone <your-repository-url>
cd FinanceNewsLLM
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Create a free key at [GroqCloud](https://console.groq.com/keys), add it to `.env`, then start the app:

```bash
make dev
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The health endpoint at `/api/health` confirms the MCP connection and lists the discovered tools.

The free default is Groq with `openai/gpt-oss-120b`. To use OpenAI instead, set
`AI_PROVIDER=openai`, `OPENAI_API_KEY`, and `AI_MODEL=gpt-5.6-terra` in `.env`.

## MCP tools

| Tool | Evidence returned |
| --- | --- |
| `get_market_snapshot` | Price, timestamp, exchange, currency, and 1D/5D/1M changes |
| `search_finance_news` | Recent headlines, publishers, publication times, and links |
| `get_recent_sec_filings` | Recent 10-K/10-Q/8-K/20-F/6-K filings and primary documents |
| `get_company_facts` | Latest commonly reported SEC XBRL financial metrics |

The server runs over MCP's stdio transport and can also be inspected independently:

```bash
signaldesk-mcp
```

## Verification

```bash
make lint
make test
make eval   # uses live data and the configured AI provider
```

The behavioral evals check that the agent calls required evidence sources, cites its answer, includes enough sources, and preserves the research-only disclaimer. Live financial answers are inherently time-dependent, so the evals test grounding behavior rather than hard-coded conclusions.

## Data and trust boundaries

- Market data is retrieved from Yahoo Finance and may be delayed.
- News discovery uses Google News RSS; publisher links and timestamps are preserved.
- Filings and fundamentals come from the official SEC EDGAR APIs.
- The app does not execute trades, connect to brokerage accounts, or provide personalized investment advice.
- No financial data result is cached as model knowledge; tools retrieve it at question time.

For heavier production use, replace public endpoints with licensed market/news feeds, add persistent request tracing, authentication, rate limiting, and a compliance review.

## Deploy to Render

The included `render.yaml` and `Dockerfile` describe a free Render web service. Connect this
repository in the Render dashboard and provide `GROQ_API_KEY` and `SEC_USER_AGENT` as secret
environment variables. Never add either secret to Git.

Render supplies the public port automatically. The container starts FastAPI, which launches the
read-only MCP server as a child process for each investigation. Anonymous visitors receive three
live investigations per rolling day, while the saved example at `/api/demo` never consumes model
quota. The in-memory limiter is intentionally lightweight for a single portfolio container; use a
shared store such as Redis if the service is ever scaled to multiple replicas.

## Portfolio talking points

- Designed an MCP boundary that keeps data retrieval provider-independent from model orchestration.
- Built a bounded tool loop with explicit evidence provenance and citation IDs.
- Added evaluation criteria around grounding, tool selection, and safety instead of evaluating prose style alone.
- Made intermediate agent behavior inspectable in the product UI.

## License

MIT
