# Руководство по метрикам производительности чата

## Обзор

Система включает подробные Prometheus-совместимые метрики для диагностики производительности эндпоинта `/chat`. Метрики помогают выявить узкие места и понять, где тратится время при обработке запросов.

## Просмотр метрик

### Эндпоинт метрик
```
GET /metrics
```

Возвращает метрики в формате Prometheus. Эндпоинт открыт для мониторинга, не требует авторизации.

### Использование curl
```bash
# Просмотр всех метрик
curl http://localhost:8000/metrics

# Фильтрация конкретной метрики
curl http://localhost:8000/metrics | grep "lightrag_chat_latency"
```

## Основные метрики производительности

### Общие метрики запросов

- **`lightrag_chat_requests_total`** - Общее количество запросов к чату
- **`lightrag_chat_requests_in_flight`** - Текущее количество обрабатываемых запросов
- **`lightrag_chat_latency_seconds_sum`** - Суммарное время обработки всех запросов

#### Вычисление среднего времени ответа:
```
Средняя задержка = lightrag_chat_latency_seconds_sum / lightrag_chat_requests_total
```

### Метрики ошибок

- **`lightrag_chat_errors_total`** - Общее количество ошибок
- **`lightrag_chat_timeout_errors_total`** - Ошибки таймаута (превышение времени ожидания)
- **`lightrag_chat_model_errors_total`** - Ошибки модели (неверный запрос, rate limits)
- **`lightrag_chat_init_errors_total`** - Ошибки инициализации системы
- **`lightrag_chat_rate_limit_rejections`** - Отклонения по rate limit

### Детальные метрики по этапам

#### История разговора
- **`lightrag_history_build_latency_seconds_sum`** - Время построения контекста истории
- **`lightrag_history_build_total`** - Количество операций построения истории

#### Создание агента  
- **`lightrag_agent_create_latency_seconds_sum`** - Время создания AI агента
- **`lightrag_agent_create_total`** - Количество созданий агента

#### RAG операции
- **`lightrag_rag_retrieve_latency_seconds_sum`** - Время выполнения RAG поиска
- **`lightrag_rag_retrieve_total`** - Количество RAG операций

#### Этапы обработки
- **`lightrag_chat_phase_latency_seconds_sum{phase="X"}`** - Время каждого этапа
- **`lightrag_chat_phase_count_total{phase="X"}`** - Количество выполнений этапа

Возможные значения `phase`:
- `history` - Построение контекста истории
- `agent_create` - Создание AI агента
- `agent_run` - Выполнение агента (основная работа)
- `handler` - Общий обработчик

### Метрики истории разговоров

**`lightrag_conversation_history_length{bucket="X"}`** - Распределение длины истории

Buckets (корзины):
- `0-2` - Короткие диалоги (1-2 сообщения)
- `3-5` - Средние диалоги
- `6-10` - Длинные диалоги
- `11-20` - Очень длинные диалоги
- `20+` - Экстремально длинные диалоги

## Диагностика узких мест

### 1. Медленные ответы в целом

Если общая задержка высокая, смотрите на детальные этапы:

```bash
curl http://localhost:8000/metrics | grep "phase_latency_seconds_sum"
```

Наиболее вероятные узкие места:
- `agent_run` - Медленная работа OpenAI API или RAG
- `history` - Большие истории разговоров
- `agent_create` - Проблемы инициализации

### 2. Высокий процент ошибок

```bash
# Проверить типы ошибок
curl http://localhost:8000/metrics | grep "_errors_total"
```

- Много `timeout_errors` → Увеличить `RAG_AGENT_TIMEOUT_SECONDS`
- Много `model_errors` → Проблемы с OpenAI API или некорректные запросы
- Много `init_errors` → Проблемы конфигурации системы

### 3. Проблемы с производительностью по длине истории

```bash
curl http://localhost:8000/metrics | grep "conversation_history_length"
```

Если много запросов в bucket `20+`:
- Пользователи ведут слишком длинные диалоги
- Рассмотрите уменьшение `RAG_MAX_HISTORY_MESSAGES`

### 4. Высокие задержки агента

```bash
curl http://localhost:8000/metrics | grep "agent_create\|rag_retrieve"
```

- Высокие `agent_create_latency` → Проблемы инициализации
- Высокие `rag_retrieve_latency` → Медленный RAG поиск

## Мониторинг с помощью PromQL

Если у вас есть Prometheus, используйте эти запросы:

### Средняя задержка за последние 5 минут:
```promql
rate(lightrag_chat_latency_seconds_sum[5m]) / rate(lightrag_chat_requests_total[5m])
```

### Процент ошибок:
```promql
rate(lightrag_chat_errors_total[5m]) / rate(lightrag_chat_requests_total[5m]) * 100
```

### Топ самых медленных этапов:
```promql
topk(3, rate(lightrag_chat_phase_latency_seconds_sum[5m]) by (phase))
```

### P95 задержки по этапам (приблизительно):
```promql
histogram_quantile(0.95, rate(lightrag_chat_phase_latency_seconds_sum[5m]))
```

## Настройки для улучшения производительности

### Переменные окружения

- **`RAG_AGENT_TIMEOUT_SECONDS`** (по умолчанию: 120) - Таймаут выполнения агента
- **`RAG_MAX_HISTORY_MESSAGES`** (по умолчанию: 12) - Максимальная длина истории
- **`RAG_DETAILED_METRICS`** (по умолчанию: 1) - Включить детальное логирование

### Рекомендации по оптимизации

1. **При высокой задержке `agent_run`:**
   - Проверить скорость OpenAI API
   - Оптимизировать RAG индекс
   - Уменьшить размер системного промпта

2. **При проблемах с `history`:**
   - Уменьшить `RAG_MAX_HISTORY_MESSAGES`
   - Использовать асинхронную обработку истории

3. **При частых таймаутах:**
   - Увеличить `RAG_AGENT_TIMEOUT_SECONDS`
   - Проверить сетевые соединения с OpenAI

## Примеры использования

### Простой мониторинг в bash:
```bash
#!/bin/bash
while true; do
  echo "=== $(date) ==="
  curl -s http://localhost:8000/metrics | grep -E "(requests_total|errors_total|latency_seconds_sum)" 
  echo ""
  sleep 30
done
```

### Проверка здоровья системы:
```bash
#!/bin/bash
METRICS=$(curl -s http://localhost:8000/metrics)
REQUESTS=$(echo "$METRICS" | grep "lightrag_chat_requests_total" | awk '{print $2}')
ERRORS=$(echo "$METRICS" | grep "lightrag_chat_errors_total" | awk '{print $2}')

if [ "$REQUESTS" -gt 0 ]; then
  ERROR_RATE=$(echo "scale=2; $ERRORS * 100 / $REQUESTS" | bc)
  echo "Error rate: $ERROR_RATE%"
  
  if (( $(echo "$ERROR_RATE > 10" | bc -l) )); then
    echo "WARNING: High error rate!"
  fi
else
  echo "No requests processed yet"
fi
```

## Заключение

Используйте эти метрики для:
- Выявления узких мест в производительности
- Мониторинга качества обслуживания  
- Настройки таймаутов и лимитов
- Планирования масштабирования системы

При проблемах с производительностью начните с анализа общих метрик, затем углубляйтесь в детальные метрики по этапам.