# Улучшенная LightRAG Implementation (перемещено)

Полная версия документа перенесена в `docs/README_IMPROVED.md`.
## 🤖 Динамический выбор модели и Fallback

Добавлен механизм динамического выбора модели (`dynamic_openai_complete`) вместо жёстко прошитой `gpt-4o-mini`.
1. Берётся основная модель из (по приоритету):
  - `OPENAI_MODEL`
  - `RAG_LLM_MODEL`
3. Если среди fallback нет `gpt-5-mini`, она автоматически добавляется в конец цепочки (как стабильная базовая модель).

4. Если всё провалилось — последняя попытка через встроенную функцию `gpt_4o_mini_complete`.
OPENAI_FALLBACK_MODELS=gpt-5-mini,gpt-4.1-mini    # Можно перечислить через запятую: gpt-5-mini,gpt-4o-mini
RAG_LLM_MODEL=gpt-5-mini             # Альтернативный источник (если OPENAI_MODEL не задан)
RAG_EMBEDDING_MODEL=gpt-5-mini       # Embedding модель — не переключается автоматически
4. Дефолт: `gpt-5-mini`

Автоматически добавляется префикс `openai:` для pydantic-ai (`openai:gpt-5-mini`).
export OPENAI_FALLBACK_MODELS=gpt-5-mini,gpt-4.1-mini

4. Дефолт: `gpt-5-mini`
3. Если среди fallback нет `gpt-5-mini`, она автоматически добавляется в конец цепочки (как стабильная базовая модель).

4. Если всё провалилось — последняя попытка через встроенную функцию `gpt_4o_mini_complete`.
  `dynamic_openai_complete: used fallback model 'gpt-5-mini' вместо 'gpt-5'`

  "model_used": "gpt-5-mini",
  "model_tried": ["gpt-5", "gpt-5-mini"],

  "model_tried": ["gpt-5", "gpt-5-mini"]
OPENAI_FALLBACK_MODELS=gpt-5-mini,gpt-4.1-mini \

4. Дефолт: `gpt-5-mini`
Автоматически добавляется префикс `openai:` для pydantic-ai (`openai:gpt-5-mini`).

export OPENAI_FALLBACK_MODELS=gpt-5-mini,gpt-4.1-mini
4. Дефолт: `gpt-5-mini`

Автоматически добавляется префикс `openai:` для pydantic-ai (`openai:gpt-5-mini`).
OPENAI_FALLBACK_MODELS=gpt-5-mini,gpt-4.1-mini \

OPENAI_FALLBACK_MODELS=gpt-5-mini,gpt-4.1-mini
# Улучшенная LightRAG Implementation (перемещено)

Полная версия документа перенесена в `docs/README_IMPROVED.md`.

Причина переноса: стандартизация структуры — все markdown файлы теперь в `docs/`.

См. `docs/README_IMPROVED.md`.

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

### 7. **Память диалогов и лимиты (новое)**
- In-memory хранение истории по `conversation_id` с авто-встраиванием последних сообщений в system prompt.
- TTL диалогов (дефолт 1 час) — `RAG_CONVERSATION_TTL_SECONDS`.
- Rate limit per user: 10 запросов/час (конфигурируется `RAG_USER_RATE_LIMIT`, `RAG_USER_RATE_WINDOW_SECONDS`).
- Эндпоинты управления: `GET/DELETE /conversations`, `GET/DELETE /conversations/{id}`.

## 📁 Структура проекта

```
LightRAG/
├── common.py              # Общие функции и RAGManager
├── config.py              # Управление конфигурацией
├── logger.py              # Система логирования
├── rag_agent.py           # Основной RAG агент
├── insert_pydantic_docs.py # Вставка документов
├── test_rag.py            # Тесты
├── examples.py            # Примеры использования
├── requirements.txt       # Зависимости
└── README_IMPROVED.md     # Этот файл
```

## 🛠️ Установка

1. **Клонируйте репозиторий**
```bash

2. **Создайте виртуальное окружение**
# или
venv\Scripts\activate     # Windows
```bash
pip install -r requirements.txt
```bash
echo "OPENAI_API_KEY=your_api_key_here" > .env

### Базовое использование

```python
from common import RAGManager, RAGConfig
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
    # Вставьте документы
    await rag.ainsert("Ваш текст здесь")
    
    # Задайте вопрос
    response = await rag.aquery("Ваш вопрос")
    print(response)

asyncio.run(main())
```

### Использование агента

```python
from rag_agent import run_rag_agent
import asyncio

async def main():
    response = await run_rag_agent("Как работает машинное обучение?")
    print(response)

asyncio.run(main())
```

### Вставка документов

```bash
# Вставить один файл
python insert_pydantic_docs.py --file /path/to/document.txt

