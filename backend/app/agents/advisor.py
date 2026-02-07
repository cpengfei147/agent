"""Advisor Agent - 搬家顾问专家"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass

from app.core import get_llm_client
from app.models.fields import Phase
from app.models.schemas import RouterOutput, IntentType
from app.agents.prompts.advisor_prompt import (
    build_advisor_prompt,
    get_quick_answer,
    MOVING_KNOWLEDGE
)

logger = logging.getLogger(__name__)


@dataclass
class AdvisorResponse:
    """Advisor agent response"""
    text: str
    question_type: str
    knowledge_used: List[str]
    suggested_next_field: Optional[str] = None
    quick_options: List[str] = None

    def __post_init__(self):
        if self.quick_options is None:
            self.quick_options = []


class AdvisorAgent:
    """Advisor Agent for answering moving-related questions"""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def advise(
        self,
        router_output: RouterOutput,
        user_message: str,
        fields_status: Dict[str, Any],
        recent_messages: List[Dict[str, Any]] = None
    ) -> AdvisorResponse:
        """
        Generate advice response for user's question

        Args:
            router_output: Router's analysis result
            user_message: User's message
            fields_status: Current fields status
            recent_messages: Recent conversation history

        Returns:
            AdvisorResponse with advice and metadata
        """
        recent_messages = recent_messages or []

        # Determine question type
        question_type = self._determine_question_type(router_output)

        # Get knowledge areas used
        knowledge_used = self._get_knowledge_areas(question_type)

        # Build prompt
        style = router_output.response_strategy.style.value
        emotion = router_output.user_emotion.value

        system_prompt = build_advisor_prompt(
            question_type=question_type,
            fields_status=fields_status,
            recent_messages=recent_messages,
            style=style,
            user_emotion=emotion
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
            text = self._get_fallback_response(question_type)
        else:
            text = response.get("content", self._get_fallback_response(question_type))

        # Determine suggested next field
        from app.core.phase_inference import get_next_priority_field
        suggested_next = get_next_priority_field(fields_status)

        # Get quick options
        quick_options = self._get_quick_options(question_type, fields_status)

        return AdvisorResponse(
            text=text,
            question_type=question_type,
            knowledge_used=knowledge_used,
            suggested_next_field=suggested_next,
            quick_options=quick_options
        )

    async def stream_advise(
        self,
        router_output: RouterOutput,
        user_message: str,
        fields_status: Dict[str, Any],
        recent_messages: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream advice response

        Yields:
            Dict with type and content
        """
        recent_messages = recent_messages or []

        # Determine question type
        question_type = self._determine_question_type(router_output)
        knowledge_used = self._get_knowledge_areas(question_type)

        # Build prompt
        style = router_output.response_strategy.style.value
        emotion = router_output.user_emotion.value

        system_prompt = build_advisor_prompt(
            question_type=question_type,
            fields_status=fields_status,
            recent_messages=recent_messages,
            style=style,
            user_emotion=emotion
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
        from app.core.phase_inference import get_next_priority_field
        suggested_next = get_next_priority_field(fields_status)
        quick_options = self._get_quick_options(question_type, fields_status)

        yield {
            "type": "metadata",
            "question_type": question_type,
            "knowledge_used": knowledge_used,
            "suggested_next_field": suggested_next,
            "quick_options": quick_options
        }

    def _determine_question_type(self, router_output: RouterOutput) -> str:
        """Determine the type of question being asked"""
        intent = router_output.intent.primary

        intent_to_question = {
            IntentType.ASK_PRICE: "ask_price",
            IntentType.ASK_PROCESS: "ask_process",
            IntentType.ASK_COMPANY: "ask_company",
            IntentType.ASK_TIPS: "ask_tips",
            IntentType.ASK_GENERAL: "ask_general"
        }

        return intent_to_question.get(intent, "ask_general")

    def _get_knowledge_areas(self, question_type: str) -> List[str]:
        """Get knowledge areas relevant to question type"""
        type_to_knowledge = {
            "ask_price": ["price"],
            "ask_process": ["process"],
            "ask_company": ["company"],
            "ask_tips": ["tips"],
            "ask_general": ["process", "tips"]
        }

        return type_to_knowledge.get(question_type, ["tips"])

    def _get_fallback_response(self, question_type: str) -> str:
        """Get fallback response when LLM fails"""
        fallbacks = {
            "ask_price": "搬家费用主要看物品数量、距离和服务类型。单身搬家一般3-8万日元，家庭搬家8-20万日元左右。想要准确报价的话，告诉我您的具体情况吧~",
            "ask_process": "搬家一般提前2-4周开始准备：确定搬家公司、整理物品、办理地址变更。需要详细的清单吗？",
            "ask_company": "日本主要的搬家公司有アート、サカイ、日通等，建议多家比价。需要我帮您整理报价请求吗？",
            "ask_tips": "搬家小建议：淡季搬家更便宜、提前整理物品、自己打包可省钱。有具体想了解的吗？",
            "ask_general": "关于搬家有什么想了解的都可以问我哦~"
        }

        return fallbacks.get(question_type, fallbacks["ask_general"])

    def _get_quick_options(
        self,
        question_type: str,
        fields_status: Dict[str, Any]
    ) -> List[str]:
        """Get quick options after answering"""
        from app.core.phase_inference import get_completion_info

        completion = get_completion_info(fields_status)

        # Base options depend on completion state
        if completion["can_submit"]:
            return ["确认信息", "还有其他问题"]

        # Options based on question type
        if question_type == "ask_price":
            return ["继续填写信息获取报价", "还有价格问题", "其他问题"]
        elif question_type == "ask_process":
            return ["开始整理搬家信息", "查看详细清单", "其他问题"]
        elif question_type == "ask_company":
            return ["帮我整理报价请求", "还想了解其他公司", "其他问题"]

        # Default: guide back to collection
        next_field = completion.get("next_priority_field")
        if next_field:
            field_names = {
                "people_count": "告诉你搬家人数",
                "from_address": "告诉你搬出地址",
                "to_address": "告诉你搬入地址",
                "move_date": "告诉你搬家日期"
            }
            guide_option = field_names.get(next_field, "继续填写信息")
            return [guide_option, "还有其他问题"]

        return ["继续", "还有问题"]


# Global advisor agent instance
_advisor_agent: Optional[AdvisorAgent] = None


def get_advisor_agent() -> AdvisorAgent:
    """Get global advisor agent instance"""
    global _advisor_agent
    if _advisor_agent is None:
        _advisor_agent = AdvisorAgent()
    return _advisor_agent
