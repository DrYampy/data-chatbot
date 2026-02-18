import os
import sys
import time
import json
import jwt
import httpx
import logging
import asyncio
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, Request
from mcp.server.sse import SseServerTransport
import uvicorn
from ingest_data import ingest

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-cube")

# Initialize FastMCP
mcp = FastMCP("Cube Semantic Layer")

# Configuration
CUBE_API_URL = os.getenv("CUBEJS_API_URL", "http://localhost:4000/cubejs-api/v1")
CUBE_API_SECRET = os.getenv("CUBEJS_API_SECRET", "your-very-secret-token")


def get_token():
    return jwt.encode(
        {"iat": int(time.time())},
        CUBE_API_SECRET,
        algorithm="HS256",
    )


async def cube_request(method: str, endpoint: str, json_data: dict = None):
    """Make an authenticated request to the Cube REST API with helpful error messages."""
    token = get_token()
    headers = {"Authorization": token}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            url = f"{CUBE_API_URL}{endpoint}"
            logger.info(f"Requesting {method} {url}")
            if method == "GET":
                response = await client.get(url, headers=headers)
            else:
                response = await client.post(url, headers=headers, json=json_data)

            if response.status_code != 200:
                error_body = response.text
                logger.error(f"Cube API error {response.status_code}: {error_body}")
                try:
                    error_msg = response.json().get("error", error_body)
                except Exception:
                    error_msg = error_body
                raise ValueError(
                    f"Cube API returned HTTP {response.status_code}. "
                    f"Error: {error_msg}. "
                    f"Hint: Check that all measure and dimension names are spelled exactly "
                    f"as returned by list_cubes or get_cube_meta (e.g. 'visits.total_visits', "
                    f"'visits.traffic_source_name')."
                )
            return response.json()
    except httpx.TimeoutException:
        raise ValueError(
            "Cube API request timed out after 60s. The query may be too broad — "
            "try adding a time filter or reducing the number of dimensions."
        )
    except httpx.ConnectError:
        raise ValueError(
            "Cannot reach Cube API. Ensure the stack is running: docker compose up -d"
        )


# ---------------------------------------------------------------------------
# MCP Resource: exposes the full semantic model as ambient context for the LLM
# ---------------------------------------------------------------------------

@mcp.resource("schema://semantic-model", mime_type="application/json")
async def semantic_model_resource() -> str:
    """
    Full Cube semantic model — all cubes with their measures, dimensions,
    and descriptions. The LLM should read this resource to understand what
    data is available before constructing queries.
    """
    try:
        meta = await cube_request("GET", "/meta")
    except Exception as e:
        return json.dumps({"error": str(e)})

    summary = []
    for cube in meta.get("cubes", []):
        summary.append({
            "name": cube["name"],
            "title": cube.get("title", cube["name"]),
            "description": cube.get("description", ""),
            "measures": [
                {
                    "name": m["name"],
                    "title": m.get("title", m["name"]),
                    "type": m.get("type", ""),
                    "description": m.get("description", ""),
                    "format": m.get("format", ""),
                }
                for m in cube.get("measures", [])
            ],
            "dimensions": [
                {
                    "name": d["name"],
                    "title": d.get("title", d["name"]),
                    "type": d.get("type", ""),
                    "description": d.get("description", ""),
                }
                for d in cube.get("dimensions", [])
            ],
        })
    return json.dumps(summary, indent=2)


# ---------------------------------------------------------------------------
# MCP Prompt: governance & usage instructions for the LLM
# ---------------------------------------------------------------------------

@mcp.prompt()
def analytics_assistant() -> str:
    """System prompt that instructs the LLM to use the semantic layer correctly."""
    return (
        "You are a data analytics assistant with access to a Cube semantic layer "
        "over a ClickHouse web analytics database (the Yandex Metrica dataset).\n\n"
        "Rules:\n"
        "1. ALWAYS use the Cube semantic layer tools — never write raw SQL.\n"
        "2. Before constructing any query, read the schema://semantic-model resource "
        "to understand the available cubes, measures, and dimensions.\n"
        "3. Use sample_data to preview what values look like before filtering.\n"
        "4. Use distinct_values to see categorical values for string dimensions.\n"
        "5. Use date_range to understand the time window before applying date filters.\n"
        "6. Map business questions to the correct measure and dimension names from "
        "the semantic model — never invent names.\n"
        "7. When presenting results, explain what the numbers mean in plain language.\n"
        "8. The data is web analytics for a Russian site (~Aug 2013). Adjust date "
        "filters accordingly.\n\n"
        "Governance: Do not expose raw SQL, internal UserIDs, or IP addresses. "
        "Aggregate and anonymise where appropriate."
    )


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_cubes() -> list:
    """List all available cubes with their titles and descriptions."""
    try:
        meta = await cube_request("GET", "/meta")
        return [
            {
                "name": cube["name"],
                "title": cube.get("title", cube["name"]),
                "description": cube.get("description", ""),
            }
            for cube in meta.get("cubes", [])
        ]
    except ValueError as e:
        return [{"error": str(e)}]


