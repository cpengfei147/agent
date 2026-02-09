import json
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.storage.redis_client import get_redis
from app.core import get_llm_client
from app.models.fields import get_default_fields, Phase
from app.agents.router import get_router_agent
from app.agents.collector import get_collector_agent
from app.agents.advisor import get_advisor_agent
from app.agents.companion import get_companion_agent
from app.core.phase_inference import infer_phase, get_completion_info
from app.services.smart_options import get_smart_quick_options
from app.models.schemas import AgentType
from app.services.quote_service import QuoteService, SessionPersistenceService
from app.services.item_service import get_item_service

logger = logging.getLogger(__name__)


def get_ui_component_for_phase(phase: Phase, fields_status: dict) -> dict:
    """
    Determine which UI component to show based on current phase and fields status.

    Returns:
        dict with type and optional data for the UI component
    """
    # Phase 2 (ADDRESS) - Show address verification component
    if phase == Phase.ADDRESS:
        from_address = fields_status.get("from_address", {})
        to_address = fields_status.get("to_address", {})

        # Check if either address needs verification
        from_status = from_address.get("status", "not_collected") if isinstance(from_address, dict) else "not_collected"
        to_status = to_address.get("status", "not_collected") if isinstance(to_address, dict) else "not_collected"

        if from_status == "needs_verification" or to_status == "needs_verification":
            return {
                "type": "address_verify",
                "data": {
                    "from_address": from_address if isinstance(from_address, dict) else {},
                    "to_address": to_address if isinstance(to_address, dict) else {},
                    "verification_needed": {
                        "from": from_status == "needs_verification",
                        "to": to_status == "needs_verification"
                    }
                }
            }

    # Phase 4 (ITEMS) - Show item evaluation component
    if phase == Phase.ITEMS:
        items = fields_status.get("items", {})
        items_status = items.get("status", "not_collected") if isinstance(items, dict) else "not_collected"

        # If items not yet collected, show item evaluation UI
        if items_status in ["not_collected", "in_progress"]:
            return {
                "type": "item_evaluation",
                "data": {
                    "current_items": items.get("list", []) if isinstance(items, dict) else [],
                    "can_upload_image": True,
                    "can_select_from_catalog": True
                }
            }

    # Phase 6 (CONFIRMATION) - Show confirmation or login card
    if phase == Phase.CONFIRMATION:
        completion_info = get_completion_info(fields_status)

        if completion_info["can_submit"]:
            # Check if user is logged in (has phone/email)
            user_contact = fields_status.get("user_contact", {})
            has_contact = bool(user_contact.get("phone") or user_contact.get("email"))

            if has_contact:
                # Show confirmation card with all collected info
                return {
                    "type": "confirm_card",
                    "data": {
                        "fields_status": fields_status,
                        "completion_rate": completion_info["completion_rate"],
                        "can_submit": True
                    }
                }
            else:
                # Show login card to collect contact info
                return {
                    "type": "login_card",
                    "data": {
                        "message": "请输入联系方式以便搬家公司与您联系"
                    }
                }

    return {"type": "none"}

router = APIRouter()


