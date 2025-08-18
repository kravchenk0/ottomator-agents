# 🚀 Быстрый старт: LightRAG + Lovable

## ⚡ За 5 минут

### 1. Запустите API сервер
```bash
cd LightRAG
./start_api.sh
```

### 2. Откройте тестовую страницу
Откройте `lovable_integration_example.html` в браузере

### 3. Протестируйте интеграцию
- Отправьте сообщение в чат
- Вставьте документ
- Проверьте поиск

## 🔧 Что уже готово

✅ **API сервер** - FastAPI на порту 8000  
✅ **JavaScript клиент** - `lovable_client.js`  
✅ **HTML пример** - `lovable_integration_example.html`  
✅ **Конфигурация** - `config.yaml`  
✅ **Автозапуск** - `start_api.sh`  

## 🌐 Endpoints

- **Чат**: `POST /chat`
- **Документы**: `POST /documents/insert`
- **Поиск**: `GET /documents/search`
- **Конфигурация**: `GET/POST /config`
- **Здоровье**: `GET /health`

## 💻 Интеграция в ваш сайт

### Добавьте в HTML:
```html
<script src="lovable_client.js"></script>
<form class="lovable-form">
    <input name="message" placeholder="Ask me anything..." required>
    <button type="submit">Send</button>
</form>
```

### Инициализируйте:
```javascript
new LovableLightRAGIntegration('http://localhost:8000');
```

## 🚨 Важно

1. **Создайте `.env`** с вашим OpenAI API ключом
2. **Настройте CORS** для production
3. **Добавьте аутентификацию** для безопасности

## 📖 Подробная документация

См. `LOVABLE_INTEGRATION.md` для полного руководства.
