"""Agent creation & run utilities (migrated from root rag_agent.py eventually).

(Шаг 1) Заглушка.
"""
from __future__ import annotations

import os
import sys
import argparse
import asyncio
import logging
from functools import lru_cache
from dataclasses import dataclass
from typing import Optional, List

from pydantic_ai import RunContext
from pydantic_ai.agent import Agent
from lightrag import QueryParam

from app.core import RAGManager, RAGConfig, get_default_config

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
	"You are a helpful assistant that answers questions about Pydantic AI based on the provided documentation. "
	"Before answering, always use the retrieve tool to fetch relevant context. "
	"If the documentation doesn't contain the answer, clearly state that the information isn't available "
	"in the current documentation and provide your best general knowledge response. "
	"When retrieving, rewrite the user's query into 2-3 focused sub-queries with key terms and synonyms. "
	"Prefer precise keywords (APIs, classes, functions) over natural language."
)

@dataclass
class RAGDeps:
	rag_manager: RAGManager


def resolve_agent_model(explicit: Optional[str] = None) -> str:
	base = explicit or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL") or "gpt-4.1-mini"
	if not base.startswith("openai:"):
		base = f"openai:{base}"
	return base


def _register_tools(agent: Agent) -> Agent:
	@agent.tool
	async def retrieve(context: RunContext[RAGDeps], search_query: str) -> str:  # type: ignore
		try:
			rag = await context.deps.rag_manager.get_rag()
			return await rag.aquery(search_query, param=QueryParam(mode="mix"))
		except Exception as e:  # noqa: BLE001
			return f"Error retrieving documents: {e}"
	return agent


@lru_cache(maxsize=32)
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
	parser.add_argument("--working-dir", default="./pydantic-docs", help="Working directory for LightRAG")
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

