#!/bin/bash
set -e
LOG_FILE=/var/log/lightrag-user-data.log
log(){ echo "[bootstrap] $1" | tee -a "$LOG_FILE"; }
fail(){ log "[ERROR] $1"; }
log "Bootstrap start"
[ -f /etc/profile.d/lightrag_env.sh ] && . /etc/profile.d/lightrag_env.sh || true
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
retry(){ local a=$1;shift; local d=$1;shift; local c="$@"; local n=1; while true; do eval "$c" && return 0 || { [ $n -lt $a ] && { log "retry $n/$a: $c"; n=$((n+1)); sleep $d; } || return 1; }; done; }

yum install -y docker git curl wget acl >/dev/null 2>&1 || yum install -y docker git curl wget acl
systemctl enable docker
systemctl start docker || true
if ! getent group docker >/dev/null 2>&1; then groupadd docker; fi
if ! id -nG ec2-user | grep -q '\bdocker\b'; then usermod -aG docker ec2-user; fi
mkdir -p /etc/docker
echo '{"group":"docker"}' > /etc/docker/daemon.json
systemctl restart docker || true
for i in {1..15}; do [ -S /var/run/docker.sock ] && { chgrp docker /var/run/docker.sock || true; chmod 660 /var/run/docker.sock || true; setfacl -m u:ec2-user:rw /var/run/docker.sock || true; break; }; sleep 1; done
log "docker socket perms: $(ls -l /var/run/docker.sock 2>/dev/null || echo missing)"
COMPOSE_VERSION=v2.27.0
mkdir -p /usr/local/lib/docker/cli-plugins
if retry 3 5 "curl -fsSL https://github.com/docker/compose/releases/download/$COMPOSE_VERSION/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/lib/docker/cli-plugins/docker-compose"; then
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose || true
  log "docker compose plugin ready"
else
  fail "compose plugin install failed"
fi
WORKDIR=/home/ec2-user/lightrag
mkdir -p "$WORKDIR" && cd "$WORKDIR"
if [ ! -d /home/ec2-user/ottomator-agents ]; then
  if [ -n "$GITHUB_TOKEN" ]; then
    su - ec2-user -c "git clone https://$GITHUB_TOKEN@github.com/kravchenk0/ottomator-agents.git" || fail "clone failed"
  else
    fail "GITHUB_TOKEN missing for clone"
  fi