# Вставить все файлы из папки
python insert_pydantic_docs.py --directory /path/to/documents/

from app.core import RAGManager, RAGConfig
python insert_pydantic_docs.py --url
```

<!-- Streamlit UI полностью исключён: файл streamlit_app.py удалён -->

### Запуск FastAPI сервера

```bash
cd LightRAG
bash start_api.sh
```

Скрипт делает:
- Создание / повторное использование venv
- Авто-upgrade pip (тихий режим)
- Установка зависимостей из `requirements.txt`
- Доустановку `fastapi` и `uvicorn`, если их нет
- Проверку `.env` (提示 если отсутствует)
- Создание рабочей директории документов (`pydantic-docs`)

После запуска:
```
http://localhost:8000/health  # health check
http://localhost:8000/docs    # Swagger UI
```

### Тестирование API (эквивалентно CLI вопросу)
from app.agent.rag_agent import run_rag_agent
# Health
curl -s http://localhost:8000/health | python -m json.tool

# Простой вопрос через чат-эндпоинт
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How do I create a Pydantic AI agent?"}' | python -m json.tool
```

### О зависимостях
Если нужно минимизировать установку для экспериментального окружения — создайте свой trimmed файл вручную, но графовые режимы могут деградировать.

## ⚙️ Конфигурация

### Через YAML файл

Создайте `config.yaml`:

```yaml
openai:
  api_key: "your_api_key"
  model: "gpt-4.1-mini"
  temperature: 0.0

rag:
  working_dir: "./documents"
  rerank_enabled: true
  batch_size: 20
bash start_api.sh  # запускает shim api_server:app → app.api.server:app

app:
  debug: false
  log_level: "INFO"
  enable_streaming: true
```

### Через переменные окружения

```bash
export OPENAI_API_KEY="your_key"
export RAG_WORKING_DIR="./docs"
from app.utils.logging import performance_logger
export APP_DEBUG="false"
```

## 🤖 Динамический выбор модели и Fallback

Добавлен механизм динамического выбора модели (`dynamic_openai_complete`) вместо жёстко прошитой `gpt-4o-mini`.

Как работает:

1. Берётся основная модель из (по приоритету):
   - `OPENAI_MODEL`
   - `RAG_LLM_MODEL`
   - дефолт: `gpt-4.1-mini`
2. Если модель = `gpt-5` (или любая другая) и вызов не удался (например, `model_not_found`), система по очереди пробует модели из списка `OPENAI_FALLBACK_MODELS`.
3. Если среди fallback нет `gpt-4.1-mini`, она автоматически добавляется в конец цепочки.
4. Если всё провалилось — последняя попытка через встроенную функцию `gpt_4o_mini_complete`.

Переменные окружения:

```bash
OPENAI_MODEL=gpt-5                     # Пытаемся сначала её
OPENAI_FALLBACK_MODELS=gpt-4.1-mini    # Можно перечислить через запятую: gpt-4.1-mini,gpt-4o-mini
RAG_LLM_MODEL=gpt-4.1-mini             # Альтернативный источник (если OPENAI_MODEL не задан)
RAG_EMBEDDING_MODEL=gpt-4.1-mini       # Embedding модель — не переключается автоматически
```

Пример .env для попытки использования гипотетической `gpt-5` с откатом:

```bash
OPENAI_MODEL=gpt-5
OPENAI_FALLBACK_MODELS=gpt-4.1-mini,gpt-4o-mini
```

Логи:
- При успешном использовании fallback увидите предупреждение вида:
  `dynamic_openai_complete: used fallback model 'gpt-4.1-mini' instead of 'gpt-5'`
- Ошибки отдельных моделей логируются с `dynamic_openai_complete: model '...' failed:`

Важно:
- Наличие строки `gpt-5` не гарантирует доступ — если у аккаунта нет такой модели, сразу будет fallback.
- Embedding функция остаётся прежней (`openai_embed`) — задавайте ей корректную модель через `RAG_EMBEDDING_MODEL` при необходимости.
- Можно централизованно менять поведение без правки кода, редактируя только переменные.

Рекомендации:
- Добавьте только реально доступные fallback модели, чтобы не тратить время на лишние ошибки.
- Если нужна разная температура для fallback — пока не поддерживается по-отдельности (используется общая `OPENAI_TEMPERATURE`).
- Следите за стоимостью: более новые/большие модели могут стоить дороже.

Минимальная проверка доступности модели (опционально):
```python
from openai import OpenAI
client = OpenAI()
print([m.id for m in client.models.list() if 'gpt' in m.id])
```

Если хотите отключить fallback и жёстко фейлиться — просто не задавайте `OPENAI_FALLBACK_MODELS` и поставьте нестандартную модель: при неудаче произойдёт только финальный встроенный fallback.

### Расширенный Health endpoint с информацией о модели

