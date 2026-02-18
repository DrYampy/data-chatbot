# Data Chatbot POC — Project Context

## Architecture

```
LLM (Claude Desktop / ChatGPT)
  |  MCP (stdio or SSE)
FastMCP Server (Python, port 8000)
  |  Cube REST API (JWT auth)
Cube Core (semantic layer, port 4000)
  |  ClickHouse driver
ClickHouse (OLAP, port 8123/9000)
```

This is a POC demonstrating the value of a **semantic layer** between LLMs and raw SQL. Cube is the semantic layer for this demo. In production, dbt's semantic layer (MetricFlow) will replace Cube, and Cube may serve as the API layer on top of dbt metrics.

## Dataset: Yandex Metrica

Two tables in `datasets` database:
- `hits_v1` — individual page views/events (~21M rows full, 1M sample)
- `visits_v1` — sessions (~1.6M rows full, ~1M sample)

### Critical: CollapsingMergeTree

`visits_v1` uses `CollapsingMergeTree(Sign)`. You MUST filter `WHERE Sign = 1` or use `sum(Sign)` in aggregates. Without this, rows with both +1 and -1 Sign values get double-counted. The Cube model handles this in its base SQL.

### ID Mappings

These are Yandex-internal integer codes. The Cube models map them to human-readable strings via CASE WHEN:

| Column | Values |
|--------|--------|
| TraficSourceID | -1=Unknown, 0=Direct, 1=Search, 2=Referral, 3=Ad, 4=Social, 5=Email, 6=Recommendations |
| OS | 0=Unknown, 1=Windows, 2=macOS, 3=Android, 4=iOS, 5=Linux, 6=WinPhone, 7=BlackBerry |
| UserAgent (browser) | 0=Unknown, 1=IE, 2=Firefox, 3=Chrome, 4=Safari, 5=Opera, 6=Yandex Browser, 7=Android Browser, 8=Samsung Browser |
| Sex | 0=Unknown, 1=Male, 2=Female |
| Income | 0=Unknown, 1=Low, 2=Below Average, 3=Average, 4=Above Average, 5=High |

RegionID maps to Yandex GeoBase regions — no lookup table loaded, still raw integers.

## Docker Gotchas

- **ClickHouse 24.8** generates a random password on first init. Set `CLICKHOUSE_PASSWORD=` (empty) to allow passwordless access for the POC.
- **Cube container** has no wget or curl — healthcheck uses `node -e` with http module.
- **MCP server container** (python:3.13-slim) has no wget or curl — healthcheck uses `python -c` with urllib.
- The `seed` service is a one-shot container that loads data via ClickHouse's native `url()` table function (no subprocess/curl piping needed).
- Cube needs `start_period: 30s` on healthcheck — it compiles YAML models at startup.

## MCP Server Features

- **Resource**: `schema://semantic-model` — full Cube metadata as JSON for ambient LLM context
- **Prompt**: `analytics_assistant` — governance rules and usage instructions
- **Tools**: list_cubes, get_cube_meta, run_cube_query, explain_query, sample_data, distinct_values, date_range, seed_data

## Key Decisions

- Kept Cube despite being heavyweight — the POC needs to demonstrate the semantic layer pattern, and Cube is standing in for what will be dbt + an API layer in production.
- Ingestion uses ClickHouse `INSERT INTO ... SELECT FROM url()` instead of subprocess piping — server-side fetch/decompress, no Python streaming bugs.
- `--sample` flag loads 1M rows per table for fast demos. Full dataset is opt-in.
- Joins between visits and hits are defined on UserID + CounterID. Both cubes need primary keys (visit_id, watch_id) for Cube's join system to work.
