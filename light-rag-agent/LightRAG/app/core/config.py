"""Configuration dataclasses and defaults for RAG (extracted from common)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RAGConfig:
	working_dir: str = "./pydantic-docs"
	embedding_model: str = "gpt-5-mini"
	llm_model: str = "gpt-5-mini"
	rerank_enabled: bool = True
	batch_size: int = 20
	max_docs_for_rerank: int = 20

def get_default_config() -> RAGConfig:
	return RAGConfig()

