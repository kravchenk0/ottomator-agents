# LightRAG API Reference (v1.0.0)

Базовый URL (пример): `http://<host>:8000`

OpenAPI/Swagger UI: `/docs` • OpenAPI JSON: `/openapi.json`

## Аутентификация

Большинство эндпоинтов (кроме `/` и `/health`, `/auth/token`) требуют JWT Bearer токен в заголовке:

```
Authorization: Bearer <token>
```

Получить токен: `POST /auth/token` {"user": "alice", "role": "admin"}

## Эндпоинты

### `GET /`
Ping. Возвращает `{status, rag_initialized}`. Без авторизации.

### `GET /health`
Расширенный health-check. Без авторизации.

Ответ (пример сокращён):
```
{
  "status": "healthy",
  "rag_status": "healthy",
  "version": "1.0.0",
  "model_ok": true,
  "model_used": "gpt-5-mini",
  "temperature_current": "0.1"
}
```

### `POST /auth/token`
Получение JWT. Тело:
```
{ "user": "alice", "role": "admin" }
```
Ответ:
```
{ "access_token": "<jwt>", "token_type": "bearer", "role": "admin" }
```

### `POST /chat`
Задать вопрос / продолжить диалог.
Тело:
```
{
  "message": "What is RAG?",
  "conversation_id": "optional-id",
  "user_id": "u123",
  "system_prompt": "(override)",
  "model": "gpt-5-mini"
}
```
Ответ:
```
{
  "response": "...",
  "conversation_id": "conv_1234",
  "sources": [...],
  "metadata": {"model": "gpt-5-mini"}
}
```

Ошибки приходят с `error` внутри JSON (а не HTTP 500, где возможно).

### `POST /config`
Обновление конфигурации RAG. Тело (любые поля опциональны):
```
{ "working_dir": "/data/docs", "system_prompt": "You are helper", "rerank_enabled": true }
```

### `GET /config`
Текущие значения: `working_dir`, `system_prompt`, `rerank_enabled`.

### `POST /documents/insert`
Быстрая вставка текста напрямую. Query form (application/x-www-form-urlencoded) или JSON строка параметров в FastAPI допустима (реализация принимает аргументы). Поля:
- `content` (обяз.)
- `document_id` (опционально)

### `GET /documents/search`
Параметры query:
- `query` (строка, обязательна)
- `limit` (int, default=5)

Ответ содержит `results` (сырой вывод движка).

### `POST /documents/upload`
Multipart загрузка файла. Параметры:
- `file`: UploadFile
- `ingest` (bool, default=true)

Сохраняет файл в `working_dir/raw_uploads` и (если ingest=true) индексирует.

### `POST /documents/ingest/scan`
Сканирует директорию (параметр `directory` или `RAG_INGEST_DIR`) и индексирует новые/изменённые файлы.

### `GET /documents/ingest/list`
Возвращает список индексированных документов.

### `POST /documents/ingest/delete`
Удаляет набор файлов из индекса. Тело:
```
{"files": ["file1.txt", "file2.pdf"]}
```

### `POST /documents/ingest/clear`
Полностью очищает индекс.

## Коды ошибок
- 401: неправильный или отсутствующий JWT / API key.
- 503: RAG не инициализирован.
- 500: внутренняя ошибка (деталь в `detail`).
- Логические ошибки chat возвращаются в поле `error` внутри ChatResponse.

## Заголовки
- `Authorization: Bearer <jwt>` — для защищённых эндпоинтов.
- `X-API-Key: <key>` — если включена проверка API ключей (переменные окружения `RAG_API_KEY(S)`).

## Переменные окружения влияющие на поведение
- `OPENAI_API_KEY` — активация моделей.
- `RAG_INGEST_DIR`, `RAG_AUTO_INGEST_ON_START` — автоингест при старте.
- `ALLOW_START_WITHOUT_OPENAI_KEY`, `FAST_FAILLESS_INIT` — деградированный режим без ключа.
- `OPENAI_MODEL`, `RAG_LLM_MODEL`, `RAG_EMBEDDING_MODEL` — выбор моделей.

## Пример curl
```
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token -H 'Content-Type: application/json' -d '{"user":"alice"}' | jq -r .access_token)
curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hello"}' | jq
```

---
Обновляйте файл при добавлении новых эндпоинтов.
