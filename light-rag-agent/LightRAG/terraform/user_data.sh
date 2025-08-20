#!/bin/bash

# User data script for LightRAG EC2 instance
# This script runs when the instance first boots

set -e

#!/bin/bash
set -e
LF=/var/log/lightrag-user-data.log;echo "[stub] start"|tee -a "$LF"
# Экспорт env в один heredoc (минимум символов)
cat >/etc/profile.d/lightrag_env.sh <<E
export OPENAI_API_KEY='${OPENAI_API_KEY}' OPENAI_MODEL='${OPENAI_MODEL}' OPENAI_TEMPERATURE='${OPENAI_TEMPERATURE}' \
RAG_WORKING_DIR='${RAG_WORKING_DIR}' RAG_EMBEDDING_MODEL='${RAG_EMBEDDING_MODEL}' RAG_LLM_MODEL='${RAG_LLM_MODEL}' \
RAG_RERANK_ENABLED='${RAG_RERANK_ENABLED}' RAG_BATCH_SIZE='${RAG_BATCH_SIZE}' RAG_MAX_DOCS_FOR_RERANK='${RAG_MAX_DOCS_FOR_RERANK}' \
RAG_CHUNK_SIZE='${RAG_CHUNK_SIZE}' RAG_CHUNK_OVERLAP='${RAG_CHUNK_OVERLAP}' APP_DEBUG='${APP_DEBUG}' APP_LOG_LEVEL='${APP_LOG_LEVEL}' \
APP_MAX_CONVERSATION_HISTORY='${APP_MAX_CONVERSATION_HISTORY}' APP_ENABLE_STREAMING='${APP_ENABLE_STREAMING}' API_HOST='${API_HOST}' \
API_PORT='${API_PORT}' API_CORS_ORIGINS='${API_CORS_ORIGINS}' API_ENABLE_DOCS='${API_ENABLE_DOCS}' API_RATE_LIMIT='${API_RATE_LIMIT}' \
API_MAX_REQUEST_SIZE='${API_MAX_REQUEST_SIZE}' API_SECRET_KEY='${API_SECRET_KEY}' CORS_ALLOWED_ORIGINS='${CORS_ALLOWED_ORIGINS}' \
GITHUB_TOKEN='${GITHUB_TOKEN}' ALLOWED_INGRESS_CIDRS='${ALLOWED_INGRESS_CIDRS}'
E
. /etc/profile.d/lightrag_env.sh || true
yum install -y git curl >/dev/null 2>&1 || true

# ---- Fail2ban installation & configuration (SSH protection) ----
echo "[security] Installing fail2ban" | tee -a "$LF"
if ! command -v fail2ban-server >/dev/null 2>&1; then
  # Amazon Linux 2: enable EPEL for fail2ban
  amazon-linux-extras install epel -y >>$LF 2>&1 || yum install -y epel-release >>$LF 2>&1 || true
  yum install -y fail2ban >>$LF 2>&1 || echo "[security][WARN] fail2ban install failed" | tee -a "$LF"
fi

if command -v fail2ban-server >/dev/null 2>&1; then
  IGNORE_IPS="127.0.0.1/8 ::1"
  # Append allowed ingress CIDRs (if any) to ignoreip to prevent self-ban
  if [ -n "$ALLOWED_INGRESS_CIDRS" ]; then
    for ip in $ALLOWED_INGRESS_CIDRS; do
      IGNORE_IPS="$IGNORE_IPS $ip"
    done
  fi
  cat >/etc/fail2ban/jail.local <<EOF_F2B
[DEFAULT]
bantime = 15m
findtime = 10m
maxretry = 5
backend = systemd
ignoreip = $IGNORE_IPS

[sshd]
enabled = true
port = ssh
logpath = /var/log/secure
EOF_F2B
  systemctl enable fail2ban >>$LF 2>&1 || true
  systemctl restart fail2ban >>$LF 2>&1 || true
  echo "[security] fail2ban configured (ignore: $IGNORE_IPS)" | tee -a "$LF"
else
  echo "[security][WARN] fail2ban not installed; skipping configuration" | tee -a "$LF"
fi
cd /home/ec2-user || exit 1
[ -z "$GITHUB_TOKEN" ] && echo "[stub][ERR] no GITHUB_TOKEN"|tee -a "$LF" && exit 1
git clone https://$GITHUB_TOKEN@github.com/kravchenk0/ottomator-agents.git 2>>$LF || echo "[stub] clone skipped"|tee -a "$LF"
chown -R ec2-user:ec2-user ottomator-agents || true
bash /home/ec2-user/ottomator-agents/light-rag-agent/LightRAG/terraform/bootstrap.sh >>$LF 2>&1 &
echo "[stub] bootstrap pid=$!"|tee -a "$LF"
  if [ -S /var/run/docker.sock ]; then
    chgrp docker /var/run/docker.sock || true
    chmod 660 /var/run/docker.sock || true
    setfacl -m u:ec2-user:rw /var/run/docker.sock || true
    break
  fi
  sleep 1
done

