# Улучшенная LightRAG Implementation

Это улучшенная версия LightRAG с исправленными архитектурными проблемами, лучшей обработкой ошибок и дополнительными возможностями.

## 🚀 Основные улучшения

### 1. **Устранение дублирования кода**
- Вынесены общие функции в `common.py`
- Централизованная инициализация RAG
- Переиспользуемые утилиты

### 2. **Улучшенная архитектура**
- Разделение ответственности между модулями
- Паттерн Manager для управления RAG
- Конфигурация через dataclass

### 3. **Обработка ошибок**
- Graceful error handling
- Fallback механизмы
- Валидация входных данных

### 4. **Конфигурация**
- Централизованная конфигурация
- Поддержка YAML файлов
- Переменные окружения

### 5. **Логирование и мониторинг**
- Структурированное логирование
- Мониторинг производительности
- Метрики выполнения

### 6. **Графовый стек и расширенные зависимости**
Полный `requirements.txt` включает как базовый RAG + API, так и граф/ML стек (networkx, graspologic, scikit-learn и др.) — для полноценной работы режимов global/mix/hybrid.

## 📁 Структура проекта (модульная после рефакторинга)

```
LightRAG/
├── app/
│   ├── core/
│   │   ├── config.py            # RAGConfig
│   │   └── rag.py               # RAGManager + dynamic_openai_complete + утилиты
│   ├── agent/
│   │   └── rag_agent.py         # Pydantic AI агент (retrieve tool)
│   ├── api/
│   │   └── server.py            # FastAPI (app.api.server:app)
│   └── utils/
│       ├── diagnostics.py       # Self-test моделей
│       └── logging.py           # Логирование и PerformanceLogger
├── common.py                    # Shim → app.core (DeprecationWarning)
├── rag_agent.py                 # Shim → app.agent.rag_agent
├── api_server.py                # Shim → app.api.server
├── diagnostics.py               # Shim → app.utils.diagnostics
├── logger.py                    # Shim → app.utils.logging
├── monkey_patch_lightrag.py     # Monkey patch LightRAG.get_vector_context
├── insert_pydantic_docs.py      # Вставка документов
├── examples.py                  # Примеры
├── test_rag.py                  # Тесты
├── requirements.txt             # Зависимости
└── README_IMPROVED.md           # Этот файл
```

Shim-файлы оставлены для обратной совместимости и будут постепенно удаляться. Новые импорты используйте из `app.*`.

## 🛠️ Установка

1. **Клонируйте репозиторий**
```bash
git clone <repository-url>
cd LightRAG
```

2. **Создайте виртуальное окружение**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

3. **Установите зависимости**
```bash
pip install -r requirements.txt
```

4. **Создайте .env файл**
```bash
echo "OPENAI_API_KEY=your_api_key_here" > .env
```

## 🚀 Использование

### Базовое использование

```python
from app.core import RAGManager, RAGConfig
import asyncio

async def main():
    config = RAGConfig(
        working_dir="./my-docs",
        rerank_enabled=True,
        batch_size=20
    )
    rag_manager = RAGManager(config)
    rag = await rag_manager.initialize()
    await rag.ainsert("Ваш текст здесь")
    response = await rag.aquery("Ваш вопрос")
    print(response)

asyncio.run(main())
```

### Использование агента

```python
from app.agent.rag_agent import run_rag_agent
import asyncio

async def main():
    response = await run_rag_agent("Как работает машинное обучение?")
    print(response)

asyncio.run(main())
```

### Вставка документов

```bash
python insert_pydantic_docs.py --file /path/to/document.txt
python insert_pydantic_docs.py --directory /path/to/documents/
python insert_pydantic_docs.py --url
```

### Запуск FastAPI сервера

```bash
bash start_api.sh  # shim api_server:app → app.api.server:app
```

Прямой запуск (минуя shim):
```bash
uvicorn app.api.server:app --host 0.0.0.0 --port 8000
```

После запуска:
```
http://localhost:8000/health
http://localhost:8000/docs
```

### Тестирование API
```bash
curl -s http://localhost:8000/health | python -m json.tool
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How do I create a Pydantic AI agent?"}' | python -m json.tool
```

### 🔁 Память диалога (in‑memory conversation history)

Сервер поддерживает краткосрочную память для чата (per `conversation_id`).

