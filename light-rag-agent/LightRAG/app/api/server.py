"""FastAPI server (migrated from root api_server.py)."""
from __future__ import annotations

import os
import time
import json
import uuid
import resource
import functools
import inspect
from typing import Any, Dict, List, Optional, Callable, Tuple

from fastapi import Header, status, FastAPI, HTTPException, Depends, UploadFile, File, Security, Request
from fastapi.responses import PlainTextResponse
from fastapi.openapi.utils import get_openapi
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
from app.utils.s3_storage import get_s3_storage, S3StorageAdapter

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

# Security wrapper для правильного OpenAPI отображения (если понадобится перейти на scopes)
def require_api_key_sec(x_api_key: str | None = Header(default=None)):
    return require_api_key(x_api_key)

# Строгая версия: всегда требует наличие непустого списка ключей и корректный header.
def require_api_key_strict(x_api_key: str | None = Header(default=None)):
    keys = _load_api_keys()
    if not keys:
        # Конфигурация отсутствует – считаем это ошибкой конфигурации
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API key auth not configured (set RAG_API_KEYS)")
    if not x_api_key or x_api_key not in keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return True


logger = setup_logger("api_server", "INFO")

DETAILED_METRICS_ENABLED = os.getenv("RAG_DETAILED_METRICS", "1").lower() in {"1", "true", "yes"}

# contextvars (могли отсутствовать после мержа)
try:
    _cv_request_id  # type: ignore[name-defined]
except NameError:
    import contextvars as _cv_mod  # локальный импорт чтобы не дублировать глобальный
    _cv_request_id = _cv_mod.ContextVar("chat_request_id", default=None)  # type: ignore
    _cv_phase = _cv_mod.ContextVar("chat_phase", default=None)  # type: ignore


