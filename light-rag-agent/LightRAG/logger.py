"""Shim module: use app.utils.logging instead."""
from __future__ import annotations

import warnings
from app.utils.logging import (  # noqa: F401
    setup_logger,
    get_logger,
    PerformanceLogger,
    performance_logger,
    log_function_call,
)

warnings.warn(
    "Importing 'logger' from root is deprecated; use 'app.utils.logging' instead.",
    DeprecationWarning,
    stacklevel=2,
)