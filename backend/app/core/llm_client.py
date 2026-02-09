from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
import json
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM clients"""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        stream: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Send chat request and yield responses"""
        pass

    @abstractmethod
    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        response_format: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Send chat request and return complete response"""
        pass


class OpenAIClient(LLMClient):
    """OpenAI API client"""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        stream: bool = True,
        temperature: float = 0.85
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Send streaming chat request"""
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": stream,
                "temperature": temperature,  # 添加温度参数让回复更多样化
            }
            if tools:
                kwargs["tools"] = tools

            response = await self.client.chat.completions.create(**kwargs)

            if stream:
                full_content = ""
                tool_calls = []

                async for chunk in response:
                    delta = chunk.choices[0].delta

                    # Handle text content
                    if delta.content:
                        full_content += delta.content
                        yield {
                            "type": "text_delta",
                            "content": delta.content
                        }

                    # Handle tool calls
                    if delta.tool_calls:
                        for tool_call in delta.tool_calls:
                            # Accumulate tool call data
                            if tool_call.index >= len(tool_calls):
                                tool_calls.append({
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name if tool_call.function else "",
                                        "arguments": ""
                                    }
                                })
                            if tool_call.function and tool_call.function.arguments:
                                tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments

                    # Check for finish
                    if chunk.choices[0].finish_reason:
                        yield {
                            "type": "done",
                            "finish_reason": chunk.choices[0].finish_reason,
                            "content": full_content,
                            "tool_calls": tool_calls if tool_calls else None
                        }
            else:
                # Non-streaming response
                yield {
                    "type": "complete",
                    "content": response.choices[0].message.content,
                    "tool_calls": response.choices[0].message.tool_calls
                }

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }

    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        response_format: Dict[str, Any] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Send non-streaming chat request"""
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,  # 添加温度参数让回复更多样化
            }
            if tools:
                kwargs["tools"] = tools
            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)

            message = response.choices[0].message

            result = {
                "content": message.content,
                "tool_calls": None,
                "finish_reason": response.choices[0].finish_reason
            }

            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]

            return result

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return {
                "content": None,
                "error": str(e)
            }

    async def check_connection(self) -> bool:
        """Check API connection"""
        try:
            response = await self.client.models.list()
            return True
        except Exception:
            return False


# Placeholder for future DeepSeek client
class DeepSeekClient(LLMClient):
    """DeepSeek API client (placeholder for future implementation)"""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.api_key = api_key
        self.model = model
        raise NotImplementedError("DeepSeek client not yet implemented")

    async def chat(self, messages, tools=None, stream=True):
        raise NotImplementedError()

    async def chat_complete(self, messages, tools=None, response_format=None):
        raise NotImplementedError()


# Global LLM client instance
_llm_client: Optional[LLMClient] = None


def create_llm_client(provider: str = "openai") -> LLMClient:
    """Factory function to create LLM client"""
    if provider == "openai":
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model
        )
    elif provider == "deepseek":
        return DeepSeekClient(
            api_key=settings.openai_api_key,  # Placeholder
            model="deepseek-chat"
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_llm_client() -> LLMClient:
    """Get global LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = create_llm_client("openai")
    return _llm_client
