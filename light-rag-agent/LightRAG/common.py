"""Backward compatibility shim; prefer imports from app.core.rag / config."""
from __future__ import annotations

import warnings
from app.core.config import RAGConfig, get_default_config  # type: ignore
from app.core.rag import (  # type: ignore
    RAGManager,
    dynamic_openai_complete,
    get_temperature_adjustment_state,
    validate_file_path,
    sanitize_filename,
)

warnings.warn(
    "Module 'common' deprecated: use 'app.core.config' and 'app.core.rag' instead.",
    DeprecationWarning,
    stacklevel=2,
)
