#!/bin/bash
# LightRAG user_data (Terraform templatefile). Placeholders ${OPENAI_API_KEY} и др. заменяются Terraform.
set -euo pipefail
LOG=/var/log/lightrag-user-data.log
exec >>"$LOG" 2>&1
echo "===== user_data start $(date -u) ====="

# 1. Base deps
if command -v dnf >/dev/null 2>&1; then dnf install -y git curl docker >/dev/null 2>&1 || true; else yum install -y git curl docker >/dev/null 2>&1 || true; fi
systemctl enable docker || true
systemctl start docker || true

# 2. Docker compose plugin (avoid ${var} so Terraform doesn't expect key)
VER=v2.27.0
if ! docker compose version >/dev/null 2>&1; then
  echo "[compose] installing plugin $VER"
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL -o /usr/local/lib/docker/cli-plugins/docker-compose \
    "https://github.com/docker/compose/releases/download/$VER/docker-compose-linux-x86_64" && \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose || echo "[compose][WARN] install failed"
fi

# 3. Socket perms
if ! getent group docker >/dev/null 2>&1; then groupadd docker || true; fi
usermod -aG docker ec2-user || true
for i in $(seq 1 15); do
  if [ -S /var/run/docker.sock ]; then
    chgrp docker /var/run/docker.sock || true
    chmod 660 /var/run/docker.sock || true
    command -v setfacl >/dev/null 2>&1 && setfacl -m u:ec2-user:rw /var/run/docker.sock || true
    break
  fi
  sleep 1
done

# 4. Env export
cat >/etc/profile.d/lightrag_env.sh <<EOF
export OPENAI_API_KEY='${OPENAI_API_KEY}'
export OPENAI_MODEL='${OPENAI_MODEL}'
export OPENAI_TEMPERATURE='${OPENAI_TEMPERATURE}'
export RAG_WORKING_DIR='${RAG_WORKING_DIR}'
export RAG_EMBEDDING_MODEL='${RAG_EMBEDDING_MODEL}'
export RAG_LLM_MODEL='${RAG_LLM_MODEL}'
export RAG_RERANK_ENABLED='${RAG_RERANK_ENABLED}'
export RAG_BATCH_SIZE='${RAG_BATCH_SIZE}'
export RAG_MAX_DOCS_FOR_RERANK='${RAG_MAX_DOCS_FOR_RERANK}'
export RAG_CHUNK_SIZE='${RAG_CHUNK_SIZE}'
export RAG_CHUNK_OVERLAP='${RAG_CHUNK_OVERLAP}'
export APP_DEBUG='${APP_DEBUG}'
export APP_LOG_LEVEL='${APP_LOG_LEVEL}'
export APP_MAX_CONVERSATION_HISTORY='${APP_MAX_CONVERSATION_HISTORY}'
export APP_ENABLE_STREAMING='${APP_ENABLE_STREAMING}'
export API_HOST='${API_HOST}'
export API_PORT='${API_PORT}'
export API_CORS_ORIGINS='${API_CORS_ORIGINS}'
export API_ENABLE_DOCS='${API_ENABLE_DOCS}'
export API_RATE_LIMIT='${API_RATE_LIMIT}'
export API_MAX_REQUEST_SIZE='${API_MAX_REQUEST_SIZE}'
export API_SECRET_KEY='${API_SECRET_KEY}'
export CORS_ALLOWED_ORIGINS='${CORS_ALLOWED_ORIGINS}'
export RAG_JWT_SECRET='${RAG_JWT_SECRET}'
export RAG_JWT_EXPIRE_SECONDS='3600'
export RAG_REQUIRE_JWT='1'
export GITHUB_TOKEN='${GITHUB_TOKEN}'
EOF
. /etc/profile.d/lightrag_env.sh || true

# 5. Source code
cd /home/ec2-user
if [ -z "$GITHUB_TOKEN" ]; then echo "[FATAL] GITHUB_TOKEN missing"; exit 1; fi
git clone https://$GITHUB_TOKEN@github.com/kravchenk0/ottomator-agents.git repo || true
WORKDIR=/home/ec2-user/lightrag
mkdir -p "$WORKDIR"
cp -r repo/light-rag-agent/LightRAG/* "$WORKDIR"/ || true
cd "$WORKDIR"

# 6. Runtime .env
cat > .env <<EOF
OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_MODEL=${OPENAI_MODEL}
OPENAI_TEMPERATURE=${OPENAI_TEMPERATURE}
RAG_WORKING_DIR=${RAG_WORKING_DIR}
RAG_EMBEDDING_MODEL=${RAG_EMBEDDING_MODEL}
RAG_LLM_MODEL=${RAG_LLM_MODEL}
RAG_RERANK_ENABLED=${RAG_RERANK_ENABLED}
RAG_BATCH_SIZE=${RAG_BATCH_SIZE}
RAG_MAX_DOCS_FOR_RERANK=${RAG_MAX_DOCS_FOR_RERANK}
RAG_CHUNK_SIZE=${RAG_CHUNK_SIZE}
RAG_CHUNK_OVERLAP=${RAG_CHUNK_OVERLAP}
APP_DEBUG=${APP_DEBUG}
APP_LOG_LEVEL=${APP_LOG_LEVEL}
APP_MAX_CONVERSATION_HISTORY=${APP_MAX_CONVERSATION_HISTORY}
APP_ENABLE_STREAMING=${APP_ENABLE_STREAMING}
API_HOST=${API_HOST}
API_PORT=${API_PORT}
API_CORS_ORIGINS=${API_CORS_ORIGINS}
API_ENABLE_DOCS=${API_ENABLE_DOCS}
API_RATE_LIMIT=${API_RATE_LIMIT}
API_MAX_REQUEST_SIZE=${API_MAX_REQUEST_SIZE}
API_SECRET_KEY=${API_SECRET_KEY}
CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS}
RAG_JWT_SECRET=${RAG_JWT_SECRET}
RAG_JWT_EXPIRE_SECONDS=3600
RAG_REQUIRE_JWT=1
EOF

# 7. Compose file
cat > docker-compose.prod.yml <<EOF
version: '3.8'
services:
  api:
    build: .
    container_name: lightrag-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      RAG_JWT_SECRET: ${RAG_JWT_SECRET}
      RAG_REQUIRE_JWT: 1
    volumes:
      - ./documents:/app/documents
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 40s
EOF

# 8. Build & run
echo "[build] building image"
docker build -t lightrag-api:latest . || exit 1
if docker compose version >/dev/null 2>&1; then
  docker compose -f docker-compose.prod.yml up -d
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose -f docker-compose.prod.yml up -d
else
  echo "[ERROR] no docker compose"; exit 1
fi

# 9. Health wait
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null; then echo "API healthy (attempt $i)"; break; fi
  sleep 2
done

echo "===== user_data end $(date -u) ====="