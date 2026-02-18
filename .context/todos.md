# Data Chatbot POC — Open Items

## Not Yet Done

- [ ] **RegionID lookup** — still raw integers. Need to load Yandex GeoBase or create a mapping table to get human-readable region/country names.
- [ ] **Full dataset test** — the `--sample` (1M rows) path is tested. The full dataset load (~800MB, 20-30 min) via `url()` has not been validated end-to-end in this rework.
- [ ] **Test suite** — no automated tests exist. Should add at minimum: YAML lint, Python syntax check, a smoke test that starts the stack and runs a query.
- [ ] **Cube pre-aggregations** — Cube supports pre-computed rollups for faster queries. Not configured yet, but would make the demo snappier for repeated queries.
- [ ] **SSE transport validation** — stdio mode with Claude Desktop is the primary path. SSE via ngrok has not been tested with this rework.

## Testing Gaps

- [ ] **MCP stdio mode** — verify `docker exec -i mcp-server python server.py` starts without crashing and responds to MCP protocol messages.
- [ ] **MCP SSE handshake** — hit `/sse` endpoint with an SSE client to verify the MCP connection lifecycle works.
- [ ] **New MCP tools** — `sample_data`, `distinct_values`, `date_range` have not been exercised through the MCP tool interface (only validated indirectly via Cube API).
- [ ] **MCP resource** (`schema://semantic-model`) — never fetched through MCP protocol, only confirmed Cube `/meta` returns data.
- [ ] **MCP prompt** (`analytics_assistant`) — never fetched through MCP protocol.
- [ ] **Error handling paths** — bad query, wrong cube name, Cube down, timeout scenarios.
- [ ] **Cross-cube join queries** — e.g. "bounce rate for pages with high first paint timing" using the visits-to-hits join. Most likely to surface real bugs.

## Future Enhancements

- [ ] **More cubes** — only hits and visits are modeled. Could add a goals cube, a URL performance cube, or a demographics-focused cube.
- [ ] **dbt semantic layer integration** — swap Cube for dbt MetricFlow + Cube as API gateway. This is the production architecture.
- [ ] **Auth** — the JWT secret is a placeholder. Production needs proper secret management.
- [ ] **Rate limiting / query guards** — no limits on query size or frequency. An LLM could accidentally run an expensive full-table scan.
- [ ] **Caching** — Cube has built-in caching but it's not tuned. For a demo this is fine; for production, configure cache TTLs.