class MetricsAggregator:
    """Простейший агрегатор метрик в памяти (не потокобезопасен, но GIL + single-worker достаточно).
    Хранит суммарные показатели и счётчики ошибок для Prometheus-совместимого вывода.
    """
    def __init__(self):
        self._data: Dict[str, Any] = {
            "chat_requests_total": 0,
            "chat_requests_in_flight": 0,
            "chat_errors_total": 0,
            "chat_latency_sum_seconds": 0.0,
            "chat_phase_latency_sum_seconds": {},  # phase -> sum
            "chat_phase_count": {},  # phase -> count
            "chat_rate_limit_rejections": 0,
            "chat_timeout_errors": 0,
            "chat_model_errors": 0,
            "chat_init_errors": 0,
            "rag_retrieve_latency_sum_seconds": 0.0,
            "rag_retrieve_count": 0,
            "agent_create_latency_sum_seconds": 0.0,
            "agent_create_count": 0,
            "history_build_latency_sum_seconds": 0.0,
            "history_build_count": 0,
            "conversation_history_lengths": {},  # length bucket -> count
            "chat_cache_hits": 0,
            "chat_cache_misses": 0,
        }

    def start(self):
        self._data["chat_requests_in_flight"] += 1

    def end(self, ok: bool, latency: float, phases: Dict[str, float], error_type: str = None, history_length: int = 0):
        self._data["chat_requests_total"] += 1
        self._data["chat_requests_in_flight"] = max(0, self._data["chat_requests_in_flight"] - 1)
        if not ok:
            self._data["chat_errors_total"] += 1
            # Track specific error types
            if error_type == "timeout":
                self._data["chat_timeout_errors"] += 1
            elif error_type == "model":
                self._data["chat_model_errors"] += 1
            elif error_type == "init":
                self._data["chat_init_errors"] += 1
        
        self._data["chat_latency_sum_seconds"] += latency
        
        # Track phase metrics
        for p, v in phases.items():
            self._data["chat_phase_latency_sum_seconds"].setdefault(p, 0.0)
            self._data["chat_phase_latency_sum_seconds"][p] += v
            self._data["chat_phase_count"].setdefault(p, 0)
            self._data["chat_phase_count"][p] += 1
        
        # Track conversation history length distribution
        if history_length > 0:
            bucket = self._get_history_bucket(history_length)
            self._data["conversation_history_lengths"].setdefault(bucket, 0)
            self._data["conversation_history_lengths"][bucket] += 1

    def rate_limited(self):
        self._data["chat_rate_limit_rejections"] += 1
    
    def track_rag_retrieve(self, latency: float):
        """Track RAG retrieve operation metrics."""
        self._data["rag_retrieve_latency_sum_seconds"] += latency
        self._data["rag_retrieve_count"] += 1
    
    def track_agent_create(self, latency: float):
        """Track agent creation metrics."""
        self._data["agent_create_latency_sum_seconds"] += latency
        self._data["agent_create_count"] += 1
    
    def track_history_build(self, latency: float):
        """Track history building metrics."""
        self._data["history_build_latency_sum_seconds"] += latency
        self._data["history_build_count"] += 1
    
    def track_cache_hit(self):
        """Track cache hit."""
        self._data["chat_cache_hits"] += 1
    
    def track_cache_miss(self):
        """Track cache miss."""
        self._data["chat_cache_misses"] += 1
    
    def _get_history_bucket(self, length: int) -> str:
        """Bucket history lengths for histogram-like tracking."""
        if length <= 2:
            return "0-2"
        elif length <= 5:
            return "3-5"
        elif length <= 10:
            return "6-10"
        elif length <= 20:
            return "11-20"
        else:
            return "20+"

    def render_prometheus(self) -> str:
        lines = [
            "# HELP lightrag_chat_requests_total Total chat requests",
            "# TYPE lightrag_chat_requests_total counter",
            f"lightrag_chat_requests_total {self._data['chat_requests_total']}",
            "",
            "# HELP lightrag_chat_requests_in_flight Current in-flight chat requests",
            "# TYPE lightrag_chat_requests_in_flight gauge",
            f"lightrag_chat_requests_in_flight {self._data['chat_requests_in_flight']}",
            "",
            "# HELP lightrag_chat_errors_total Total chat errors",
            "# TYPE lightrag_chat_errors_total counter",
            f"lightrag_chat_errors_total {self._data['chat_errors_total']}",
            "",
            "# HELP lightrag_chat_timeout_errors_total Chat timeout errors",
            "# TYPE lightrag_chat_timeout_errors_total counter", 
            f"lightrag_chat_timeout_errors_total {self._data['chat_timeout_errors']}",
            "",
            "# HELP lightrag_chat_model_errors_total Chat model errors",
            "# TYPE lightrag_chat_model_errors_total counter",
            f"lightrag_chat_model_errors_total {self._data['chat_model_errors']}",
            "",
            "# HELP lightrag_chat_init_errors_total Chat initialization errors",
            "# TYPE lightrag_chat_init_errors_total counter",
            f"lightrag_chat_init_errors_total {self._data['chat_init_errors']}",
            "",
            "# HELP lightrag_chat_latency_seconds_sum Sum of chat request latency seconds",
            "# TYPE lightrag_chat_latency_seconds_sum counter",
            f"lightrag_chat_latency_seconds_sum {self._data['chat_latency_sum_seconds']}",
            "",
            "# HELP lightrag_chat_rate_limit_rejections Total chat rate limit rejections",
            "# TYPE lightrag_chat_rate_limit_rejections counter",
            f"lightrag_chat_rate_limit_rejections {self._data['chat_rate_limit_rejections']}",
            "",
            "# HELP lightrag_rag_retrieve_latency_seconds_sum Sum of RAG retrieve operation latency",
            "# TYPE lightrag_rag_retrieve_latency_seconds_sum counter",
            f"lightrag_rag_retrieve_latency_seconds_sum {self._data['rag_retrieve_latency_sum_seconds']}",
            "",
            "# HELP lightrag_rag_retrieve_total Total RAG retrieve operations",
            "# TYPE lightrag_rag_retrieve_total counter",
            f"lightrag_rag_retrieve_total {self._data['rag_retrieve_count']}",
            "",
            "# HELP lightrag_agent_create_latency_seconds_sum Sum of agent creation latency",
            "# TYPE lightrag_agent_create_latency_seconds_sum counter",
            f"lightrag_agent_create_latency_seconds_sum {self._data['agent_create_latency_sum_seconds']}",
            "",
            "# HELP lightrag_agent_create_total Total agent creation operations",
            "# TYPE lightrag_agent_create_total counter",
            f"lightrag_agent_create_total {self._data['agent_create_count']}",
            "",
            "# HELP lightrag_history_build_latency_seconds_sum Sum of history building latency",
            "# TYPE lightrag_history_build_latency_seconds_sum counter",
            f"lightrag_history_build_latency_seconds_sum {self._data['history_build_latency_sum_seconds']}",
            "",
            "# HELP lightrag_history_build_total Total history building operations",
            "# TYPE lightrag_history_build_total counter",
            f"lightrag_history_build_total {self._data['history_build_count']}",
            "",
            "# HELP lightrag_chat_cache_hits_total Chat cache hits",
            "# TYPE lightrag_chat_cache_hits_total counter",
            f"lightrag_chat_cache_hits_total {self._data['chat_cache_hits']}",
            "",
            "# HELP lightrag_chat_cache_misses_total Chat cache misses", 
            "# TYPE lightrag_chat_cache_misses_total counter",
            f"lightrag_chat_cache_misses_total {self._data['chat_cache_misses']}",
            "",
            "# HELP lightrag_chat_phase_latency_seconds_sum Sum of chat phase latency by phase",
            "# TYPE lightrag_chat_phase_latency_seconds_sum counter",
        ]
        
        # Phase latency metrics
        for phase, total in self._data["chat_phase_latency_sum_seconds"].items():
            lines.append(f"lightrag_chat_phase_latency_seconds_sum{{phase=\"{phase}\"}} {total}")
        
        lines.append("")
        lines.append("# HELP lightrag_chat_phase_count_total Count of chat phases by phase")
        lines.append("# TYPE lightrag_chat_phase_count_total counter")
        
        # Phase count metrics
        for phase, count in self._data["chat_phase_count"].items():
            lines.append(f"lightrag_chat_phase_count_total{{phase=\"{phase}\"}} {count}")
        
        lines.append("")
        lines.append("# HELP lightrag_conversation_history_length Distribution of conversation history lengths")
        lines.append("# TYPE lightrag_conversation_history_length counter")
        
        # History length distribution
        for bucket, count in self._data["conversation_history_lengths"].items():
            lines.append(f"lightrag_conversation_history_length{{bucket=\"{bucket}\"}} {count}")
        
        return "\n".join(lines) + "\n"


