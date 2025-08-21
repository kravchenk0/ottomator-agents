# Документация LightRAG (Index)

Этот каталог содержит всю документацию проекта, перенесённую из корня для единообразия.

## 📚 Быстрый индекс

| Документ | Описание | Категория |
|----------|----------|-----------|
| [README_IMPROVED.md](README_IMPROVED.md) | Полное описание, архитектура, сценарии | Основное |
| [QUICK_START.md](QUICK_START.md) | Минимальные шаги запуска локально | Старт |
| [LOVABLE_INTEGRATION.md](LOVABLE_INTEGRATION.md) | Встраивание в веб / фронтенд чат | Интеграция |
| [AWS_QUICK_START.md](AWS_QUICK_START.md) | 10‑минутный AWS запуск | Deployment |
| [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) | Подробный AWS гайд (Docker/Terraform) | Deployment |
| [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) | Переход со старой структуры | Миграция |
| [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md) | Сводка улучшений и выгоды | Обзор |

## 🔍 Рекомендуемая последовательность чтения
1. QUICK_START.md — быстрый старт
2. README_IMPROVED.md — понять архитектуру и возможности
3. LOVABLE_INTEGRATION.md — подключить к приложению или сайту
4. AWS_QUICK_START.md → AWS_DEPLOYMENT.md — вывести в облако
5. MIGRATION_GUIDE.md — если обновляетесь
6. IMPROVEMENTS_SUMMARY.md — посмотреть прогресс

## 🧱 Структура кода (кратко)
```
LightRAG/
├── app/
│   ├── core/      # RAGConfig, RAGManager, динамический выбор моделей
│   ├── agent/     # Pydantic AI агент (инструмент retrieval)
│   ├── api/       # FastAPI сервер (server.py)
│   └── utils/     # Логирование, диагностика, performance
├── monkey_patch_lightrag.py  # runtime patch LightRAG.get_vector_context
├── docs/          # Документация (вы здесь)
├── *.py (shim)    # Временная обратная совместимость → app.*
└── documents/ # Рабочие данные / индексы
```

## ♻️ Обратная совместимость
Shim-файлы (`common.py`, `api_server.py`, и др.) оставлены для плавной миграции. Новый код импортирует напрямую из `app.*`. Планируется график удаления в CHANGELOG (TODO).

## 🤝 Вклад
1. Форк и ветка `feature/<topic>`
2. Изменения + тест / пример
3. PR с кратким описанием и ссылками на обновлённые документы

## 🧪 Быстрые проверки
```bash
curl -s http://localhost:8000/health | jq
python rag_agent.py --question "ping"
```

## 🗺 Навигация
Если вы впервые здесь — начните с [QUICK_START.md](QUICK_START.md). Для глубины — [README_IMPROVED.md](README_IMPROVED.md). Для продакшена — AWS документы.

---
Последнее обновление индекса: обновляйте при добавлении или переименовании файлов.

## 🔐 Аутентификация и авторизация

Сервер поддерживает JWT.

Включение:
1. Установите секрет: `export RAG_JWT_SECRET=supersecret`
2. (Опционально) Срок жизни: `export RAG_JWT_EXPIRE_SECONDS=7200`
3. (Опционально) Ограничить пользователей: `export RAG_ALLOWED_USERS=alice,bob`
4. (Опционально) Ограничить роли: `export RAG_ALLOWED_ROLES=admin,user,viewer`
5. (Опционально) Роль по умолчанию: `export RAG_DEFAULT_ROLE=user`
6. (Опционально) Кастомные роли по пользователям: `export RAG_ROLE_MAP_JSON='{"alice":"admin","bob":"viewer"}'`

Получение токена:
```bash
curl -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"user":"alice","role":"admin"}'
```
Ответ: `{ "access_token": "<JWT>", "token_type": "bearer", "role": "admin" }`

Использование:
```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"ping"}'
```

Поведение:
- Если `RAG_JWT_SECRET` не задан → открытый режим (проверка не требуется)
- Если `RAG_ALLOWED_USERS` задан → только перечисленные `sub`
- Если `RAG_ALLOWED_ROLES` задан → только перечисленные роли (default / mapped / запрошенная должна входить)
- Токен содержит: `sub`, `role`, `iat`, `exp`, `iss`

Безопасность продакшена:
- Генерируйте 32+ символа секрет (или используйте менеджер секретов)
- Рассмотрите переход на RS256 (пара ключей) → расширение TODO
- Добавьте ротацию токенов (refresh) если требуется длительный доступ

Удаление доступа пользователя: обновите переменную окружения и перезапустите — существующие токены станут невалидными при проверке.
