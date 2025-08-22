"""Agent creation & run utilities (migrated from root rag_agent.py eventually).

(Шаг 1) Заглушка.
"""
from __future__ import annotations

import os
import sys
import argparse
import asyncio
import logging
import hashlib
import time
from functools import lru_cache
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

from pydantic_ai import RunContext
from pydantic_ai.agent import Agent
from lightrag import QueryParam

from app.core import RAGManager, RAGConfig, get_default_config

logger = logging.getLogger(__name__)

# Простой in-memory кэш для RAG запросов
RAG_CACHE_TTL = int(os.getenv("RAG_CACHE_TTL_SECONDS", "300"))  # 5 минут
_rag_cache: Dict[str, Tuple[str, float]] = {}  # {query_hash: (result, timestamp)}

# Оптимизированный системный промпт для лучшей производительности
DEFAULT_SYSTEM_PROMPT = (
	"""Вы - консультант по фризонам Дубая. Компетенции: визы/иммиграция, HR/оформление сотрудников.

Источник данных: корпоративное хранилище документов. Доступ только через retrieve.

Правила:
1. Используйте retrieve для каждого запроса
2. Цитируйте источники: [документ, раздел]
3. При отсутствии данных - скажите честно
4. Для чисел указывайте дату документа

Алгоритм:
Извлечь ключевые слова → retrieve → синтезировать ответ с источниками

Формат ответа:
- Резюме (1-2 строки)
- Детали по категориям
- Чек-лист шагов
- Источники

Отвечайте на языке вопроса, кратко и точно."""
)

@dataclass
class RAGDeps:
	rag_manager: RAGManager


def resolve_agent_model(explicit: Optional[str] = None) -> str:
	base = explicit or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL") or "gpt-5-mini"
	if not base.startswith("openai:"):
		base = f"openai:{base}"
	return base


def _get_cache_key(search_query: str) -> str:
	"""Генерирует ключ кэша для запроса."""
	return hashlib.md5(search_query.encode('utf-8')).hexdigest()

def _get_cached_result(search_query: str) -> Optional[str]:
	"""Получает результат из кэша, если он актуален."""
	cache_key = _get_cache_key(search_query)
	if cache_key in _rag_cache:
		result, timestamp = _rag_cache[cache_key]
		if time.time() - timestamp < RAG_CACHE_TTL:
			return result
		else:
			# Удаляем просроченный результат
			del _rag_cache[cache_key]
	return None

def _cache_result(search_query: str, result: str) -> None:
	"""Кэширует результат запроса."""
	cache_key = _get_cache_key(search_query)
	_rag_cache[cache_key] = (result, time.time())
	# Простая очистка: если кэш слишком большой, удаляем старые записи
	if len(_rag_cache) > 1000:
		now = time.time()
		expired_keys = [k for k, (_, ts) in _rag_cache.items() if now - ts > RAG_CACHE_TTL]
		for k in expired_keys:
			del _rag_cache[k]

def _register_tools(agent: Agent) -> Agent:
	@agent.tool
	async def retrieve(context: RunContext[RAGDeps], search_query: str) -> str:  # type: ignore
		import time
		retrieve_start = time.perf_counter()
		
		try:
			logger.debug(f"[retrieve] start query='{search_query}'")
			
			# Проверяем кэш
			cache_start = time.perf_counter()
			cached_result = _get_cached_result(search_query)
			if cached_result is not None:
				cache_time = time.perf_counter() - cache_start
				logger.info(f"[retrieve] cache hit in {cache_time:.3f}s")
				# Попытка логирования метрик (если доступен aggregator)
				try:
					from app.api.server import aggregator
					aggregator.track_rag_retrieve(time.perf_counter() - retrieve_start)
				except ImportError:
					pass
				return cached_result
			
			# Адаптивный таймаут и режим поиска
			rag = await context.deps.rag_manager.get_rag()
			query_length = len(search_query.split())
			
			# Оптимизация: используем более агрессивную адаптацию
			if query_length <= 3:  # Очень простые запросы
				retrieve_timeout = int(os.getenv("RAG_RETRIEVE_TIMEOUT_FAST", "10"))
				search_mode = "local"
			elif query_length <= 7:  # Средние запросы  
				retrieve_timeout = int(os.getenv("RAG_RETRIEVE_TIMEOUT_MEDIUM", "30"))
				search_mode = "hybrid"
			else:  # Сложные запросы
				retrieve_timeout = int(os.getenv("RAG_RETRIEVE_TIMEOUT_SECONDS", "60"))
				search_mode = "mix"
			
			logger.info(f"[retrieve] query_len={query_length}, timeout={retrieve_timeout}s, mode={search_mode}")
			
			try:
				rag_start = time.perf_counter()
				result = await asyncio.wait_for(
					rag.aquery(search_query, param=QueryParam(mode=search_mode)),
					timeout=retrieve_timeout
				)
				rag_time = time.perf_counter() - rag_start
				logger.info(f"[retrieve] RAG query completed in {rag_time:.3f}s")
				
			except asyncio.TimeoutError:
				timeout_time = time.perf_counter() - retrieve_start
				logger.warning(f"[retrieve] timeout after {retrieve_timeout}s (total: {timeout_time:.3f}s)")
				
				# Интеллектуальный fallback: попробуем более быстрый режим
				try:
					logger.info("[retrieve] attempting fast fallback with 'local' mode")
					fallback_start = time.perf_counter()
					result = await asyncio.wait_for(
						rag.aquery(search_query, param=QueryParam(mode="local")),
						timeout=15  # Короткий таймаут для fallback
					)
					fallback_time = time.perf_counter() - fallback_start
					logger.info(f"[retrieve] fast fallback succeeded in {fallback_time:.3f}s")
				except (asyncio.TimeoutError, Exception) as fb_err:
					logger.warning(f"[retrieve] fallback also failed: {fb_err}")
					fallback_msg = f"Поиск по запросу '{search_query}' занял слишком много времени. Попробуйте упростить запрос."
					_cache_result(search_query, fallback_msg)
					# Логируем метрики даже для таймаутов
					try:
						from app.api.server import aggregator
						aggregator.track_rag_retrieve(time.perf_counter() - retrieve_start)
					except ImportError:
						pass
					return fallback_msg
			
			# Преобразуем результат в строку для кэширования
			result_str = str(result)
			_cache_result(search_query, result_str)
			
			# Улучшенная диагностика
			result_size = len(result_str)
			try:
				if isinstance(result, list):
					logger.info(f"[retrieve] got list len={len(result)}, total_chars={result_size}")
				elif isinstance(result, dict):
					logger.info(f"[retrieve] got dict keys={list(result.keys())[:6]}, total_chars={result_size}")
			except Exception:  # noqa: BLE001
				pass
			
			total_time = time.perf_counter() - retrieve_start
			logger.info(f"[retrieve] completed in {total_time:.3f}s")
			
			# Логируем метрики
			try:
				from app.api.server import aggregator
				aggregator.track_rag_retrieve(total_time)
			except ImportError:
				pass
			
			return result
			
		except Exception as e:  # noqa: BLE001
			error_time = time.perf_counter() - retrieve_start
			logger.error(f"[retrieve] error after {error_time:.3f}s: {e}")
			# Логируем метрики даже для ошибок
			try:
				from app.api.server import aggregator
				aggregator.track_rag_retrieve(error_time)
			except ImportError:
				pass
			return f"Error retrieving documents: {e}"
	return agent


