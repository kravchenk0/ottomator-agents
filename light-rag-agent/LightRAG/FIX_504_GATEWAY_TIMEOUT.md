# 🔧 Исправление 504 Gateway Timeout

## Проблема
Эндпоинты `/documents/ingest/scan` и `/chat` возвращают ошибку 504 Gateway Timeout:
```html
<html>
<head><title>504 Gateway Time-out</title></head>
<body>
<center><h1>504 Gateway Time-out</h1></center>
</body>
</html>
```

## Диагностика

### Цепочка таймаутов:
1. **Application timeout:** 300 секунд (5 минут)
2. **Nginx timeout:** 320 секунд (5:20)
3. **ALB idle timeout:** 120 секунд (2 минуты) ⚠️ **ПРОБЛЕМА**

**Узкое место:** ALB прерывает запросы через 2 минуты, не дожидаясь ответа от приложения.

### Дополнительные факторы:
- Операции ingest могут быть медленными для больших файлов
- Отсутствие ранних проверок (существование директории)
- Блокировка `_ingest_lock` может задерживать запросы

## Решения

### 1. **Увеличение ALB timeout (Terraform)**
```hcl
# terraform/secrets.tfvars
alb_idle_timeout = 600  # 10 minutes
```

### 2. **Оптимизация application timeout**
```python
# app/api/server.py
upload_timeout = int(os.getenv("RAG_UPLOAD_TIMEOUT_SECONDS", "240"))  # 4 minutes
```

### 3. **Ранние проверки директорий**
```python
# Добавлено в _ingest_scan_impl()
if not scan_path.exists():
    return {"status": "directory_not_found", ...}
```

### 4. **Улучшенное логирование**
```python
logger.info(f"[ingest_scan] Starting scan with timeout={upload_timeout}s")
```

## Применение исправлений

### Немедленно (для работающего сервера):
```bash
# 1. Обновить код в контейнере
docker cp app/api/server.py lightrag-api:/app/app/api/
docker restart lightrag-api

# 2. Проверить через прямой доступ (порт 8000)
curl -X POST http://YOUR_EC2_IP:8000/documents/ingest/scan \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Постоянно (через Terraform):
```bash
# 3. Обновить ALB timeout
cd terraform
terraform apply -var-file="secrets.tfvars"

# 4. Дождаться обновления ALB (2-3 минуты)
# 5. Проверить через HTTPS
curl -X POST https://api.businessindunes.ai/documents/ingest/scan \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Временные обходные пути

### 1. **Прямое подключение к порту 8000**
Обход ALB для длительных операций:
```bash
curl -X POST http://YOUR_EC2_IP:8000/documents/ingest/scan \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 2. **Локальная обработка через ingest_local.py**
Для больших batch операций:
```bash
docker exec -it lightrag-api python3 tools/ingest_local.py \
  --directory /app/documents/raw_uploads
```

## Проверка результатов

### 1. **Проверка таймаутов ALB**
```bash
aws elbv2 describe-load-balancers --query 'LoadBalancers[0].IdleTimeout'
# Должно показать 600
```

### 2. **Тест малых операций**
```bash
# Пустая директория (должна отвечать быстро)
curl -X POST https://api.businessindunes.ai/documents/ingest/scan \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. **Мониторинг логов**
```bash
docker logs -f lightrag-api | grep "\[ingest_scan\]"
```

## Ожидаемые улучшения

| Сценарий | До исправления | После исправления |
|----------|----------------|-------------------|
| Пустая/отсутствующая директория | 504 через 2 минуты | Быстрый ответ (~1 секунда) |
| Малые файлы (1-2 документа) | 504 через 2 минуты | Успешно (~30-60 секунд) |
| Средние batch (5-10 документов) | 504 через 2 минуты | Успешно (~2-4 минуты) |
| Большие batch (10+ документов) | 504 через 2 минуты | Успешно (~5-8 минут) |

## Мониторинг

### Ключевые метрики:
- **ALB Target Response Time** - должно быть < 600 секунд
- **Application Logs** - искать `[ingest_scan]` события
- **504 Errors** - должны исчезнуть после исправлений

### Алерты:
```bash
# Если видите в логах:
"Ingest scan timeout after 240 seconds"  # App timeout
"504 Gateway Time-out"                   # ALB timeout
```

## Профилактика

1. **Регулярная очистка:** Удаляйте обработанные файлы из `raw_uploads`
2. **Batch size:** Обрабатывайте не более 10 файлов за раз через API
3. **Мониторинг размера:** Файлы > 2MB обрабатываются медленнее
4. **Прямой доступ:** Используйте порт 8000 для больших операций

Эти исправления должны устранить 504 ошибки и обеспечить стабильную работу API для обработки документов.