echo "[user_data] docker socket perms:" $(ls -l /var/run/docker.sock 2>/dev/null || echo 'not-found') >> /var/log/lightrag-user-data.log

log "Install Docker Compose (CLI plugin)"
COMPOSE_URL_BASE="https://github.com/docker/compose/releases/download"
COMPOSE_VERSION="v2.27.0"
mkdir -p /usr/local/lib/docker/cli-plugins
if retry 3 5 "curl -fsSL $COMPOSE_URL_BASE/$COMPOSE_VERSION/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/lib/docker/cli-plugins/docker-compose"; then
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose || true
  log "Docker Compose plugin installed"
else
  fail "Compose binary install failed, fallback to pip"
  if command -v python3 >/dev/null 2>&1; then
    python3 -m ensurepip --upgrade || true
    retry 3 5 "python3 -m pip install --upgrade pip" || true
    if retry 2 5 "python3 -m pip install docker-compose"; then
      ln -sf $(command -v docker-compose) /usr/local/bin/docker-compose || true
      log "docker-compose (pip) installed"
    else
      fail "pip docker-compose install failed; продолжим попытку без compose"
    fi
  fi
fi
command -v docker-compose && docker-compose version || log "Compose not available yet"

# Create application directory
mkdir -p /home/ec2-user/lightrag
cd /home/ec2-user/lightrag

# Create necessary directories
mkdir -p documents logs config

# Create basic environment file
cat > .env << 'EOF'
# Production Environment Variables
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5-mini
OPENAI_TEMPERATURE=0.0

# RAG Configuration
RAG_WORKING_DIR=/app/documents
RAG_EMBEDDING_MODEL=gpt-5-mini
RAG_LLM_MODEL=gpt-5-mini
RAG_RERANK_ENABLED=true
RAG_BATCH_SIZE=20
RAG_MAX_DOCS_FOR_RERANK=20
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200

# App Configuration
APP_DEBUG=false
APP_LOG_LEVEL=INFO
APP_MAX_CONVERSATION_HISTORY=100
APP_ENABLE_STREAMING=true

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=*
API_ENABLE_DOCS=false
API_RATE_LIMIT=100
API_MAX_REQUEST_SIZE=10MB

# Security
API_SECRET_KEY=change_this_in_production
CORS_ALLOWED_ORIGINS=*
EOF



# Клонируем приватный репозиторий с использованием переменной окружения GITHUB_TOKEN
export GITHUB_TOKEN="${GITHUB_TOKEN}"
cd /home/ec2-user
if [ -z "$GITHUB_TOKEN" ]; then
  echo "GITHUB_TOKEN не задан! Остановлено." >&2
  exit 1
fi
git clone https://$GITHUB_TOKEN@github.com/kravchenk0/ottomator-agents.git

