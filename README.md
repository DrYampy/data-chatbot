# Data Chatbot PoC (ClickHouse + Cube + MCP)

This Proof of Concept (PoC) sets up a complete AI-driven analytics stack:
- **ClickHouse**: High-performance OLAP database containing the Metrica web analytics dataset.
- **Cube Core**: Semantic layer to define measures (Bounce Rate, Visits, etc.) and dimensions.
- **FastMCP Server**: Python-based MCP server that allows AI models (Claude, ChatGPT) to query the data via Cube's semantic model.

## Quick Start

### 1. Start the Stack
Ensure you have Docker and Docker Compose installed.

```bash
docker compose up -d
```

This will start:
- ClickHouse (Port 8123, 9000)
- Cube Core (Port 4000)
- MCP Server (Port 8000)

### 2. Seeding Data (Ad-hoc)
Data ingestion is **not** automatic on startup. You must trigger it manually using one of the following methods:

#### Method A: Via MCP Tool (Recommended)
Once your LLM (Claude/ChatGPT) is connected to the MCP server, simply ask it to:
> "Seed the data" or "Run the seed_data tool"

#### Method B: Via Docker Command
```bash
docker exec -it mcp-server python ingest_data.py
```

This process is **idempotent**—it will only download and load data if the tables are empty. The Metrica dataset is ~800MB compressed, so it may take a few minutes depending on your internet speed.

### 3. Using with Claude Desktop (Stdio)
To use this with Claude Desktop locally, you can use the `docker exec` command to run the server in stdio mode.

Add this to your Claude Desktop configuration (usually `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "cube-analytics": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "mcp-server",
        "python",
        "server.py"
      ]
    }
  }
}
```

### 4. Using with ChatGPT (SSE via ngrok)
ChatGPT requires an SSE endpoint accessible over the internet.

#### Expose with ngrok
```bash
ngrok http 8000
```

#### Configure ChatGPT
1. Use the [MCP Connector](https://github.com/modelcontextprotocol/chatgpt-connector) or a similar ChatGPT Action that supports MCP.
2. Provide the ngrok URL: `https://<your-ngrok-id>.ngrok-free.app/sse`

## Semantic Model
The following measures are defined in `cube/model/cubes/`:
- **Hits**: Total Hits, Unique Users.
- **Visits**: Total Visits, Bounce Rate, Avg Session Duration, Page Views per Visit, Goal Conversion Rate.

Dimensions include: Event Time, Traffic Source, OS, Browser, Device, Region.

## Project Structure
- `cube/model/`: Cube YAML semantic definitions.
- `mcp_server/`: Python MCP server and ingestion scripts.
- `docker-compose.yml`: Full stack definition.
- `.env`: Contains the `CUBEJS_API_SECRET` used for JWT authentication.

## Tools Provided to LLM
- `list_cubes`: Shows available data models.
- `get_cube_meta`: Explains measures and dimensions for a cube.
- `run_cube_query`: Executes an analytics query.
- `explain_query`: Shows the generated SQL for transparency.
- `seed_data`: Triggers the idempotent ingestion of the Metrica dataset.
