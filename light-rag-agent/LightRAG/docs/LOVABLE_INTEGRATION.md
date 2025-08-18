# 🚀 LightRAG + Lovable Integration

Это руководство поможет вам интегрировать LightRAG с вашим сайтом Lovable для создания умного чат-бота с RAG возможностями.

## 📋 Что вы получите

- **API сервер** для интеграции с веб-формами
- **JavaScript клиент** для простой интеграции
- **Готовые HTML формы** для тестирования
- **Поддержка чата** с контекстом
- **Управление документами** через API

## 🛠️ Установка и запуск

### 1. Установите зависимости

```bash
cd LightRAG
pip install -r requirements.txt
```

### 2. Настройте переменные окружения

Создайте `.env` файл:

```bash
echo "OPENAI_API_KEY=your_api_key_here" > .env
```

### 3. Запустите API сервер

```bash
python api_server.py
```

Сервер будет доступен по адресу: `http://localhost:8000`

## 🌐 API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Проверка состояния сервера |
| `/chat` | POST | Основной чат endpoint |
| `/config` | GET/POST | Управление конфигурацией |
| `/documents/insert` | POST | Вставка документов |
| `/documents/search` | GET | Поиск по документам |

После запуска сервера откройте: `http://localhost:8000/docs`

## 💻 Интеграция с Lovable

### 1. Добавьте JavaScript клиент

```html
<script src="https://your-domain.com/lovable_client.js"></script>
```

### 2. Создайте форму чата

```html
<form class="lovable-form">
    <textarea name="message" placeholder="Ask me anything..." required></textarea>
    <button type="submit">Send</button>
</form>
```

### 3. Инициализируйте интеграцию

```javascript
const integration = new LovableLightRAGIntegration('http://localhost:8000', {
    autoGenerateConversationId: true,
    showTypingIndicator: true
});
```

### 4. Простой клиент

```javascript
const client = new LightRAGClient('http://localhost:8000');
const response = await client.chat("Your question here");
console.log(response.response);
```

## 🔧 Production настройки

### CORS
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # Ваш домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Rate limiting
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/chat")
@limiter.limit("10/minute")
async def chat_endpoint(request: ChatRequest):
    ...
```

### Аутентификация
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not verify_token(credentials.credentials):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    return credentials.credentials
```

## 📱 Примеры использования

Минимальная HTML страница уже в репозитории: `lovable_integration_example.html`.

## 🔒 Безопасность

- Ограничьте `allow_origins`
- Используйте API ключи / токены
- Валидация длины входного текста

## 📊 Мониторинг и логирование

Пример middleware логирования запросов и Prometheus метрик (Counter/Histogram) можно адаптировать из документации.

## 🚀 Deployment

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### systemd service
```ini
[Unit]
Description=LightRAG API Server
After=network.target

[Service]
Type=simple
User=lightrag
WorkingDirectory=/opt/lightrag
Environment=PATH=/opt/lightrag/venv/bin
ExecStart=/opt/lightrag/venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx reverse proxy
```nginx
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🧪 Тестирование

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"message":"Hello"}'
```

## 🆘 Troubleshooting

| Проблема | Диагностика | Решение |
|----------|------------|---------|
| CORS | Браузерная консоль | Обновить allow_origins |
| 401 | Ответ API | Проверить токен/ключ |
| Таймаут | Логи uvicorn | Увеличить timeout или оптимизировать обработку |
| Нет ответа OpenAI | Логи | Проверить OPENAI_API_KEY |

## 🎯 Следующие шаги

1. Production окружение
2. Мониторинг и алерты
3. Кэширование популярных запросов
4. WebSocket real-time чат
5. Аналитика (GA / Mixpanel)
