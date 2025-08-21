#!/bin/bash

# User data script for LightRAG EC2 instance
# This script runs when the instance first boots

set -e

#!/bin/bash
set -e
LF=/var/log/lightrag-user-data.log;echo "[stub] start"|tee -a "$LF"
#!/bin/bash
set -euo pipefail
LOG=/var/log/lightrag-user-data.log
exec >>$LOG 2>&1
echo "===== user_data start $(date -u) ====="

if command -v dnf >/dev/null 2>&1; then dnf install -y git curl docker >/dev/null 2>&1 || true; else yum install -y git curl docker >/dev/null 2>&1 || true; fi
systemctl enable docker || true
systemctl start docker || true

# Install docker compose plugin if absent
install_compose() {
  local ver="v2.27.0"
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL -o /usr/local/lib/docker/cli-plugins/docker-compose \
    https://github.com/docker/compose/releases/download/${ver}/docker-compose-linux-x86_64 || return 1
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  echo "[compose] installed ${ver}";
}
if ! docker compose version >/dev/null 2>&1; then
  echo "[compose] plugin missing, installing..."
  install_compose || echo "[compose][WARN] install failed"
fi

# Docker socket permissions & group access for ec2-user
if ! getent group docker >/dev/null 2>&1; then
  groupadd docker || true
fi
usermod -aG docker ec2-user || true
# Wait for socket and fix perms so current and future sessions of ec2-user have access
for i in $(seq 1 15); do
  if [ -S /var/run/docker.sock ]; then
    chgrp docker /var/run/docker.sock || true
    chmod 660 /var/run/docker.sock || true
    # extra ACL (не критично, но гарантирует rw даже если группа сменится)
    command -v setfacl >/dev/null 2>&1 && setfacl -m u:ec2-user:rw /var/run/docker.sock || true
    echo "[docker-perms] adjusted at attempt $i"; break
  fi
  sleep 1
done
id ec2-user || true

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

cd /home/ec2-user
if [ -z "$GITHUB_TOKEN" ]; then echo "[FATAL] GITHUB_TOKEN missing"; exit 1; fi
git clone https://$GITHUB_TOKEN@github.com/kravchenk0/ottomator-agents.git repo || true
WORKDIR=/home/ec2-user/lightrag
mkdir -p "$WORKDIR"
cp -r repo/light-rag-agent/LightRAG/* "$WORKDIR"/ || true
cd "$WORKDIR"

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

echo "[build] building image"
docker build -t lightrag-api:latest . || exit 1
if docker compose version >/dev/null 2>&1; then
  docker compose -f docker-compose.prod.yml up -d
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose -f docker-compose.prod.yml up -d
else
  echo "[ERROR] docker compose not available"; exit 1
fi

echo "[health] waiting for API"
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null; then echo "API healthy (attempt $i)"; break; fi
  sleep 2
  [ $i -eq 30 ] && echo "[WARN] API not healthy after attempts" || true
done

echo "===== user_data end $(date -u) ====="
RAG_REQUIRE_JWT=1
EOF

# 5. docker-compose
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

# 6. Build & run
echo "Building image..."
docker build -t lightrag-api:latest . || exit 1
echo "Starting compose..."
docker compose -f docker-compose.prod.yml up -d || docker-compose -f docker-compose.prod.yml up -d

# 7. Wait health (max ~60s)
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null; then
    echo "API healthy in $i attempts"; break
  fi
  sleep 2
done

echo "===== user_data end $(date -u) ====="