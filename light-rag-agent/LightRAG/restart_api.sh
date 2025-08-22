#!/bin/bash
set -euo pipefail

echo "🔄 Restarting LightRAG API with updated timeout configuration..."

# Kill any existing uvicorn processes
echo "🛑 Stopping existing API server..."
pkill -f "uvicorn.*app.api.server" || echo "No existing server found"

# Wait a moment for graceful shutdown
sleep 2

# Check if port is still occupied
if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "⚠️  Port 8000 still occupied, force killing..."
    lsof -iTCP:8000 -sTCP:LISTEN | awk 'NR>1 {print $2}' | xargs kill -9 || true
    sleep 1
fi

echo "🚀 Starting API server with new timeout settings..."
echo "📊 New timeouts:"
echo "   - OpenAI: 60 seconds"
echo "   - RAG Agent: 90 seconds" 
echo "   - Query-based: 30-90 seconds"

# Start the server in background
nohup bash start_api.sh > server.log 2>&1 &
SERVER_PID=$!

echo "🌐 Server starting (PID: $SERVER_PID)..."
echo "📋 Logs: tail -f server.log"

# Wait a bit for server to start
sleep 5

# Check if server is responding
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Server is responding on http://localhost:8000"
    echo "🔍 Health endpoint: http://localhost:8000/health"
    echo "📖 API docs: http://localhost:8000/docs"
else
    echo "❌ Server may not be ready yet, check logs: tail -f server.log"
fi

echo "🎉 Restart complete!"