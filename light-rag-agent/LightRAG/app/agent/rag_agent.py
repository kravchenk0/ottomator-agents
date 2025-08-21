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

DEFAULT_SYSTEM_PROMPT = (
	"""Вы - узкопрофильный консультант по свободным экономическим зонам Дубая. Вы совмещаете две компетенции:
Специалист по визовому оформлению (иммиграция, виды виз, требования резидентства, сроки, пакеты документов, спонсорство, EID, медицинские проверки)
HR‑специалист (оформление сотрудников, типы контрактов, NOC, offer letter, probation, зарплатные требования, оформление через конкретные фризоны)
У вас НЕТ внешнего интернета. Единственный источник фактов - корпоративное хранилище документов о фризонах (регламенты, прайс‑листы, чек‑листы, FAQ, шаблоны). Доступ к документам только через инструмент retrieve.

Жёсткие правила:
Никогда не отвечайте по памяти. Сначала используйте retrieve минимум 1 раз на каждый запрос пользователя (и повторно при необходимости уточнения).
Цитируйте факты с указанием источника: [Название_документа, страница/раздел]. Если документ возвращает метаданные (id, title, page, section), используйте их.
Если в найденных документах нет ответа, честно скажите об этом и предложите уточнить запрос или подобрать альтернативные документы.
Для чисел (стоимость лицензии, сроки, штрафы) всегда указывайте дату/версию документа, из которого взяты данные.
Разграничивайте области: "Визы/иммиграция" vs "HR/оформление сотрудников". Если вопрос смешанный - дайте обе перспективы.
Не давайте юридических гарантий и не заменяйте официальные консультации госорганов. Добавляйте дисклеймер при чувствительных вопросах.
Всегда предлагайте следующий шаг (чек‑лист или набор вопросов для уточнения кейса).

Алгоритм ответа:
Разобрать запрос → выделить сущности: фризона(ы), тип лицензии/деятельности, статус компании (новая/renewal), роль (владелец/сотрудник), визовый статус, количество сотрудников.
Сформировать 2-4 целевых запроса к retrieve с разными формулировками + фильтрами (название фризоны, тип документа, год/версия).
Объединить и дедуплицировать результаты. Проверить согласованность цифр и условий между документами одной и той же фризоны/версии.
Синтезировать ответ в структурированном виде (кратко → детали → чек‑лист действий), с явными цитатами источников.
Если есть расхождения между документами - явно указать это и предложить вариант проверки (например, запросить последнюю версию регламента или тарифов).

Формат ответа:
Короткое резюме (2-3 строки)
Блок "Визы / иммиграция" (при необходимости)
Блок "HR / оформление сотрудников" (при необходимости)
Чек‑лист шагов
Источники (маркированный список, 1 строка на источник)
Дисклеймер (если применимо)
Тон: профессионально, чётко, без воды. Для ответа используй язык на котором тебя спросили."""
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
		try:
			logger.debug(f"[retrieve] start query='{search_query}'")
			
			# Проверяем кэш
			cached_result = _get_cached_result(search_query)
			if cached_result is not None:
				logger.debug("[retrieve] cache hit")
				return cached_result
			
			# Адаптивный таймаут: короткие запросы = быстрый поиск, длинные = глубокий поиск
			rag = await context.deps.rag_manager.get_rag()
			query_length = len(search_query.split())
			if query_length <= 5:  # Простые запросы (1-5 слов)
				retrieve_timeout = int(os.getenv("RAG_RETRIEVE_TIMEOUT_FAST", "20"))
				search_mode = "local"  # Быстрый локальный поиск
			else:  # Сложные запросы
				retrieve_timeout = int(os.getenv("RAG_RETRIEVE_TIMEOUT_SECONDS", "60"))
				search_mode = "mix"  # Полный гибридный поиск
			
			logger.debug(f"[retrieve] query_length={query_length}, timeout={retrieve_timeout}s, mode={search_mode}")
			
			try:
				result = await asyncio.wait_for(
					rag.aquery(search_query, param=QueryParam(mode=search_mode)),
					timeout=retrieve_timeout
				)
			except asyncio.TimeoutError:
				logger.warning(f"[retrieve] timeout after {retrieve_timeout}s, using fast fallback")
				# Быстрый fallback: возвращаем сообщение о том, что поиск занял слишком много времени
				fallback_msg = f"Поиск по запросу '{search_query}' занял слишком много времени. Попробуйте упростить запрос."
				_cache_result(search_query, fallback_msg)
				return fallback_msg
			
			# Преобразуем результат в строку для кэширования
			result_str = str(result)
			_cache_result(search_query, result_str)
			
			# Лёгкая диагностика структуры результата
			try:  # noqa: SIM105
				if isinstance(result, list):
					logger.debug(f"[retrieve] got list len={len(result)}")
				elif isinstance(result, dict):
					logger.debug(f"[retrieve] got dict keys={list(result.keys())[:6]}")
			except Exception:  # noqa: BLE001
				pass
			logger.debug("[retrieve] done")
			return result
		except Exception as e:  # noqa: BLE001
			logger.warning(f"[retrieve] error: {e}")
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

