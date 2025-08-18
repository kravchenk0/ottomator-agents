## Перемещено

Полный документ: `docs/LOVABLE_INTEGRATION.md`.

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

### Основные endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Проверка состояния сервера |
| `/chat` | POST | Основной чат endpoint |
| `/config` | GET/POST | Управление конфигурацией |
| `/documents/insert` | POST | Вставка документов |
| `/documents/search` | GET | Поиск по документам |

### Документация API

После запуска сервера, откройте: `http://localhost:8000/docs`

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

### 4. Или используйте простой клиент

```javascript
const client = new LightRAGClient('http://localhost:8000');

// Отправить сообщение
const response = await client.chat("Your question here");
console.log(response.response);
```

## 🔧 Настройка для production

### 1. Обновите CORS настройки

В `api_server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # Ваш домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Настройте rate limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/chat")
@limiter.limit("10/minute")  # 10 запросов в минуту
async def chat_endpoint(request: ChatRequest):
    # ... ваш код
```

### 3. Добавьте аутентификацию

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Проверьте токен
    if not verify_token(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return credentials.credentials

@app.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: str = Depends(get_current_user)
):
    # ... ваш код
```

## 📱 Примеры использования

### Простая форма чата

```html
<!DOCTYPE html>
<html>
<head>
    <script src="lovable_client.js"></script>
</head>
<body>
    <form class="lovable-form">
        <input type="text" name="message" placeholder="Ask me anything..." required>
        <button type="submit">Send</button>
    </form>
    
    <script>
        new LovableLightRAGIntegration('http://localhost:8000');
    </script>
</body>
</html>
```

### Кастомный чат интерфейс

```javascript
const client = new LightRAGClient('http://localhost:8000');

async function sendMessage() {
    const message = document.getElementById('messageInput').value;
    
    try {
        const response = await client.chat(message, {
            system_prompt: "You are a helpful assistant for our website.",
            user_id: "user123"
        });
        
        displayResponse(response.response);
    } catch (error) {
        console.error('Error:', error);
    }
}
```

### Вставка документов

```javascript
// Вставьте документ в RAG систему
const result = await client.insertDocument(
    "Your document content here",
    "document_id_123"
);

console.log('Document inserted:', result.document_id);
```

## 🔒 Безопасность

### 1. Ограничьте доступ

```python
# В api_server.py
ALLOWED_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### 2. Добавьте API ключи

```python
async def verify_api_key(api_key: str = Header(None)):
    if api_key != "your-secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

@app.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key)
):
    # ... ваш код
```

### 3. Валидация входных данных

```python
from pydantic import validator

class ChatRequest(BaseModel):
    message: str
    
    @validator('message')
    def validate_message(cls, v):
        if len(v.strip()) < 1:
            raise ValueError('Message cannot be empty')
        if len(v) > 1000:
            raise ValueError('Message too long')
        return v.strip()
```

## 📊 Мониторинг и логирование

### 1. Логирование запросов

```python
import logging
from datetime import datetime

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = datetime.now() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {duration.total_seconds():.2f}s"
    )
    
    return response
```

### 2. Метрики производительности

```python
from prometheus_client import Counter, Histogram
import time

request_counter = Counter('chat_requests_total', 'Total chat requests')
request_duration = Histogram('chat_request_duration_seconds', 'Chat request duration')

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    start_time = time.time()
    request_counter.inc()
    
    try:
        result = await process_chat(request)
        return result
    finally:
        request_duration.observe(time.time() - start_time)
```

## 🚀 Deployment

### 1. Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Systemd service

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

### 3. Nginx reverse proxy

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

### 1. Тест API endpoints

```bash
# Проверка здоровья
curl http://localhost:8000/health

# Тест чата
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'
```

### 2. Тест JavaScript клиента

Откройте `lovable_integration_example.html` в браузере для тестирования всех функций.

## 🆘 Troubleshooting

### Частые проблемы

1. **CORS ошибки**: Проверьте настройки `allow_origins` в middleware
2. **Таймауты**: Увеличьте `timeout` в uvicorn настройках
3. **Память**: Мониторьте использование памяти при обработке больших документов
4. **API ключи**: Убедитесь, что OpenAI API ключ правильно установлен

### Логи

```bash
# Запуск с подробными логами
uvicorn api_server:app --host 0.0.0.0 --port 8000 --log-level debug

# Просмотр логов
tail -f lightrag.log
```

<!-- Контент перенесён в docs/LOVABLE_INTEGRATION.md -->