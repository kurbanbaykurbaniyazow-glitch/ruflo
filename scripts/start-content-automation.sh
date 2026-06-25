#!/usr/bin/env bash
# Start the autonomous content automation system
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LANGGRAPH_DIR="$ROOT_DIR/src/content-automation/langgraph"

# Load .env if exists
if [ -f "$ROOT_DIR/.env" ]; then
  export $(grep -v '^#' "$ROOT_DIR/.env" | xargs)
fi

VIDEO_OUTPUT_DIR="${VIDEO_OUTPUT_DIR:-/tmp/content-automation}"
mkdir -p "$VIDEO_OUTPUT_DIR"

echo "=== Content Automation System ==="
echo "Video output: $VIDEO_OUTPUT_DIR"
echo ""

# Step 1: Start LangGraph Python service
echo "[1/2] Starting LangGraph video pipeline server..."
cd "$LANGGRAPH_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating Python virtualenv..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt --quiet
fi

export VIDEO_OUTPUT_DIR
.venv/bin/python api/server.py &
PYTHON_PID=$!
echo "LangGraph server started (PID: $PYTHON_PID)"

# Wait for Python server to be ready
echo "Waiting for video pipeline to be ready..."
for i in {1..15}; do
  if curl -sf "http://localhost:${VIDEO_PIPELINE_PORT:-8001}/health" > /dev/null 2>&1; then
    echo "Video pipeline ready!"
    break
  fi
  sleep 1
done

# Step 2: Start Ruflo orchestrator
echo ""
echo "[2/2] Starting Ruflo content orchestrator..."
cd "$ROOT_DIR"
npx tsx src/content-automation/index.ts --daemon &
RUFLO_PID=$!
echo "Ruflo orchestrator started (PID: $RUFLO_PID)"

echo ""
echo "=== System Running ==="
echo "LangGraph API: http://localhost:${VIDEO_PIPELINE_PORT:-8001}"
echo "Press Ctrl+C to stop"

# Cleanup on exit
trap "kill $PYTHON_PID $RUFLO_PID 2>/dev/null; echo 'Stopped'" EXIT
wait
