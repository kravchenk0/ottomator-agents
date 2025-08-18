# LightRAG: Retrieval-Augmented Generation with Knowledge Graph

Этот репозиторий теперь сфокусирован ТОЛЬКО на LightRAG реализации (упрощённый и более мощный вариант). Ранее здесь была сравнительная BasicRAG версия — она удалена для уменьшения сложности.

## Project Goal

The primary goal of this project is to showcase the power and efficiency of LightRAG compared to traditional RAG implementations. LightRAG offers several advantages:

- **Simplified API**: LightRAG provides a more streamlined API with fewer configuration parameters
- **Automatic Document Processing**: LightRAG handles document chunking and embedding automatically
- **Knowledge Graph Integration**: LightRAG leverages knowledge graph capabilities for improved context understanding
- **More Efficient Retrieval**: LightRAG's query mechanism provides more relevant results with less configuration

## Установка

### Prerequisites
- Python 3.11+
- OpenAI API key

### Setup

1. Clone this repository

2. Создайте `.env` файл в директории `LightRAG` c вашим OpenAI ключом:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

3. Создайте виртуальное окружение и установите зависимости:

   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # Windows
   .\venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   
   # Установка зависимостей LightRAG
   cd LightRAG
   pip install -r requirements.txt
   ```

## Запуск

### LightRAG (CLI)

1. **Insert Documentation** (this will take a while - using full Pydantic AI docs as an example!):
   ```bash
   cd LightRAG
   python insert_pydantic_docs.py
   ```
   This will fetch the Pydantic AI documentation and process it using LightRAG's advanced document processing.

2. **Run the Agent**:
   ```bash
   python rag_agent.py --question "How do I create a Pydantic AI agent?"
   ```

3. (Streamlit UI удалён — используйте CLI или FastAPI сервер.)

## Ключевые особенности

- Автоматическая обработка и чанкинг документов
- Знаниевая графовая структура (knowledge graph) для лучшего контекстного поиска
- Режимы запросов (naive / local / global / mix / hybrid)
- Простая интеграция через FastAPI (`api_server.py`)

## Структура

- `LightRAG/rag_agent.py` — CLI агент
- `LightRAG/insert_pydantic_docs.py` — загрузка и индексация документации Pydantic AI (адаптируйте под свои файлы)
- `LightRAG/api_server.py` — FastAPI сервер
- `LightRAG/start_api.sh` — скрипт запуска

## Быстрый запуск API

```bash
cd LightRAG
export OPENAI_API_KEY=sk-... # или в .env
bash start_api.sh
```

Проверка здоровья:
```bash
curl -s http://localhost:8000/health
```

Запрос к чату:
```bash
curl -s -X POST http://localhost:8000/chat \
   -H 'Content-Type: application/json' \
   -d '{"message":"Explain LightRAG architecture briefly"}' | jq
```

## Индексация своих документов

Модифицируйте `insert_pydantic_docs.py` или создайте аналогичный скрипт: соберите тексты, вызовите метод вставки (см. пример кода внутри файла) — затем можно задавать вопросы через CLI / API.

## Лицензия

MIT (если требуется другая — обновите этот раздел).
