# 📚 Руководство по загрузке документов в LightRAG

## Обзор

LightRAG поддерживает два способа загрузки документов:
1. **REST API** - для разовой загрузки через веб-интерфейс
2. **Локальная обработка** - для массовой загрузки на сервере

## 🌐 Метод 1: REST API загрузка

### Получение JWT токена
```bash
curl -X POST http://your-api-domain/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-api-key"}'
```

### Загрузка документа
```bash
curl -X POST http://your-api-domain/documents/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf"
```

### Проверка загруженных документов
```bash
curl -X GET http://your-api-domain/documents/list \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 💻 Метод 2: Локальная обработка (ingest_local.py)

### Преимущества локальной обработки
- ✅ Быстрая массовая загрузка
- ✅ Обход ограничений REST API
- ✅ Работа с большими файлами
- ✅ Пакетная обработка папок

### Подготовка к использованию

#### На EC2 инстансе
```bash
# 1. Подключение к серверу
ssh -i ~/.ssh/your-key.pem ubuntu@your-instance-ip

# 2. Проверка наличия LightRAG
cd /app
ls -la tools/ingest_local.py

# 3. Проверка переменных окружения
echo $OPENAI_API_KEY  # Должен быть установлен
echo $RAG_WORKING_DIR # По умолчанию /app/documents
```

#### В Docker контейнере
```bash
# Проверка статуса контейнера
docker ps | grep lightrag

# Вход в контейнер
docker exec -it lightrag-api bash

# Проверка окружения
env | grep -E "(OPENAI_API_KEY|RAG_)"
```

### Базовое использование

#### Простая загрузка
```bash
# Создайте папку для файлов
mkdir -p /app/documents/raw_uploads

