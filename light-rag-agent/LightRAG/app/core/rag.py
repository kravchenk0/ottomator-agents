"""Core RAG management & dynamic OpenAI completion (extracted from common)."""
from __future__ import annotations

import os
import logging
from typing import Optional, List
from pathlib import Path

from openai import AsyncOpenAI
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status

from ..utils import monkey_patch_lightrag  # noqa: F401  (ensure patch import)
from .config import RAGConfig

logger = logging.getLogger(__name__)

_models_reject_any_temp: set[str] = set()
_temperature_auto_adjust_done = False


class RAGManager:
	def __init__(self, config: RAGConfig):
		self.config = config
		self._rag: Optional[LightRAG] = None
		Path(config.working_dir).mkdir(parents=True, exist_ok=True)
		if not os.getenv("OPENAI_API_KEY") and os.getenv("ALLOW_START_WITHOUT_OPENAI_KEY", "0").lower() not in {"1","true","yes"}:
			raise ValueError("OPENAI_API_KEY environment variable not set. Set it or ALLOW_START_WITHOUT_OPENAI_KEY=1 for degraded mode.")

	async def initialize(self) -> LightRAG:
		if self._rag is None:
			if not os.getenv("OPENAI_API_KEY"):
				raise ValueError("Cannot initialize LightRAG without OPENAI_API_KEY")
			self._rag = LightRAG(
				working_dir=self.config.working_dir,
				embedding_func=openai_embed,
				llm_model_func=dynamic_openai_complete,
			)
			await self._rag.initialize_storages()
			await initialize_pipeline_status()
			try:
				self._backfill_file_path_fields()
			except Exception as e:  # noqa: BLE001
				logger.debug(f"file_path backfill skipped/failed: {e}")
		return self._rag

	async def get_rag(self) -> LightRAG:
		if self._rag is None:
			await self.initialize()
		return self._rag

	def _backfill_file_path_fields(self) -> None:
		if self._rag is None:
			return
		placeholder = "unknown_source"
		total_added = 0
		for attr_name in ["kv_store_full_docs", "kv_store_text_chunks", "kv_store_doc_status"]:
			store = getattr(self._rag, attr_name, None)
			if store is None:
				continue
			inner = getattr(store, "_store", None)
			if not isinstance(inner, dict):
				continue
			for _k, _v in inner.items():
				if isinstance(_v, dict) and "file_path" not in _v:
					_v["file_path"] = placeholder
					total_added += 1
		if total_added:
			logger.info(f"file_path backfill: inserted placeholder for {total_added} records")


async def dynamic_openai_complete(prompt: str, *args, **kwargs) -> str:  # noqa: D401
	global _temperature_auto_adjust_done
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise ValueError("OPENAI_API_KEY is required for dynamic_openai_complete")
	primary_model = os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL") or "gpt-4.1-mini"
	fallback_env = os.getenv("OPENAI_FALLBACK_MODELS", "").strip()
	fallback_list = [m.strip() for m in fallback_env.split(",") if m.strip()]
	models_to_try: List[str] = []
	if primary_model:
		models_to_try.append(primary_model)
	if primary_model == "gpt-5" and "gpt-4.1-mini" not in models_to_try:
		fallback_list.append("gpt-4.1-mini")
	if "gpt-4.1-mini" not in fallback_list and primary_model != "gpt-4.1-mini":
		fallback_list.append("gpt-4.1-mini")
	for m in fallback_list:
		if m not in models_to_try:
			models_to_try.append(m)
	try:
		temperature = float(os.getenv("OPENAI_TEMPERATURE", "0") or 0)
	except ValueError:
		temperature = 0.0
	client = AsyncOpenAI(api_key=api_key)
	last_error: Exception | None = None
	for model_name in models_to_try:
		try:
			logger.debug(f"dynamic_openai_complete: trying model={model_name}")
			def _messages():
				return [
					{"role": "system", "content": kwargs.get("system_prompt", "You are a helpful assistant.")},
					{"role": "user", "content": prompt},
				]
			omit_temp = model_name in _models_reject_any_temp
			try:
				if not omit_temp:
					resp = await client.chat.completions.create(model=model_name, messages=_messages(), temperature=temperature)
				else:
					resp = await client.chat.completions.create(model=model_name, messages=_messages())
			except Exception as e:  # noqa: BLE001
				es = str(e)
				if ("Unsupported value" in es or "unsupported_value" in es) and "temperature" in es:
					_models_reject_any_temp.add(model_name)
					if not _temperature_auto_adjust_done:
						logger.warning("Auto-adjust: model rejected explicit temperature; omitting going forward.")
						_temperature_auto_adjust_done = True
					resp = await client.chat.completions.create(model=model_name, messages=_messages())
				else:
					raise
			content = resp.choices[0].message.content if resp.choices else ""
			if not content:
				raise RuntimeError("Empty response content")
			if model_name != primary_model:
				logger.warning(f"dynamic_openai_complete: used fallback model '{model_name}' instead of '{primary_model}'")
			return content
		except Exception as e:  # noqa: BLE001
			last_error = e
			logger.warning(f"dynamic_openai_complete: model '{model_name}' failed: {e}")
			continue
	try:
		logger.warning("dynamic_openai_complete: falling back to bundled gpt_4o_mini_complete helper")
		return await gpt_4o_mini_complete(prompt, *args, **kwargs)
	except Exception as e2:  # noqa: BLE001
		raise RuntimeError(f"All model attempts failed. Last error: {last_error}; builtin fallback error: {e2}") from e2


def get_temperature_adjustment_state() -> dict:
	return {
		"auto_adjusted": _temperature_auto_adjust_done,
		"rejected_models": sorted(_models_reject_any_temp),
		"current_temperature": os.getenv("OPENAI_TEMPERATURE"),
	}


def validate_file_path(file_path: str) -> bool:
	try:
		path = Path(file_path)
		return path.exists() and path.is_file() and path.stat().st_size > 0
	except Exception:  # noqa: BLE001
		return False


def sanitize_filename(filename: str) -> str:
	import re
	sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
	return sanitized[:100]

