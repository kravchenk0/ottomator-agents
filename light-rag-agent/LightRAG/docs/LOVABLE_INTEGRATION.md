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

### 5. Расширенный пример (JWT, память диалога, лимиты)

```html
<script src="/lovable_client.js"></script>
<script>
    // Инициализация клиента с JWT и (опционально) API ключом
    const client = new LightRAGClient('https://api.example.com', {
        authToken: 'YOUR_JWT_TOKEN',
        apiKey: 'OPTIONAL_API_KEY'
    });
    // Установка user_id (будет отображаться в metadata)
    client.setUserId('user_42');

    async function ask(msg) {
        const res = await client.chat(msg, {
            // conversation_id можно задать явно для связывания разных вкладок
            conversation_id: client.conversationId || 'conv_demo_1'
            // newConversation: true  // раскомментируйте чтобы форсировать новую ветку
        });
        console.log('Answer:', res.response);
        console.log('Rate limit left:', res.rate_limit_remaining,
                                'reset in (s):', res.rate_limit_reset_seconds,
                                'history messages:', res.metadata.history_messages);
    }

    // Последовательные вопросы в одном диалоге (история попадёт в prompt)
    ask('Привет, расскажи про типы виз в фризонах?');
    // позже
    setTimeout(() => ask('А требования для инвесторской?'), 2000);
</script>
```

### 6. Управление диалогами через API клиента

```javascript
// Получить список conversation_id (учитывает TTL)
const list = await client.listConversations();
console.log(list);

// Получить историю одного диалога
const hist = await client.getConversation(client.conversationId);
console.log(hist.messages);

// Удалить текущий диалог
await client.deleteConversation(client.conversationId);
client.resetConversation();

// Очистить все диалоги (in-memory на сервере)
await client.clearConversations();
```

### 7. Обработка лимита (429)

```javascript
try {
    await client.chat('Много подряд запросов');
} catch (e) {
    if (e.message.includes('429')) {
        console.warn('Достигнут лимит. Подождите перед повтором.');
    }
}
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

## 🧩 Полная инструкция интеграции в Lovable (использование всех возможностей клиента)

Ниже пошаговый рецепт как на платформе Lovable подключить LightRAG со всеми функциями: память диалога, JWT, API ключ, управление историями, индикатор набора и лимиты.

### 1. Подготовка API
1. Запустите сервер LightRAG (uvicorn / docker). Убедитесь что доступны эндпоинты `/chat`, `/conversations`, `/health`.
2. В `.env` задайте переменные (пример):
     ```bash
     OPENAI_API_KEY=sk-...            # ключ модели
     RAG_JWT_SECRET=supersecret       # включает JWT
     RAG_CONVERSATION_TTL_SECONDS=3600
     RAG_USER_RATE_LIMIT=10
     RAG_USER_RATE_WINDOW_SECONDS=3600
     RAG_MAX_HISTORY_MESSAGES=12
     ```
3. (Опционально) `RAG_API_KEYS=your_api_key` если нужен двойной слой (JWT + API key).

### 2. Получение JWT токена (если фронт не имеет серверной части)
Временный токен можно сгенерировать вручную вызовом:
```bash
curl -X POST http://<api-host>/auth/token -H 'Content-Type: application/json' -d '{"user":"demo"}'
```
В продакшене лучше выдавать токен из вашего backend после аутентификации пользователя.

### 3. Подключение скрипта в Lovable
Загрузите `lovable_client.js` на ваш домен / CDN и вставьте в HTML блок Lovable:
```html
<script src="https://your-cdn.com/lovable_client.js"></script>
```

### 4. Базовая HTML разметка для чата
```html
<div class="chat-wrapper">
    <div class="lightrag-chat-container"></div>
    <input class="lovable-chat-input" placeholder="Задайте вопрос..." />
    <button id="reset-conv">Новый диалог</button>
    <button id="show-history">История</button>
    <pre id="history-dump" style="max-height:200px;overflow:auto;"></pre>
    <div id="rate-info" style="font-size:12px;color:#555;margin-top:4px;"></div>
    <div id="error-box" style="color:red;"></div>
    <div id="loader" style="display:none;font-size:12px;">Typing...</div>
