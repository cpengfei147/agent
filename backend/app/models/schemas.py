from enum import Enum
from typing import Optional, List, Any, Dict
from pydantic import BaseModel
from datetime import datetime


# ============ Enums ============

class UIComponentType(str, Enum):
    """UI Component types"""
    NONE = "none"
    ADDRESS_VERIFY_SINGLE = "address_verify_single"
    ADDRESS_VERIFY_MULTIPLE = "address_verify_multiple"
    BUILDING_TYPE_SELECT = "building_type_select"
    ITEM_EVALUATION = "item_evaluation"
    ITEM_RESULT = "item_result"
    CONFIRM_CARD = "confirm_card"
    LOGIN_CARD = "login_card"
    PRIVACY_MODAL = "privacy_modal"


class MessageType(str, Enum):
    """WebSocket message types"""
    MESSAGE = "message"
    QUICK_OPTION = "quick_option"
    BUTTON_CLICK = "button_click"
    IMAGE_UPLOADED = "image_uploaded"
    PING = "ping"


class ResponseType(str, Enum):
    """WebSocket response types"""
    TEXT_DELTA = "text_delta"
    TEXT_DONE = "text_done"
    TOOL_STATUS = "tool_status"
    METADATA = "metadata"
    ERROR = "error"
    PONG = "pong"


# ============ Request Models ============

class ChatMessage(BaseModel):
    """Chat message from client"""
    type: MessageType
    content: Optional[str] = None
    button_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    image_id: Optional[str] = None


# ============ Response Models ============

class UIComponent(BaseModel):
    """UI Component structure"""
    type: UIComponentType = UIComponentType.NONE
    data: Optional[Dict[str, Any]] = None


class CompletionInfo(BaseModel):
    """Completion information"""
    can_submit: bool = False
    completion_rate: float = 0.0
    next_priority_field: Optional[str] = None
    missing_fields: List[str] = []


class ChatResponse(BaseModel):
    """Chat response to client"""
    type: ResponseType
    content: Optional[str] = None
    tool: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    current_phase: Optional[int] = None
    fields_status: Optional[Dict[str, Any]] = None
    completion: Optional[CompletionInfo] = None
    ui_component: Optional[UIComponent] = None
    quick_options: Optional[List[str]] = None
    code: Optional[str] = None


class SessionResponse(BaseModel):
    """Session response"""
    session_id: str
    session_token: str
    current_phase: int = 0
    fields_status: Dict[str, Any] = {}
    messages: List[Dict[str, Any]] = []
    completion: Optional[CompletionInfo] = None
    created_at: datetime


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    checks: Dict[str, str]


# ============ Agent Models ============

class IntentType(str, Enum):
    """Intent types"""
    # Task related
    PROVIDE_INFO = "provide_info"
    MODIFY_INFO = "modify_info"
    CONFIRM = "confirm"
    REJECT = "reject"
    SKIP = "skip"
    COMPLETE = "complete"

    # Consultation related
    ASK_PRICE = "ask_price"
    ASK_PROCESS = "ask_process"
    ASK_COMPANY = "ask_company"
    ASK_TIPS = "ask_tips"
    ASK_GENERAL = "ask_general"

    # Emotion related
    EXPRESS_ANXIETY = "express_anxiety"
    EXPRESS_CONFUSION = "express_confusion"
    EXPRESS_URGENCY = "express_urgency"
    EXPRESS_FRUSTRATION = "express_frustration"
    CHITCHAT = "chitchat"

    # Flow control
    GO_BACK = "go_back"
    START_OVER = "start_over"
    REQUEST_SUMMARY = "request_summary"
    REQUEST_QUOTE = "request_quote"


class Emotion(str, Enum):
    """User emotion types"""
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    ANXIOUS = "anxious"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    URGENT = "urgent"


class AgentType(str, Enum):
    """Agent types"""
    COLLECTOR = "collector"
    ADVISOR = "advisor"
    COMPANION = "companion"


class ResponseStyle(str, Enum):
    """Response style"""
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    EMPATHETIC = "empathetic"
    CONCISE = "concise"


class Intent(BaseModel):
    """Intent recognition result"""
    primary: IntentType
    secondary: Optional[IntentType] = None
    confidence: float = 0.0


class ExtractedField(BaseModel):
    """Extracted field from user message"""
    field_name: str
    raw_value: str
    parsed_value: Any = None
    needs_verification: bool = False
    confidence: float = 0.0


class ActionType(str, Enum):
    """Action types"""
    UPDATE_FIELD = "update_field"
    CALL_TOOL = "call_tool"
    COLLECT_FIELD = "collect_field"
    ANSWER_QUESTION = "answer_question"
    HANDLE_EMOTION = "handle_emotion"


class Action(BaseModel):
    """Next action"""
    type: ActionType
    target: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    priority: int = 1


class ResponseStrategy(BaseModel):
    """Response generation strategy"""
    agent_type: AgentType
    style: ResponseStyle = ResponseStyle.FRIENDLY
    should_acknowledge: bool = True
    guide_to_field: Optional[str] = None
    skip_field: Optional[str] = None  # 当 intent=skip 时，指明要跳过的具体字段
    include_options: bool = True


class RouterOutput(BaseModel):
    """Router Agent output"""
    intent: Intent
    extracted_fields: Dict[str, ExtractedField] = {}
    user_emotion: Emotion = Emotion.NEUTRAL
    current_phase: int = 0  # 处理消息前的阶段
    phase_after_update: int = 0  # 处理消息后应该进入的阶段（由LLM决定）
    next_actions: List[Action] = []
    response_strategy: ResponseStrategy
    updated_fields_status: Dict[str, Any] = {}


class SpecialistOutput(BaseModel):
    """Specialist Agent output"""
    message: str
    ui_component: UIComponent = UIComponent()
    quick_options: List[str] = []
    fields_update: Optional[Dict[str, Any]] = None
    current_phase: Optional[int] = None