@mcp.tool()
async def get_cube_meta(cube_name: str) -> dict:
    """Get detailed metadata for a specific cube, including all measures and dimensions with descriptions."""
    try:
        meta = await cube_request("GET", "/meta")
        for cube in meta.get("cubes", []):
            if cube["name"] == cube_name:
                return cube
        available = [c["name"] for c in meta.get("cubes", [])]
        return {"error": f"Cube '{cube_name}' not found. Available cubes: {available}"}
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
async def run_cube_query(query: dict) -> dict:
    """
    Execute a query against the Cube semantic layer.

    Query format example:
    {
        "measures": ["visits.total_visits", "visits.bounce_rate"],
        "dimensions": ["visits.traffic_source_name"],
        "timeDimensions": [{"dimension": "visits.start_time", "granularity": "month", "dateRange": "last 1 year"}],
        "limit": 100
    }
    """
    try:
        return await cube_request("POST", "/load", {"query": query})
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
async def explain_query(query: dict) -> dict:
    """
    Get the underlying SQL that Cube generates for a given query.
    Use this to show transparency — the semantic layer translates business
    questions into optimised SQL so users don't have to.
    """
    try:
        return await cube_request("POST", "/sql", {"query": query})
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
async def sample_data(cube_name: str, limit: int = 5) -> dict:
    """
    Return a small sample of rows from a cube so you can see what the data looks like.
    Use this before writing a real query to understand the shape and values.

    cube_name: e.g. 'hits' or 'visits'
    limit: number of rows (default 5, max 20)
    """
    limit = min(limit, 20)
    try:
        meta = await cube_request("GET", "/meta")
        cube_meta = next(
            (c for c in meta.get("cubes", []) if c["name"] == cube_name), None
        )
        if not cube_meta:
            available = [c["name"] for c in meta.get("cubes", [])]
            return {"error": f"Cube '{cube_name}' not found. Available cubes: {available}"}

        dims = [
            d["name"]
            for d in cube_meta.get("dimensions", [])
            if d.get("type") in ("string", "time", "boolean")
        ][:6]
        measures = [m["name"] for m in cube_meta.get("measures", [])][:3]

        query = {"dimensions": dims, "measures": measures, "limit": limit}
        result = await cube_request("POST", "/load", {"query": query})
        return {"sample": result.get("data", []), "query_used": query}
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
async def distinct_values(cube_name: str, dimension_name: str, limit: int = 20) -> dict:
    """
    Return distinct values for a categorical dimension.
    Use this to understand what values exist before filtering.

    cube_name: e.g. 'visits'
    dimension_name: e.g. 'traffic_source_name' (will be auto-qualified to 'visits.traffic_source_name')
    limit: max distinct values (default 20, max 100)
    """
    limit = min(limit, 100)
    if "." not in dimension_name:
        dimension_name = f"{cube_name}.{dimension_name}"
    try:
        query = {"dimensions": [dimension_name], "limit": limit}
        result = await cube_request("POST", "/load", {"query": query})
        values = [row.get(dimension_name) for row in result.get("data", [])]
        return {"dimension": dimension_name, "distinct_values": values, "count": len(values)}
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
async def date_range(cube_name: str, time_dimension: str) -> dict:
    """
    Return the min and max dates for a time dimension so you know the valid time window.

    cube_name: e.g. 'hits' or 'visits'
    time_dimension: e.g. 'event_time' or 'start_time'
    """
    qualified = f"{cube_name}.{time_dimension}" if "." not in time_dimension else time_dimension

    # Pick a count measure for the cube
    try:
        meta = await cube_request("GET", "/meta")
        cube_meta = next(
            (c for c in meta.get("cubes", []) if c["name"] == cube_name), None
        )
        if not cube_meta:
            available = [c["name"] for c in meta.get("cubes", [])]
            return {"error": f"Cube '{cube_name}' not found. Available cubes: {available}"}

        count_measure = next(
            (m["name"] for m in cube_meta.get("measures", []) if m.get("type") == "count"),
            cube_meta["measures"][0]["name"] if cube_meta.get("measures") else None,
        )
        if not count_measure:
            return {"error": f"No measures found in cube '{cube_name}'"}

        # Query ascending to get earliest month
        query = {
            "measures": [count_measure],
            "timeDimensions": [
                {"dimension": qualified, "granularity": "month", "dateRange": "from 2000-01-01 to 2030-01-01"}
            ],
            "order": {qualified: "asc"},
            "limit": 1,
        }
        result_asc = await cube_request("POST", "/load", {"query": query})

        # Query descending to get latest month
        query["order"] = {qualified: "desc"}
        result_desc = await cube_request("POST", "/load", {"query": query})

        data_asc = result_asc.get("data", [])
        data_desc = result_desc.get("data", [])

        # Extract the time dimension key from the response
        time_key = f"{qualified}.month"
        return {
            "time_dimension": qualified,
            "earliest": data_asc[0].get(time_key) if data_asc else None,
            "latest": data_desc[0].get(time_key) if data_desc else None,
        }
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
async def seed_data(sample: bool = True) -> dict:
    """
    Trigger idempotent ingestion of the Metrica dataset into ClickHouse.

    sample=True (default): loads only the first 1M rows per table — fast for demos.
    sample=False: loads the full ~21M hits and ~1.6M visits — may take 20-30 min.
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: ingest(sample=sample))
        return {"status": "success", "message": "Ingestion complete."}
    except Exception as e:
        logger.exception("Ingestion failed")
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# FastAPI setup for SSE transport + health check
# ---------------------------------------------------------------------------

app = FastAPI()
sse = SseServerTransport("/messages")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options(),
        )


@app.post("/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        logger.info("Starting SSE server on port 8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        logger.info("Starting stdio server")
        mcp.run()
