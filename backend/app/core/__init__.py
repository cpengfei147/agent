"""Core modules"""

# Lazy imports to avoid dependency issues during testing
def get_llm_client():
    from .llm_client import get_llm_client as _get_llm_client
    return _get_llm_client()


def create_llm_client():
    from .llm_client import create_llm_client as _create
    return _create()


def create_trace(session_id: str, user_message: str):
    from .tracing import create_trace as _create_trace
    return _create_trace(session_id, user_message)


def get_debug_tracer(session_id: str, enabled: bool = True):
    from .tracing import DebugTracer
    return DebugTracer(session_id, enabled)


__all__ = ["get_llm_client", "create_llm_client", "create_trace", "get_debug_tracer"]