aggregator = MetricsAggregator()


class PhaseTimer:
    def __init__(self):
        self._starts: Dict[str, float] = {}
        self._durations: Dict[str, float] = {}
        self._t0 = time.perf_counter()

    def start(self, name: str):
        self._starts[name] = time.perf_counter()

    def end(self, name: str):
        if name in self._starts:
            self._durations[name] = time.perf_counter() - self._starts.pop(name)

    def finish(self) -> Dict[str, float]:
        return dict(self._durations)

    @property
    def total(self) -> float:
        return time.perf_counter() - self._t0


def _mem_usage_kb() -> int:
    # ru_maxrss в KB на Linux, на macOS в байтах — нормализуем примерно
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if usage > 10_000_000:  # вероятно байты (macOS)
        return int(usage / 1024)
    return usage


async def _log_chat_event(event: str, payload: Dict[str, Any]):
    if not DETAILED_METRICS_ENABLED:
        return
    try:
        logger.info(f"chat_{event} {json.dumps(payload, ensure_ascii=False)}")
    except Exception:
        logger.info(f"chat_{event} (unserializable)")


def instrument_chat(handler: Callable):
    @functools.wraps(handler)
    async def wrapper(*args, **kwargs):  # noqa: D401
        if not DETAILED_METRICS_ENABLED:
            return await handler(*args, **kwargs)
        phase = PhaseTimer()
        req_id = str(uuid.uuid4())
        # Устанавливаем contextvars, чтобы не ломать сигнатуру handler
        token_req = _cv_request_id.set(req_id)
        token_phase = _cv_phase.set(phase)
        try:
            logger.debug("instrument_chat v2 active (contextvars)")
        except Exception:
            pass
        aggregator.start()
        await _log_chat_event("start", {"request_id": req_id, "ts": time.time(), "mem_kb": _mem_usage_kb()})
        try:
            phase.start("handler")
            result = await handler(*args, **kwargs)
            phase.end("handler")
            phases = phase.finish()
            aggregator.end(True, phase.total, phases, history_length=getattr(handler, '_history_length', 0))
            await _log_chat_event("end", {
                "request_id": req_id,
                "ok": True,
                "total_sec": phase.total,
                "phases": phases,
                "mem_kb": _mem_usage_kb(),
            })
            return result
        except HTTPException as he:  # propagate but log
            phase.end("handler")
            phases = phase.finish()
            error_type = "model" if he.status_code in [400, 422] else "timeout" if he.status_code == 504 else "other"
            aggregator.end(False, phase.total, phases, error_type=error_type)
            await _log_chat_event("end", {
                "request_id": req_id,
                "ok": False,
                "status": he.status_code,
                "detail": he.detail,
                "total_sec": phase.total,
                "phases": phases,
                "mem_kb": _mem_usage_kb(),
            })
            raise
        except Exception as e:  # noqa: BLE001
            phase.end("handler")
            phases = phase.finish()
            aggregator.end(False, phase.total, phases, error_type="init")
            await _log_chat_event("end", {
                "request_id": req_id,
                "ok": False,
                "error": str(e),
                "total_sec": phase.total,
                "phases": phases,
                "mem_kb": _mem_usage_kb(),
            })
            raise
        finally:
            # Восстанавливаем contextvars чтобы избежать утечек между запросами (важно при reuse event loop)
            try:
                _cv_request_id.reset(token_req)
                _cv_phase.reset(token_phase)
            except Exception:
                pass
    # Сохраняем оригинальную сигнатуру, чтобы FastAPI корректно распознал тело запроса
    try:
        wrapper.__signature__ = inspect.signature(handler)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    return wrapper

app = FastAPI(
    title="LightRAG API Server",
    description=(
        "REST API для интеграции с движком LightRAG: чат поверх встроенного RAG, загрузка/ингест документов, "
        "поиск и администрирование. Большинство операций требуют JWT Bearer токен (см. /auth/token)."
    ),
    version="1.0.0"
)

# --- OpenAPI: добавить схему BearerAuth и пометить защищённые эндпоинты ---
_OPEN_ENDPOINTS = {("GET", "/health"), ("GET", "/alb-health")}  # /auth/token теперь защищён ApiKey

def custom_openapi():  # type: ignore
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Добавляем security schemes
    components = schema.setdefault("components", {}).setdefault("securitySchemes", {})
    components["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT"
    }
    components["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key"
    }
    # Применяем ко всем кроме открытых
    token_path = app.url_path_for("issue_jwt") if any(r.name == "issue_jwt" for r in app.routes) else "/auth/token"
    for path, methods in schema.get("paths", {}).items():
        for method, spec in methods.items():
            key = (method.upper(), path)
            if key in _OPEN_ENDPOINTS:
                spec["security"] = []  # полностью открыто
            elif path == token_path and method.upper() == "POST":
                spec["security"] = [{"ApiKeyAuth": []}]
            else:
                spec.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi  # type: ignore

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
s3_storage: Optional[S3StorageAdapter] = None

