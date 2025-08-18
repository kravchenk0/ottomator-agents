"""Shim module: use app.utils.diagnostics instead."""
from __future__ import annotations

import warnings
from app.utils.diagnostics import self_test_model  # noqa: F401

warnings.warn(
    "Importing 'diagnostics' from root is deprecated; use 'app.utils.diagnostics' instead.",
    DeprecationWarning,
    stacklevel=2,
)
