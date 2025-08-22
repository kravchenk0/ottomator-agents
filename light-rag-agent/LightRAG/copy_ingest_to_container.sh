#!/bin/bash
set -euo pipefail

echo "🔧 Copying ingest_local.py to running Docker container..."

# Check if container is running
if ! docker ps | grep -q lightrag-api; then
    echo "❌ Container 'lightrag-api' is not running"
    echo "Start it with: docker-compose up -d"
    exit 1
fi

# Create tools directory in container
echo "📁 Creating tools directory in container..."
docker exec lightrag-api mkdir -p /app/tools

# Copy the ingest script
echo "📋 Copying ingest_local.py script..."
docker cp tools/ingest_local.py lightrag-api:/app/tools/

# Set executable permissions
echo "🔐 Setting permissions..."
docker exec lightrag-api chmod +x /app/tools/ingest_local.py

# Verify the file is there
echo "✅ Verifying installation..."
if docker exec lightrag-api test -f /app/tools/ingest_local.py; then
    echo "🎉 ingest_local.py successfully installed in container!"
    echo ""
    echo "Now you can run:"
    echo "docker exec -it lightrag-api python3 tools/ingest_local.py --directory /app/documents/raw_uploads"
else
    echo "❌ Failed to copy ingest_local.py to container"
    exit 1
fi