# 🔍 Исправление проблемы поиска документов в /chat

## Проблема
API `/chat` не мог найти документы и возвращал ошибку:
```
"retrieve завершился ошибкой: «name 'query_length' is not defined»"
```

## Причины (две независимые проблемы)

### 1. **Ошибка в коде RAG agent (КРИТИЧЕСКАЯ)**
**Файл:** `app/agent/rag_agent.py`, строка 134  
**Проблема:** Использовалась неопределенная переменная `query_length`
```python
# БЫЛО (ошибка):
logger.info(f"[retrieve] query_len={query_length}, timeout={retrieve_timeout}s, mode={search_mode}")

# СТАЛО (исправлено):
query_length = len(search_query)
logger.info(f"[retrieve] query_len={query_length}, timeout={retrieve_timeout}s, mode={search_mode}")
```

**Влияние:** RAG retrieve полностью не работал из-за этой ошибки!

### 2. **Дублирование путей в индексе**
**Проблема:** Файлы индексировались с разными путями:
- `/app/documents/raw_uploads/Golden Visa...` (абсолютный путь)
- `documents/raw_uploads/Golden Visa...` (относительный путь)

**Влияние:** 
- LightRAG мог обрабатывать файл дважды
- Индекс был загрязнен дубликатами
- Возможны проблемы с поиском из-за несогласованности

## Решения

### Немедленное исправление для работающего сервера

**1. Скопируйте исправленный файл в контейнер:**
```bash
# Скопируйте исправленный rag_agent.py
docker cp app/agent/rag_agent.py lightrag-api:/app/app/agent/

# Перезапустите контейнер
docker restart lightrag-api
```

**2. Очистите дубликаты в индексе:**
```bash
# Через API
curl -X POST https://api.businessindunes.ai/documents/ingest/cleanup-duplicates \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Или через скрипт в контейнере
docker exec -it lightrag-api python3 fix_duplicate_paths.py
```

### Постоянное решение (пересборка)

```bash
# Остановка и пересборка
docker-compose down
docker-compose build --no-cache lightrag-api
docker-compose up -d
```

## Проверка работоспособности

### 1. Проверка индекса документов
```bash
curl -X GET https://api.businessindunes.ai/documents/ingest/list \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Должны увидеть чистые пути без дубликатов:
```json
{
  "index": [
    {"file": "raw_uploads/Golden Visa – Skilled Professionals (knowledge workers) (1).md"}
  ]
}
```

### 2. Проверка поиска через /chat
```bash
curl -X POST https://api.businessindunes.ai/chat \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "расскажи про золотую визу"}'
```

Должен вернуть реальный ответ с информацией из документов, а не ошибку retrieve.

## Что изменилось

### До исправления:
- ❌ `/chat` падал с ошибкой `name 'query_length' is not defined`
- ❌ Документы не находились из-за критической ошибки в коде
- ❌ Индекс содержал дубликаты путей

### После исправления:
- ✅ RAG retrieve работает корректно
- ✅ Документы успешно находятся и обрабатываются
- ✅ Индекс содержит нормализованные пути без дубликатов
- ✅ `/chat` возвращает релевантную информацию из загруженных документов

## Связь между проблемами

Хотя дублирование путей и ошибка `query_length` - это две независимые проблемы, они вместе создавали впечатление, что "документы не находятся":

1. **Основная причина:** Ошибка `query_length` приводила к полному отказу функции retrieve
2. **Усугубляющий фактор:** Даже если бы retrieve работал, дублирование путей могло вызывать проблемы с поиском

Теперь обе проблемы исправлены, и система должна работать корректно.

## Рекомендации

1. **Мониторинг:** Следите за логами на предмет ошибок типа `NameError`
2. **Тестирование:** После загрузки документов всегда проверяйте через `/chat`
3. **Очистка:** Периодически запускайте cleanup-duplicates для поддержания чистоты индекса
4. **Обновление:** Применяйте исправления как можно скорее для стабильной работы