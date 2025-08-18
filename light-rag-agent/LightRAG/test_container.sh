#!/usr/bin/env bash
set -euo pipefail

# Simple automated test for LightRAG container.
# Usage:
#   1) cp .env.example .env  (и пропиши настоящий OPENAI_API_KEY)
#   2) bash test_container.sh
# Optional env vars:
#   IMAGE=lightrag-api CONTAINER=lightrag-api-test PORT=8000 bash test_container.sh

IMAGE=${IMAGE:-lightrag-api}
CONTAINER=${CONTAINER:-lightrag-api-test}
PORT=${PORT:-8000}
ENV_FILE=${ENV_FILE:-.env}
REBUILD=${REBUILD:-0}

if [ ! -f "$ENV_FILE" ]; then
  echo "[ERROR] ENV file '$ENV_FILE' not found. Create it (см. .env.example)." >&2
  exit 1
fi

if ! grep -q '^OPENAI_API_KEY=' "$ENV_FILE"; then
  echo "[ERROR] OPENAI_API_KEY not set in $ENV_FILE" >&2
  exit 1
fi

if [ -z "$(grep '^OPENAI_API_KEY=' "$ENV_FILE" | cut -d= -f2-)" ]; then
  echo "[ERROR] OPENAI_API_KEY value is empty in $ENV_FILE" >&2
  exit 1
fi

# Build image if missing or forced
if [ "$REBUILD" = "1" ]; then
  echo "[INFO] Forced rebuild (REBUILD=1)."
  docker build -t "$IMAGE" .
else
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "[INFO] Building image $IMAGE (not found)..."
    docker build -t "$IMAGE" .
  else
    echo "[INFO] Image $IMAGE already exists (skip build). Set REBUILD=1 to force rebuild."
  fi
fi

# Ensure port free
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[INFO] Port $PORT busy; attempting to kill existing process (needs permissions).";
  lsof -tiTCP:"$PORT" | xargs -r kill || true
  sleep 1
fi

# Cleanup old container
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

echo "[INFO] Starting container $CONTAINER..."
docker run -d --name "$CONTAINER" --env-file "$ENV_FILE" -p "$PORT:8000" "$IMAGE" >/dev/null

echo "[INFO] Waiting for /health ..."
TRIES=40
SLEEP=1
READY=0
for i in $(seq 1 $TRIES); do
  if curl -s "http://localhost:$PORT/health" | grep -q '"status":"healthy"'; then
    READY=1
    break
  fi
  sleep $SLEEP
  if ! docker ps --format '{{.Names}}' | grep -q "^$CONTAINER$"; then
    echo "[ERROR] Container exited early. Logs:" >&2
    docker logs "$CONTAINER" || true
    exit 1
  fi
done

if [ "$READY" -ne 1 ]; then
  echo "[ERROR] Health endpoint not ready after $((TRIES*SLEEP))s" >&2
  docker logs "$CONTAINER" | tail -n 60
  exit 1
fi

echo "[PASS] Health endpoint is healthy"

CHAT_PAYLOAD='{"message":"Привет, что ты умеешь?","conversation_id":"test-chat-1"}'
echo "[INFO] Sending /chat request..."
CHAT_RESPONSE=$(curl -s -X POST "http://localhost:$PORT/chat" -H 'Content-Type: application/json' -d "$CHAT_PAYLOAD") || true

echo "[INFO] Raw /chat response: $CHAT_RESPONSE"
if echo "$CHAT_RESPONSE" | grep -q '"response"'; then
  echo "[PASS] Chat response contains 'response' field"
else
  echo "[WARN] Chat response does not contain expected field. Check logs." >&2
fi

echo "[INFO] Tail of container logs:"; docker logs "$CONTAINER" | tail -n 40

echo "[DONE] To stop: docker rm -f $CONTAINER"
