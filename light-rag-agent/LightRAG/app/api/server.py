"""FastAPI server (migrated from root api_server.py)."""
from __future__ import annotations

import os
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core import RAGManager, RAGConfig, get_default_config, get_temperature_adjustment_state
from monkey_patch_lightrag import is_patch_applied
from app.utils.logging import setup_logger, performance_logger
from app.utils.ingestion import ingest_files, scan_directory, list_index
from pathlib import Path
import asyncio
from fastapi import Header, status
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


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None  # запрошенная модель (опционально)


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    sources: Optional[list] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None  # текст ошибки, если запрос завершился неуспешно


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
        system_prompt = (
            "You are a helpful AI assistant integrated with a website. Always use the retrieve tool first."
        )
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
    summary="Ping / корневой статус",
    description="Простой ping для проверки доступности сервера (без авторизации)."
)
async def root():
    return {"status": "ok", "rag_initialized": rag_manager is not None }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Расширенный health-check",
    description="Проверка статуса RAG, версии, модели и динамических параметров температуры. Доступно без авторизации."
)
async def health_check():
    rag_status = "healthy" if rag_manager is not None else "unhealthy"
    ms = _model_self_test or {}
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


@app.post(
    "/chat",
    response_model=ChatResponse,
    summary="Задать вопрос / продолжить диалог",
    description=(
        "Главная точка взаимодействия с RAG. Принимает сообщение пользователя, опционально conversation_id для контекста и "
        "system_prompt override. Возвращает ответ модели, id сессии и источники (если доступны). Требует JWT Bearer."
    ),
)
async def chat_endpoint(request: ChatRequest, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    performance_logger.start_timer("chat_request")
    conv_id = request.conversation_id or f"conv_{hash(request.message) % 10000}"
    current_prompt = request.system_prompt or system_prompt
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
            performance_logger.end_timer("chat_request")
            performance_logger.log_metric("messages_processed", 1, "msg")
            return ChatResponse(
                response=result.data,
                conversation_id=conv_id,
                sources=sources,
                metadata={
                    "user_id": request.user_id,
                    "model": request.model or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL"),
                    "system_prompt_used": (current_prompt[:100] + "...") if current_prompt and len(current_prompt) > 100 else current_prompt,
                    "processing_time": performance_logger.get_summary().get("chat_request", 0),
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
                    "user_id": request.user_id,
                    "model": request.model or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL"),
                    "processing_time": performance_logger.get_summary().get("chat_request", 0),
                },
            )
    except Exception as outer:  # noqa: BLE001
        performance_logger.end_timer("chat_request")
        return ChatResponse(
            response="",
            conversation_id=conv_id,
            error=f"INIT_ERROR: {outer}",
            metadata={"stage": "outer"},
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
        if request.system_prompt is not None:
            system_prompt = request.system_prompt
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
    description="Асинхронно добавляет один текстовый документ напрямую в индекс без загрузки файла. Требует JWT Bearer."
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
    description="Выполняет смешанный (mode=mix) запрос к RAG индексу. Возвращает сырые результаты движка. Требует JWT Bearer."
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
    description="Загружает файл (multipart/form-data) в raw_uploads и опционально сразу выполняет ingest (парсинг + индексирование). Требует JWT Bearer."
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
    description="Сканирует директорию (по умолчанию RAG_INGEST_DIR) и индексирует новые/обновлённые файлы. Требует JWT Bearer."
)
async def ingest_scan(directory: str | None = None, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    rag = await rag_mgr.get_rag()
    scan_dir = directory or os.getenv("RAG_INGEST_DIR", "/data/ingest")
    files = scan_directory(scan_dir)
    if not files:
        return {"status": "no_files", "directory": scan_dir, "files": 0}
    async with _ingest_lock:
        result = await ingest_files(rag, files, rag_mgr.config.working_dir)
    return {"status": "ok", "directory": scan_dir, **result}


@app.get(
    "/documents/ingest/list",
    summary="Список индексированных документов",
    description="Возвращает содержимое локального индекса (метаданные). Требует JWT Bearer."
)
async def ingest_list(rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    return {"status": "ok", "index": list_index(rag_mgr.config.working_dir)}


from app.utils.ingestion import delete_from_index, clear_index


@app.post(
    "/documents/ingest/delete",
    summary="Удалить документы из индекса",
    description="Удаляет перечисленные файлы из индекса по именам. Требует JWT Bearer."
)
async def ingest_delete(files: list[str], rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    result = delete_from_index(rag_mgr.config.working_dir, files)
    return {"status": "ok", **result}


@app.post(
    "/documents/ingest/clear",
    summary="Очистить индекс",
    description="Полностью очищает локальный индекс документов. Требует JWT Bearer."
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