# ---- In-memory conversation storage (этап 1) ----
# conversations[conversation_id] = list[ {"role": "user"|"assistant", "content": str} ]
conversations: Dict[str, List[Dict[str, str]]] = {}
conversation_meta: Dict[str, Dict[str, float]] = {}  # {id: {created, last_activity}}
MAX_HISTORY_MESSAGES = int(os.getenv("RAG_MAX_HISTORY_MESSAGES", "12"))  # обрезаем глубину
CONVERSATION_TTL_SECONDS = int(os.getenv("RAG_CONVERSATION_TTL_SECONDS", "3600"))  # 1 час по умолчанию
ASYNC_HISTORY_THRESHOLD = int(os.getenv("RAG_HISTORY_ASYNC_THRESHOLD", "20"))  # порог длины (сообщений) для offload
USER_RATE_LIMIT = int(os.getenv("RAG_USER_RATE_LIMIT", "10"))  # 10 запросов / окно
USER_RATE_WINDOW_SECONDS = int(os.getenv("RAG_USER_RATE_WINDOW_SECONDS", "3600"))
user_rate: Dict[str, Dict[str, float]] = {}  # {user_id: {count, window_start}}
_cleanup_task = None  # background task handler
CONVERSATION_CLEANUP_INTERVAL = int(os.getenv("RAG_CONVERSATION_CLEANUP_INTERVAL", "300"))

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
    # Оптимизация: проверяем только если есть диалоги для проверки
    if not conversation_meta:
        return 0
    # Батчевая обработка для больших объемов
    batch_size = 100
    items = list(conversation_meta.items())
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        for cid, meta in batch:
            if now - meta.get("last_activity", meta.get("created", now)) > CONVERSATION_TTL_SECONDS:
                expired.append(cid)
    # Удаляем батчем
    for cid in expired:
        conversations.pop(cid, None)
        conversation_meta.pop(cid, None)
    return len(expired)

def _format_history(relevant: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    for m in relevant:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        prefix = "User" if role == "user" else "Assistant"
        lines.append(f"{prefix}: {content}")
    return "\n".join(lines)


async def build_history_context_async(messages: List[Dict[str, str]], include_last_user: bool = False) -> str:
    """Асинхронно собирает историю с умной обрезкой для производительности.

    Оптимизация: избегаем блокирования event loop при длинных историях + умная обрезка.
    """
    if not messages:
        return ""
    
    # Умная обрезка: сохраняем важные сообщения
    relevant = _smart_truncate_history(messages, MAX_HISTORY_MESSAGES)
    
    if not include_last_user and relevant and relevant[-1].get("role") == "user":
        relevant = relevant[:-1]
    if len(relevant) <= ASYNC_HISTORY_THRESHOLD:
        return _format_history(relevant)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _format_history, relevant)

def _smart_truncate_history(messages: List[Dict[str, str]], max_messages: int) -> List[Dict[str, str]]:
    """Умная обрезка истории: сохраняем первое и последние сообщения, пропускаем середину."""
    if len(messages) <= max_messages:
        return messages
    
    # Всегда сохраняем последние сообщения (они наиболее релевантны)
    keep_recent = max_messages // 2
    recent_messages = messages[-keep_recent:]
    
    # Сохраняем начальные сообщения для контекста
    keep_initial = max_messages - keep_recent
    if keep_initial > 0:
        initial_messages = messages[:keep_initial]
        # Добавляем маркер о пропущенных сообщениях
        if len(messages) > max_messages:
            gap_message = {
                "role": "system", 
                "content": f"[Пропущено {len(messages) - max_messages} сообщений для оптимизации производительности]"
            }
            return initial_messages + [gap_message] + recent_messages
        else:
            return initial_messages + recent_messages
    else:
        return recent_messages

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

# Chat response caching
CHAT_CACHE_TTL = int(os.getenv("RAG_CHAT_CACHE_TTL_SECONDS", "1800"))  # 30 минут
_chat_cache: Dict[str, Tuple[ChatResponse, float]] = {}  # {cache_key: (response, timestamp)}

def _get_chat_cache_key(message: str, conversation_id: str, user_id: str, model: str) -> str:
    """Generate cache key for chat responses."""
    import hashlib
    cache_data = f"{message}|{conversation_id}|{user_id}|{model}"
    return hashlib.md5(cache_data.encode('utf-8')).hexdigest()

def _get_cached_chat_response(cache_key: str) -> Optional[ChatResponse]:
    """Get cached chat response if still valid."""
    if cache_key in _chat_cache:
        response, timestamp = _chat_cache[cache_key]
        if time.time() - timestamp < CHAT_CACHE_TTL:
            return response
        else:
            del _chat_cache[cache_key]
    return None

