# LightRAG Agent: Интеллектуальный API-сервер для семантического поиска

## 🎯 О проекте

LightRAG Agent — это высокопроизводительный REST API сервер для семантического поиска и чат-взаимодействий с использованием технологии RAG (Retrieval-Augmented Generation). Проект построен на базе LightRAG с интеграцией Knowledge Graph для глубокого понимания контекста.

### Ключевые возможности

- **🚀 FastAPI сервер** с JWT-аутентификацией и мониторингом Prometheus
- **🤖 Pydantic AI агенты** с кешированием для высокой производительности  
- **🧠 LightRAG движок** с NanoVectorDB и автоматической обработкой документов
- **☁️ S3 интеграция** для хранения и управления документами
- **⚡ Оптимизация производительности** с многоуровневым кешированием и адаптивными таймаутами
- **🔄 Умное управление моделями** с автоматическим переключением между GPT-5-mini, GPT-4.1 и GPT-4o-mini

## 🛠️ Установка

### Требования
- Python 3.11+
- OpenAI API ключ
- Docker и Docker Compose (для контейнерного развертывания)
- AWS CLI (опционально, для S3 интеграции)

### Быстрый старт

1. **Клонируйте репозиторий**
   ```bash
   git clone <repository-url>
   cd light-rag-agent
   ```

2. **Настройте переменные окружения**
   ```bash
   cd LightRAG
   cp .env.example .env
   ```
   
   Отредактируйте `.env` файл:
   ```env
   # Core
   OPENAI_API_KEY=your_api_key
   RAG_API_KEYS=key1,key2,key3  # API ключи для доступа
   
   # AI Models
   OPENAI_MODEL=gpt-5-mini
   RAG_EMBEDDING_MODEL=text-embedding-3-large
   
   # Performance
   RAG_CACHE_TTL_SECONDS=300
   RAG_MAX_HISTORY_MESSAGES=12
   ```

3. **Установите зависимости**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # или
   .\venv\Scripts\activate  # Windows
   
   pip install -r requirements.txt
   ```

## 🚀 Запуск

### Вариант 1: Docker Compose (рекомендуется)

```bash
cd LightRAG
docker-compose up -d
```

Сервер будет доступен на `http://localhost:8000`

### Вариант 2: Локальный запуск

```bash
cd LightRAG
bash start_api.sh
```

### Вариант 3: Production с AWS

```bash
cd LightRAG/terraform
terraform init
terraform apply
```

Подробнее в [AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md)

## 📊 API Endpoints

### Основные эндпоинты

| Endpoint | Method | Описание | Аутентификация |
|----------|--------|----------|----------------|
| `/health` | GET | Проверка здоровья сервера | Нет |
| `/token` | POST | Получение JWT токена | API Key |
| `/chat` | POST | Чат с RAG агентом | JWT |
| `/documents/upload` | POST | Загрузка документов | JWT |
| `/documents/list` | GET | Список документов | JWT |
| `/rag/query` | POST | Прямой RAG запрос | JWT |
| `/rag/insert` | POST | Добавление текста в индекс | JWT |
| `/metrics` | GET | Prometheus метрики | Нет |

## 📁 Структура проекта

```
LightRAG/
├── app/                      # Основное приложение
│   ├── api/                 # API эндпоинты
│   │   └── server.py        # FastAPI сервер
│   ├── agent/               # AI агенты
│   │   └── rag_agent.py     # Pydantic AI агент с кешированием
│   ├── core/                # Ядро системы
│   │   ├── config.py        # Конфигурация
│   │   └── rag.py          # RAG менеджер
│   └── utils/               # Утилиты
│       ├── auth.py         # JWT аутентификация
│       ├── ingestion.py    # Обработка документов
│       └── s3_storage.py   # S3 интеграция
├── terraform/               # IaC для AWS
├── tests/                   # Юнит-тесты
├── docker-compose.yml       # Контейнеризация
└── requirements.txt         # Python зависимости
```

## 🔧 Примеры использования

### Получение токена
```bash
curl -X POST http://localhost:8000/token \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"user": "user@example.com"}'
```

### Чат запрос
```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Как работает LightRAG?",
    "conversation_id": "optional-conv-id",
    "mode": "hybrid"
  }'
```

### Загрузка документа

#### Через REST API
```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf"
```

#### Локальная загрузка на сервере (ingest_local.py)