Эндпоинт `/health` теперь возвращает статус self-test модели.
  "status": "healthy",
  "rag_status": "healthy",
  "version": "1.0.0",
  "model_ok": true,
  "model_used": "gpt-4.1-mini",
  "model_tried": ["gpt-5", "gpt-4.1-mini"],
  "temperature_auto_adjusted": true,
  "temperature_current": "0.1",
```

Пример неуспешного (fallback тоже не помог):
```jsonc
{
  "status": "healthy",
  "rag_status": "healthy",
  "version": "1.0.0",
  "model_ok": false,
  "model_error": "model_not_found: gpt-5",
  "model_tried": ["gpt-5", "gpt-4.1-mini"]
}
```

Поля:
- `model_ok` – bool или null (если self-test не запускался)
- `model_used` – реальная модель, которая ответила первой успешно
- `model_tried` – список моделей по порядку попыток
- `model_error` – текст ошибки, если не удалось
 - `temperature_auto_adjusted` – применялась ли автоматическая коррекция (если модели не принимают temperature=0)
 - `temperature_current` – актуальное значение переменной OPENAI_TEMPERATURE после возможной коррекции
 - `temperature_rejected_models` – список моделей, отклонивших temperature=0, для которых теперь не указываем явную температуру

Self-test выполняется однократно при старте сервера. Для повторной проверки перезапустите процесс / контейнер. Лёгкая задержка при старте возможна, но запрос короткий (`ping`).

```python
from logger import performance_logger
# Запустите таймер
performance_logger.start_timer("document_processing")

# Ваш код здесь
process_documents()

# Остановите таймер
performance_logger.end_timer("document_processing")

# Логируйте метрики
performance_logger.log_metric("documents_processed", 100, "docs")

# Получите сводку
## 🧪 Тестирование

```bash
# Запустите все тесты
python -m pytest test_rag.py -v

# Запустите конкретный тест
python -m pytest test_rag.py::TestRAGConfig::test_default_config -v
```

## 📝 Примеры

Запустите все примеры:

```bash
python examples.py
```

Или отдельные примеры:

```python
from examples import example_basic_usage, example_agent_usage

# Запустите конкретные примеры
asyncio.run(example_basic_usage())
asyncio.run(example_agent_usage())
```

## 🔧 CLI команды

### RAG Agent

```bash
# Базовое использование
python rag_agent.py --question "Ваш вопрос"

# С настройками
python rag_agent.py \
  --question "Ваш вопрос" \
  --working-dir "./custom-docs" \
  --no-rerank

# Явный выбор модели (перебивает OPENAI_MODEL / RAG_LLM_MODEL)
python rag_agent.py --question "Test" --model gpt-5

# Отключить fallback цепочку (вернёт ошибку если модель недоступна)
python rag_agent.py --question "Test" --model gpt-5 --no-fallback

# Использовать системный prompt из файла и fallback список из окружения
OPENAI_FALLBACK_MODELS=gpt-4.1-mini,gpt-4o-mini \
python rag_agent.py --question "Explain indexing" --system-prompt-file custom_prompt.txt --model gpt-5
```

#### Динамический выбор модели в агенте

Агент теперь использует ту же стратегию выбора модели, что и остальная система:

Приоритет источников модели:
1. `--model` (CLI аргумент)
2. `OPENAI_MODEL`
3. `RAG_LLM_MODEL`
4. Дефолт: `gpt-4.1-mini`

Автоматически добавляется префикс `openai:` для pydantic-ai (`openai:gpt-4.1-mini`).

Fallback логика в агенте упрощённая (умышленно для низкой задержки):
- Срабатывает только при ошибке с признаками `model_not_found` или `404`.
- Берёт первую модель из `OPENAI_FALLBACK_MODELS` (если список задан).
- Выполняет ОДНУ повторную попытку. (Глубокий каскад реализован в `dynamic_openai_complete` для RAG внутри LightRAG.)
- Если повтор тоже упал — возвращается текст ошибки вместо ответа.

Примеры:
```bash
# Основная модель gpt-5, fallback список
export OPENAI_MODEL=gpt-5
export OPENAI_FALLBACK_MODELS=gpt-4.1-mini,gpt-4o-mini
python rag_agent.py --question "How to configure embeddings?"

# Принудительно отключить fallback
python rag_agent.py --question "How to configure embeddings?" --no-fallback
```

Кеширование агентов: фабрика `create_agent()` кэширует инстансы (LRU до 32 комбинаций model+prompt) — повторные вызовы с теми же аргументами не пересоздают объект.

Регистрация инструментов: `retrieve` привязывается при создании агента через `_register_tools`, что позволяет иметь несколько агентов с разными prompt без конфликтов.

