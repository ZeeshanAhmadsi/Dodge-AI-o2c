"""
app/core/log_context.py
=======================
Thread and async-safe session ID propagation for per-request log tagging.

Uses Python's `contextvars.ContextVar` so that every async task or thread
that handles a distinct request carries its own isolated session ID — no
globals, no thread-local hacks.

Usage:
    # At the start of a request (e.g. in ChatRouter.process_query):
    from app.core.log_context import set_session_id
    set_session_id("abc-123")

    # Anywhere downstream, the SessionLogFilter reads it automatically.
    # You never need to pass session_id through function arguments.
"""

from contextvars import ContextVar

# ---------------------------------------------------------------------------
# Context variable — default is "NO_SESSION" so stray log lines are obvious
# ---------------------------------------------------------------------------

session_id_var: ContextVar[str] = ContextVar("session_id", default="NO_SESSION")


def set_session_id(session_id: str) -> None:
    """
    Bind a session ID to the current execution context.

    Call this once at the top of a request handler before any logging
    happens. All downstream modules will automatically inherit this value
    through Python's context propagation (asyncio tasks and threads created
    after this call will each carry their own copy of the var).

    Args:
        session_id: Unique identifier for the current user session or request.
    """
    session_id_var.set(session_id or "NO_SESSION")


def get_session_id() -> str:
    """
    Return the session ID bound to the current execution context.

    Returns:
        The session ID string, or "NO_SESSION" if none has been set.
    """
    return session_id_var.get()
