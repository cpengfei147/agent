"""Core modules"""

# Lazy imports to avoid dependency issues during testing
def get_llm_client():
    from .llm_client import get_llm_client as _get_llm_client
    return _get_llm_client()


def create_llm_client():
    from .llm_client import create_llm_client as _create
    return _create()


__all__ = ["get_llm_client", "create_llm_client"]
