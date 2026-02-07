"""Data models"""

# Import lightweight models directly
from .fields import FieldStatus, CollectedFields, Phase, get_default_fields
from .schemas import (
    ChatMessage,
    ChatResponse,
    SessionResponse,
    UIComponent,
    UIComponentType,
)


# Lazy import for database models to avoid import errors during testing
def get_database_models():
    from .database import Base, Session, Message, UploadedImage, Quote, User
    return Base, Session, Message, UploadedImage, Quote, User


__all__ = [
    "FieldStatus",
    "CollectedFields",
    "Phase",
    "get_default_fields",
    "ChatMessage",
    "ChatResponse",
    "SessionResponse",
    "UIComponent",
    "UIComponentType",
    "get_database_models",
]
