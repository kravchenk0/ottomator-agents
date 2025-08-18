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

## ⚙️ Конфигурация

### YAML
```yaml
openai:
  api_key: "your_api_key"
  model: "gpt-4.1-mini"
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
```

## 🤖 Динамический выбор модели и Fallback
(Сокращено для индекса — см. раздел в полном README ранее.)

Основная идея: `dynamic_openai_complete` пробует основную модель + цепочку fallback из `OPENAI_FALLBACK_MODELS`, гарантируя наличие `gpt-4.1-mini` в конце. При проблеме с temperature авто-исключает параметр.

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
