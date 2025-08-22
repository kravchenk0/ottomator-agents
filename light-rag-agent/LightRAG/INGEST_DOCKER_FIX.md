# 🔧 Исправление: ingest_local.py отсутствует в Docker контейнере

## Проблема
```bash
docker exec -it lightrag-api python3 tools/ingest_local.py --directory /app/documents/raw_uploads
# python3: can't open file '/app/tools/ingest_local.py': [Errno 2] No such file or directory
```

## Причина
Директория `tools/` была исключена из Docker образа в `.dockerignore` и не копировалась в `Dockerfile`.

## Быстрое решение (для текущего контейнера)

Используйте готовый скрипт для копирования файла в работающий контейнер:

```bash
# Запустите скрипт копирования
./copy_ingest_to_container.sh
```

Или вручную:
```bash
# Создайте директорию tools в контейнере
docker exec lightrag-api mkdir -p /app/tools

# Скопируйте скрипт
docker cp tools/ingest_local.py lightrag-api:/app/tools/

# Установите права доступа
docker exec lightrag-api chmod +x /app/tools/ingest_local.py

# Проверьте что файл на месте
docker exec lightrag-api ls -la /app/tools/
```

После этого команда должна работать:
```bash
docker exec -it lightrag-api python3 tools/ingest_local.py --directory /app/documents/raw_uploads
```

## Постоянное решение (пересборка образа)

Для будущих развертываний исправлены:

### 1. Dockerfile
Добавлена строка копирования tools:
```dockerfile
# Copy application code (исключаем секреты и ненужные файлы)  
COPY app/ ./app/
COPY tools/ ./tools/    # <- Добавлено
COPY config.yaml ./
COPY start_api.sh ./
```

### 2. .dockerignore
Убрана строка исключения tools:
```dockerignore
# Tools и скрипты - ingest_local.py нужен в runtime для загрузки документов
# tools/ - commented out to include ingest_local.py
```

### 3. Пересборка образа
```bash
# Остановите текущий контейнер
docker-compose down

# Пересоберите образ
docker-compose build --no-cache lightrag-api

# Запустите с новым образом
docker-compose up -d

# Проверьте что tools доступны
docker exec lightrag-api ls -la /app/tools/
```

## Проверка работоспособности

После применения любого из решений:

```bash
# Создайте тестовую папку для загрузки
docker exec lightrag-api mkdir -p /app/documents/raw_uploads

# Скопируйте тестовый файл (с хоста)
echo "Тест загрузки документов" | docker exec -i lightrag-api tee /app/documents/raw_uploads/test.txt

# Запустите dry-run для проверки
docker exec -it lightrag-api python3 tools/ingest_local.py \
  --directory /app/documents/raw_uploads --dry-run

# Если все ОК, запустите реальную обработку
docker exec -it lightrag-api python3 tools/ingest_local.py \
  --directory /app/documents/raw_uploads
```

Ожидаемый результат:
```json
{
  "status": "ok",
  "directory": "/app/documents/raw_uploads",
  "working_dir": "/app/documents", 
  "processed_files": 1,
  "success_count": 1,
  "error_count": 0,
  "total_chunks": 1,
  "processing_time": "2.1s"
}
```

## Альтернативы

Если не хотите использовать ingest_local.py в контейнере, можете:

### 1. REST API загрузка (рекомендуется для небольших файлов)
```bash
# Получите JWT токен
curl -X POST https://api.businessindunes.ai/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-api-key"}'

# Загрузите файл через API
curl -X POST https://api.businessindunes.ai/documents/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf"
```

### 2. Монтирование тома (для постоянного доступа)
```yaml
# В docker-compose.yml
services:
  lightrag-api:
    volumes:
      - ./documents:/app/documents
      - ./tools:/app/tools  # Добавьте эту строку
```

Затем:
```bash
docker-compose down && docker-compose up -d
```

## Статус исправления

- ✅ Быстрое решение: готово (copy_ingest_to_container.sh)
- ✅ Dockerfile: исправлен 
- ✅ .dockerignore: исправлен
- 📋 Требуется: пересборка образа для постоянного решения

Используйте быстрое решение для немедленного доступа, затем пересоберите образ для постоянного исправления.