Основные свойства:
- Хранение в оперативной памяти процесса (не персистентно — при рестарте всё очищается)
- Формат: `conversations[conversation_id] = [{"role":"user|assistant","content":"..."}, ...]`
- История автоматически встраивается в `system_prompt` в виде блока `Conversation so far:` (последние N сообщений)
- Обрезка: хранится максимум `~ 2 * MAX_HISTORY_MESSAGES` сообщений (мягкая прунка)
- TTL: диалог удаляется если не было активности > `RAG_CONVERSATION_TTL_SECONDS` (по умолчанию 3600 секунд)
- Rate limit: максимум `RAG_USER_RATE_LIMIT` запросов на пользователя в окно `RAG_USER_RATE_WINDOW_SECONDS` (дефолт 10 / час)

Env переменные (настройка):
```bash
export RAG_MAX_HISTORY_MESSAGES=12              # Сколько последних сообщений используется для контекста
export RAG_CONVERSATION_TTL_SECONDS=3600        # Время жизни (1 час по умолчанию)
export RAG_USER_RATE_LIMIT=10                   # Запросов на пользователя в окно
export RAG_USER_RATE_WINDOW_SECONDS=3600        # Размер окна
```

Дополнительные поля в `metadata` ответа `/chat`:
- `history_messages` – сколько сообщений сейчас хранится в диалоге
- `history_context_chars` – длина переданного в prompt контекста
- `rate_limit_remaining` – сколько запросов осталось в текущем окне

Пример запроса с явным `conversation_id` для продолжения диалога:
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <JWT>" \
  -H 'Content-Type: application/json' \
  -d '{"message":"Привет, расскажи про виды виз.", "conversation_id":"conv_abc123"}' | python -m json.tool

curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <JWT>" \
  -H 'Content-Type: application/json' \
  -d '{"message":"А теперь требования для инвесторской?", "conversation_id":"conv_abc123"}' | python -m json.tool
```

### 📚 Conversation API эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/conversations` | Список активных `conversation_id` (учитывает TTL) |
| GET | `/conversations/{id}` | История сообщений указанного диалога |
| DELETE | `/conversations/{id}` | Удалить один диалог |
| DELETE | `/conversations` | Очистить все диалоги |

Ответы:
- `GET /conversations` → `{ "conversations": ["conv_abc123", ...] }`
- `GET /conversations/{id}` → `{ "conversation_id": "conv_abc123", "messages": [{"role":"user","content":"..."}, ...] }`
- `DELETE /conversations/{id}` → `{ "status":"ok", "cleared":1, "conversations_remaining":0 }`
- При истечении TTL → 404 `{"detail":"Conversation expired"}`

Ограничения / заметки:
- Память не реплицируется между воркерами (использовать sticky sessions или внешний стор для продакшена — Redis/DB)
- Нет шифрования содержимого (если нужно — внедрите перед записью)
- Не храните чувствительные данные: история живёт в памяти процесса
- Для устойчивости к OOM следите за количеством активных диалогов и настройте агрессивный TTL

Типовая стратегия продакшен-памяти (если потребуется позже):
1. Абстрагировать storage интерфейс `ConversationStore`
2. Реализации: InMemory / Redis / Postgres
3. Добавить фон очистки просроченных записей (или rely on Redis TTL)
4. Расширить `/conversations` фильтрами (user_id)


## ⚙️ Конфигурация

### YAML
```yaml
openai:
  api_key: "your_api_key"
  model: "gpt-5-mini"
  temperature: 0.0
rag:
  working_dir: "./documents"
  rerank_enabled: true
  batch_size: 20
  chunk_size: 1000
app:
  debug: false
  log_level: "INFO"
  enable_streaming: true
```

### Env переменные
```bash
export OPENAI_API_KEY="your_key"
export RAG_WORKING_DIR="./docs"
export RAG_RERANK_ENABLED="true"
export RAG_CONVERSATION_TTL_SECONDS=3600
export RAG_USER_RATE_LIMIT=10
export RAG_USER_RATE_WINDOW_SECONDS=3600
export RAG_MAX_HISTORY_MESSAGES=12
```

## 🤖 Динамический выбор модели и Fallback
(Сокращено для индекса — см. раздел в полном README ранее.)

Основная идея: `dynamic_openai_complete` пробует основную модель + цепочку fallback из `OPENAI_FALLBACK_MODELS`, гарантируя наличие `gpt-5-mini` в конце как стабильной базовой модели. При проблеме с temperature авто-исключает параметр.

## 📊 Мониторинг производительности

```python
from app.utils.logging import performance_logger
performance_logger.start_timer("op")
# ...
performance_logger.end_timer("op")
print(performance_logger.get_summary())
```

## 🔄 Миграция

```python
# Было
a = LightRAG(working_dir="./docs")
await a.initialize_storages()
# Стало
from app.core import RAGManager, RAGConfig
rag = await RAGManager(RAGConfig(working_dir="./docs")).initialize()
```

## 🧪 Тесты
```bash
pytest -q
```

## 📄 Лицензия
MIT