class ConnectionManager:
    """WebSocket connection manager"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, session_token: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_token] = websocket

    def disconnect(self, session_token: str):
        if session_token in self.active_connections:
            del self.active_connections[session_token]

    async def send_json(self, session_token: str, data: dict):
        if session_token in self.active_connections:
            await self.active_connections[session_token].send_json(data)


manager = ConnectionManager()


async def get_or_create_session(session_token: Optional[str]) -> dict:
    """Get existing session or create new one"""
    redis_client = await get_redis()

    if session_token:
        # Try to get existing session
        session = await redis_client.get_session(session_token)
        if session:
            return {
                "session_token": session_token,
                "session_id": session.get("id"),
                "current_phase": int(session.get("current_phase", 0)),
                "fields_status": session.get("fields_status", get_default_fields()),
                "is_new": False
            }

    # Create new session
    new_token = str(uuid.uuid4())
    new_id = str(uuid.uuid4())

    await redis_client.set_session(
        session_token=new_token,
        session_id=new_id,
        current_phase=0,
        fields_status=get_default_fields()
    )

    return {
        "session_token": new_token,
        "session_id": new_id,
        "current_phase": 0,
        "fields_status": get_default_fields(),
        "is_new": True
    }


async def process_message(
    user_message: str,
    session: dict,
    websocket: WebSocket
):
    """Process user message and generate response using Router + Specialist Agents"""
    redis_client = await get_redis()
    router_agent = get_router_agent()

    # Get recent messages from cache
    cached_messages = await redis_client.get_messages(session["session_token"])

    # Step 1: Router Agent analyzes intent and extracts fields
    router_output = await router_agent.analyze(
        user_message=user_message,
        fields_status=session["fields_status"],
        recent_messages=cached_messages[-10:]
    )

    # Log routing decision
    agent_type = router_output.response_strategy.agent_type
    logger.info(f"Router decision: intent={router_output.intent.primary.value}, "
                f"emotion={router_output.user_emotion.value}, "
                f"agent_type={agent_type.value}")

    # Step 2: Dispatch to appropriate specialist agent
    if agent_type == AgentType.COLLECTOR:
        await process_with_collector(
            router_output=router_output,
            user_message=user_message,
            session=session,
            cached_messages=cached_messages,
            websocket=websocket,
            redis_client=redis_client
        )
    elif agent_type == AgentType.ADVISOR:
        await process_with_advisor(
            router_output=router_output,
            user_message=user_message,
            session=session,
            cached_messages=cached_messages,
            websocket=websocket,
            redis_client=redis_client
        )
    elif agent_type == AgentType.COMPANION:
        await process_with_companion(
            router_output=router_output,
            user_message=user_message,
            session=session,
            cached_messages=cached_messages,
            websocket=websocket,
            redis_client=redis_client
        )
    else:
        # Fallback to collector
        await process_with_collector(
            router_output=router_output,
            user_message=user_message,
            session=session,
            cached_messages=cached_messages,
            websocket=websocket,
            redis_client=redis_client
        )


async def process_with_collector(
    router_output,
    user_message: str,
    session: dict,
    cached_messages: list,
    websocket: WebSocket,
    redis_client
):
    """Process message using Collector Agent with streaming"""
    collector_agent = get_collector_agent()

    full_response = ""
    updated_fields = session["fields_status"]
    quick_options = []

    # Stream response from collector
    async for chunk in collector_agent.stream_collect(
        router_output=router_output,
        user_message=user_message,
        fields_status=session["fields_status"],
        recent_messages=cached_messages[-10:]
    ):
        if chunk["type"] == "text_delta":
            await websocket.send_json({
                "type": "text_delta",
                "content": chunk["content"]
            })
            full_response += chunk["content"]

        elif chunk["type"] == "text_done":
            await websocket.send_json({"type": "text_done"})

        elif chunk["type"] == "validation":
            # Send validation feedback to frontend
            await websocket.send_json({
                "type": "field_validation",
                "field": chunk["field"],
                "status": chunk["status"],
                "message": chunk["message"]
            })

        elif chunk["type"] == "metadata":
            updated_fields = chunk["updated_fields"]
            quick_options = chunk.get("quick_options", [])

        elif chunk["type"] == "error":
            await websocket.send_json({
                "type": "error",
                "code": "collector_error",
                "message": chunk.get("error", "Unknown error")
            })
            return

    # Save messages to cache
    await redis_client.add_message(session["session_token"], "user", user_message)
    await redis_client.add_message(session["session_token"], "assistant", full_response)

    # Update session state
    current_phase = infer_phase(updated_fields)
    completion_info = get_completion_info(updated_fields)

    await redis_client.set_session(
        session_token=session["session_token"],
        session_id=session["session_id"],
        current_phase=current_phase.value,
        fields_status=updated_fields
    )

    session["fields_status"] = updated_fields
    session["current_phase"] = current_phase.value

    # Determine UI component based on phase
    ui_component = get_ui_component_for_phase(current_phase, updated_fields)

    # Send metadata
    await websocket.send_json({
        "type": "metadata",
        "current_phase": current_phase.value,
        "fields_status": updated_fields,
        "completion": {
            "can_submit": completion_info["can_submit"],
            "completion_rate": completion_info["completion_rate"],
            "next_priority_field": completion_info["next_priority_field"],
            "missing_fields": completion_info["missing_fields"]
        },
        "ui_component": ui_component,
        "quick_options": quick_options,
        "router_debug": {
            "intent": {
                "primary": router_output.intent.primary.value,
                "secondary": router_output.intent.secondary.value if router_output.intent.secondary else None,
                "confidence": router_output.intent.confidence
            },
            "emotion": router_output.user_emotion.value,
            "agent_type": router_output.response_strategy.agent_type.value
        }
    })


async def process_with_advisor(
    router_output,
    user_message: str,
    session: dict,
    cached_messages: list,
    websocket: WebSocket,
    redis_client
):
    """Process message using Advisor Agent with streaming"""
    advisor_agent = get_advisor_agent()

    full_response = ""
    updated_fields = router_output.updated_fields_status
    quick_options = []

    # Stream response from advisor
    async for chunk in advisor_agent.stream_advise(
        router_output=router_output,
        user_message=user_message,
        fields_status=session["fields_status"],
        recent_messages=cached_messages[-10:]
    ):
        if chunk["type"] == "text_delta":
            await websocket.send_json({
                "type": "text_delta",
                "content": chunk["content"]
            })
            full_response += chunk["content"]

        elif chunk["type"] == "text_done":
            await websocket.send_json({"type": "text_done"})

        elif chunk["type"] == "metadata":
            quick_options = chunk.get("quick_options", [])

        elif chunk["type"] == "error":
            await websocket.send_json({
                "type": "error",
                "code": "advisor_error",
                "message": chunk.get("error", "Unknown error")
            })
            return

    # Save messages
    await redis_client.add_message(session["session_token"], "user", user_message)
    await redis_client.add_message(session["session_token"], "assistant", full_response)

    # Update session (advisor doesn't change fields)
    current_phase = infer_phase(updated_fields)
    completion_info = get_completion_info(updated_fields)

    await redis_client.set_session(
        session_token=session["session_token"],
        session_id=session["session_id"],
        current_phase=current_phase.value,
        fields_status=updated_fields
    )

    session["fields_status"] = updated_fields
    session["current_phase"] = current_phase.value

    # Send metadata
    await websocket.send_json({
        "type": "metadata",
        "current_phase": current_phase.value,
        "fields_status": updated_fields,
        "completion": {
            "can_submit": completion_info["can_submit"],
            "completion_rate": completion_info["completion_rate"],
            "next_priority_field": completion_info["next_priority_field"],
            "missing_fields": completion_info["missing_fields"]
        },
        "ui_component": {"type": "none"},
        "quick_options": quick_options,
        "router_debug": {
            "intent": {
                "primary": router_output.intent.primary.value,
                "secondary": router_output.intent.secondary.value if router_output.intent.secondary else None,
                "confidence": router_output.intent.confidence
            },
            "emotion": router_output.user_emotion.value,
            "agent_type": "advisor"
        }
    })


async def process_with_companion(
    router_output,
    user_message: str,
    session: dict,
    cached_messages: list,
    websocket: WebSocket,
    redis_client
):
    """Process message using Companion Agent with streaming"""
    companion_agent = get_companion_agent()

    full_response = ""
    updated_fields = router_output.updated_fields_status
    quick_options = []

    # Stream response from companion
    async for chunk in companion_agent.stream_comfort(
        router_output=router_output,
        user_message=user_message,
        fields_status=session["fields_status"],
        recent_messages=cached_messages[-10:]
    ):
        if chunk["type"] == "text_delta":
            await websocket.send_json({
                "type": "text_delta",
                "content": chunk["content"]
            })
            full_response += chunk["content"]

        elif chunk["type"] == "text_done":
            await websocket.send_json({"type": "text_done"})

        elif chunk["type"] == "metadata":
            quick_options = chunk.get("quick_options", [])

        elif chunk["type"] == "error":
            await websocket.send_json({
                "type": "error",
                "code": "companion_error",
                "message": chunk.get("error", "Unknown error")
            })
            return

    # Save messages
    await redis_client.add_message(session["session_token"], "user", user_message)
    await redis_client.add_message(session["session_token"], "assistant", full_response)

    # Update session (companion doesn't change fields)
    current_phase = infer_phase(updated_fields)
    completion_info = get_completion_info(updated_fields)

    await redis_client.set_session(
        session_token=session["session_token"],
        session_id=session["session_id"],
        current_phase=current_phase.value,
        fields_status=updated_fields
    )

    session["fields_status"] = updated_fields
    session["current_phase"] = current_phase.value

    # Send metadata
    await websocket.send_json({
        "type": "metadata",
        "current_phase": current_phase.value,
        "fields_status": updated_fields,
        "completion": {
            "can_submit": completion_info["can_submit"],
            "completion_rate": completion_info["completion_rate"],
            "next_priority_field": completion_info["next_priority_field"],
            "missing_fields": completion_info["missing_fields"]
        },
        "ui_component": {"type": "none"},
        "quick_options": quick_options,
        "router_debug": {
            "intent": {
                "primary": router_output.intent.primary.value,
                "secondary": router_output.intent.secondary.value if router_output.intent.secondary else None,
                "confidence": router_output.intent.confidence
            },
            "emotion": router_output.user_emotion.value,
            "agent_type": "companion"
        }
    })


async def handle_quote_submission(
    session: dict,
    websocket: WebSocket,
    user_email: Optional[str] = None,
    user_phone: Optional[str] = None
):
    """Handle quote submission request"""
    try:
        # Validate fields completion
        fields_status = session["fields_status"]
        completion_info = get_completion_info(fields_status)

        if not completion_info["can_submit"]:
            await websocket.send_json({
                "type": "quote_error",
                "code": "incomplete_fields",
                "message": "请先完成所有必填信息",
                "missing_fields": completion_info["missing_fields"]
            })
            return

        # Create quote
        result = await QuoteService.create_quote(
            session_token=session["session_token"],
            fields_status=fields_status,
            user_email=user_email,
            user_phone=user_phone
        )

        # Persist session to PostgreSQL
        await SessionPersistenceService.persist_session(
            session_token=session["session_token"],
            session_id=session["session_id"],
            current_phase=session["current_phase"],
            fields_status=fields_status
        )

        logger.info(f"Quote submitted: {result['quote_id']}")

        # Send success response
        await websocket.send_json({
            "type": "quote_submitted",
            "quote_id": result["quote_id"],
            "status": "submitted",
            "message": "报价请求已提交！我们将尽快为您联系搬家公司获取报价。"
        })

        # Send a friendly confirmation message
        confirmation_msg = """太好了！您的搬家需求已经提交成功 🎉

