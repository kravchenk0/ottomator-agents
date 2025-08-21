"""FastAPI server (migrated from root api_server.py)."""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import Header, status, FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import asyncio
from pathlib import Path

from app.core import RAGManager, RAGConfig, get_default_config
try:  # автозагрузка .env если присутствует (локальная разработка)
    from dotenv import load_dotenv  # type: ignore
    # Можно переопределить путь переменной RAG_DOTENV_FILE
    _dotenv_path = os.getenv("RAG_DOTENV_FILE", ".env")
    if os.path.isfile(_dotenv_path):
        load_dotenv(_dotenv_path)
except Exception:
    pass
from app.utils.ingestion import scan_directory, list_index, ingest_files
from app.utils.auth import require_jwt, issue_token

try:  # гибкий импорт логгера
    from app.logger import setup_logger  # type: ignore
except Exception:  # noqa: BLE001
    def setup_logger(name: str, level: str = "INFO"):
        import logging as _logging
        _logging.basicConfig(level=getattr(_logging, level.upper(), _logging.INFO))
        return _logging.getLogger(name)
from app.utils.auth import require_jwt, issue_token
from pydantic import BaseModel as _BM


class TokenRequest(_BM):
    user: str
    role: str | None = None
    # future: extra claims


class TokenResponse(_BM):
    access_token: str
    token_type: str = "bearer"
    role: str | None = None


# ---------------- Security (API Key) ----------------
_API_KEYS: set[str] | None = None


def _load_api_keys() -> set[str] | None:
    keys = os.getenv("RAG_API_KEYS") or os.getenv("RAG_API_KEY")
    if not keys:
        return None  # auth disabled
    return {k.strip() for k in keys.split(",") if k.strip()}


def api_keys_enabled() -> bool:
    global _API_KEYS
    if _API_KEYS is None:
        _API_KEYS = _load_api_keys()
    return bool(_API_KEYS)


def require_api_key(x_api_key: str | None = Header(default=None)):
    if not api_keys_enabled():  # open mode
        return True
    if not x_api_key or x_api_key not in _API_KEYS:  # type: ignore[arg-type]
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return True


logger = setup_logger("api_server", "INFO")

