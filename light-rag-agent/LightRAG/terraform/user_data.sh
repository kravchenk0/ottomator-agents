#!/bin/bash

# User data script for LightRAG EC2 instance
# This script runs when the instance first boots

set -e

# Update system
yum update -y

# Install required packages
yum install -y docker git curl wget

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Add ec2-user to docker group

# Добавляем ec2-user в группу docker и применяем изменения
usermod -a -G docker ec2-user
newgrp docker <<EONG
echo "ec2-user теперь в группе docker"
EONG

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

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

# Убедимся что структура корректна и файл monkey_patch_lightrag.py лежит в корне (для import из app)
if [ ! -f /home/ec2-user/lightrag/monkey_patch_lightrag.py ]; then
  echo "[user_data][WARN] monkey_patch_lightrag.py не найден в корне, пытаемся перенести" >> /var/log/lightrag-user-data.log
  if [ -f /home/ec2-user/lightrag/app/monkey_patch_lightrag.py ]; then
    mv /home/ec2-user/lightrag/app/monkey_patch_lightrag.py /home/ec2-user/lightrag/
  fi
fi

# Создаём docker-compose (едиственный вариант, убираем дубли)
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
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_MODEL=${OPENAI_MODEL}
      - OPENAI_TEMPERATURE=${OPENAI_TEMPERATURE}
      - RAG_WORKING_DIR=${RAG_WORKING_DIR}
      - RAG_EMBEDDING_MODEL=${RAG_EMBEDDING_MODEL}
      - RAG_LLM_MODEL=${RAG_LLM_MODEL}
      - RAG_RERANK_ENABLED=${RAG_RERANK_ENABLED}
      - RAG_BATCH_SIZE=${RAG_BATCH_SIZE}
      - RAG_MAX_DOCS_FOR_RERANK=${RAG_MAX_DOCS_FOR_RERANK}
      - RAG_CHUNK_SIZE=${RAG_CHUNK_SIZE}
      - RAG_CHUNK_OVERLAP=${RAG_CHUNK_OVERLAP}
      - APP_DEBUG=${APP_DEBUG}
      - APP_LOG_LEVEL=${APP_LOG_LEVEL}
      - APP_MAX_CONVERSATION_HISTORY=${APP_MAX_CONVERSATION_HISTORY}
      - APP_ENABLE_STREAMING=${APP_ENABLE_STREAMING}
      - API_HOST=${API_HOST}
      - API_PORT=${API_PORT}
      - API_CORS_ORIGINS=${API_CORS_ORIGINS}
      - API_ENABLE_DOCS=${API_ENABLE_DOCS}
      - API_RATE_LIMIT=${API_RATE_LIMIT}
      - API_MAX_REQUEST_SIZE=${API_MAX_REQUEST_SIZE}
      - API_SECRET_KEY=${API_SECRET_KEY}
      - CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS}
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
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '1.0'

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

#############################
# Сборка образа и запуск
#############################
docker build -t lightrag-api:latest .
docker images | grep lightrag-api || echo "[user_data][ERROR] Образ не собран" >> /var/log/lightrag-user-data.log

docker compose -f docker-compose.prod.yml up -d || /usr/local/bin/docker-compose -f docker-compose.prod.yml up -d

# Ожидание health (до 60 сек)
echo "Ждём readiness API..." >> /var/log/lightrag-user-data.log
for i in {1..30}; do
  if curl -sf http://localhost:8000/health > /dev/null; then
    echo "API готов" >> /var/log/lightrag-user-data.log
    break
  fi
  sleep 2
done

# Создаём systemd unit после успешной первичной инициализации
cat > /etc/systemd/system/lightrag.service << 'EOF'
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
EOF

systemctl enable lightrag.service
systemctl start lightrag.service || echo "[user_data][WARN] systemd старт не критичен (контейнер уже запущен)" >> /var/log/lightrag-user-data.log





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

# Reboot to ensure all changes take effect
# reboot 