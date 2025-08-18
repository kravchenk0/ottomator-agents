"""Shim module: use app.agent.rag_agent instead."""
from __future__ import annotations

import warnings
from app.agent.rag_agent import (  # noqa: F401
    RAGDeps,
    resolve_agent_model,
    create_agent,
    agent,
    run_rag_agent,
)

warnings.warn(
    "Importing 'rag_agent' from root is deprecated; use 'app.agent.rag_agent' instead.",
    DeprecationWarning,
    stacklevel=2,
)
