import os
import time
import jwt
import httpx
import logging
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, Request
from mcp.server.sse import SseServerTransport
import uvicorn
import asyncio

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
        algorithm="HS256"
    )

async def cube_request(method: str, endpoint: str, json_data: dict = None):
    token = get_token()
    headers = {"Authorization": token}
    async with httpx.AsyncClient(timeout=60.0) as client:
        url = f"{CUBE_API_URL}{endpoint}"
        logger.info(f"Requesting {method} {url}")
        if method == "GET":
            response = await client.get(url, headers=headers)
        else:
            response = await client.post(url, headers=headers, json=json_data)

        if response.status_code != 200:
            logger.error(f"Cube API error: {response.status_code} - {response.text}")

        response.raise_for_status()
        return response.json()

@mcp.tool()
async def list_cubes():
    """List all available cubes and their descriptions."""
    meta = await cube_request("GET", "/meta")
    cubes = []
    for cube in meta.get("cubes", []):
        cubes.append({
            "name": cube["name"],
            "title": cube["title"],
            "description": cube.get("description", "")
        })
    return cubes

@mcp.tool()
async def get_cube_meta(cube_name: str):
    """Get detailed metadata for a specific cube, including measures and dimensions."""
    meta = await cube_request("GET", "/meta")
    for cube in meta.get("cubes", []):
        if cube["name"] == cube_name:
            return cube
    return {"error": f"Cube {cube_name} not found"}

@mcp.tool()
async def run_cube_query(query: dict):
    """
    Execute a query against the Cube semantic layer.
    Query format example:
    {
        "measures": ["hits.total_hits"],
        "dimensions": ["hits.event_time.day"],
        "timeDimensions": [{"dimension": "hits.event_time", "granularity": "day", "dateRange": "last 30 days"}]
    }
    """
    result = await cube_request("POST", "/load", {"query": query})
    return result

@mcp.tool()
async def explain_query(query: dict):
    """Get the underlying SQL for a given Cube query."""
    result = await cube_request("POST", "/sql", {"query": query})
    return result

# FastAPI setup for SSE
app = FastAPI()
sse = SseServerTransport("/messages")

@app.get("/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        # Note: FastMCP.run_sse is not standard, we use the underlying server
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options()
        )

@app.post("/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    import sys
    # If "sse" is passed as an argument, run the FastAPI server
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        logger.info("Starting SSE server on port 8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        # Default to stdio for Claude Desktop
        logger.info("Starting stdio server")
        mcp.run()
