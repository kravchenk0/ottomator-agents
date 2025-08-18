"""FastAPI server (migrated from root api_server.py)."""
from __future__ import annotations

import os
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core import RAGManager, RAGConfig, get_default_config, get_temperature_adjustment_state
from monkey_patch_lightrag import is_patch_applied
from app.utils.logging import setup_logger, performance_logger

logger = setup_logger("api_server", "INFO")

app = FastAPI(
    title="LightRAG API Server",
    description="API server for LightRAG integration",
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


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    sources: Optional[list] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


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
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed init: {e}")
        if os.getenv("FAST_FAILLESS_INIT", "0").lower() not in {"1", "true", "yes"}:
            raise


@app.get("/")
async def root():
    return {"status": "ok", "rag_initialized": rag_manager is not None}


@app.get("/health", response_model=HealthResponse)
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


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, rag_mgr: RAGManager = Depends(get_rag_manager)):
    try:
        performance_logger.start_timer("chat_request")
        conv_id = request.conversation_id or f"conv_{hash(request.message) % 10000}"
        current_prompt = request.system_prompt or system_prompt
        global _create_agent, _RAGDeps
        if _create_agent is None or _RAGDeps is None:
            if os.getenv("OPENAI_API_KEY"):
                from app.agent.rag_agent import create_agent as _ca, RAGDeps as _rd
                _create_agent, _RAGDeps = _ca, _rd
            else:
                raise HTTPException(status_code=503, detail="RAG/Agent unavailable: no API key")
        agent = _create_agent(current_prompt)
        deps = _RAGDeps(rag_manager=rag_mgr)
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
                "system_prompt_used": (current_prompt[:100] + "...") if current_prompt and len(current_prompt) > 100 else current_prompt,
                "processing_time": performance_logger.get_summary().get("chat_request", 0),
            },
        )
    except Exception as e:  # noqa: BLE001
        performance_logger.end_timer("chat_request")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.post("/config", response_model=Dict[str, Any])
async def update_config(request: ConfigRequest):
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


@app.get("/config")
async def get_config():
    return {
        "working_dir": rag_manager.config.working_dir if rag_manager else None,
        "system_prompt": system_prompt,
        "rerank_enabled": rag_manager.config.rerank_enabled if rag_manager else None,
    }


@app.post("/documents/insert")
async def insert_document(content: str, document_id: Optional[str] = None, rag_mgr: RAGManager = Depends(get_rag_manager)):
    try:
        rag = await rag_mgr.get_rag()
        await rag.ainsert(content)
        return {"status": "success", "message": "Document inserted successfully", "document_id": document_id or f"doc_{hash(content) % 10000}"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to insert document: {e}")


@app.get("/documents/search")
async def search_documents(query: str, limit: int = 5, rag_mgr: RAGManager = Depends(get_rag_manager)):
    try:
        rag = await rag_mgr.get_rag()
        results = await rag.aquery(query, param={"mode": "mix"})
        return {"query": query, "results": results, "limit": limit}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to search documents: {e}")


def get_app() -> FastAPI:  # helper for ASGI servers
    return app
"""FastAPI application assembly (will replace api_server.py).

(Шаг 1) Заглушка.
"""