Для массовой загрузки документов напрямую на EC2 инстансе используйте скрипт `tools/ingest_local.py`:

**На хост-системе:**
```bash
# Подключитесь к EC2 инстансу
ssh -i ~/.ssh/your-key.pem ubuntu@your-instance-ip

# Перейдите в директорию проекта
cd /app

# Загрузите файлы в папку для обработки
mkdir -p /app/documents/raw_uploads
# Скопируйте ваши файлы в /app/documents/raw_uploads/

# Запустите локальную обработку
python3 tools/ingest_local.py --directory /app/documents/raw_uploads
```

**Через Docker контейнер:**
```bash
# Скопируйте файлы в контейнер
docker cp ./my-documents/ lightrag-api:/app/documents/raw_uploads/

# Выполните обработку внутри контейнера
docker exec -it lightrag-api python3 tools/ingest_local.py \
  --directory /app/documents/raw_uploads
```

**Опции команды:**
```bash
# Проверка файлов без обработки (dry run)
python3 tools/ingest_local.py --directory /path/to/files --dry-run

# Указать рабочую директорию RAG
python3 tools/ingest_local.py \
  --directory /path/to/files \
  --working-dir /custom/rag/directory

# Обработка из переменной окружения RAG_INGEST_DIR
export RAG_INGEST_DIR=/app/documents/bulk_upload
python3 tools/ingest_local.py
```

**Поддерживаемые форматы файлов:**
- `.txt`, `.md` - Текстовые файлы
- `.pdf` - PDF документы
- `.docx` - Word документы
- `.json` - JSON данные

**Пример вывода:**
```json
{
  "status": "ok",
  "directory": "/app/documents/raw_uploads", 
  "working_dir": "/app/documents",
  "processed_files": 15,
  "success_count": 14,
  "error_count": 1,
  "total_chunks": 142,
  "processing_time": "2.3s"
}
```

**📖 Подробное руководство:** См. [docs/DOCUMENT_INGESTION_GUIDE.md](docs/DOCUMENT_INGESTION_GUIDE.md) для полной инструкции по загрузке документов.

## ⚙️ Конфигурация

### Режимы поиска RAG
- **naive**: Простой поиск по ключевым словам
- **local**: Локальный контекстный поиск
- **global**: Глобальный поиск по всей базе знаний
- **hybrid**: Комбинированный поиск (рекомендуется)
- **mix**: Адаптивный выбор стратегии

### Оптимизация производительности

```env
# Кеширование
RAG_CACHE_TTL_SECONDS=300           # TTL для кеша результатов
RAG_CHAT_CACHE_TTL_SECONDS=1800     # TTL для кеша чатов

# Таймауты
OPENAI_TIMEOUT_SECONDS=45           # Таймаут OpenAI API
RAG_AGENT_TIMEOUT_SECONDS=75        # Таймаут агента
RAG_RETRIEVE_TIMEOUT_SECONDS=45     # Таймаут поиска

# Лимиты
RAG_MAX_HISTORY_MESSAGES=12         # Макс. сообщений в истории
RAG_USER_RATE_LIMIT=10              # Лимит запросов на пользователя
```

## 📈 Мониторинг и метрики

### Prometheus метрики
- Количество запросов по эндпоинтам
- Время ответа (p50, p95, p99)
- Частота ошибок
- Использование кеша
- Активные сессии

### Логирование
- Структурированные JSON логи
- Request ID для трассировки
- Фазы выполнения запросов

## 🔒 Безопасность

- JWT токены с настраиваемым TTL
- API ключи для доступа к системе
- Rate limiting по пользователям
- CORS настройки для web-клиентов
- Шифрование S3 хранилища

## 🤝 Вклад в проект

Мы приветствуем вклад в развитие проекта! См. [CLAUDE.md](docs/CLAUDE.md) для руководства по разработке.

## 📚 Дополнительная документация

- [PLANNING.md](docs/PLANNING.md) - Архитектура и планирование
- [TASK.md](docs/TASK.md) - Текущие задачи и прогресс
- [DOCUMENT_INGESTION_GUIDE.md](docs/DOCUMENT_INGESTION_GUIDE.md) - Полное руководство по загрузке документов
- [S3_INTEGRATION.md](docs/S3_INTEGRATION.md) - Руководство по S3
- [AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md) - Развертывание на AWS
- [MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md) - Миграция с других RAG систем

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE) файл для деталей.
