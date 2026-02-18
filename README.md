# Data Chatbot PoC (ClickHouse + Cube + MCP)

A proof of concept demonstrating how a **semantic layer** between an LLM and a data warehouse makes AI-driven analytics reliable, governed, and useful.

## Why a Semantic Layer?

Without Cube, an LLM would need to write raw SQL against 100+ column tables filled with opaque integer IDs (`TraficSourceID = 3`, `OS = 2`, `UserAgent = 6`). It would need to know that `visits_v1` uses a CollapsingMergeTree engine and requires `WHERE Sign = 1` to avoid double-counting. It would hallucinate column names and produce incorrect aggregations.

With Cube as a semantic layer, the LLM asks for `visits.traffic_source_name = 'Ad'` and `visits.bounce_rate` — vetted, human-readable, correctly computed metrics. The business logic lives in YAML definitions, not in LLM-generated SQL. This is the pattern that scales.

## Architecture

```
User / LLM (Claude Desktop, ChatGPT, etc.)
    │
    │  MCP protocol (stdio or SSE)
    ▼
FastMCP Server (Python)
    │  ├── schema://semantic-model  (MCP resource — ambient context)
    │  ├── analytics_assistant      (MCP prompt — governance rules)
    │  └── tools: list_cubes, get_cube_meta, run_cube_query,
    │            explain_query, sample_data, distinct_values,
    │            date_range, seed_data
    │
    │  Cube REST API (JWT auth)
    ▼
Cube Core (Semantic Layer)
    │  ├── visits cube: bounce rate, conversion rate, session duration...
    │  └── hits cube: page views, unique users, first paint timing...
    │
    │  ClickHouse driver
    ▼
ClickHouse (hits_v1, visits_v1 — Yandex Metrica dataset)
```

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env and set CUBEJS_API_SECRET to a random string
```

### 2. Start the Stack

```bash
docker compose up -d
```

This starts four services:
- **ClickHouse** (ports 8123, 9000) — OLAP database
- **Cube Core** (port 4000) — semantic layer
- **Seed** (one-shot) — automatically loads a 1M-row sample of the Metrica dataset
- **MCP Server** (port 8000) — bridges Cube to any LLM via MCP

The seed service runs automatically on first startup and is idempotent. To load the full dataset (~21M hits, ~1.6M visits, ~800MB download):

```bash
docker compose run --rm seed python ingest_data.py
```

### 3. Connect Claude Desktop (Stdio)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cube-analytics": {
      "command": "docker",
      "args": ["exec", "-i", "mcp-server", "python", "server.py"]
    }
  }
}
```

### 4. Connect via SSE (Remote LLMs)

The MCP server exposes an SSE endpoint at `http://localhost:8000/sse`. For remote access:

```bash
ngrok http 8000
```

Then point your LLM client to `https://<ngrok-id>.ngrok-free.app/sse`.

## Semantic Model

The Cube semantic layer defines business-friendly metrics and dimensions in `cube/model/cubes/`.

### Visits Cube

**Measures:** Total Visits, Bounce Rate, Avg Session Duration, Page Views per Visit, Goal Conversion Rate, Visits with Goals.

**Dimensions:** Session Start Time, Traffic Source (Direct / Search / Referral / Ad / Social / Email / Recommendations), Operating System, Browser, Gender, Income Level, Is Mobile, Is New Visitor, Search Phrase, UTM Source / Medium / Campaign.

### Hits Cube

**Measures:** Total Hits, Unique Users, Real Page Views (filtered), Avg First Paint (ms).

**Dimensions:** Event Time, Operating System, Browser, Region ID, Full URL, URL Domain, Referer Domain, Is Mobile, Page Title.

All categorical dimensions use human-readable labels (not raw integer IDs). The visits cube joins to hits via UserID + CounterID for cross-cube analytics.

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_cubes` | List available cubes with descriptions |
| `get_cube_meta` | Get measures and dimensions for a specific cube |
| `run_cube_query` | Execute a Cube query and get results |
| `explain_query` | Show the SQL that Cube generates (transparency) |
| `sample_data` | Preview rows from a cube to see data shape |
| `distinct_values` | List unique values for a categorical dimension |
| `date_range` | Get min/max dates for a time dimension |
| `seed_data` | Trigger data ingestion (idempotent) |

The server also exposes:
- **`schema://semantic-model`** — MCP resource with the full semantic model as JSON, so the LLM has ambient context without needing tool calls.
- **`analytics_assistant`** — MCP prompt template with governance rules and usage instructions.

## Project Structure

```
├── cube/model/cubes/
│   ├── hits.yml          # Hits semantic model
│   └── visits.yml        # Visits semantic model (with join to hits)
├── mcp_server/
│   ├── server.py         # FastMCP server (tools, resources, prompts)
│   ├── ingest_data.py    # ClickHouse data ingestion
│   ├── Dockerfile
│   ├── requirements.txt
│   └── start.sh
├── docker-compose.yml    # Full stack orchestration
├── .env.example          # Configuration template
└── README.md
```

## Production Path

This PoC uses Cube as the semantic layer. In production, **dbt's semantic layer (MetricFlow)** defines the metrics, and Cube (or another API layer) serves them to MCP. The MCP server pattern stays the same — only the semantic layer backend changes.
