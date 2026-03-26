"""
app/core/logger.py
==================
Structured logging factory for the Swiftex analytical pipeline.

Design Goals:
- Every log line carries: timestamp | level | session_id | module | func | message
- Session ID is auto-injected from the current execution context (no arg threading)
- Logs go to both the console (colour-coded by level) and a persistent log file
- Simple FileHandler — no rotation, no size limits (append forever)
- One call to get_logger() is all any module needs

Usage:
    from app.core.logger import get_logger
    logger = get_logger(__name__)

    logger.info("Step started")   # automatically tagged with session_id
    logger.debug("Raw args: %s", args)
    logger.error("Tool failed: %s", exc)
"""

import logging
import os
from pathlib import Path

from app.core.log_context import get_session_id

# ---------------------------------------------------------------------------
# Log file location — project_root/logs/analytical.log
# The logs/ directory is created automatically if it does not exist.
# ---------------------------------------------------------------------------

_LOG_DIR  = Path(__file__).resolve().parents[2] / "logs"
_LOG_FILE = _LOG_DIR / "analytical.log"

# ANSI colour codes mapped to each log level (console only)
_LEVEL_COLOURS: dict[int, str] = {
    logging.DEBUG:    "\033[36m",   # Cyan
    logging.INFO:     "\033[32m",   # Green
    logging.WARNING:  "\033[33m",   # Yellow
    logging.ERROR:    "\033[31m",   # Red
    logging.CRITICAL: "\033[35m",   # Magenta
}
_RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Log record format — the same fields appear on every single line
# ---------------------------------------------------------------------------

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(session_id)s | %(name)s.%(funcName)s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# SessionLogFilter — reads session_id from contextvars and injects it
# ---------------------------------------------------------------------------

class SessionLogFilter(logging.Filter):
    """
    Injects the active ``session_id`` contextvar value into every LogRecord
    before it reaches a handler formatter.

    This approach keeps logging calls clean — callers never pass session_id
    as a kwarg.  The filter runs synchronously on the same thread/task that
    emitted the log, so the contextvar lookup is always correct.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.session_id = get_session_id()
        return True  # Always pass the record through


# ---------------------------------------------------------------------------
# ColourFormatter — wraps level name in ANSI codes for the console handler
# ---------------------------------------------------------------------------

class ColourFormatter(logging.Formatter):
    """
    Console-only formatter that colour-codes the level name using ANSI escape
    sequences for quick visual scanning.

    IMPORTANT: We copy the LogRecord before mutating ``levelname`` so that the
    original record (shared with all other handlers on the same logger) is never
    modified.  Without this, the ANSI codes would bleed into the file handler's
    output as well.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Shallow-copy so we don't pollute the original record seen by other handlers
        coloured = logging.makeLogRecord(record.__dict__)
        colour = _LEVEL_COLOURS.get(record.levelno, "")
        coloured.levelname = f"{colour}{record.levelname}{_RESET}"
        return super().format(coloured)


# ---------------------------------------------------------------------------
# Internal registry — one logger instance per name, created once
# ---------------------------------------------------------------------------

_registry: dict[str, logging.Logger] = {}


def _build_logger(name: str) -> logging.Logger:
    """
    Construct and fully configure a named logger.

    Called exactly once per unique name; subsequent calls return the cached
    instance from ``_registry`` to avoid adding duplicate handlers.
    """
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)  # Floor — handlers control effective output level
    log.propagate = False        # Don't bubble up to the root logger

    # Shared filter that injects session_id into every record
    session_filter = SessionLogFilter()

    # ── Console handler (INFO+ by default; DEBUG shown only in dev) ──────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        ColourFormatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    )
    console_handler.addFilter(session_filter)

    # ── Full log file handler (DEBUG+) ──────────────────────────────────
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(filename=_LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    )
    file_handler.addFilter(session_filter)

    # ── Error-only log file handler (ERROR+) ────────────────────────────
    _ERROR_LOG_FILE = _LOG_DIR / "analytical_error.log"
    error_handler = logging.FileHandler(filename=_ERROR_LOG_FILE, mode="a", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    )
    error_handler.addFilter(session_filter)

    log.addHandler(console_handler)
    log.addHandler(file_handler)
    log.addHandler(error_handler)
    return log


def get_logger(name: str) -> logging.Logger:
    """
    Return a fully configured, session-aware logger for the given module name.

    This is the single public API for obtaining a logger anywhere in the
    analytical pipeline.  Call it at module level, exactly as you would call
    ``logging.getLogger``.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A ``logging.Logger`` instance that:
        - Writes structured lines to the console and ``logs/analytical.log``
        - Auto-injects ``session_id`` from the current async/thread context
        - Supports all standard log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

    Example::

        from app.core.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Planner invoked for query: %s", query)
    """
    if name not in _registry:
        _registry[name] = _build_logger(name)
    return _registry[name]