Рекомендации:
- Для быстрой проверки доступности новой модели запустите `python rag_agent.py --question ping --model gpt-X`.
- Если нужна многоступенчатая цепочка fallback внутри самого агента — расширьте блок в `run_rag_agent` (комментарий к месту уже очевиден по структуре).
- Для систематической проверки доступности моделей используйте `/health` (self-test Responses API) или отдельный скрипт.

### Вставка документов

```bash
# Помощь
python insert_pydantic_docs.py --help

# Вставка файла
python insert_pydantic_docs.py --file document.txt

# Вставка папки
python insert_pydantic_docs.py --directory ./docs/
```

## 🚨 Обработка ошибок

Система теперь gracefully обрабатывает ошибки:

- Неверные пути к файлам
- Проблемы с API
- Ошибки инициализации
- Проблемы с конфигурацией

## 📈 Логирование

Настройте логирование:

```python
from logger import setup_logger

# Базовое логирование
logger = setup_logger("myapp", "INFO")

# Логирование в файл
logger = setup_logger("myapp", "DEBUG", "app.log")

# Кастомный формат
logger = setup_logger("myapp", "INFO", log_format="%(levelname)s: %(message)s")
```

## 🔄 Миграция с старой версии

1. **Обновите импорты**:
   ```python
   # Старый способ
   from lightrag import LightRAG
   
   # Новый способ
   from common import RAGManager, RAGConfig
   ```

2. **Замените инициализацию**:
   ```python
   # Старый способ
   rag = LightRAG(working_dir="./docs")
   await rag.initialize_storages()
   
   # Новый способ
   config = RAGConfig(working_dir="./docs")
   rag_manager = RAGManager(config)
   rag = await rag_manager.initialize()
   ```

3. **Используйте новую обработку ошибок**:
   ```python
   try:
       response = await rag.aquery(query)
   except Exception as e:
       logger.error(f"Query failed: {e}")
       # Graceful fallback
   ```

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License

## 🆘 Поддержка

- Создайте Issue для багов
- Используйте Discussions для вопросов
- Проверьте examples.py для примеров
- Изучите test_rag.py для понимания API 

## 🔍 Устранение типичных проблем

### 1. Сообщение pip: `[notice] A new release of pip is available`
Можно игнорировать (информативно). В скрипте `start_api.sh` уже выполняется `pip install --upgrade --quiet pip`.

### 2. `ModuleNotFoundError: No module named 'fastapi'`
Причины:
- Запуск до установки зависимостей
- Перепутан venv
Решение: переустановить полный профиль `pip install -r requirements.txt` или вручную `pip install fastapi uvicorn`.

### 3. Конфликт `starlette` и `sse-starlette`
Сообщение вида: `requires starlette>=0.41.3 but you have starlette 0.36.x`.
Решение для лёгкого профиля: убрать `sse-starlette` / `httpx-sse`, они не нужны для базового API.

### 4. Health endpoint не отвечает
Проверьте, завершился ли startup (должно появиться `Application startup complete`). Инициализация LightRAG может занять время при первой загрузке.

### 5. Нет ответов / пустой результат
Проверьте, что документы вставлены (`pydantic-docs` содержит JSON-хранилища) или запустите заново `insert_pydantic_docs.py`.

### 6. Перезапуск в чистом окружении
```bash
rm -rf LightRAG/venv
bash LightRAG/start_api.sh
```

### 7. Проверка корректного окружения
```bash
which python
python -c "import fastapi, lightrag; print('OK')"
```

## 🗜 Оптимизация производительности
- Для CI можно сформировать кастомный сокращённый requirements, но по умолчанию используйте полный.
- Избегайте повторной вставки одинаковых документов
- Кешируйте ответы (см. `kv_store_llm_response_cache.json`)
- Следите за размером рабочей директории: удаляйте устаревшие файлы перед массовой переиндексацией

## 🧩 План возможных дальнейших улучшений
- Импорт Postman коллекции: `LightRAG.postman_collection.json`

## 🧪 Быстрый старт через Postman / Bruno / Hoppscotch

1. Откройте Postman → Import → Выберите файл `LightRAG/LightRAG.postman_collection.json`
2. Убедитесь, что сервер запущен (`bash start_api.sh`)
3. Проверьте запросы:
  - Health Check
  - Chat: Ask Question
  - Documents: Insert / Search
  - Config: Get / Update
4. При необходимости измените переменную `base_url` (по умолчанию `http://localhost:8000`)

Для Bruno/Hoppscotch можно скопировать raw JSON коллекции.
- Добавить автоматический health-поллинг в скрипт
- Вынести curl-примеры в Postman коллекцию
- Добавить эндпоинт `/ask` с выбором режима (mix/hybrid/local)
- Включить опционально SSE для стриминга (требует вернуть `sse-starlette` в полный профиль)