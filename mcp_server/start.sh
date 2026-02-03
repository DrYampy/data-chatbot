#!/bin/bash
set -e

echo "Starting ingestion..."
python ingest_data.py || echo "Ingestion failed or already completed"

echo "Starting MCP server in SSE mode..."
python server.py sse