# Поместите файлы в папку (через scp, rsync, или cp)
# Например:
scp -i ~/.ssh/your-key.pem ./my-files/*.pdf ubuntu@your-ip:/app/documents/raw_uploads/

# Запустите обработку
python3 tools/ingest_local.py --directory /app/documents/raw_uploads
```

#### Проверка без обработки (dry-run)
```bash
python3 tools/ingest_local.py --directory /app/documents/raw_uploads --dry-run
```

**Пример вывода dry-run:**
```json
{
  "status": "dry_run",
  "directory": "/app/documents/raw_uploads",
  "working_dir": "/app/documents", 
  "files": 12,
  "note": "no changes applied"
}
```

### Продвинутое использование

#### Пользовательская рабочая директория
```bash
# Создайте кастомную директорию для RAG
mkdir -p /custom/rag/workspace

# Обработка с указанием рабочей директории
python3 tools/ingest_local.py \
  --directory /path/to/source/files \
  --working-dir /custom/rag/workspace
```

#### Использование переменных окружения
```bash
# Настройка через переменные окружения
export RAG_WORKING_DIR=/app/documents
export RAG_INGEST_DIR=/app/documents/bulk_upload

# Создание директории и копирование файлов
mkdir -p $RAG_INGEST_DIR
cp /path/to/files/* $RAG_INGEST_DIR/

# Запуск без параметров (использует переменные окружения)
python3 tools/ingest_local.py
```

#### Обработка через Docker
```bash
# Метод 1: Копирование файлов в контейнер
docker cp ./my-documents/ lightrag-api:/app/documents/raw_uploads/
docker exec lightrag-api python3 tools/ingest_local.py \
  --directory /app/documents/raw_uploads

# Метод 2: Монтирование тома
docker run -v /host/path/to/docs:/app/input \
  lightrag-api python3 tools/ingest_local.py --directory /app/input
```

### Поддерживаемые форматы

| Формат | Расширения | Примечания |
|--------|------------|------------|
| Текст | `.txt`, `.md` | Обычные текстовые файлы |
| PDF | `.pdf` | Автоматическое извлечение текста |
| Word | `.docx` | Microsoft Word документы |
| JSON | `.json` | Структурированные данные |

### Результаты обработки

#### Успешная обработка
```json
{
  "status": "ok",
  "directory": "/app/documents/raw_uploads",
  "working_dir": "/app/documents",
  "processed_files": 25,
  "success_count": 24,
  "error_count": 1,
  "total_chunks": 340,
  "processing_time": "45.2s",
  "errors": [
    {
      "file": "corrupted.pdf",
      "error": "Unable to extract text"
    }
  ]
}
```

#### Ошибки конфигурации
```json
{
  "status": "error",
  "error": "OPENAI_API_KEY is not set in environment",
  "hint": "export OPENAI_API_KEY=... inside container or host env"
}
```

```json
{
  "status": "error", 
  "error": "scan directory not found: /wrong/path",
  "working_dir": "/app/documents"
}
```

### Оптимизация производительности

#### Переменные окружения для ускорения
```bash
# Увеличение параллелизма (в .env файле или export)
export RAG_BATCH_SIZE=50              # Размер пакета для обработки
export RAG_CHUNK_SIZE=1200           # Размер чанков
export RAG_CHUNK_OVERLAP=300         # Перекрытие чанков
export OPENAI_TIMEOUT_SECONDS=90     # Таймаут для embeddings
```

#### Мониторинг процесса
```bash
# Запуск с выводом в файл для анализа
python3 tools/ingest_local.py \
  --directory /app/documents/raw_uploads 2>&1 | tee ingestion.log

# Проверка статуса в реальном времени
tail -f ingestion.log
```

## 🔧 Устранение проблем

### Частые проблемы

#### 1. Отсутствует OPENAI_API_KEY
```bash
# Проверка
echo $OPENAI_API_KEY

# Установка (временно)
export OPENAI_API_KEY=sk-your-key-here

# Установка в Docker
docker exec -e OPENAI_API_KEY=sk-your-key-here lightrag-api \
  python3 tools/ingest_local.py --directory /app/documents/raw_uploads
```

#### 2. Папка не найдена
```bash
# Создание нужных папок
mkdir -p /app/documents/raw_uploads
chmod 755 /app/documents/raw_uploads

# Проверка прав доступа
ls -la /app/documents/
```

#### 3. Проблемы с инициализацией RAG
```bash
# Проверка состояния рабочей директории
ls -la /app/documents/

# Очистка и пересоздание (ОСТОРОЖНО!)
rm -rf /app/documents/*
mkdir -p /app/documents/raw_uploads
```

#### 4. Ошибки обработки файлов
```bash
# Проверка типа файлов
file /app/documents/raw_uploads/*

# Удаление проблемных файлов
rm /app/documents/raw_uploads/problem-file.ext

# Повторная обработка
python3 tools/ingest_local.py --directory /app/documents/raw_uploads
```

### Логи и отладка

#### Включение подробных логов
```bash
# Установка уровня логирования
export LOG_LEVEL=DEBUG

# Запуск с детальными логами
python3 tools/ingest_local.py \
  --directory /app/documents/raw_uploads \
  --dry-run  # Сначала проверьте dry-run
```

#### Анализ результатов обработки
```bash
# После обработки проверьте содержимое рабочей директории
ls -la /app/documents/

# Файлы векторной базы
ls -la /app/documents/vdb_*.json

# Файлы графа знаний
ls -la /app/documents/graph_*.json
```

## 📊 Мониторинг и оптимизация

### Рекомендации по производительности

1. **Размер файлов**: Оптимально до 10MB на файл
2. **Количество файлов**: До 100 файлов за раз для стабильности
3. **Формат документов**: PDF и DOCX требуют больше времени на обработку
4. **Ресурсы сервера**: Убедитесь в достаточном объеме RAM (минимум 4GB)

### Мониторинг процесса
```bash
# Мониторинг использования ресурсов во время обработки
top -p $(pgrep -f ingest_local)

# Проверка размера векторной базы
du -sh /app/documents/vdb_*.json

# Количество обработанных документов
jq '.total_chunks' < ingestion_result.json
```

## 🚀 Автоматизация

### Bash скрипт для регулярной загрузки
```bash
#!/bin/bash
# auto_ingest.sh

set -euo pipefail

UPLOAD_DIR="/app/documents/raw_uploads"
ARCHIVE_DIR="/app/documents/processed" 
LOG_FILE="/app/logs/ingestion.log"

echo "$(date): Starting automatic ingestion" >> $LOG_FILE

# Проверка наличия новых файлов
if [ "$(ls -A $UPLOAD_DIR)" ]; then
    echo "$(date): Found files to process" >> $LOG_FILE
    
    # Обработка файлов
    python3 /app/tools/ingest_local.py \
        --directory $UPLOAD_DIR >> $LOG_FILE 2>&1
    
    # Архивирование обработанных файлов
    mkdir -p $ARCHIVE_DIR/$(date +%Y-%m-%d)
    mv $UPLOAD_DIR/* $ARCHIVE_DIR/$(date +%Y-%m-%d)/
    
    echo "$(date): Ingestion completed successfully" >> $LOG_FILE
else
    echo "$(date): No files to process" >> $LOG_FILE
fi
```

### Настройка cron для автоматической обработки
```bash
# Добавление в crontab
crontab -e

# Запуск каждый час
0 * * * * /app/scripts/auto_ingest.sh

# Запуск каждые 15 минут  
*/15 * * * * /app/scripts/auto_ingest.sh
```

## 📋 Контрольный список

Перед использованием ingest_local.py убедитесь:

- [ ] OPENAI_API_KEY установлен и валиден
- [ ] Директория с файлами существует и доступна
- [ ] Рабочая директория RAG (/app/documents) имеет права записи
- [ ] Файлы имеют поддерживаемые форматы
- [ ] Достаточно свободного места на диске
- [ ] LightRAG API сервер не запущен (для избежания конфликтов)

После обработки проверьте:

- [ ] Файлы векторной базы созданы (vdb_*.json)
- [ ] Нет ошибок в выводе JSON
- [ ] Количество обработанных файлов соответствует ожидаемому
- [ ] API возвращает релевантные результаты для тестовых запросов

Успешной загрузки документов! 🎉