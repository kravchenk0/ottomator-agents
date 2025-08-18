"""Shim: moved to app.api.server (import app.api.server:app)."""
from __future__ import annotations

import warnings
from app.api.server import app  # noqa: F401

warnings.warn(
    "Import api_server:app from app.api.server instead of root api_server.",
    DeprecationWarning,
    stacklevel=2,
)