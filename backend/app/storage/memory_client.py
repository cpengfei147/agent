"""In-memory storage client for development without Redis/PostgreSQL"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from collections import defaultdict


class MemoryClient:
    """In-memory client that mimics Redis interface for development"""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._messages: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._rate_limits: Dict[str, int] = {}
        self._privacy_shown: set = set()
        self.session_ttl = 24 * 3600

    async def connect(self):
        """No-op for memory client"""
        pass

    async def disconnect(self):
        """No-op for memory client"""
        pass

    async def ping(self) -> bool:
        """Always returns True"""
        return True

    # ============ Session Operations ============

    async def get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get session data from memory"""
        return self._sessions.get(f"session:{session_token}")

    async def set_session(
        self,
        session_token: str,
        session_id: str,
        current_phase: int,
        fields_status: Dict[str, Any],
        context: Dict[str, Any] = None,
        user_id: str = None
    ):
        """Save session data to memory"""
        key = f"session:{session_token}"
        data = {
            "id": session_id,
            "current_phase": current_phase,
            "fields_status": fields_status,
            "context": context or {},
            "last_activity": int(datetime.utcnow().timestamp())
        }
        if user_id:
            data["user_id"] = user_id
        self._sessions[key] = data

    async def update_session_field(
        self,
        session_token: str,
        field: str,
        value: Any
    ):
        """Update a single session field"""
        key = f"session:{session_token}"
        if key in self._sessions:
            self._sessions[key][field] = value

    async def delete_session(self, session_token: str):
        """Delete session from memory"""
        key = f"session:{session_token}"
        self._sessions.pop(key, None)
        self._messages.pop(f"session:{session_token}:messages", None)

    # ============ Message Cache Operations ============

    async def add_message(
        self,
        session_token: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Add message to cache"""
        key = f"session:{session_token}:messages"
        message = {
            "role": role,
            "content": content,
            "metadata": metadata,
            "ts": int(datetime.utcnow().timestamp())
        }
        self._messages[key].insert(0, message)
        # Keep only recent messages
        self._messages[key] = self._messages[key][:20]

    async def get_messages(
        self,
        session_token: str,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get cached messages"""
        key = f"session:{session_token}:messages"
        messages = self._messages.get(key, [])
        limit = limit or 20
        return list(reversed(messages[:limit]))

    # ============ Rate Limiting ============

    async def check_rate_limit(self, session_token: str) -> bool:
        """Check if session is rate limited"""
        key = f"ratelimit:{session_token}"
        self._rate_limits[key] = self._rate_limits.get(key, 0) + 1
        return self._rate_limits[key] <= 30

    # ============ Privacy Modal Flag ============

    async def is_privacy_shown(self, session_token: str) -> bool:
        """Check if privacy modal has been shown"""
        return session_token in self._privacy_shown

    async def set_privacy_shown(self, session_token: str):
        """Mark privacy modal as shown"""
        self._privacy_shown.add(session_token)


# Global memory client instance
_memory_client: Optional[MemoryClient] = None


async def get_memory_client() -> MemoryClient:
    """Get memory client instance"""
    global _memory_client
    if _memory_client is None:
        _memory_client = MemoryClient()
        await _memory_client.connect()
    return _memory_client


async def close_memory_client():
    """Close memory client (no-op)"""
    global _memory_client
    _memory_client = None
