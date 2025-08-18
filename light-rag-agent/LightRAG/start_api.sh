#!/bin/bash
set -euo pipefail

# LightRAG API Server Startup Script (optimized)

echo "🚀 Starting LightRAG API Server..."

REQ_FILE="requirements.txt"

# Create venv if missing
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "⬆️  Upgrading pip ..."
python -m pip install --upgrade pip

echo "📚 Installing dependencies from $REQ_FILE ..."
python -m pip install -r "$REQ_FILE"

# Ensure fastapi/uvicorn present even in custom cases
python - <<'EOF'
import importlib, sys
missing=[]
for m in ("fastapi","uvicorn"):
    try: importlib.import_module(m)
    except ImportError: missing.append(m)
if missing:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
EOF

# Validate .env
if [ ! -f ".env" ]; then
    echo "⚠️  .env not found (OPENAI_API_KEY). Create it: echo 'OPENAI_API_KEY=sk-...' > .env"
else
    if ! grep -q "OPENAI_API_KEY" .env; then
        echo "⚠️  OPENAI_API_KEY not set inside .env"
    fi
fi

# Ensure working docs dir exists (LightRAG default ./pydantic-docs or documents fallback)
if [ ! -d "pydantic-docs" ] && [ ! -d "documents" ]; then
    echo "📁 Creating default working directory pydantic-docs"
    mkdir -p pydantic-docs
fi

PORT="${PORT:-8000}"
RELOAD="${RELOAD:-0}"

# Check if port already in use
if lsof -iTCP:"$PORT" -sTCP:LISTEN -Pn >/dev/null 2>&1; then
    echo "⚠️  Port $PORT already in use. Existing process(es):"
    lsof -iTCP:"$PORT" -sTCP:LISTEN -Pn || true
    echo "🔁 Attempting graceful kill (uvicorn/api_server)..."
    pkill -f "uvicorn api_server:app" || true
    sleep 1
    if lsof -iTCP:"$PORT" -sTCP:LISTEN -Pn >/dev/null 2>&1; then
        echo "❌ Port $PORT still occupied. Abort or set PORT env var to another port."
        exit 1
    fi
fi

echo "🌐 Starting API server on http://localhost:$PORT"
echo "📖 Docs:    http://localhost:$PORT/docs"
echo "🔍 Health:  http://localhost:$PORT/health"
echo "💡 Env RELOAD=1 для авто-перезапуска | PORT=XXXX для смены порта"
echo "Ctrl+C to stop"

UVICORN_CMD=(uvicorn api_server:app --host 0.0.0.0 --port "$PORT" --log-level info)
if [[ "$RELOAD" == "1" ]]; then
    UVICORN_CMD+=(--reload)
fi

exec "${UVICORN_CMD[@]}"