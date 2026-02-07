"""Companion Agent - 情感陪伴专家"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass

from app.core import get_llm_client
from app.models.fields import Phase
from app.models.schemas import RouterOutput, IntentType, Emotion
from app.agents.prompts.companion_prompt import (
    build_companion_prompt,
    get_chitchat_response,
    detect_chitchat_type,
    EMOTION_STRATEGIES
)

logger = logging.getLogger(__name__)


@dataclass
class CompanionResponse:
    """Companion agent response"""
    text: str
    emotion_handled: str
    strategy_used: str
    should_transition: bool
    suggested_next_field: Optional[str] = None
    quick_options: List[str] = None

    def __post_init__(self):
        if self.quick_options is None:
            self.quick_options = []


class CompanionAgent:
    """Companion Agent for emotional support and conversation"""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def comfort(
        self,
        router_output: RouterOutput,
        user_message: str,
        fields_status: Dict[str, Any],
        recent_messages: List[Dict[str, Any]] = None
    ) -> CompanionResponse:
        """
        Generate comfort/support response

        Args:
            router_output: Router's analysis result
            user_message: User's message
            fields_status: Current fields status
            recent_messages: Recent conversation history

        Returns:
            CompanionResponse with comfort message and metadata
        """
        recent_messages = recent_messages or []

        # Determine emotion and strategy
        emotion = router_output.user_emotion.value
        strategy = self._determine_strategy(emotion, router_output.intent.primary)

        # Check for chitchat
        chitchat_type = detect_chitchat_type(user_message)
        if chitchat_type:
            quick_response = get_chitchat_response(chitchat_type)
            if quick_response:
                return CompanionResponse(
                    text=quick_response,
                    emotion_handled=emotion,
                    strategy_used="chitchat",
                    should_transition=chitchat_type not in ["bye"],
                    quick_options=self._get_quick_options(emotion, fields_status)
                )

        # Build prompt
        style = router_output.response_strategy.style.value

        system_prompt = build_companion_prompt(
            emotion=emotion,
            user_message=user_message,
            fields_status=fields_status,
            recent_messages=recent_messages,
            style=style
        )

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add conversation history
        for msg in recent_messages[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        messages.append({
            "role": "user",
            "content": user_message
        })

        # Call LLM
        response = await self.llm_client.chat_complete(messages=messages)

        if response.get("error"):
            logger.error(f"LLM error: {response['error']}")
            text = self._get_fallback_response(emotion)
        else:
            text = response.get("content", self._get_fallback_response(emotion))

        # Determine if we should transition back to collection
        should_transition = self._should_transition(emotion, router_output.intent.primary)

        # Get suggested next field
        from app.core.phase_inference import get_next_priority_field
        suggested_next = get_next_priority_field(fields_status) if should_transition else None

        # Get quick options
        quick_options = self._get_quick_options(emotion, fields_status)

        return CompanionResponse(
            text=text,
            emotion_handled=emotion,
            strategy_used=strategy,
            should_transition=should_transition,
            suggested_next_field=suggested_next,
            quick_options=quick_options
        )

    async def stream_comfort(
        self,
        router_output: RouterOutput,
        user_message: str,
        fields_status: Dict[str, Any],
        recent_messages: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream comfort response

        Yields:
            Dict with type and content
        """
        recent_messages = recent_messages or []

        emotion = router_output.user_emotion.value
        strategy = self._determine_strategy(emotion, router_output.intent.primary)

        # Check for chitchat first
        chitchat_type = detect_chitchat_type(user_message)
        if chitchat_type:
            quick_response = get_chitchat_response(chitchat_type)
            if quick_response:
                # Stream character by character for natural feel
                for char in quick_response:
                    yield {
                        "type": "text_delta",
                        "content": char
                    }
                yield {"type": "text_done"}

                yield {
                    "type": "metadata",
                    "emotion_handled": emotion,
                    "strategy_used": "chitchat",
                    "should_transition": chitchat_type not in ["bye"],
                    "quick_options": self._get_quick_options(emotion, fields_status)
                }
                return

        # Build prompt for LLM
        style = router_output.response_strategy.style.value

        system_prompt = build_companion_prompt(
            emotion=emotion,
            user_message=user_message,
            fields_status=fields_status,
            recent_messages=recent_messages,
            style=style
        )

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        for msg in recent_messages[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        messages.append({
            "role": "user",
            "content": user_message
        })

        # Stream response
        full_text = ""
        async for chunk in self.llm_client.chat(messages, stream=True):
            if chunk["type"] == "text_delta":
                full_text += chunk["content"]
                yield {
                    "type": "text_delta",
                    "content": chunk["content"]
                }
            elif chunk["type"] == "done":
                yield {"type": "text_done"}
            elif chunk["type"] == "error":
                yield {
                    "type": "error",
                    "error": chunk.get("error", "Unknown error")
                }
                return

        # Yield metadata
        should_transition = self._should_transition(emotion, router_output.intent.primary)

        from app.core.phase_inference import get_next_priority_field
        suggested_next = get_next_priority_field(fields_status) if should_transition else None

        yield {
            "type": "metadata",
            "emotion_handled": emotion,
            "strategy_used": strategy,
            "should_transition": should_transition,
            "suggested_next_field": suggested_next,
            "quick_options": self._get_quick_options(emotion, fields_status)
        }

    def _determine_strategy(self, emotion: str, intent: IntentType) -> str:
        """Determine handling strategy based on emotion and intent"""
        # For chitchat intent
        if intent == IntentType.CHITCHAT:
            return "casual_chat"

        # For emotional expressions
        emotion_strategies = {
            "anxious": "comfort_and_clarify",
            "confused": "simplify_and_guide",
            "frustrated": "listen_and_support",
            "urgent": "efficient_response",
            "positive": "maintain_momentum",
            "neutral": "friendly_engagement"
        }

        return emotion_strategies.get(emotion, "friendly_engagement")

    def _should_transition(self, emotion: str, intent: IntentType) -> bool:
        """Determine if we should transition back to collection"""
        # Don't push if user is frustrated or just chatting
        if intent == IntentType.CHITCHAT:
            return False

        if emotion in ["frustrated"]:
            return False

        # For other emotions, gentle transition is okay
        return True

    def _get_fallback_response(self, emotion: str) -> str:
        """Get fallback response when LLM fails"""
        strategy = EMOTION_STRATEGIES.get(emotion, EMOTION_STRATEGIES["positive"])

        # Combine acknowledge and one comfort
        acknowledge = strategy["acknowledge"]
        comfort = strategy["comfort"][0] if strategy["comfort"] else ""

        return f"{acknowledge}。{comfort}"

    def _get_quick_options(
        self,
        emotion: str,
        fields_status: Dict[str, Any]
    ) -> List[str]:
        """Get quick options based on emotion"""
        from app.core.phase_inference import get_completion_info

        completion = get_completion_info(fields_status)

        # Emotion-specific options
        if emotion == "anxious":
            return ["帮我理清思路", "先回答一些问题", "我需要休息一下"]
        elif emotion == "confused":
            return ["从头开始", "解释一下流程", "我先想想"]
        elif emotion == "frustrated":
            return ["继续吧", "让我冷静一下", "有什么问题吗"]
        elif emotion == "urgent":
            return ["快速填写关键信息", "我需要帮助", "有什么捷径吗"]

        # Default options
        if completion["can_submit"]:
            return ["继续", "确认信息"]

        next_field = completion.get("next_priority_field")
        if next_field:
            return ["继续填写", "我有问题想问", "休息一下"]

        return ["继续", "有问题"]


# Global companion agent instance
_companion_agent: Optional[CompanionAgent] = None


def get_companion_agent() -> CompanionAgent:
    """Get global companion agent instance"""
    global _companion_agent
    if _companion_agent is None:
        _companion_agent = CompanionAgent()
    return _companion_agent
