from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
import json
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Langfuse integration for observability
_langfuse = None

def get_langfuse_client():
    """Get Langfuse client for tracing"""
    global _langfuse
    if _langfuse is None and settings.langfuse_enabled:
        try:
            from langfuse import Langfuse
            _langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host
            )
            logger.info("Langfuse client initialized for LLM tracing")
        except ImportError:
            logger.warning("Langfuse not installed. Run: pip install langfuse")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
    return _langfuse


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
    """OpenAI API client (also supports DeepSeek and other compatible APIs)"""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = None):
        if base_url:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
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
        temperature: float = 0.7,
        trace_name: str = None,
        trace_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Send non-streaming chat request with optional Langfuse tracing"""
        generation = None
        langfuse = get_langfuse_client()

        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools
            if response_format:
                kwargs["response_format"] = response_format

            # Start Langfuse generation tracking (独立 try-except，不影响 LLM 调用)
            if langfuse and trace_name:
                try:
                    generation = langfuse.generation(
                        name=trace_name,
                        model=self.model,
                        input=messages,
                        metadata=trace_metadata or {}
                    )
                except Exception as e:
                    logger.warning(f"Langfuse tracking failed (will continue without tracing): {e}")
                    generation = None

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

            # End Langfuse generation tracking
            if generation:
                try:
                    generation.end(
                        output=message.content,
                        usage={
                            "input": response.usage.prompt_tokens if response.usage else 0,
                            "output": response.usage.completion_tokens if response.usage else 0,
                            "total": response.usage.total_tokens if response.usage else 0
                        }
                    )
                    langfuse.flush()
                except Exception as e:
                    logger.warning(f"Langfuse end tracking failed: {e}")

            return result

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            if generation:
                try:
                    generation.end(output=None, level="ERROR", status_message=str(e))
                    langfuse.flush()
                except Exception:
                    pass
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
            model=settings.openai_model,
            base_url=settings.openai_base_url  # 支持 DeepSeek 等兼容 API
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_llm_client() -> LLMClient:
    """Get global LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = create_llm_client("openai")
    return _llm_client
