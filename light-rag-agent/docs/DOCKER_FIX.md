# 🐳 Исправление проблем с Docker

## 🚨 Исправленные проблемы

### 1. **Неправильный CMD в Dockerfile**
**Было:**
```dockerfile
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**Стало:**
```dockerfile
CMD ["uvicorn", "app.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop", "--access-log"]
```

### 2. **Неправильный путь в start_api.sh**
**Было:**
```bash
UVICORN_CMD=(uvicorn api_server:app --host 0.0.0.0 --port "$PORT" --log-level info)
```

**Стало:**
```bash
UVICORN_CMD=(uvicorn app.api.server:app --host 0.0.0.0 --port "$PORT" --log-level info)
```

### 3. **Оптимизированная структура копирования**
**Было:** `COPY . .` (копирует всё включая ненужные файлы)

**Стало:**
```dockerfile
COPY app/ ./app/
COPY config.yaml ./
COPY start_api.sh ./
```

### 4. **Добавлен .dockerignore**
Исключает ненужные файлы из Docker контекста:
- `.env` файлы (секреты)
- Документацию
- Terraform файлы  
- Временные файлы
- IDE настройки

## 🚀 Тестирование исправлений

### Вариант 1: Docker Compose (рекомендуется)
```bash
cd LightRAG

# Убедитесь что .env настроен
cp .env.optimized .env
# Отредактируйте OPENAI_API_KEY в .env

# Пересоберите и запустите
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Проверьте логи
docker-compose logs -f lightrag-api
```

### Вариант 2: Docker Build напрямую
```bash
cd LightRAG

# Соберите образ
docker build -t lightrag-api .

# Запустите контейнер
docker run -d --name lightrag-api \
  -p 8000:8000 \
  --env-file .env \
  lightrag-api

# Проверьте логи
docker logs -f lightrag-api
```

### Вариант 3: Локальный запуск (для отладки)
```bash
cd LightRAG

# Запустите локально для отладки
bash start_api.sh

# В другом терминале протестируйте
curl -v http://localhost:8000/health
```

## 📋 Проверочный чеклист

После запуска контейнера проверьте:

### 1. **Контейнер запущен:**
```bash
docker ps | grep lightrag-api
```
Должен показать RUNNING статус

### 2. **Логи без ошибок:**
```bash
docker logs lightrag-api
```
Должны видеть:
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 3. **Health check работает:**
```bash
curl -v http://localhost:8000/health
```
Должен вернуть:
```json
{
  "status": "ok",
  "rag_status": "healthy",
  "version": "..."
}
```

### 4. **API endpoints доступны:**
```bash
# Проверить docs
curl http://localhost:8000/docs

# Проверить chat (если есть тестовые данные)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
```

## 🚨 Troubleshooting

### Проблема: "ModuleNotFoundError: No module named 'app'"
**Решение:** Убедитесь что в Dockerfile используется правильный `PYTHONPATH=/app`

### Проблема: "failed to read dockerfile"
**Решение:** Запускайте `docker build` из директории `LightRAG`, где находится Dockerfile

### Проблема: Контейнер сразу завершается
```bash
# Проверьте логи для диагностики
docker logs lightrag-api

# Запустите в интерактивном режиме для отладки
docker run -it --rm --env-file .env lightrag-api /bin/bash
```

### Проблема: Порт 8000 недоступен
```bash
# Проверьте что порт проброшен
docker port lightrag-api

# Проверьте что процесс слушает внутри контейнера
docker exec lightrag-api netstat -tlnp | grep 8000
```

### Проблема: "OPENAI_API_KEY not found"
```bash
# Убедитесь что .env файл содержит ключ
grep OPENAI_API_KEY .env

# Проверьте переменные окружения в контейнере
docker exec lightrag-api printenv | grep OPENAI
```

## ⚡ Оптимизации в новом Dockerfile

1. **uvloop**: Быстрая асинхронная библиотека для Python
2. **--access-log**: Включено логирование запросов
3. **Селективное копирование**: Только нужные файлы
4. **Улучшенный health check**: Увеличен start-period до 10s
5. **Исключение секретов**: .env файлы не копируются в образ

## 🔄 Workflow для обновления

После изменений в коде:

```bash
# 1. Остановить и удалить старый контейнер
docker-compose down

# 2. Пересобрать без кеша
docker-compose build --no-cache lightrag-api

# 3. Запустить обновлённый
docker-compose up -d

# 4. Проверить здоровье
curl http://localhost:8000/health
```

## 📖 Связанные документы

- [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) - Оптимизации приложения
- [TERRAFORM_SECURITY_FIX.md](TERRAFORM_SECURITY_FIX.md) - Исправления Security Group
- В корне: `docker-compose.yml` - Конфигурация контейнеров