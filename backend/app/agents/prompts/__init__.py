"""Agent prompts module"""

from app.agents.prompts.router_prompt import (
    ROUTER_SYSTEM_PROMPT,
    format_recent_messages,
    format_fields_status
)
from app.agents.prompts.collector_prompt import (
    build_collector_prompt,
    build_confirmation_prompt,
    get_field_collection_prompt,
    FIELD_COLLECTION_PROMPTS
)
from app.agents.prompts.advisor_prompt import (
    build_advisor_prompt,
    get_quick_answer,
    MOVING_KNOWLEDGE
)
from app.agents.prompts.companion_prompt import (
    build_companion_prompt,
    get_chitchat_response,
    detect_chitchat_type,
    EMOTION_STRATEGIES
)
from app.agents.prompts.persona import (
    ERABU_PERSONA,
    PERSONA_INJECTION,
    VARIETY_INSTRUCTION,
    EXAMPLE_PHRASES
)

__all__ = [
    # Router
    "ROUTER_SYSTEM_PROMPT",
    "format_recent_messages",
    "format_fields_status",
    # Collector
    "build_collector_prompt",
    "build_confirmation_prompt",
    "get_field_collection_prompt",
    "FIELD_COLLECTION_PROMPTS",
    # Advisor
    "build_advisor_prompt",
    "get_quick_answer",
    "MOVING_KNOWLEDGE",
    # Companion
    "build_companion_prompt",
    "get_chitchat_response",
    "detect_chitchat_type",
    "EMOTION_STRATEGIES",
    # Persona
    "ERABU_PERSONA",
    "PERSONA_INJECTION",
    "VARIETY_INSTRUCTION",
    "EXAMPLE_PHRASES"
]