</div>
```

### 5. Инициализация клиента (JWT + API key)
```html
<script>
    const client = new LightRAGClient('https://api.example.com', {
        authToken: 'JWT_TOKEN_HERE',      // внедрите динамически из вашего бекенда
        apiKey: 'OPTIONAL_API_KEY'        // если включено на сервере
    }).setUserId('user_123');

    // Автогенерация первого conversation_id при первом сообщении
    const integration = new LovableLightRAGIntegration('https://api.example.com', {
        autoGenerateConversationId: true,
        showTypingIndicator: true
    });
</script>
```

### 6. Отправка сообщений и использование памяти
Сообщения с одинаковым `conversation_id` автоматически накапливают контекст; сервер встраивает последние N сообщений.

Принудительно начать новый диалог:
```javascript
await client.chat('Новый контекст', { newConversation: true });
```

### 7. Отображение метаданных (лимиты и история)
В ответе `/chat` приходит `metadata`:
```jsonc
{
    "metadata": {
        "processing_time": 1.23,
        "history_messages": 5,
        "rate_limit_remaining": 7,
        "rate_limit_reset_seconds": 3200
    }
}
```
Можно обновлять UI:
```javascript
function renderRate(meta){
    document.getElementById('rate-info').textContent = `Осталось: ${meta.rate_limit_remaining} | Reset через: ${meta.rate_limit_reset_seconds}s`;
}
```

### 8. Управление диалогами (API клиента)
```javascript
// Список активных диалогов
const list = await client.listConversations();
// История конкретного
const hist = await client.getConversation(client.conversationId);
// Удалить один
await client.deleteConversation(client.conversationId);
// Очистить все
await client.clearConversations();
// Сбросить локально
client.resetConversation();
```

### 9. Обработка ошибок и 429
```javascript
async function safeAsk(q){
    try {
        const r = await client.chat(q);
        if(r.metadata) renderRate(r.metadata);
        return r;
    } catch(e){
        if(e.message.includes('429')){
            document.getElementById('error-box').textContent = 'Достигнут лимит. Подождите сброс окна.';
        } else {
            document.getElementById('error-box').textContent = 'Ошибка: ' + e.message;
        }
    }
}
```

### 10. Индикатор набора
Встроен в `LovableLightRAGIntegration` — при `showTypingIndicator: true` автоматически показывает `<div class="typing-indicator">`.
Если нужно вручную:
```javascript
integration.showTypingIndicator();
// ...
integration.hideTypingIndicator();
```

### 11. Рекомендации для продакшена
| Задача | Рекомендация |
|--------|--------------|
| Безопасность токена | Выдавать JWT из backend, не хранить в публичном коде |
| CORS | Ограничить `allow_origins` конкретным доменом |
| Множественные воркеры | In-memory память не шарится → для горизонтального скейла использовать Redis (будущая доработка) |
| Ошибки сети | Ретраи (экспоненциальная задержка) для одиночных сбоев |
| UX | Отображать счётчик лимита и кнопку «Новый диалог» |

### 12. Быстрый полнофункциональный пример
```html
<div class="lightrag-chat-container" style="border:1px solid #ddd;padding:8px;height:300px;overflow:auto"></div>
<input class="lovable-chat-input" placeholder="Ваш вопрос..." />
<button id="new-conv">Новый диалог</button>
<div id="rate-info" style="font-size:12px;color:#555;margin-top:4px;"></div>
<div id="error-box" style="color:red;"></div>
<script src="/lovable_client.js"></script>
<script>
    const client = new LightRAGClient('https://api.example.com', { authToken: 'JWT_TOKEN' }).setUserId('demo-user');
    new LovableLightRAGIntegration('https://api.example.com', { autoGenerateConversationId: true, showTypingIndicator: true });
    document.getElementById('new-conv').onclick = () => { client.resetConversation(); };
</script>
```

### 13. Диагностика
| Симптом | Проверка |
|---------|----------|
| Всегда новый conversation_id | Убедитесь, что отправляете то же поле `conversation_id` (не опечатка) |
| Лимит сразу 0 | Пользователь сделал > лимита в окне, проверьте `rate_limit_reset_seconds` |
| История не растёт | Возможен новый conversation_id или перезапуск сервера (in-memory) |
| 401 | Проверить JWT / срок действия |

Готово: теперь интерфейс Lovable использует все возможности клиента.


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