fi
SRC=/home/ec2-user/ottomator-agents/light-rag-agent/LightRAG
cp -r $SRC/* "$WORKDIR" || fail "copy sources"
# Создаём скрипт обновления кода (git pull + rsync + rebuild)
cat > /usr/local/bin/lightrag-update.sh <<'UPD'
#!/bin/bash
set -e
LOG=/var/log/lightrag-update.log
echo "[update] start $(date)" | tee -a "$LOG"
REPO_DIR=/home/ec2-user/ottomator-agents
RUNTIME_DIR=/home/ec2-user/lightrag
if [ ! -d "$REPO_DIR/.git" ]; then
  echo "[update] repo missing at $REPO_DIR" | tee -a "$LOG"; exit 1
fi
cd "$REPO_DIR"
if [ -n "$GITHUB_TOKEN" ]; then
  CUR_URL=$(git remote get-url origin || echo '')
  if ! echo "$CUR_URL" | grep -q "$GITHUB_TOKEN"; then
    git remote set-url origin "https://$GITHUB_TOKEN@github.com/kravchenk0/ottomator-agents.git" || true
  fi
fi
git pull 2>&1 | tee -a "$LOG" || { echo "[update] git pull failed" | tee -a "$LOG"; exit 1; }
rsync -a --delete $REPO_DIR/light-rag-agent/LightRAG/ "$RUNTIME_DIR/" 2>&1 | tee -a "$LOG"
cd "$RUNTIME_DIR"
docker compose -f docker-compose.prod.yml build lightrag-api 2>&1 | tee -a "$LOG"
docker compose -f docker-compose.prod.yml up -d lightrag-api 2>&1 | tee -a "$LOG"
echo "[update] done $(date)" | tee -a "$LOG"
UPD
chmod +x /usr/local/bin/lightrag-update.sh || true
if [ ! -f Dockerfile ]; then
  if [ -f $SRC/Dockerfile ]; then cp $SRC/Dockerfile Dockerfile; else
    log "[WARN] Dockerfile missing, creating minimal"
    cat > Dockerfile <<'MINI'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt . || true
RUN pip install --no-cache-dir --upgrade pip && ( [ -f requirements.txt ] && pip install --no-cache-dir -r requirements.txt || true )
COPY . .
CMD ["python","-m","http.server","8000"]
MINI
  fi
fi
[ -f requirements.txt ] || echo -e "fastapi\nuvicorn" > requirements.txt
cat > .env <<EOF
OPENAI_API_KEY=$OPENAI_API_KEY
OPENAI_MODEL=$OPENAI_MODEL
OPENAI_TEMPERATURE=$OPENAI_TEMPERATURE
RAG_WORKING_DIR=$RAG_WORKING_DIR
RAG_EMBEDDING_MODEL=$RAG_EMBEDDING_MODEL
RAG_LLM_MODEL=$RAG_LLM_MODEL
RAG_RERANK_ENABLED=$RAG_RERANK_ENABLED
RAG_BATCH_SIZE=$RAG_BATCH_SIZE
RAG_MAX_DOCS_FOR_RERANK=$RAG_MAX_DOCS_FOR_RERANK
RAG_CHUNK_SIZE=$RAG_CHUNK_SIZE
RAG_CHUNK_OVERLAP=$RAG_CHUNK_OVERLAP
APP_DEBUG=$APP_DEBUG
APP_LOG_LEVEL=$APP_LOG_LEVEL
APP_MAX_CONVERSATION_HISTORY=$APP_MAX_CONVERSATION_HISTORY
APP_ENABLE_STREAMING=$APP_ENABLE_STREAMING
API_HOST=$API_HOST
API_PORT=$API_PORT
API_CORS_ORIGINS=$API_CORS_ORIGINS
API_ENABLE_DOCS=$API_ENABLE_DOCS
API_RATE_LIMIT=$API_RATE_LIMIT
API_MAX_REQUEST_SIZE=$API_MAX_REQUEST_SIZE
API_SECRET_KEY=$API_SECRET_KEY
CORS_ALLOWED_ORIGINS=$CORS_ALLOWED_ORIGINS
EOF
cat > docker-compose.prod.yml <<'EOF'
version: '3.8'
services:
  lightrag-api:
    build: .
    image: lightrag-api:latest
    container_name: lightrag-api-prod
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_MODEL: ${OPENAI_MODEL}
      OPENAI_TEMPERATURE: ${OPENAI_TEMPERATURE}
      RAG_WORKING_DIR: ${RAG_WORKING_DIR}
      RAG_EMBEDDING_MODEL: ${RAG_EMBEDDING_MODEL}
      RAG_LLM_MODEL: ${RAG_LLM_MODEL}
      RAG_RERANK_ENABLED: ${RAG_RERANK_ENABLED}
      RAG_BATCH_SIZE: ${RAG_BATCH_SIZE}
      RAG_MAX_DOCS_FOR_RERANK: ${RAG_MAX_DOCS_FOR_RERANK}
      RAG_CHUNK_SIZE: ${RAG_CHUNK_SIZE}
      RAG_CHUNK_OVERLAP: ${RAG_CHUNK_OVERLAP}
      APP_DEBUG: ${APP_DEBUG}
      APP_LOG_LEVEL: ${APP_LOG_LEVEL}
      APP_MAX_CONVERSATION_HISTORY: ${APP_MAX_CONVERSATION_HISTORY}
      APP_ENABLE_STREAMING: ${APP_ENABLE_STREAMING}
      API_HOST: ${API_HOST}
      API_PORT: ${API_PORT}
      API_CORS_ORIGINS: ${API_CORS_ORIGINS}
      API_ENABLE_DOCS: ${API_ENABLE_DOCS}
      API_RATE_LIMIT: ${API_RATE_LIMIT}
      API_MAX_REQUEST_SIZE: ${API_MAX_REQUEST_SIZE}
      API_SECRET_KEY: ${API_SECRET_KEY}
      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS}
      REDIS_HOST: redis
      REDIS_PORT: 6379
    volumes:
      - ./documents:/app/documents
      - ./logs:/app/logs
      - ./config:/app/config
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
  redis:
    image: redis:7-alpine
    container_name: lightrag-redis-prod
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
volumes:
  redis_data:
    driver: local
EOF
log "START build"
if docker build -t lightrag-api:latest . >> $LOG_FILE 2>&1; then log "build OK"; else fail "build failed"; fi
docker images | grep -q lightrag-api && log "image present" || fail "image missing"
log "docker compose up"
if command -v docker compose >/dev/null 2>&1; then
  docker compose -f docker-compose.prod.yml up -d >> $LOG_FILE 2>&1 || fail "compose up failed"
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose -f docker-compose.prod.yml up -d >> $LOG_FILE 2>&1 || fail "compose up failed"
else
  fail "compose not installed"
fi
log "containers:"; docker ps -a >> $LOG_FILE 2>&1 || true
log "wait health"
for i in {1..30}; do curl -sf http://localhost:8000/health && { log "API healthy"; break; }; sleep 2; done
cat > /etc/systemd/system/lightrag.service <<'UNIT'
[Unit]
Description=LightRAG API Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ec2-user/lightrag
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
User=ec2-user
Group=ec2-user

[Install]
WantedBy=multi-user.target
UNIT
systemctl enable lightrag.service || true
systemctl start lightrag.service || true
chown -R ec2-user:ec2-user "$WORKDIR"
log "Bootstrap finished"