我已经记录了您的所有信息，接下来会为您联系多家搬家公司获取报价。

您可以：
• 继续和我聊天，了解更多搬家知识
• 修改之前的信息，重新提交
• 等待搬家公司的报价通知"""

        for char in confirmation_msg:
            await websocket.send_json({
                "type": "text_delta",
                "content": char
            })
        await websocket.send_json({"type": "text_done"})

        # Save confirmation message
        redis_client = await get_redis()
        await redis_client.add_message(
            session["session_token"],
            "assistant",
            confirmation_msg
        )

    except Exception as e:
        logger.error(f"Quote submission error: {e}")
        await websocket.send_json({
            "type": "quote_error",
            "code": "submission_failed",
            "message": f"提交失败，请稍后重试: {str(e)}"
        })


async def handle_image_uploaded(
    session: dict,
    websocket: WebSocket,
    image_id: str,
    recognized_items: list,
    redis_client
):
    """
    Handle image uploaded and items recognized via Vision API

    Args:
        session: Current session dict
        websocket: WebSocket connection
        image_id: ID of the uploaded image
        recognized_items: List of items recognized from the image
        redis_client: Redis client instance
    """
    try:
        logger.info(f"Processing image upload result: {image_id}, items: {len(recognized_items)}")

        # Get current fields
        fields_status = session["fields_status"].copy()

        # Initialize items if needed
        if "items" not in fields_status or not isinstance(fields_status["items"], dict):
            fields_status["items"] = {"list": [], "status": "in_progress"}

        # Add recognized items to the list
        current_items = fields_status["items"].get("list", [])

        for item in recognized_items:
            # Check if item already exists (by name)
            existing = next(
                (i for i in current_items if i.get("name_ja") == item.get("name_ja")),
                None
            )
            if existing:
                # Update count
                existing["count"] = existing.get("count", 1) + item.get("count", 1)
            else:
                current_items.append({
                    "name": item.get("name", "Unknown"),
                    "name_ja": item.get("name_ja", "Unknown"),
                    "category": item.get("category", "small_items"),
                    "count": item.get("count", 1),
                    "note": item.get("note"),
                    "from_image": image_id
                })

        fields_status["items"]["list"] = current_items
        fields_status["items"]["status"] = "in_progress"

        # Update session
        await redis_client.set_session(
            session_token=session["session_token"],
            session_id=session["session_id"],
            current_phase=Phase.ITEMS.value,
            fields_status=fields_status
        )

        session["fields_status"] = fields_status

        # Send items recognized response
        await websocket.send_json({
            "type": "items_recognized",
            "image_id": image_id,
            "items": recognized_items,
            "current_items": current_items
        })

        # 不输出文字消息，识别卡片已经显示了内容

        # Send updated metadata
        current_phase = infer_phase(fields_status)
        completion_info = get_completion_info(fields_status)
        ui_component = get_ui_component_for_phase(current_phase, fields_status)

        await websocket.send_json({
            "type": "metadata",
            "current_phase": current_phase.value,
            "fields_status": fields_status,
            "completion": {
                "can_submit": completion_info["can_submit"],
                "completion_rate": completion_info["completion_rate"],
                "next_priority_field": completion_info["next_priority_field"],
                "missing_fields": completion_info["missing_fields"]
            },
            "ui_component": ui_component,
            "quick_options": []  # 识别结果卡片显示时不显示快捷选项
        })

    except Exception as e:
        logger.error(f"Handle image uploaded error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "image_process_failed",
            "message": f"Failed to process image: {str(e)}"
        })


async def handle_items_confirmed(
    session: dict,
    websocket: WebSocket,
    confirmed_items: list,
    redis_client
):
    """
    Handle items confirmation from the user

    Args:
        session: Current session dict
        websocket: WebSocket connection
        confirmed_items: List of confirmed items
        redis_client: Redis client instance
    """
    try:
        logger.info(f"Processing items confirmation: {len(confirmed_items)} items")

        # Validate items using item service
        item_service = get_item_service()
        validation_result = item_service.validate_item_selection(confirmed_items)

        if not validation_result["valid"]:
            await websocket.send_json({
                "type": "items_validation_error",
                "errors": validation_result["errors"]
            })
            return

        # Get current fields
        fields_status = session["fields_status"].copy()

        # Update items with validated list
        fields_status["items"] = {
            "list": validation_result["items"],
            "status": "baseline",
            "total_count": validation_result["total_count"]
        }

        # Update session
        current_phase = infer_phase(fields_status)

        await redis_client.set_session(
            session_token=session["session_token"],
            session_id=session["session_id"],
            current_phase=current_phase.value,
            fields_status=fields_status
        )

        session["fields_status"] = fields_status
        session["current_phase"] = current_phase.value

        # Send confirmation - 前端会更新卡片按钮为"已添加"状态
        await websocket.send_json({
            "type": "items_confirmed",
            "items": validation_result["items"],
            "total_count": validation_result["total_count"],
            "keep_card": True  # 告诉前端保留卡片
        })

        # 简化确认消息 - 卡片下方显示
        total = validation_result["total_count"]
        response_msg = f"已添加 {total}件物品，已添加的行李可点击页面右上角【搬家清单】查看"

        # Stream the response
        for char in response_msg:
            await websocket.send_json({
                "type": "text_delta",
                "content": char
            })
        await websocket.send_json({"type": "text_done"})

        # Save message
        await redis_client.add_message(session["session_token"], "assistant", response_msg)

        # Send updated metadata
        completion_info = get_completion_info(fields_status)

        # 物品确认后显示"继续添加"或"没有其他行李了"选项
        smart_options = ["继续添加", "没有其他行李了"]

        await websocket.send_json({
            "type": "metadata",
            "current_phase": current_phase.value,
            "fields_status": fields_status,
            "completion": {
                "can_submit": completion_info["can_submit"],
                "completion_rate": completion_info["completion_rate"],
                "next_priority_field": completion_info["next_priority_field"],
                "missing_fields": completion_info["missing_fields"]
            },
            "ui_component": {"type": "none"},  # 卡片由前端保持显示
            "quick_options": smart_options
        })

    except Exception as e:
        logger.error(f"Handle items confirmed error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "items_confirm_failed",
            "message": f"Failed to confirm items: {str(e)}"
        })


async def handle_session_reset(
    session: dict,
    websocket: WebSocket,
    redis_client
):
    """Handle session reset request"""
    try:
        # Delete old session data
        await redis_client.delete_session(session["session_token"])

        # Create new session data
        new_fields = get_default_fields()
        new_id = str(uuid.uuid4())

        await redis_client.set_session(
            session_token=session["session_token"],
            session_id=new_id,
            current_phase=0,
            fields_status=new_fields
        )

        # Update session reference
        session["session_id"] = new_id
        session["current_phase"] = 0
        session["fields_status"] = new_fields

        logger.info(f"Session reset: {session['session_token']}")

        # Send reset confirmation
        await websocket.send_json({
            "type": "session_reset",
            "session_token": session["session_token"],
            "current_phase": 0,
            "fields_status": new_fields
        })

        # Send welcome message
        welcome_message = """👋 好的，我们重新开始吧！