@lru_cache(maxsize=256)
def create_agent(model: Optional[str] = None, system_prompt: Optional[str] = None) -> Agent:
	resolved_model = resolve_agent_model(model)
	sp = system_prompt or DEFAULT_SYSTEM_PROMPT
	logger.info(f"Creating Agent(model={resolved_model}, system_prompt_len={len(sp)})")
	agent = Agent(resolved_model, deps_type=RAGDeps, system_prompt=sp)
	return _register_tools(agent)


agent = create_agent()


async def run_rag_agent(
	question: str,
	config: Optional[RAGConfig] = None,
	system_prompt: Optional[str] = None,
	model: Optional[str] = None,
	enable_fallback: bool = True,
) -> str:
	try:
		if config is None:
			config = get_default_config()
		rag_manager = RAGManager(config)
		deps = RAGDeps(rag_manager=rag_manager)
		local_agent = create_agent(model=model, system_prompt=system_prompt)
		try:
			result = await local_agent.run(question, deps=deps)
			return result.data
		except Exception as primary_err:  # noqa: BLE001
			err_str = str(primary_err)
			if enable_fallback and ("model_not_found" in err_str or "404" in err_str):
				fallbacks_env = os.getenv("OPENAI_FALLBACK_MODELS", "")
				fallbacks: List[str] = [m.strip() for m in fallbacks_env.split(",") if m.strip()]
				if fallbacks:
					fb = fallbacks[0]
					logger.warning(f"Primary model failed ({err_str}). Retrying with fallback model '{fb}'")
					try:
						fb_agent = create_agent(model=fb, system_prompt=system_prompt)
						result_fb = await fb_agent.run(question, deps=deps)
						return result_fb.data
					except Exception as fb_err:  # noqa: BLE001
						return f"Error running RAG agent (fallback '{fb}' failed): {fb_err}"
			return f"Error running RAG agent: {primary_err}"
	except Exception as e:  # noqa: BLE001
		return f"Error running RAG agent setup: {e}"


def _load_prompt_from_file(path: str) -> str:
	with open(path, 'r', encoding='utf-8') as f:
		return f.read()


def main():
	parser = argparse.ArgumentParser(description="Run a Pydantic AI agent with RAG using LightRAG")
	parser.add_argument("--question", required=True, help="The question to answer about Pydantic AI")
	parser.add_argument("--working-dir", default="./documents", help="Working directory for LightRAG")
	parser.add_argument("--no-rerank", action="store_true", help="Disable reranking")
	parser.add_argument("--system-prompt", help="Inline system prompt to guide retrieval and answering")
	parser.add_argument("--system-prompt-file", help="Path to a file containing the system prompt (overrides --system-prompt)")
	parser.add_argument("--model", help="Override model (e.g. gpt-5)")
	parser.add_argument("--no-fallback", action="store_true", help="Disable fallback chain even if OPENAI_FALLBACK_MODELS is set")
	args = parser.parse_args()
	config = RAGConfig(working_dir=args.working_dir, rerank_enabled=not args.no_rerank)
	system_prompt_val: Optional[str] = None
	if args.system_prompt_file:
		try:
			system_prompt_val = _load_prompt_from_file(args.system_prompt_file)
		except Exception as e:  # noqa: BLE001
			print(f"Failed to read system prompt file: {e}")
			sys.exit(1)
	elif args.system_prompt:
		system_prompt_val = args.system_prompt
	try:
		response = asyncio.run(run_rag_agent(
			args.question,
			config,
			system_prompt_val,
			model=args.model,
			enable_fallback=not args.no_fallback,
		))
		print("\nResponse:")
		print(response)
	except KeyboardInterrupt:
		print("\nOperation cancelled by user.")
	except Exception as e:  # noqa: BLE001
		print(f"Error: {e}")
		sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
	main()

