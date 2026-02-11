"""
State Machine - 基于 Intent 的状态转换规则

职责分离：
- LLM (Router): 识别用户意图 (intent)
- 状态机 (本模块): 根据 intent + 当前状态 → 执行状态转换

规则格式：
- 条件: (field_type, current_condition, intent)
- 结果: 状态更新字典
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

from app.models.fields import FieldStatus

logger = logging.getLogger(__name__)


# =============================================================================
# 状态转换规则表
# =============================================================================
# 格式: (字段类型, 当前条件, intent) → 状态更新
# 字段类型: "address", "items", "special_notes", "*" (通配)
# 当前条件: "needs_confirmation", "in_progress", "*" (通配)
# intent: "confirm", "reject", "skip", "complete", etc.

STATE_TRANSITION_RULES: List[Tuple[Tuple[str, str, str], Dict[str, Any]]] = [
    # =========================================================================
    # 地址确认场景
    # =========================================================================
    # 用户确认地址 (说"是的"、"没错"、"对的")
    (
        ("address", "needs_confirmation", "confirm"),
        {
            "needs_confirmation": False,
            "status": FieldStatus.BASELINE.value,
            "_log": "用户文字确认地址"
        }
    ),

    # 用户拒绝地址 (说"不对"、"错了")
    (
        ("address", "needs_confirmation", "reject"),
        {
            "needs_confirmation": False,
            "status": FieldStatus.NOT_COLLECTED.value,
            "verification_status": None,
            "value": None,
            "_log": "用户拒绝地址，重新收集"
        }
    ),

    # =========================================================================
    # 通用跳过场景
    # =========================================================================
    # 用户跳过任何字段 (说"先跳过"、"不知道"、"还没定")
    (
        ("*", "*", "skip"),
        {
            "status": FieldStatus.SKIPPED.value,
            "_log": "用户跳过该字段"
        }
    ),

    # =========================================================================
    # 物品收集完成
    # =========================================================================
    # 用户表示物品收集完成 (说"没有了"、"就这些")
    (
        ("items", "*", "complete"),
        {
            "status": FieldStatus.BASELINE.value,
            "_log": "用户表示物品收集完成"
        }
    ),

    # =========================================================================
    # 特殊注意事项完成
    # =========================================================================
    # 用户表示没有更多特殊需求 (说"没有了"、"没有其他了")
    (
        ("special_notes", "*", "complete"),
        {
            "_set_flag": ("special_notes_done", True),
            "_log": "用户表示特殊注意事项完成"
        }
    ),
]


def get_field_type(field_name: str) -> str:
    """获取字段类型"""
    if "address" in field_name:
        return "address"
    elif field_name == "items":
        return "items"
    elif field_name == "special_notes":
        return "special_notes"
    else:
        return "other"


def get_current_condition(field_state: Dict[str, Any]) -> str:
    """获取字段当前条件"""
    if field_state.get("needs_confirmation"):
        return "needs_confirmation"

    status = field_state.get("status", FieldStatus.NOT_COLLECTED.value)
    if status == FieldStatus.IN_PROGRESS.value:
        return "in_progress"
    elif status == FieldStatus.BASELINE.value:
        return "baseline"
    elif status == FieldStatus.NOT_COLLECTED.value:
        return "not_collected"
    else:
        return status


def match_rule(
    field_type: str,
    condition: str,
    intent: str
) -> Optional[Dict[str, Any]]:
    """
    匹配规则表，返回状态更新

    支持通配符 "*" 匹配任意值
    """
    for (rule_field_type, rule_condition, rule_intent), updates in STATE_TRANSITION_RULES:
        # 检查字段类型匹配
        if rule_field_type != "*" and rule_field_type != field_type:
            continue

        # 检查条件匹配
        if rule_condition != "*" and rule_condition != condition:
            continue

        # 检查 intent 匹配
        if rule_intent != "*" and rule_intent != intent:
            continue

        # 匹配成功
        return updates.copy()

    return None


def apply_state_transition(
    field_name: str,
    current_state: Dict[str, Any],
    intent: str,
    fields_status: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any], bool]:
    """
    应用状态转换规则

    Args:
        field_name: 字段名 (如 "from_address", "items")
        current_state: 字段当前状态
        intent: 用户意图
        fields_status: 完整的字段状态 (用于设置全局标志)

    Returns:
        (更新后的字段状态, 更新后的 fields_status, 是否有规则匹配)
    """
    field_type = get_field_type(field_name)
    condition = get_current_condition(current_state)

    # 查找匹配的规则
    updates = match_rule(field_type, condition, intent)

    if updates is None:
        logger.debug(f"[STATE_MACHINE] No rule matched: field={field_name}, type={field_type}, condition={condition}, intent={intent}")
        return current_state, fields_status, False

    # 记录日志
    log_msg = updates.pop("_log", None)
    if log_msg:
        logger.info(f"[STATE_MACHINE] {log_msg}: field={field_name}, intent={intent}")

    # 处理全局标志设置
    set_flag = updates.pop("_set_flag", None)
    if set_flag:
        flag_name, flag_value = set_flag
        fields_status[flag_name] = flag_value
        logger.info(f"[STATE_MACHINE] Set flag: {flag_name}={flag_value}")

    # 应用状态更新
    new_state = {**current_state, **updates}

    logger.info(f"[STATE_MACHINE] State transition: {field_name} {condition} + {intent} → {new_state.get('status', 'unchanged')}")

    return new_state, fields_status, True


def process_intent_transitions(
    intent: str,
    fields_status: Dict[str, Any],
    context: Dict[str, Any] = None
) -> Tuple[Dict[str, Any], List[str]]:
    """
    根据 intent 处理所有可能的状态转换

    Args:
        intent: 用户意图
        fields_status: 当前字段状态
        context: 上下文信息 (如当前阶段、正在询问的字段等)

    Returns:
        (更新后的 fields_status, 被更新的字段列表)
    """
    context = context or {}
    updated_fields = []

    # 根据 intent 类型决定检查哪些字段
    if intent == "confirm":
        # 确认意图：检查是否有地址需要确认
        for addr_field in ["from_address", "to_address"]:
            addr_state = fields_status.get(addr_field, {})
            if isinstance(addr_state, dict) and addr_state.get("needs_confirmation"):
                new_state, fields_status, matched = apply_state_transition(
                    addr_field, addr_state, intent, fields_status
                )
                if matched:
                    fields_status[addr_field] = new_state
                    updated_fields.append(addr_field)
                    break  # 一次只确认一个地址

    elif intent == "reject":
        # 拒绝意图：检查是否有地址需要确认
        for addr_field in ["from_address", "to_address"]:
            addr_state = fields_status.get(addr_field, {})
            if isinstance(addr_state, dict) and addr_state.get("needs_confirmation"):
                new_state, fields_status, matched = apply_state_transition(
                    addr_field, addr_state, intent, fields_status
                )
                if matched:
                    fields_status[addr_field] = new_state
                    updated_fields.append(addr_field)
                    break

    elif intent == "skip":
        # 跳过意图：跳过当前正在询问的字段
        current_field = context.get("current_field") or context.get("guide_to_field")
        if current_field:
            field_state = fields_status.get(current_field, {})
            if not isinstance(field_state, dict):
                field_state = {"status": FieldStatus.NOT_COLLECTED.value}

            new_state, fields_status, matched = apply_state_transition(
                current_field, field_state, intent, fields_status
            )
            if matched:
                fields_status[current_field] = new_state
                updated_fields.append(current_field)

    elif intent == "complete":
        # 完成意图：根据当前阶段决定完成什么
        current_phase = context.get("current_phase", 0)

        if current_phase == 4:
            # 阶段4：物品收集完成
            items_state = fields_status.get("items", {})
            if not isinstance(items_state, dict):
                items_state = {"status": FieldStatus.NOT_COLLECTED.value}

            new_state, fields_status, matched = apply_state_transition(
                "items", items_state, intent, fields_status
            )
            if matched:
                fields_status["items"] = new_state
                updated_fields.append("items")

        elif current_phase == 5:
            # 阶段5：特殊注意事项完成
            new_state, fields_status, matched = apply_state_transition(
                "special_notes", {}, intent, fields_status
            )
            if matched:
                updated_fields.append("special_notes")

    return fields_status, updated_fields