请问您想咨询什么？或者直接告诉我您的搬家计划也可以。

我可以帮您："""

        for char in welcome_message:
            await websocket.send_json({
                "type": "text_delta",
                "content": char
            })
        await websocket.send_json({"type": "text_done"})

        # Save welcome message first
        await redis_client.add_message(
            session["session_token"],
            "assistant",
            welcome_message
        )

        # Get smart options for opening - LLM根据欢迎消息上下文判断
        smart_options = await get_smart_quick_options(
            fields_status=new_fields,
            recent_messages=[{"role": "assistant", "content": welcome_message}],
            next_field=None,
            context_hint="会话重置，Agent刚发送欢迎消息"
        )

        # Send metadata
        await websocket.send_json({
            "type": "metadata",
            "current_phase": 0,
            "fields_status": new_fields,
            "completion": {
                "can_submit": False,
                "completion_rate": 0.0,
                "next_priority_field": "people_count"
            },
            "ui_component": {"type": "none"},
            "quick_options": smart_options
        })

    except Exception as e:
        logger.error(f"Session reset error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "reset_failed",
            "message": f"重置失败: {str(e)}"
        })


@router.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    session_token: Optional[str] = Query(None)
):
    """WebSocket endpoint for chat"""

    # Get or create session
    session = await get_or_create_session(session_token)
    token = session["session_token"]
    redis_client = await get_redis()

    await manager.connect(token, websocket)

    try:
        # Send session info
        await websocket.send_json({
            "type": "session",
            "session_token": token,
            "current_phase": session["current_phase"],
            "is_new": session["is_new"]
        })

        # If new session, send welcome message
        if session["is_new"]:
            welcome_message = """👋 你好，我是 ERABU

