"""Diagnostics utilities (migrated from root diagnostics.py)."""
from __future__ import annotations

import os
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def _collect_models_chain() -> List[str]:
	primary = os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL") or "gpt-5-mini"
	fallbacks_env = os.getenv("OPENAI_FALLBACK_MODELS", "")
	fallbacks = [m.strip() for m in fallbacks_env.split(",") if m.strip()]
	chain: List[str] = []
	if primary:
		chain.append(primary)
	# Always ensure gpt-5-mini is present as a stable fallback
	if primary != "gpt-5-mini" and "gpt-5-mini" not in fallbacks:
		fallbacks.append("gpt-5-mini")
	for m in fallbacks:
		if m not in chain:
			chain.append(m)
	return chain


async def self_test_model(prompt: str = "ping", max_output_tokens: int = 8) -> Dict[str, Any]:
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		return {"ok": False, "error": "NO_API_KEY", "tried": []}
	client = AsyncOpenAI(api_key=api_key)
	chain = _collect_models_chain()
	temperature = float(os.getenv("OPENAI_TEMPERATURE", "0"))
	tried: List[str] = []
	last_error: Optional[str] = None
	for model in chain:
		tried.append(model)
		try:
			resp = await client.responses.create(
				model=model,
				input=prompt,
				max_output_tokens=max_output_tokens,
				temperature=temperature,
			)
			text = resp.output_text or ""
			return {"ok": True, "model": model, "text_preview": text[:120], "tried": tried}
		except Exception as e:  # noqa: BLE001
			last_error = str(e)
			logger.warning(f"self_test_model: model '{model}' failed: {e}")
			continue
	return {"ok": False, "error": last_error or "UNKNOWN_ERROR", "tried": tried}

