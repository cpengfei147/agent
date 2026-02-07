"""Output parsing utilities with error tolerance"""

import json
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON from text that may contain other content

    Handles cases like:
    - Pure JSON
    - JSON wrapped in markdown code blocks
    - JSON with leading/trailing text
    """
    if not text:
        return None

    text = text.strip()

    # Try to parse as-is first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Try to extract from markdown code block
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    matches = re.findall(code_block_pattern, text)
    for match in matches:
        try:
            json.loads(match.strip())
            return match.strip()
        except json.JSONDecodeError:
            continue

    # Try to find JSON object pattern
    json_pattern = r'\{[\s\S]*\}'
    matches = re.findall(json_pattern, text)

    # Try each match, starting from the longest
    for match in sorted(matches, key=len, reverse=True):
        try:
            json.loads(match)
            return match
        except json.JSONDecodeError:
            continue

    return None


def safe_parse_json(text: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Safely parse JSON with fallback to default

    Args:
        text: Text to parse
        default: Default value if parsing fails

    Returns:
        Parsed dict or default
    """
    if default is None:
        default = {}

    extracted = extract_json_from_text(text)
    if extracted is None:
        logger.warning(f"Could not extract JSON from: {text[:200]}...")
        return default

    try:
        return json.loads(extracted)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return default


def parse_intent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and validate intent data"""
    valid_intents = {
        "provide_info", "modify_info", "confirm", "reject", "skip", "complete",
        "ask_price", "ask_process", "ask_company", "ask_tips", "ask_general",
        "express_anxiety", "express_confusion", "express_urgency", "express_frustration", "chitchat",
        "go_back", "start_over", "request_summary", "request_quote"
    }

    intent = data.get("intent", {})

    # Validate primary intent
    primary = intent.get("primary", "provide_info")
    if primary not in valid_intents:
        primary = "provide_info"

    # Validate secondary intent
    secondary = intent.get("secondary")
    if secondary and secondary not in valid_intents:
        secondary = None

    # Validate confidence
    confidence = intent.get("confidence", 0.8)
    if not isinstance(confidence, (int, float)):
        confidence = 0.8
    confidence = max(0.0, min(1.0, float(confidence)))

    return {
        "primary": primary,
        "secondary": secondary,
        "confidence": confidence
    }


def parse_emotion(emotion_str: str) -> str:
    """Parse and validate emotion string"""
    valid_emotions = {"neutral", "positive", "anxious", "confused", "frustrated", "urgent"}

    if emotion_str in valid_emotions:
        return emotion_str
    return "neutral"


def parse_extracted_fields(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Parse and validate extracted fields"""
    extracted = data.get("extracted_fields", {})
    result = {}

    valid_fields = {
        "people_count", "from_address", "to_address", "from_building_type", "to_building_type",
        "move_date", "move_time_slot", "from_floor", "from_has_elevator",
        "to_floor", "to_has_elevator", "packing_service", "special_notes"
    }

    for field_name, field_data in extracted.items():
        if field_name not in valid_fields:
            continue

        if not isinstance(field_data, dict):
            continue

        result[field_name] = {
            "raw_value": str(field_data.get("raw_value", "")),
            "parsed_value": field_data.get("parsed_value"),
            "needs_verification": bool(field_data.get("needs_verification", False)),
            "confidence": float(field_data.get("confidence", 0.8))
        }

    return result


def parse_next_actions(data: Dict[str, Any]) -> list:
    """Parse and validate next actions"""
    actions = data.get("next_actions", [])
    result = []

    valid_action_types = {"update_field", "call_tool", "collect_field", "answer_question", "handle_emotion"}

    for action in actions:
        if not isinstance(action, dict):
            continue

        action_type = action.get("type", "collect_field")
        if action_type not in valid_action_types:
            continue

        result.append({
            "type": action_type,
            "target": action.get("target"),
            "params": action.get("params", {}),
            "priority": int(action.get("priority", 1))
        })

    return result


def parse_response_strategy(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and validate response strategy"""
    strategy = data.get("response_strategy", {})

    valid_agent_types = {"collector", "advisor", "companion"}
    valid_styles = {"friendly", "professional", "empathetic", "concise"}

    agent_type = strategy.get("agent_type", "collector")
    if agent_type not in valid_agent_types:
        agent_type = "collector"

    style = strategy.get("style", "friendly")
    if style not in valid_styles:
        style = "friendly"

    return {
        "agent_type": agent_type,
        "style": style,
        "should_acknowledge": bool(strategy.get("should_acknowledge", True)),
        "guide_to_field": strategy.get("guide_to_field"),
        "include_options": bool(strategy.get("include_options", True))
    }


def parse_router_output(text: str) -> Dict[str, Any]:
    """
    Parse complete router output with full validation

    Args:
        text: Raw LLM output

    Returns:
        Validated router output dict
    """
    data = safe_parse_json(text, {})

    return {
        "intent": parse_intent(data),
        "extracted_fields": parse_extracted_fields(data),
        "user_emotion": parse_emotion(data.get("user_emotion", "neutral")),
        "current_phase": int(data.get("current_phase", 0)),
        "next_actions": parse_next_actions(data),
        "response_strategy": parse_response_strategy(data)
    }
