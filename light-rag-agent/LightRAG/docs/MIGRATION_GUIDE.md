# Руководство по миграции на улучшенную версию

Это руководство поможет вам перейти с оригинальной версии LightRAG на улучшенную версию с исправленной архитектурой.

## 🔄 Что изменилось

### 1. **Структура файлов**
- Добавлен `common.py` с общими функциями
- Добавлен `config.py` для управления конфигурацией
- Добавлен `logger.py` для логирования
- Добавлен `test_rag.py` для тестирования
- Добавлен `examples.py` с примерами

### 2. **Архитектурные изменения**
- Введен паттерн Manager для управления RAG
- Централизованная конфигурация
- Улучшенная обработка ошибок
- Разделение ответственности между модулями

### 3. **API изменения**
- Новые классы: `RAGManager`, `RAGConfig`
- Обновленные функции с лучшей обработкой ошибок
- Новые CLI параметры

## 📋 Пошаговая миграция

### Шаг 1: Обновите зависимости

```bash
# Установите новые зависимости
pip install -r requirements.txt
```

### Шаг 2: Обновите импорты

**Было:**
```python
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status
```

**Стало:**
```python
from common import RAGManager, RAGConfig
```

### Шаг 3: Обновите инициализацию RAG

**Было:**
```python
async def initialize_rag():
    rag = LightRAG(
        working_dir=WORKING_DIR,
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete,
        rerank_model_func=openai_rerank
    )
    await rag.initialize_storages()
    return rag
```

**Стало:**
```python
async def initialize_rag():
    config = RAGConfig(
        working_dir=WORKING_DIR,
        rerank_enabled=True
    )
    rag_manager = RAGManager(config)
    return await rag_manager.initialize()
```

### Шаг 4: Обновите использование RAG

**Было:**
```python
rag = await initialize_rag()
response = await rag.aquery(query)
```

**Стало:**
```python
rag = await initialize_rag()
response = await rag.aquery(query, param={"mode": "mix"})
```

### Шаг 5: Обновите обработку ошибок

**Было:**
```python
response = await rag.aquery(query)
```

**Стало:**
```python
try:
    response = await rag.aquery(query, param={"mode": "mix"})
except Exception as e:
    logger.error(f"Query failed: {e}")
    response = "Sorry, I couldn't process your request."
```

## 🔧 Примеры миграции

### Пример 1: Простой скрипт

**Было:**
```python
import asyncio
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed

async def main():
    rag = LightRAG(
        working_dir="./docs",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete
    )
    await rag.initialize_storages()
    
    await rag.ainsert("Sample document")
    response = await rag.aquery("Sample query")
    print(response)

asyncio.run(main())
```

**Стало:**
```python
import asyncio
from common import RAGManager, RAGConfig

async def main():
    config = RAGConfig(working_dir="./docs")
    rag_manager = RAGManager(config)
    rag = await rag_manager.initialize()
    
    await rag.ainsert("Sample document")
    response = await rag.aquery("Sample query", param={"mode": "mix"})
    print(response)

asyncio.run(main())
```

### Пример 2: С настройками

**Было:**
```python
rag = LightRAG(
    working_dir="./docs",
    embedding_func=openai_embed,
    llm_model_func=gpt_4o_mini_complete,
    rerank_model_func=openai_rerank
)
```

**Стало:**
```python
config = RAGConfig(
    working_dir="./docs",
    rerank_enabled=True,
    batch_size=20,
    chunk_size=1000
)
rag_manager = RAGManager(config)
rag = await rag_manager.initialize()
```

### Пример 3: С обработкой ошибок

**Было:**
```python
response = await rag.aquery(query)
```

**Стало:**
```python
try:
    response = await rag.aquery(query, param={"mode": "mix"})
except Exception as e:
    logger.error(f"Query failed: {e}")
    response = "I encountered an error while processing your request."
```

## 🚨 Потенциальные проблемы

### 1. **Импорты**
- Убедитесь, что все импорты обновлены
- Проверьте, что `common.py` доступен

### 2. **Конфигурация**
- Проверьте, что все параметры передаются через `RAGConfig`
- Убедитесь, что working_dir существует

### 3. **Обработка ошибок**
- Добавьте try-catch блоки где необходимо
- Используйте логирование для отладки

### 4. **Асинхронность**
- Убедитесь, что все async функции правильно вызываются
- Используйте `asyncio.run()` для запуска async функций

## ✅ Проверка миграции

### 1. **Запустите тесты**
```bash
python -m pytest test_rag.py -v
```

### 2. **Запустите примеры**
```bash
python examples.py
```

### 3. **Проверьте базовую функциональность**
```bash
python rag_agent.py --question "Test question"
```

### 4. **Проверьте веб-интерфейс**
```bash
streamlit run streamlit_app.py
```

## 🔍 Отладка

### 1. **Логирование**
```python
from logger import setup_logger

logger = setup_logger("debug", "DEBUG")
logger.debug("Debug information")
```

### 2. **Валидация конфигурации**
```python
from config import Config

config = Config()
if not config.validate():
    print("Configuration errors:", config.errors)
```

### 3. **Проверка зависимостей**
```bash
pip list | grep -E "(lightrag|pydantic|openai)"
```

## 📚 Дополнительные ресурсы

- `examples.py` - Примеры использования
- `test_rag.py` - Тесты для понимания API
- `README_IMPROVED.md` - Подробная документация
- `config.py` - Примеры конфигурации

## 🆘 Получение помощи

Если у вас возникли проблемы с миграцией:

1. Проверьте логи на наличие ошибок
2. Убедитесь, что все зависимости установлены
3. Сравните ваш код с примерами в `examples.py`
4. Запустите тесты для проверки функциональности
5. Создайте Issue с описанием проблемы

## 🎯 Следующие шаги

После успешной миграции:

1. Изучите новые возможности (логирование, мониторинг)
2. Настройте конфигурацию под ваши нужды
3. Добавьте тесты для вашего кода
4. Внедрите мониторинг производительности
5. Рассмотрите возможность использования YAML конфигурации