app = FastAPI(
    title="LightRAG API Server",
    description=(
        "REST API для интеграции с движком LightRAG: чат поверх встроенного RAG, загрузка/ингест документов, "
        "поиск и администрирование. Большинство операций требуют JWT Bearer токен (см. /auth/token)."
    ),
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_manager: Optional[RAGManager] = None
system_prompt: Optional[str] = None
_model_self_test: Dict[str, Any] | None = None
_create_agent = None  # type: ignore
_RAGDeps = None  # type: ignore

# ---- In-memory conversation storage (этап 1) ----
# conversations[conversation_id] = list[ {"role": "user"|"assistant", "content": str} ]
conversations: Dict[str, List[Dict[str, str]]] = {}
conversation_meta: Dict[str, Dict[str, float]] = {}  # {id: {created, last_activity}}
MAX_HISTORY_MESSAGES = int(os.getenv("RAG_MAX_HISTORY_MESSAGES", "12"))  # обрезаем глубину
CONVERSATION_TTL_SECONDS = int(os.getenv("RAG_CONVERSATION_TTL_SECONDS", "3600"))  # 1 час по умолчанию
USER_RATE_LIMIT = int(os.getenv("RAG_USER_RATE_LIMIT", "10"))  # 10 запросов / окно
USER_RATE_WINDOW_SECONDS = int(os.getenv("RAG_USER_RATE_WINDOW_SECONDS", "3600"))
user_rate: Dict[str, Dict[str, float]] = {}  # {user_id: {count, window_start}}

def _enforce_user_rate_limit(user_id: str):
    now = time.time()
    data = user_rate.get(user_id)
    if not data:
        user_rate[user_id] = {"count": 1, "window_start": now}
        return
    window_start = data["window_start"]
    if now - window_start >= USER_RATE_WINDOW_SECONDS:
        # reset window
        user_rate[user_id] = {"count": 1, "window_start": now}
        return
    if data["count"] >= USER_RATE_LIMIT:
        remaining = int(USER_RATE_WINDOW_SECONDS - (now - window_start))
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {USER_RATE_LIMIT} requests per {USER_RATE_WINDOW_SECONDS//60}m window. Retry in {remaining}s")
    data["count"] += 1

def _rate_limit_remaining(user_id: str) -> int:
    data = user_rate.get(user_id)
    if not data:
        return USER_RATE_LIMIT
    if time.time() - data["window_start"] >= USER_RATE_WINDOW_SECONDS:
        return USER_RATE_LIMIT
    return max(0, USER_RATE_LIMIT - int(data["count"]))

def _rate_limit_reset_in(user_id: str) -> int:
    data = user_rate.get(user_id)
    now = time.time()
    if not data:
        return USER_RATE_WINDOW_SECONDS
    elapsed = now - data["window_start"]
    if elapsed >= USER_RATE_WINDOW_SECONDS:
        return 0
    return int(USER_RATE_WINDOW_SECONDS - elapsed)

def cleanup_expired_conversations() -> int:
    now = time.time()
    expired: List[str] = []
    for cid, meta in list(conversation_meta.items()):
        if now - meta.get("last_activity", meta.get("created", now)) > CONVERSATION_TTL_SECONDS:
            expired.append(cid)
    for cid in expired:
        conversations.pop(cid, None)
        conversation_meta.pop(cid, None)
    return len(expired)

def build_history_context(messages: List[Dict[str, str]], include_last_user: bool = False) -> str:
    """Собирает текстовую историю для встраивания в system_prompt.

    Берём последние MAX_HISTORY_MESSAGES сообщений. По умолчанию исключаем
    последнее пользовательское сообщение (оно приходит отдельным prompt'ом в agent.run).
    Форматируем строки вида "User: ..." / "Assistant: ...".
    """
    if not messages:
        return ""
    relevant = messages[-MAX_HISTORY_MESSAGES:]
    if not include_last_user and relevant and relevant[-1].get("role") == "user":
        relevant = relevant[:-1]
    lines: List[str] = []
    for m in relevant:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        prefix = "User" if role == "user" else "Assistant"
        lines.append(f"{prefix}: {content}")
    return "\n".join(lines)

# Простой performance logger fallback (используется чатом)
class _PerfLogger:
    def __init__(self):
        self._timers: Dict[str, float] = {}
    def start_timer(self, name: str):
        import time
        self._timers[name] = time.time()
    def end_timer(self, name: str):
        import time
        if name in self._timers:
            self._timers[name] = time.time() - self._timers[name]
    def log_metric(self, *_, **__):
        pass
    def get_summary(self):
        return self._timers

performance_logger = _PerfLogger()


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    # Частая опечатка: клиент мог отправить 'conversations'. Поддержим как deprecated alias.
    conversations: Optional[str] = Field(default=None, description="Deprecated: use conversation_id")
    user_id: Optional[str] = None
    # system_prompt поле удалено из использования (оставим для обратной совместимости, но игнорируем)
    system_prompt: Optional[str] = None  # deprecated: игнорируется
    model: Optional[str] = None  # запрошенная модель (опционально)


class ChatSource(BaseModel):
    file_path: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    sources: Optional[List[ChatSource]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None  # текст ошибки, если запрос завершился неуспешно


class ConversationHistory(BaseModel):
    conversation_id: str
    messages: List[Dict[str, str]]


class ConversationList(BaseModel):
    conversations: List[str]


class ConversationClearResult(BaseModel):
    status: str
    cleared: int
    conversations_remaining: int


class HealthResponse(BaseModel):
    status: str
    rag_status: str
    version: str
    model_ok: Optional[bool] = None
    model_used: Optional[str] = None
    model_tried: Optional[list] = None
    model_error: Optional[str] = None
    temperature_auto_adjusted: Optional[bool] = None
    temperature_current: Optional[str] = None
    temperature_rejected_models: Optional[list] = None
    patch_applied: Optional[bool] = None


class ConfigRequest(BaseModel):
    working_dir: Optional[str] = None
    system_prompt: Optional[str] = None
    rerank_enabled: Optional[bool] = None


# ---- Ingestion / Index models ----
class IngestionDetail(BaseModel):
    file: str
    status: str
    reason: Optional[str] = None
    error: Optional[str] = None


class IngestionResult(BaseModel):
    status: str  # e.g. "ok" | "no_files"
    directory: Optional[str] = None
    added: int
    skipped: int
    total_indexed: int
    details: List[IngestionDetail]


class IndexEntry(BaseModel):
    file: str
    hash: Optional[str] = None
    size: Optional[int] = None


class IndexListResponse(BaseModel):
    status: str
    index: List[IndexEntry]


class DeleteRequest(BaseModel):
    files: List[str]


class DeleteResult(BaseModel):
    status: str
    removed: int
    not_found: List[str]
    total_indexed: int


class ClearResult(BaseModel):
    status: str
    cleared: bool
    total_indexed: int


class InsertResult(BaseModel):
    status: str
    message: str
    document_id: str


class SearchResultItem(BaseModel):
    # структура неизвестна детально: оставляем гибкие поля
    data: Optional[str] = None
    score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    query: str
    limit: int
    results: List[Any]  # оставляем Any, т.к. движок может вернуть сложную структуру


async def get_rag_manager() -> RAGManager:
    if rag_manager is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    return rag_manager


@app.on_event("startup")
async def startup_event():  # noqa: D401
    global rag_manager, system_prompt, _model_self_test, _create_agent, _RAGDeps
    try:
        logger.info("Initializing RAG system...")
        if not os.getenv("OPENAI_API_KEY"):
            if os.getenv("ALLOW_START_WITHOUT_OPENAI_KEY", "0").lower() in {"1", "true", "yes"}:
                logger.warning("OPENAI_API_KEY not set. Starting degraded mode.")
                rag_manager = None
            elif os.getenv("FAST_FAILLESS_INIT", "0").lower() in {"1", "true", "yes"}:
                logger.error("OPENAI_API_KEY missing, FAST_FAILLESS_INIT allows continuing.")
                rag_manager = None
            else:
                raise ValueError("OPENAI_API_KEY environment variable not set")
        else:
            config = get_default_config()
            rag_manager = RAGManager(config)
            await rag_manager.initialize()
            from app.agent.rag_agent import create_agent as _ca, RAGDeps as _rd
            _create_agent, _RAGDeps = _ca, _rd
        # Базовый системный промпт: из DEFAULT_SYSTEM_PROMPT агента, с опциональным переопределением
        try:
            from app.agent.rag_agent import DEFAULT_SYSTEM_PROMPT as _DSP
            system_prompt = _DSP
        except Exception:  # noqa: BLE001
            system_prompt = "You are a domain assistant. Use retrieve before answering."
        # Если задан путь к файлу с промптом — читаем и заменяем
        sp_file = os.getenv("RAG_SYSTEM_PROMPT_FILE")
        if sp_file and os.path.isfile(sp_file):
            try:
                with open(sp_file, 'r', encoding='utf-8') as f:
                    system_prompt = f.read()
                logger.info(f"Loaded system prompt from {sp_file} (len={len(system_prompt)})")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to load RAG_SYSTEM_PROMPT_FILE '{sp_file}': {e}")
        if os.getenv("OPENAI_API_KEY"):
            try:
                from app.utils.diagnostics import self_test_model
                _model_self_test = await self_test_model()
                if _model_self_test.get("ok"):
                    logger.info(f"Model self-test ok: {_model_self_test.get('model')}")
                else:
                    logger.warning(f"Model self-test failed: {_model_self_test}")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Model self-test error: {e}")
                _model_self_test = {"ok": False, "error": str(e), "tried": []}
        # Auto-ingest on startup if configured
        try:
            auto_dir = os.getenv("RAG_INGEST_DIR")
            auto_scan = os.getenv("RAG_AUTO_INGEST_ON_START", "1").lower() in {"1", "true", "yes"}
            if rag_manager and auto_scan and auto_dir and os.path.isdir(auto_dir):
                logger.info(f"Auto-ingest scan on startup: {auto_dir}")
                rag = await rag_manager.get_rag()
                files = scan_directory(auto_dir)
                if files:
                    from app.utils.ingestion import ingest_files as _if
                    await _if(rag, files, rag_manager.config.working_dir)
                    logger.info(f"Auto-ingested {len(files)} candidate files (filtered by change/hash)")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Auto-ingest on startup failed: {e}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed init: {e}")
        if os.getenv("FAST_FAILLESS_INIT", "0").lower() not in {"1", "true", "yes"}:
            raise


@app.get(
    "/",
    summary="Ping / корневой статус (требует JWT)",
    description="Простой ping для проверки доступности сервера. Теперь закрыт и требует JWT Bearer."
)
async def root(_claims=Depends(require_jwt)):
    return {"status": "ok", "rag_initialized": rag_manager is not None }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Расширенный health-check (открыт)",
    description="Проверка статуса RAG, версии, модели и т.д. Открыт для ALB и мониторинга."
)
async def health_check():
    rag_status = "healthy" if rag_manager is not None else "unhealthy"
    ms = _model_self_test or {}
    # Заглушка температурной адаптации (если модуль отсутствует)
    def get_temperature_adjustment_state():  # type: ignore
        return {"auto_adjusted": False, "current_temperature": None, "rejected_models": []}
    def is_patch_applied():  # type: ignore
        return True
    temp_state = get_temperature_adjustment_state()
    return HealthResponse(
        status="healthy",
        rag_status=rag_status,
        version="1.0.0",
        model_ok=ms.get("ok"),
        model_used=ms.get("model"),
        model_tried=ms.get("tried"),
        model_error=ms.get("error") if ms and not ms.get("ok") else None,
        temperature_auto_adjusted=temp_state.get("auto_adjusted"),
        temperature_current=temp_state.get("current_temperature"),
        temperature_rejected_models=temp_state.get("rejected_models"),
        patch_applied=is_patch_applied(),
    )


@app.get(
    "/alb-health",
    summary="Простой health для ALB (без авторизации)",
    description="Минимальный открытый health эндпоинт для Target Group ALB. Возвращает только status и версию."
)
async def alb_health():
    return {"status": "ok", "version": "1.0.0"}

@app.get(
    "/health-secure",
    response_model=HealthResponse,
    summary="Закрытый health-check (JWT)",
    description="Та же информация что /health, но требует JWT (для внутренних проверок)."
)
async def health_secure(_claims=Depends(require_jwt)):
    return await health_check()


@app.post(
    "/chat",
    response_model=ChatResponse,
    summary="Задать вопрос / продолжить диалог",
    description=(
        "Главная точка взаимодействия с RAG. Принимает JSON {message, optional conversation_id, model}. "
        "system_prompt в запросе игнорируется (зафиксирован глобально). Возвращает ответ модели, id сессии и источники. Требует JWT Bearer."
    ),
)
async def chat_endpoint(
    request: ChatRequest,
    rag_mgr: RAGManager = Depends(get_rag_manager),
    _claims=Depends(require_jwt),
):
    performance_logger.start_timer("chat_request")
    conv_id = request.conversation_id or request.conversations or f"conv_{hash(request.message) % 10000}"
    if not request.message or not request.message.strip():
        performance_logger.end_timer("chat_request")
        raise HTTPException(status_code=400, detail="'message' is required and cannot be empty")

    # --- Conversation memory (этап 2) ---
    # Очистка просроченных диалогов (ленивая)
    cleanup_expired_conversations()
    # User id для лимитов
    user_id = request.user_id or (_claims.get("sub") if isinstance(_claims, dict) else None) or "anonymous"
    # Rate limit enforcement
    _enforce_user_rate_limit(user_id)
    msgs = conversations.setdefault(conv_id, [])  # существующая или новая история
    meta = conversation_meta.setdefault(conv_id, {"created": time.time(), "last_activity": time.time()})
    # Добавляем текущий user message в хвост
    msgs.append({"role": "user", "content": request.message})
    # При необходимости ограничиваем размер хранимой истории (мягкая обрезка)
    if len(msgs) > MAX_HISTORY_MESSAGES * 3:
        del msgs[: len(msgs) - MAX_HISTORY_MESSAGES * 2]
    # Формируем history_context (исключая только что добавленное user сообщение)
    history_context = build_history_context(msgs, include_last_user=False)
    if history_context:
        effective_prompt = f"{system_prompt}\n\nConversation so far:\n{history_context}\n---"
    else:
        effective_prompt = system_prompt
    current_prompt = effective_prompt  # будет передан агенту
    global _create_agent, _RAGDeps
    try:
        # (re)init agent factory if needed
        if _create_agent is None or _RAGDeps is None:
            if os.getenv("OPENAI_API_KEY"):
                from app.agent.rag_agent import create_agent as _ca, RAGDeps as _rd
                _create_agent, _RAGDeps = _ca, _rd
            else:
                return ChatResponse(
                    response="",
                    conversation_id=conv_id,
                    error="RAG/Agent unavailable: no OPENAI_API_KEY",
                    metadata={"stage": "init"},
                )
        # создаём агент: не перепутать model/system_prompt (используем именованные аргументы)
        agent = _create_agent(model=request.model, system_prompt=current_prompt)
        deps = _RAGDeps(rag_manager=rag_mgr)
        try:
            result = await agent.run(request.message, deps=deps)
            try:
                sources = getattr(result, 'metadata', {}).get('sources') if getattr(result, 'metadata', None) else None
            except Exception:  # noqa: BLE001
                sources = None
            # Добавляем assistant ответ в историю
            msgs.append({"role": "assistant", "content": result.data})
            meta["last_activity"] = time.time()
            performance_logger.end_timer("chat_request")
            performance_logger.log_metric("messages_processed", 1, "msg")
            return ChatResponse(
                response=result.data,
                conversation_id=conv_id,
                sources=sources,
                metadata={
                    "user_id": user_id,
                    "model": request.model or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL"),
                    "system_prompt_used": (current_prompt[:100] + "...") if current_prompt and len(current_prompt) > 100 else current_prompt,
                    "processing_time": performance_logger.get_summary().get("chat_request", 0),
                    "history_messages": len(msgs),
                    "history_context_chars": len(history_context) if history_context else 0,
                    "rate_limit_remaining": _rate_limit_remaining(user_id),
                    "rate_limit_reset_seconds": _rate_limit_reset_in(user_id),
                },
            )
        except Exception as run_err:  # noqa: BLE001
            performance_logger.end_timer("chat_request")
            err_str = str(run_err)
            # Попытка классифицировать
            if "model_not_found" in err_str or "does not exist" in err_str:
                code = "MODEL_NOT_FOUND"
            elif "rate limit" in err_str.lower():
                code = "RATE_LIMIT"
            else:
                code = "EXECUTION_ERROR"
            return ChatResponse(
                response="",
                conversation_id=conv_id,
                error=f"{code}: {err_str}",
                metadata={
                    "user_id": user_id,
                    "model": request.model or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL"),
                    "processing_time": performance_logger.get_summary().get("chat_request", 0),
            "history_messages": len(msgs),
            "history_context_chars": len(history_context) if history_context else 0,
                    "rate_limit_remaining": _rate_limit_remaining(user_id),
                    "rate_limit_reset_seconds": _rate_limit_reset_in(user_id),
                },
            )
    except Exception as outer:  # noqa: BLE001
        performance_logger.end_timer("chat_request")
        return ChatResponse(
            response="",
            conversation_id=conv_id,
            error=f"INIT_ERROR: {outer}",
        metadata={"stage": "outer", "history_messages": len(conversations.get(conv_id, []))},
        )


@app.post(
    "/config",
    response_model=Dict[str, Any],
    summary="Обновить конфигурацию RAG",
    description="Изменить рабочую директорию, system prompt и флаг rerank_enabled. Перезапускает менеджер при смене working_dir. Требует JWT Bearer."
)
async def update_config(request: ConfigRequest, _claims=Depends(require_jwt)):
    global rag_manager, system_prompt
    try:
        if request.working_dir:
            config = RAGConfig(working_dir=request.working_dir)
            nm = RAGManager(config)
            await nm.initialize()
            rag_manager = nm
    # Игнорируем попытку сменить system_prompt через API (зафиксирован на старте)
        if request.rerank_enabled is not None and rag_manager:
            rag_manager.config.rerank_enabled = request.rerank_enabled
        return {
            "status": "success",
            "message": "Configuration updated successfully",
            "current_config": {
                "working_dir": rag_manager.config.working_dir if rag_manager else None,
                "system_prompt": system_prompt,
                "rerank_enabled": rag_manager.config.rerank_enabled if rag_manager else None,
            },
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {e}")


@app.get(
    "/config",
    summary="Текущая конфигурация",
    description="Получение текущих параметров RAG (working_dir, system_prompt, rerank_enabled). Требует JWT Bearer."
)
async def get_config(_claims=Depends(require_jwt)):
    return {
        "working_dir": rag_manager.config.working_dir if rag_manager else None,
        "system_prompt": system_prompt,
        "rerank_enabled": rag_manager.config.rerank_enabled if rag_manager else None,
    }


@app.post(
    "/documents/insert",
    summary="Быстрая вставка текста",
    description="Асинхронно добавляет один текстовый документ напрямую в индекс без загрузки файла. Требует JWT Bearer.",
    response_model=InsertResult
)
async def insert_document(content: str, document_id: Optional[str] = None, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    try:
        rag = await rag_mgr.get_rag()
        await rag.ainsert(content)
        return {"status": "success", "message": "Document inserted successfully", "document_id": document_id or f"doc_{hash(content) % 10000}"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to insert document: {e}")


@app.get(
    "/documents/search",
    summary="Поиск по индексированным документам",
    description="Выполняет смешанный (mode=mix) запрос к RAG индексу. Возвращает сырые результаты движка. Требует JWT Bearer.",
    response_model=SearchResponse
)
async def search_documents(query: str, limit: int = 5, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    try:
        rag = await rag_mgr.get_rag()
        results = await rag.aquery(query, param={"mode": "mix"})
        return {"query": query, "results": results, "limit": limit}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to search documents: {e}")


# Ingestion support
_ingest_lock = asyncio.Lock()


@app.post(
    "/documents/upload",
    summary="Загрузка файла",
    description="Загружает файл (multipart/form-data) в raw_uploads и опционально сразу выполняет ingest (парсинг + индексирование). Требует JWT Bearer.",
    response_model=Dict[str, Any]
)
async def upload_document(file: UploadFile = File(...), ingest: bool = True, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    rag = await rag_mgr.get_rag()
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    raw_dir = Path(rag_mgr.config.working_dir) / "raw_uploads"
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / file.filename
    dest.write_bytes(content_bytes)
    result = None
    if ingest:
        async with _ingest_lock:
            result = await ingest_files(rag, [dest], rag_mgr.config.working_dir)
    return {"status": "ok", "stored_as": str(dest), "ingestion": result}


@app.post(
    "/documents/ingest/scan",
    summary="Скан + ingest директории",
    description="Сканирует директорию (по умолчанию RAG_INGEST_DIR) и индексирует новые/обновлённые файлы. Требует JWT Bearer.",
    response_model=IngestionResult
)
async def ingest_scan(directory: str | None = None, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    rag = await rag_mgr.get_rag()
    # Логика выбора директории:
    # 1) Явно передана параметром
    # 2) Переменная окружения RAG_INGEST_DIR
    # 3) Папка raw_uploads внутри working_dir (загруженные файлы)
    # 4) Фолбэк /data/ingest (исторический)
    scan_dir = directory or os.getenv("RAG_INGEST_DIR") or str(Path(rag_mgr.config.working_dir) / "raw_uploads") or "/data/ingest"
    files = scan_directory(scan_dir)
    if not files:
        # При отсутствии файлов всё равно возвращаем валидную структуру модели
        from app.utils.ingestion import load_index  # локальный импорт чтобы избежать циклов
        idx_len = len(load_index(rag_mgr.config.working_dir))
        return {
            "status": "no_files",
            "directory": scan_dir,
            "added": 0,
            "skipped": 0,
            "total_indexed": idx_len,
            "details": [],
        }
    async with _ingest_lock:
        result = await ingest_files(rag, files, rag_mgr.config.working_dir)
    return {"status": "ok", "directory": scan_dir, **result}


@app.get(
    "/documents/ingest/list",
    summary="Список индексированных документов",
    description="Возвращает содержимое локального индекса (метаданные). Требует JWT Bearer.",
    response_model=IndexListResponse
)
async def ingest_list(rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    idx = list_index(rag_mgr.config.working_dir)
    # нормализуем ключи: ensure hash/size присутствуют даже если нет
    norm = []
    for e in idx:
        norm.append({
            "file": e.get("file"),
            "hash": e.get("hash"),
            "size": e.get("size"),
        })
    return {"status": "ok", "index": norm}


from app.utils.ingestion import delete_from_index, clear_index


@app.post(
    "/documents/ingest/delete",
    summary="Удалить документы из индекса",
    description="Удаляет перечисленные файлы из индекса по именам. Требует JWT Bearer.",
    response_model=DeleteResult
)
async def ingest_delete(req: DeleteRequest, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    result = delete_from_index(rag_mgr.config.working_dir, req.files)
    return {"status": "ok", **result}


@app.post(
    "/documents/ingest/clear",
    summary="Очистить индекс",
    description="Полностью очищает локальный индекс документов. Требует JWT Bearer.",
    response_model=ClearResult
)
async def ingest_clear(rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    result = clear_index(rag_mgr.config.working_dir)
    return {"status": "ok", **result}


@app.post(
    "/auth/token",
    response_model=TokenResponse,
    summary="Выдать JWT токен",
    description="Генерация простого JWT (без подписки внешними ключами) по имени пользователя и роли. Используется для авторизации остальных эндпоинтов."
)
async def issue_jwt(req: TokenRequest):
    try:
        token = issue_token(req.user, {}, role=req.role)
        return TokenResponse(access_token=token, role=req.role)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


def get_app() -> FastAPI:  # helper for ASGI servers
    return app
"""FastAPI application assembly (will replace api_server.py).

(Шаг 1) Заглушка.
"""


# -------- Conversation management endpoints --------
@app.get(
    "/conversations",
    response_model=ConversationList,
    summary="Список conversation_id",
    description="Возвращает список активных conversation_id в памяти. Требует JWT Bearer.")
async def list_conversations(_claims=Depends(require_jwt)):
    cleanup_expired_conversations()
    return {"conversations": list(conversations.keys())}


@app.get(
    "/conversations/{conversation_id}",
    response_model=ConversationHistory,
    summary="История диалога",
    description="Возвращает полную историю сообщений для указанного conversation_id. Требует JWT Bearer.")
async def get_conversation(conversation_id: str, _claims=Depends(require_jwt)):
    # Проверяем TTL и очищаем если нужно
    meta = conversation_meta.get(conversation_id)
    if meta and time.time() - meta.get("last_activity", meta.get("created", 0)) > CONVERSATION_TTL_SECONDS:
        conversations.pop(conversation_id, None)
        conversation_meta.pop(conversation_id, None)
        raise HTTPException(status_code=404, detail="Conversation expired")
    msgs = conversations.get(conversation_id)
    if msgs is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation_id": conversation_id, "messages": msgs}


@app.delete(
    "/conversations/{conversation_id}",
    response_model=ConversationClearResult,
    summary="Удалить один диалог",
    description="Удаляет конкретный диалог из памяти. Требует JWT Bearer.")
async def delete_conversation(conversation_id: str, _claims=Depends(require_jwt)):
    removed = 1 if conversations.pop(conversation_id, None) is not None else 0
    conversation_meta.pop(conversation_id, None)
    return {"status": "ok", "cleared": removed, "conversations_remaining": len(conversations)}


@app.delete(
    "/conversations",
    response_model=ConversationClearResult,
    summary="Очистить все диалоги",
    description="Полностью очищает память всех диалогов. Требует JWT Bearer.")
async def clear_conversations(_claims=Depends(require_jwt)):
    count = len(conversations)
    conversations.clear()
    conversation_meta.clear()
    return {"status": "ok", "cleared": count, "conversations_remaining": 0}
