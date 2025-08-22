# Миграция на gpt-5-mini модель

## Обзор изменений

Обновлены все OpenAI модели для использования новейшей и быстрой `gpt-5-mini` в качестве основной модели.

### ✅ Новая конфигурация моделей:

- **Основная модель**: `gpt-5-mini` (быстрая, cost-effective, новейшая)
- **Fallback цепочка**: `gpt-4.1` → `gpt-4o-mini`
- **Embedding модель**: `text-embedding-3-large` (максимальное качество)

### 📝 Изменения в коде:

#### В app/core/rag.py:
```python
# Было
primary_model = ... or "gpt-4o-mini"
fallback_list.append("gpt-4o-mini")

# Стало  
primary_model = ... or "gpt-5-mini"
fallback_list.append("gpt-4.1")
```

#### В app/agent/rag_agent.py:
```python
# Было
base = ... or "gpt-4o-mini"

# Стало
base = ... or "gpt-5-mini"
```

#### В .env файле:
```bash
# Было
OPENAI_MODEL=gpt-4o-mini
OPENAI_FALLBACK_MODELS=gpt-4o-mini,gpt-3.5-turbo
RAG_LLM_MODEL=gpt-4o-mini

# Стало
OPENAI_MODEL=gpt-5-mini
OPENAI_FALLBACK_MODELS=gpt-4.1,gpt-4o-mini  
RAG_LLM_MODEL=gpt-5-mini
RAG_EMBEDDING_MODEL=text-embedding-3-large
```

#### В CLAUDE.md:
Добавлена секция "AI Model Configuration" с актуальными настройками.

## 🚀 Как применить изменения

### Автоматический способ:
```bash
# В контейнере или локально
python update_models_to_gpt5.py
```

### Ручной способ (контейнер):
```bash
# Скопировать обновленные файлы
docker cp app/ lightrag-api:/app/
docker cp .env lightrag-api:/app/

# Перезапустить контейнер
docker restart lightrag-api
```

### Быстрое переключение (environment variables):
```bash
# Установить переменные окружения напрямую
docker exec -it lightrag-api bash -c "
export OPENAI_MODEL=gpt-5-mini
export RAG_LLM_MODEL=gpt-5-mini  
export OPENAI_FALLBACK_MODELS=gpt-4.1,gpt-4o-mini
# Перезапустить сервис
pkill -f uvicorn
"
```

## 🎯 Преимущества gpt-5-mini

- **🚀 Скорость**: Значительно быстрее предыдущих моделей
- **💰 Стоимость**: Более cost-effective чем gpt-4 модели  
- **🎯 Качество**: Улучшенное понимание контекста и точность
- **🔄 Совместимость**: Полная обратная совместимость API

## 📊 Ожидаемые результаты

### До обновления:
- gpt-4o-mini как основная модель
- Простой fallback на gpt-3.5-turbo
- Базовая производительность

### После обновления:
- gpt-5-mini - новейшая модель с улучшенной производительностью
- Умная fallback цепочка: gpt-4.1 → gpt-4o-mini
- Лучшее качество ответов при сохранении скорости

## ⚠️ Важные примечания

1. **Обратная совместимость**: Все существующие API calls будут работать
2. **Fallback стратегия**: При недоступности gpt-5-mini автоматически переключается на gpt-4.1
3. **Monitoring**: Метрики автоматически отслеживают использование разных моделей
4. **Environment переменные**: Можно переопределить модель через `OPENAI_MODEL=your_model`

## 🔍 Проверка изменений

После применения проверьте:

```bash
# Проверить логи запуска
docker logs lightrag-api | grep -i "model"

# Тестовый запрос к чату
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message": "test gpt-5-mini"}' | jq '.metadata.model'

# Проверить метрики
curl http://localhost:8000/metrics | grep model
```

Должны увидеть использование `gpt-5-mini` в логах и метриках.

## 📋 Откат изменений (если нужно)

Для возврата к предыдущей конфигурации:

```bash
export OPENAI_MODEL=gpt-4o-mini
export RAG_LLM_MODEL=gpt-4o-mini
export OPENAI_FALLBACK_MODELS=gpt-4o-mini,gpt-3.5-turbo
```

---

**Резюме**: Система теперь использует новейшую `gpt-5-mini` модель для максимальной производительности и качества ответов, с надежной fallback стратегией через gpt-4.1.