请问您想咨询什么？或者直接告诉我您的搬家计划也可以。

我可以帮您："""

            # Stream welcome message character by character for effect
            for char in welcome_message:
                await websocket.send_json({
                    "type": "text_delta",
                    "content": char
                })

            await websocket.send_json({"type": "text_done"})

            # Save welcome message first
            await redis_client.add_message(token, "assistant", welcome_message)

            # Get smart options for new session - LLM根据欢迎消息上下文判断
            smart_options = await get_smart_quick_options(
                fields_status=session["fields_status"],
                recent_messages=[{"role": "assistant", "content": welcome_message}],
                next_field=None,
                context_hint="新会话开始，Agent刚发送欢迎消息"
            )

            # Send initial metadata
            await websocket.send_json({
                "type": "metadata",
                "current_phase": 0,
                "fields_status": session["fields_status"],
                "completion": {
                    "can_submit": False,
                    "completion_rate": 0.0,
                    "next_priority_field": "people_count"
                },
                "ui_component": {"type": "none"},
                "quick_options": smart_options
            })

        else:
            # Existing session - send previous messages and current state
            cached_messages = await redis_client.get_messages(token)

            # Send message history
            await websocket.send_json({
                "type": "message_history",
                "messages": cached_messages
            })

            # Send current metadata
            completion_info = get_completion_info(session["fields_status"])
            current_phase = infer_phase(session["fields_status"])
            ui_component = get_ui_component_for_phase(current_phase, session["fields_status"])

            # Get smart options based on conversation history - LLM根据上下文判断
            smart_options = await get_smart_quick_options(
                fields_status=session["fields_status"],
                recent_messages=cached_messages[-6:],
                next_field=completion_info.get("next_priority_field"),
                context_hint="用户重新连接，根据最后一条Agent消息判断选项"
            )

            await websocket.send_json({
                "type": "metadata",
                "current_phase": current_phase.value,
                "fields_status": session["fields_status"],
                "completion": {
                    "can_submit": completion_info["can_submit"],
                    "completion_rate": completion_info["completion_rate"],
                    "next_priority_field": completion_info["next_priority_field"],
                    "missing_fields": completion_info["missing_fields"]
                },
                "ui_component": ui_component,
                "quick_options": smart_options
            })

        # Main message loop
        while True:
            data = await websocket.receive_json()

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type in ["message", "quick_option"]:
                content = data.get("content", "")
                if content:
                    await process_message(content, session, websocket)

            elif msg_type == "button_click":
                # Handle button clicks (will be expanded in later phases)
                button_id = data.get("button_id")
                button_data = data.get("data", {})
                logger.info(f"Button click: {button_id}, data: {button_data}")
                # For now, treat as confirmation message
                await process_message(f"[点击了 {button_id}]", session, websocket)

            elif msg_type == "submit_quote":
                # Handle quote submission
                await handle_quote_submission(
                    session=session,
                    websocket=websocket,
                    user_email=data.get("email"),
                    user_phone=data.get("phone")
                )

            elif msg_type == "reset_session":
                # Handle session reset
                await handle_session_reset(
                    session=session,
                    websocket=websocket,
                    redis_client=redis_client
                )

            elif msg_type == "image_uploaded":
                # Handle image recognition result
                image_id = data.get("image_id", "")
                recognized_items = data.get("items", [])
                await handle_image_uploaded(
                    session=session,
                    websocket=websocket,
                    image_id=image_id,
                    recognized_items=recognized_items,
                    redis_client=redis_client
                )

            elif msg_type == "items_confirmed":
                # Handle items selection confirmation
                confirmed_items = data.get("items", [])
                await handle_items_confirmed(
                    session=session,
                    websocket=websocket,
                    confirmed_items=confirmed_items,
                    redis_client=redis_client
                )

            elif msg_type == "items_updated":
                # Handle items list update (add/remove/modify)
                updated_items = data.get("items", [])
                await handle_items_confirmed(
                    session=session,
                    websocket=websocket,
                    confirmed_items=updated_items,
                    redis_client=redis_client
                )

    except WebSocketDisconnect:
        manager.disconnect(token)
        logger.info(f"WebSocket disconnected: {token}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(token)
