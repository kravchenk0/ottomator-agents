# 🚨 СРОЧНОЕ ИСПРАВЛЕНИЕ: Phase Variable Error

## Ошибка
```
UnboundLocalError: cannot access local variable 'phase' where it is not associated with a value
```

## Причина
Переменная `phase` используется до её объявления в функции `chat_endpoint`.

## ⚡ Быстрое исправление

### Вариант 1: Автоматический патч
```bash
# Скопировать скрипт в контейнер и запустить
docker cp fix_phase_error.py lightrag-api:/app/
docker exec -it lightrag-api python /app/fix_phase_error.py

# Перезапустить сервер (или просто подождать автоперезагрузки)
docker exec -it lightrag-api pkill -f uvicorn
```

### Вариант 2: Ручное исправление
```bash
# Войти в контейнер
docker exec -it lightrag-api bash

# Отредактировать файл
vi /app/app/api/server.py

# Найти строку (~957):
# user_id = request.user_id or (_claims.get("sub") if isinstance(_claims, dict) else None) or "anonymous"

# Добавить ПОСЛЕ неё:
# Get phase from contextvar early (used throughout the function)
phase = _cv_phase.get() or _phase

# Найти и удалить дублированную строку (~990):
# phase = _cv_phase.get() or _phase
```

### Вариант 3: Полная замена файла
```bash
# Скопировать исправленный server.py
docker cp app/api/server.py lightrag-api:/app/app/api/server.py
```

## ✅ Проверка исправления

После применения исправления:
```bash
# Проверить что сервер запустился без ошибок
docker logs lightrag-api --tail 20

# Протестировать эндпоинт
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message": "test"}'
```

Не должно быть ошибки `UnboundLocalError: cannot access local variable 'phase'`.

## 🎯 Результат
- ❌ `500 Internal Server Error` исправлен
- ✅ `/chat` эндпоинт работает корректно
- ✅ Метрики производительности собираются правильно