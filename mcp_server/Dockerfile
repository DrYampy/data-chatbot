FROM python:3.13-slim

WORKDIR /app

COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_server/ .

RUN chmod +x start.sh

CMD ["./start.sh"]