def _cache_chat_response(cache_key: str, response: ChatResponse) -> None:
    """Cache chat response."""
    _chat_cache[cache_key] = (response, time.time())
    # Simple cleanup: remove old entries if cache gets too large
    if len(_chat_cache) > 500:  # Keep cache size reasonable
        now = time.time()
        expired_keys = [k for k, (_, ts) in _chat_cache.items() if now - ts > CHAT_CACHE_TTL]
        for k in expired_keys:
            del _chat_cache[k]


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
    global rag_manager, system_prompt, _model_self_test, _create_agent, _RAGDeps, s3_storage
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
        
        # Initialize S3 storage if configured
        try:
            s3_storage = get_s3_storage()
            if s3_storage:
                logger.info(f"S3 storage initialized: bucket={s3_storage.bucket_name}")
            else:
                logger.info("S3 storage not configured - using local file storage")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"S3 storage initialization failed: {e}")
            s3_storage = None
        
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

    # Запуск фоновой очистки разговоров
    async def conversation_cleanup_loop():  # noqa: D401
        while True:
            try:
                await asyncio.sleep(CONVERSATION_CLEANUP_INTERVAL)
                removed = cleanup_expired_conversations()
                if removed > 0:
                    logger.info(f"conversation_cleanup removed={removed} total_active={len(conversations)}")
            except asyncio.CancelledError:  # graceful shutdown
                break
            except Exception as e:  # noqa: BLE001
                logger.warning(f"conversation_cleanup_loop error: {e}")
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():  # type: ignore
        _cleanup_task = asyncio.create_task(conversation_cleanup_loop())


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
@instrument_chat
async def chat_endpoint(
    request: ChatRequest,
    rag_mgr: RAGManager = Depends(get_rag_manager),
    _claims=Depends(require_jwt),
    _req_id: str | None = None,  # backward compatibility (старый декоратор мог передавать)
    _phase: Any | None = None,   # будет проигнорирован если используется новый декоратор
):
    performance_logger.start_timer("chat_request")
    conv_id = request.conversation_id or request.conversations or f"conv_{hash(request.message) % 10000}"
    if not request.message or not request.message.strip():
        performance_logger.end_timer("chat_request")
        raise HTTPException(status_code=400, detail="'message' is required and cannot be empty")

    # User id для лимитов
    user_id = request.user_id or (_claims.get("sub") if isinstance(_claims, dict) else None) or "anonymous"
    
    # Get phase from contextvar early (used throughout the function)
    phase = _cv_phase.get() or _phase
    
    # Check cache first (for identical questions, skip rate limits for cache hits)
    model_name = request.model or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL") or "gpt-4o-mini"
    cache_key = _get_chat_cache_key(request.message, conv_id, user_id, model_name)
    
    if phase: phase.start("cache_check")
    cached_response = _get_cached_chat_response(cache_key)
    if phase: phase.end("cache_check")
    
    if cached_response:
        logger.info(f"[chat] cache hit for user={user_id}, conv={conv_id}")
        aggregator.track_cache_hit()
        # Update conversation_id in cached response
        cached_response.conversation_id = conv_id
        cached_response.metadata["cached"] = True
        cached_response.metadata["cache_hit_time"] = time.time()
        return cached_response
    
    # Track cache miss
    aggregator.track_cache_miss()
    
    # Rate limit enforcement (only for non-cached requests)
    _enforce_user_rate_limit(user_id)
    msgs = conversations.setdefault(conv_id, [])  # существующая или новая история
    meta = conversation_meta.setdefault(conv_id, {"created": time.time(), "last_activity": time.time()})
    # Добавляем текущий user message в хвост
    msgs.append({"role": "user", "content": request.message})
    # При необходимости ограничиваем размер хранимой истории (мягкая обрезка)
    if len(msgs) > MAX_HISTORY_MESSAGES * 3:
        del msgs[: len(msgs) - MAX_HISTORY_MESSAGES * 2]
    # Формируем history_context (исключая только что добавленное user сообщение)
    if phase: 
        phase.start("history")
        history_start = time.perf_counter()
    history_context = await build_history_context_async(msgs, include_last_user=False)
    if phase: 
        phase.end("history")
        aggregator.track_history_build(time.perf_counter() - history_start)
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
        if phase: 
            phase.start("agent_create")
            agent_create_start = time.perf_counter()
        agent = _create_agent(model=request.model, system_prompt=current_prompt)
        if phase: 
            phase.end("agent_create")
            aggregator.track_agent_create(time.perf_counter() - agent_create_start)
        deps = _RAGDeps(rag_manager=rag_mgr)
        try:
            if phase: phase.start("agent_run")
            
            # Адаптивный таймаут на основе сложности запроса и истории
            base_timeout = int(os.getenv("RAG_AGENT_TIMEOUT_SECONDS", "120"))
            query_words = len(request.message.split())
            history_length = len(msgs)
            
            # Оптимизация: простые запросы = короткий таймаут, сложные = длинный
            if query_words <= 5 and history_length <= 3:
                agent_timeout = min(base_timeout, 45)  # Простые запросы
            elif query_words <= 15 and history_length <= 8:
                agent_timeout = min(base_timeout, 75)  # Средние запросы
            else:
                agent_timeout = base_timeout  # Сложные запросы
            
            logger.info(f"[chat] adaptive timeout: {agent_timeout}s (query_words={query_words}, history_len={history_length})")
            result = await asyncio.wait_for(
                agent.run(request.message, deps=deps),
                timeout=agent_timeout
            )
            if phase: phase.end("agent_run")
            try:
                sources = getattr(result, 'metadata', {}).get('sources') if getattr(result, 'metadata', None) else None
            except Exception:  # noqa: BLE001
                sources = None
            # Добавляем assistant ответ в историю
            msgs.append({"role": "assistant", "content": result.data})
            meta["last_activity"] = time.time()
            performance_logger.end_timer("chat_request")
            performance_logger.log_metric("messages_processed", 1, "msg")
            
            # Track successful completion with detailed metrics
            phases = phase.finish() if phase else {}
            aggregator.end(True, phase.total if phase else 0, phases, history_length=len(msgs))
            resp = ChatResponse(
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
                    "request_id": _cv_request_id.get(),
                    "cached": False,
                },
            )
            
            # Cache successful responses (only for non-error responses)
            if result.data and len(result.data.strip()) > 10:  # Cache substantial responses
                _cache_chat_response(cache_key, resp)
                logger.info(f"[chat] cached response for future use, key={cache_key[:8]}...")
            
            if DETAILED_METRICS_ENABLED:
                await _log_chat_event("result", {"request_id": _cv_request_id.get(), "conversation_id": conv_id, "history_messages": len(msgs)})
            return resp
        except asyncio.TimeoutError:
            performance_logger.end_timer("chat_request")
            if phase: phase.end("agent_run")
            phases = phase.finish() if phase else {}
            aggregator.end(False, phase.total if phase else 0, phases, error_type="timeout", history_length=len(msgs))
            resp = ChatResponse(
                response="Запрос занял слишком много времени. Попробуйте упростить вопрос или повторить позже.",
                conversation_id=conv_id,
                error="TIMEOUT: Agent execution timed out",
                metadata={
                    "user_id": user_id,
                    "model": request.model or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL"),
                    "timeout_seconds": agent_timeout,
                    "request_id": _cv_request_id.get(),
                    "history_messages": len(msgs),
                },
            )
            return resp
        except Exception as run_err:  # noqa: BLE001
            performance_logger.end_timer("chat_request")
            if phase: phase.end("agent_run")
            phases = phase.finish() if phase else {}
            err_str = str(run_err)
            # Попытка классифицировать
            if "model_not_found" in err_str or "does not exist" in err_str:
                code = "MODEL_NOT_FOUND"
                error_type = "model"
            elif "rate limit" in err_str.lower():
                code = "RATE_LIMIT"
                error_type = "model"
            elif "timeout" in err_str.lower():
                code = "TIMEOUT"
                error_type = "timeout"
            else:
                code = "EXECUTION_ERROR"
                error_type = "model"
            
            aggregator.end(False, phase.total if phase else 0, phases, error_type=error_type, history_length=len(msgs))
            resp = ChatResponse(
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
                    "request_id": _cv_request_id.get(),
                },
            )
            if DETAILED_METRICS_ENABLED:
                await _log_chat_event("error", {"request_id": _cv_request_id.get(), "error": code, "detail": err_str})
            return resp
    except Exception as outer:  # noqa: BLE001
        performance_logger.end_timer("chat_request")
        phases = phase.finish() if phase else {}
        aggregator.end(False, phase.total if phase else 0, phases, error_type="init", 
                      history_length=len(conversations.get(conv_id, [])))
        resp = ChatResponse(
            response="",
            conversation_id=conv_id,
            error=f"INIT_ERROR: {outer}",
            metadata={"stage": "outer", "history_messages": len(conversations.get(conv_id, [])), "request_id": _cv_request_id.get()},
        )
        if DETAILED_METRICS_ENABLED:
            await _log_chat_event("init_error", {"request_id": _cv_request_id.get(), "error": str(outer)})
        return resp


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
    # Get upload timeout from environment
    upload_timeout = int(os.getenv("RAG_UPLOAD_TIMEOUT_SECONDS", "300"))
    
    try:
        return await asyncio.wait_for(
            _insert_document_impl(content, document_id, rag_mgr),
            timeout=upload_timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Document insert timeout after {upload_timeout} seconds")
        raise HTTPException(status_code=504, detail=f"Document insert timeout after {upload_timeout} seconds")


async def _insert_document_impl(content: str, document_id: Optional[str], rag_mgr: RAGManager):
    """Internal implementation of document insert with proper error handling."""
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
    description="Загружает файл в S3 (если настроено) или локально, и опционально выполняет ingest. Требует JWT Bearer.",
    response_model=Dict[str, Any]
)
async def upload_document(file: UploadFile = File(...), ingest: bool = True, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    """
    Upload document to S3 or local storage and optionally ingest into RAG.
    
    Args:
        file: Uploaded file object.
        ingest: Whether to immediately ingest file into RAG index.
        rag_mgr: RAG manager dependency.
        _claims: JWT claims dependency.
        
    Returns:
        Dict with upload status, storage location, and ingestion results.
    """
    # Get upload timeout from environment
    upload_timeout = int(os.getenv("RAG_UPLOAD_TIMEOUT_SECONDS", "300"))
    
    try:
        return await asyncio.wait_for(
            _upload_document_impl(file, ingest, rag_mgr),
            timeout=upload_timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Upload timeout after {upload_timeout} seconds")
        raise HTTPException(status_code=504, detail=f"Upload timeout after {upload_timeout} seconds")


async def _upload_document_impl(file: UploadFile, ingest: bool, rag_mgr: RAGManager):
    """Internal implementation of document upload with proper error handling."""
    rag = await rag_mgr.get_rag()
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    
    storage_info = {}
    local_path = None
    
    try:
        # Try S3 upload first if configured
        if s3_storage:
            import io
            file_obj = io.BytesIO(content_bytes)
            s3_key = await s3_storage.upload_file_obj(
                file_obj, 
                file.filename or "unknown_file",
                metadata={
                    'content_type': file.content_type or 'application/octet-stream',
                    'original_filename': file.filename or 'unknown'
                }
            )
            storage_info = {
                "storage_type": "s3",
                "s3_bucket": s3_storage.bucket_name,
                "s3_key": s3_key,
                "s3_url": f"s3://{s3_storage.bucket_name}/{s3_key}"
            }
            
            # Download to temp location for ingestion if needed
            if ingest:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=f"_{file.filename}", delete=False) as tmp:
                    tmp.write(content_bytes)
                    local_path = tmp.name
        else:
            # Fallback to local storage
            raw_dir = Path(rag_mgr.config.working_dir) / "raw_uploads"
            raw_dir.mkdir(parents=True, exist_ok=True)
            local_path = raw_dir / (file.filename or "unknown_file")
            local_path.write_bytes(content_bytes)
            storage_info = {
                "storage_type": "local",
                "local_path": str(local_path)
            }
        
        # Perform ingestion if requested
        ingestion_result = None
        if ingest and local_path:
            async with _ingest_lock:
                ingestion_result = await ingest_files(rag, [Path(local_path)], rag_mgr.config.working_dir)
            
            # Clean up temp file if used for S3
            if s3_storage and local_path.startswith('/tmp'):
                try:
                    os.unlink(local_path)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Failed to cleanup temp file {local_path}: {e}")
        
        return {
            "status": "ok",
            "file_size": len(content_bytes),
            "filename": file.filename,
            **storage_info,
            "ingestion": ingestion_result
        }
        
    except Exception as e:  # noqa: BLE001
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post(
    "/documents/ingest/scan",
    summary="Скан + ingest директории",
    description="Сканирует директорию (по умолчанию RAG_INGEST_DIR) и индексирует новые/обновлённые файлы. Требует JWT Bearer.",
    response_model=IngestionResult
)
async def ingest_scan(directory: str | None = None, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    # Get upload timeout from environment
    upload_timeout = int(os.getenv("RAG_UPLOAD_TIMEOUT_SECONDS", "300"))
    
    try:
        return await asyncio.wait_for(
            _ingest_scan_impl(directory, rag_mgr),
            timeout=upload_timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Ingest scan timeout after {upload_timeout} seconds")
        raise HTTPException(status_code=504, detail=f"Ingest scan timeout after {upload_timeout} seconds")


async def _ingest_scan_impl(directory: str | None, rag_mgr: RAGManager):
    """Internal implementation of ingest scan with proper error handling."""
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


@app.get(
    "/documents/s3/list",
    summary="Список S3 документов",
    description="Возвращает список документов в S3 бакете. Требует JWT Bearer.",
    response_model=Dict[str, Any]
)
async def list_s3_documents(prefix: str = "", max_items: int = 100, _claims=Depends(require_jwt)):
    """List documents stored in S3 bucket."""
    if not s3_storage:
        raise HTTPException(status_code=503, detail="S3 storage not configured")
    
    try:
        objects = await s3_storage.list_objects(prefix_filter=prefix, max_keys=max_items)
        return {
            "status": "ok",
            "bucket": s3_storage.bucket_name,
            "prefix": prefix,
            "count": len(objects),
            "objects": objects
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to list S3 objects: {e}")
        raise HTTPException(status_code=500, detail=f"S3 list failed: {str(e)}")


@app.get(
    "/documents/s3/download/{s3_key:path}",
    summary="Скачать S3 документ",
    description="Генерирует presigned URL для скачивания документа из S3. Требует JWT Bearer."
)
async def download_s3_document(s3_key: str, expiration: int = 3600, _claims=Depends(require_jwt)):
    """Generate presigned URL for downloading S3 document."""
    if not s3_storage:
        raise HTTPException(status_code=503, detail="S3 storage not configured")
    
    try:
        # Check if object exists
        if not await s3_storage.object_exists(s3_key):
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Generate presigned URL
        download_url = s3_storage.get_presigned_url(s3_key, expiration=expiration)
        
        return {
            "status": "ok",
            "s3_key": s3_key,
            "download_url": download_url,
            "expires_in_seconds": expiration
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to generate download URL for {s3_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Download URL generation failed: {str(e)}")


@app.delete(
    "/documents/s3/{s3_key:path}",
    summary="Удалить S3 документ",
    description="Удаляет документ из S3 бакета. Требует JWT Bearer."
)
async def delete_s3_document(s3_key: str, _claims=Depends(require_jwt)):
    """Delete document from S3 bucket."""
    if not s3_storage:
        raise HTTPException(status_code=503, detail="S3 storage not configured")
    
    try:
        # Check if object exists
        if not await s3_storage.object_exists(s3_key):
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete object
        success = await s3_storage.delete_object(s3_key)
        
        return {
            "status": "ok" if success else "error",
            "s3_key": s3_key,
            "deleted": success
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to delete S3 object {s3_key}: {e}")
        raise HTTPException(status_code=500, detail=f"S3 deletion failed: {str(e)}")


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
    name="issue_jwt",
    response_model=TokenResponse,
    summary="Выдать JWT токен (требует X-API-Key)",
    description="Генерация JWT. Требует валидный X-API-Key (RAG_API_KEYS/RAG_API_KEY)."
)
async def issue_jwt(req: TokenRequest, _api=Security(require_api_key_strict)):
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


@app.get(
    "/metrics",
    summary="Prometheus-совместимые метрики",
    description="Возвращает внутренние метрики чата. Можно ограничить через SG/ingress.",
    response_class=PlainTextResponse
)
async def metrics():  # noqa: D401
    try:
        data = aggregator.render_prometheus()
    except Exception as e:  # noqa: BLE001
        # fallback на случай непредвиденной ошибки
        data = f"# metrics_error\nerror_info{{}} 1\n# detail: {e}"
    return PlainTextResponse(content=data, media_type="text/plain; version=0.0.4")


from fastapi.responses import StreamingResponse  # добавлено для стриминга


@app.post(
    "/chat/stream",
    summary="Стриминговый чат (частичный ответ)",
    description="Возвращает частичный ответ потоком text/event-stream чтобы удерживать соединение живым при долгой генерации. Требует JWT Bearer.")
@instrument_chat
async def chat_stream_endpoint(request: ChatRequest, rag_mgr: RAGManager = Depends(get_rag_manager), _claims=Depends(require_jwt)):
    performance_logger.start_timer("chat_request_stream")
    conv_id = request.conversation_id or request.conversations or f"conv_{hash(request.message) % 10000}"
    if not request.message or not request.message.strip():
        performance_logger.end_timer("chat_request_stream")
        raise HTTPException(status_code=400, detail="'message' is required and cannot be empty")
    # Фоновая очистка диалогов выполняется в отдельной задаче
    user_id = request.user_id or (_claims.get("sub") if isinstance(_claims, dict) else None) or "anonymous"
    _enforce_user_rate_limit(user_id)
    msgs = conversations.setdefault(conv_id, [])
    meta = conversation_meta.setdefault(conv_id, {"created": time.time(), "last_activity": time.time()})
    msgs.append({"role": "user", "content": request.message})
    phase = _cv_phase.get()
    if phase: phase.start("history")
    history_context = await build_history_context_async(msgs, include_last_user=False)
    if phase: phase.end("history")
    if history_context:
        effective_prompt = f"{system_prompt}\n\nConversation so far:\n{history_context}\n---"
    else:
        effective_prompt = system_prompt
    global _create_agent, _RAGDeps
    if _create_agent is None or _RAGDeps is None:
        if os.getenv("OPENAI_API_KEY"):
            from app.agent.rag_agent import create_agent as _ca, RAGDeps as _rd
            _create_agent, _RAGDeps = _ca, _rd
        else:
            raise HTTPException(status_code=503, detail="RAG/Agent unavailable: no OPENAI_API_KEY")
    if phase: phase.start("agent_create")
    agent = _create_agent(model=request.model, system_prompt=effective_prompt)
    if phase: phase.end("agent_create")
    deps = _RAGDeps(rag_manager=rag_mgr)

    async def event_generator():
        # Первичный ping, чтобы ALB видел активность
        rid = _cv_request_id.get() or "unknown"
        yield f"data: {{\"status\":\"started\",\"request_id\":\"{rid}\"}}\n\n"
        try:
            # Запуск основного выполнения с таймаутом (стриминг версия)
            if phase: phase.start("agent_run")
            agent_timeout = int(os.getenv("RAG_AGENT_TIMEOUT_SECONDS", "120"))
            result = await asyncio.wait_for(
                agent.run(request.message, deps=deps),
                timeout=agent_timeout
            )
            if phase: phase.end("agent_run")
            msgs.append({"role": "assistant", "content": result.data})
            meta["last_activity"] = time.time()
            performance_logger.end_timer("chat_request_stream")
            yield (
                "data: " +
                __import__("json").dumps({
                    "status": "complete",
                    "conversation_id": conv_id,
                    "response": result.data,
                    "processing_time": performance_logger.get_summary().get("chat_request_stream", 0),
                    "history_messages": len(msgs)
                }) + "\n\n"
            )
        except asyncio.TimeoutError:
            performance_logger.end_timer("chat_request_stream")
            yield "data: {\"status\":\"timeout\",\"error\": \"Request timed out\"}\n\n"
        except Exception as e:  # noqa: BLE001
            performance_logger.end_timer("chat_request_stream")
            yield "data: {\"status\":\"error\",\"error\": " + __import__("json").dumps(str(e)) + "}\n\n"
        yield "event: end\ndata: end\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