# Копируем исходники целиком (упрощаем логику) в рабочую директорию сборки
RSYNC_SRC="/home/ec2-user/ottomator-agents/light-rag-agent/LightRAG"
cp -r $RSYNC_SRC/* /home/ec2-user/lightrag/
cd /home/ec2-user/lightrag || { echo "[user_data][ERROR] cannot cd to workdir" >> /var/log/lightrag-user-data.log; exit 1; }
log "Содержимое рабочего каталога после копирования (top 30)"; ls -al | head -n 30 >> /var/log/lightrag-user-data.log 2>&1 || true

# Верифицируем наличие Dockerfile (иногда может не скопироваться из-за временных задержек FS)
if [ ! -f /home/ec2-user/lightrag/Dockerfile ]; then
  if [ -f "$RSYNC_SRC/Dockerfile" ]; then
    cp "$RSYNC_SRC/Dockerfile" /home/ec2-user/lightrag/
    log "Dockerfile восстановлен из исходников"
  else
    log "[WARN] Dockerfile отсутствует, создаём минимальный"
    cat > /home/ec2-user/lightrag/Dockerfile <<'MINIDOCK'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt . || true
RUN pip install --no-cache-dir --upgrade pip && \
    ( [ -f requirements.txt ] && pip install --no-cache-dir -r requirements.txt || true )
COPY . .
CMD ["python","-m","http.server","8000"]
MINIDOCK
  fi
fi

# Создаём requirements.txt если вдруг отсутствует (для мини-докерфайла)
if [ ! -f /home/ec2-user/lightrag/requirements.txt ]; then
  echo "fastapi\nuvicorn" > /home/ec2-user/lightrag/requirements.txt
fi

# Убедимся что структура корректна и файл monkey_patch_lightrag.py лежит в корне (для import из app)
if [ ! -f /home/ec2-user/lightrag/monkey_patch_lightrag.py ]; then
  echo "[user_data][WARN] monkey_patch_lightrag.py не найден в корне, пытаемся перенести" >> /var/log/lightrag-user-data.log
  if [ -f /home/ec2-user/lightrag/app/monkey_patch_lightrag.py ]; then
    mv /home/ec2-user/lightrag/app/monkey_patch_lightrag.py /home/ec2-user/lightrag/
  fi
fi

# Создаём docker-compose (актуальная версия с environment mapping)
cat > docker-compose.prod.yml << 'EOF'
version: '3.8'

services:
  lightrag-api:
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

# Логируем первые строки docker-compose для диагностики
head -n 60 docker-compose.prod.yml >> /var/log/lightrag-user-data.log 2>&1 || true

#############################
# Сборка образа и запуск
#############################
log "START build"
 if docker build -t lightrag-api:latest . >> /var/log/lightrag-user-data.log 2>&1; then
   echo "[user_data] build OK" >> /var/log/lightrag-user-data.log
 else
   echo "[user_data][ERROR] build failed" >> /var/log/lightrag-user-data.log
 fi
 
 if docker images | grep -q lightrag-api; then
   echo "[user_data] image present" >> /var/log/lightrag-user-data.log
 else
   echo "[user_data][ERROR] image missing after build" >> /var/log/lightrag-user-data.log
 fi
 
log "docker compose up"
if command -v docker compose >/dev/null 2>&1; then
  docker compose -f docker-compose.prod.yml up -d >> /var/log/lightrag-user-data.log 2>&1 || fail "docker compose (plugin) up failed"
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose -f docker-compose.prod.yml up -d >> /var/log/lightrag-user-data.log 2>&1 || fail "docker-compose (standalone) up failed"
else
  fail "Compose not installed; skipping container start"
fi
 
log "containers after up:"; docker ps -a >> /var/log/lightrag-user-data.log 2>&1 || true

# Ожидание health (до 60 сек)
echo "Ждём readiness API..." >> /var/log/lightrag-user-data.log
for i in {1..30}; do
  if curl -sf http://localhost:8000/health > /dev/null; then
    environment:
      OPENAI_API_KEY: $OPENAI_API_KEY
      OPENAI_MODEL: $OPENAI_MODEL
      OPENAI_TEMPERATURE: $OPENAI_TEMPERATURE
      RAG_WORKING_DIR: $RAG_WORKING_DIR
      RAG_EMBEDDING_MODEL: $RAG_EMBEDDING_MODEL
      RAG_LLM_MODEL: $RAG_LLM_MODEL
      RAG_RERANK_ENABLED: $RAG_RERANK_ENABLED
      RAG_BATCH_SIZE: $RAG_BATCH_SIZE
      RAG_MAX_DOCS_FOR_RERANK: $RAG_MAX_DOCS_FOR_RERANK
      RAG_CHUNK_SIZE: $RAG_CHUNK_SIZE
      RAG_CHUNK_OVERLAP: $RAG_CHUNK_OVERLAP
      APP_DEBUG: $APP_DEBUG
      APP_LOG_LEVEL: $APP_LOG_LEVEL
      APP_MAX_CONVERSATION_HISTORY: $APP_MAX_CONVERSATION_HISTORY
      APP_ENABLE_STREAMING: $APP_ENABLE_STREAMING
      API_HOST: $API_HOST
      API_PORT: $API_PORT
      API_CORS_ORIGINS: $API_CORS_ORIGINS
      API_ENABLE_DOCS: $API_ENABLE_DOCS
      API_RATE_LIMIT: $API_RATE_LIMIT
      API_MAX_REQUEST_SIZE: $API_MAX_REQUEST_SIZE
      API_SECRET_KEY: $API_SECRET_KEY
      CORS_ALLOWED_ORIGINS: $CORS_ALLOWED_ORIGINS
EOF

systemctl enable lightrag.service
systemctl start lightrag.service || echo "[user_data][WARN] systemd старт не критичен (контейнер уже запущен)" >> /var/log/lightrag-user-data.log
 
log "final docker ps:"; docker ps -a >> /var/log/lightrag-user-data.log 2>&1 || true





docker build -t lightrag-api:latest .
/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d

# Set proper permissions
chown -R ec2-user:ec2-user /home/ec2-user/lightrag

# Create a simple health check script
cat > /home/ec2-user/health_check.sh << 'EOF'
#!/bin/bash
# Simple health check script

if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "LightRAG API is healthy"
    exit 0
else
    echo "LightRAG API is not responding"
    exit 1
fi
EOF

chmod +x /home/ec2-user/health_check.sh

# Create a startup log
echo "LightRAG instance setup completed at $(date)" > /home/ec2-user/setup.log

log "START build (pwd=$(pwd))"
if [ ! -f Dockerfile ]; then
  log "[WARN] Dockerfile не найден перед сборкой, вывод ls:"; ls -al >> /var/log/lightrag-user-data.log 2>&1 || true
fi
if docker build -t lightrag-api:latest . >> /var/log/lightrag-user-data.log 2>&1; then
  echo "[user_data] build OK" >> /var/log/lightrag-user-data.log
else
  echo "[user_data][ERROR] build failed" >> /var/log/lightrag-user-data.log
  find . -maxdepth 3 -type f -name 'Dockerfile' >> /var/log/lightrag-user-data.log 2>&1 || true
fi

if docker images | grep -q lightrag-api; then
  echo "[user_data] image present" >> /var/log/lightrag-user-data.log
else
  echo "[user_data][ERROR] image missing after build" >> /var/log/lightrag-user-data.log
fi