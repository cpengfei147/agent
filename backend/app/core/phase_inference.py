"""Phase Inference - 根据字段状态推断当前阶段"""

from typing import Dict, Any, Optional, List
from app.models.fields import Phase, FieldStatus


def infer_phase(fields_status: Dict[str, Any]) -> Phase:
    """
    根据字段完成度推断当前阶段

    阶段推断规则：
    - 所有字段都未收集 → 阶段 0 (开场)
    - 人数未完成 → 阶段 1
    - 地址未完成 → 阶段 2
    - 日期未完成 → 阶段 3
    - 物品未完成（且前置条件满足）→ 阶段 4
    - 其他信息未完成 → 阶段 5
    - 全部完成 → 阶段 6
    """

    # Helper function to check if a field is done
    def is_done(status: str) -> bool:
        return status in [FieldStatus.BASELINE.value, FieldStatus.IDEAL.value]

    def is_skipped_or_done(status: str) -> bool:
        return status in [FieldStatus.BASELINE.value, FieldStatus.IDEAL.value, FieldStatus.SKIPPED.value]

    def is_in_progress_or_done(status: str) -> bool:
        return status in [FieldStatus.BASELINE.value, FieldStatus.IDEAL.value, FieldStatus.IN_PROGRESS.value]

    # Check if any field has been touched (for OPENING phase)
    people_status = fields_status.get("people_count_status", FieldStatus.NOT_COLLECTED.value)
    from_addr = fields_status.get("from_address", {})
    from_status = from_addr.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_addr, dict) else FieldStatus.NOT_COLLECTED.value
    to_addr = fields_status.get("to_address", {})
    to_status = to_addr.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(to_addr, dict) else FieldStatus.NOT_COLLECTED.value

    # If nothing has been collected yet, stay in OPENING phase
    all_not_collected = (
        people_status == FieldStatus.NOT_COLLECTED.value and
        from_status == FieldStatus.NOT_COLLECTED.value and
        to_status == FieldStatus.NOT_COLLECTED.value
    )
    if all_not_collected:
        return Phase.OPENING

    # Check people_count
    if not is_done(people_status):
        return Phase.PEOPLE_COUNT

    # Check addresses
    from_addr = fields_status.get("from_address", {})
    to_addr = fields_status.get("to_address", {})

    from_status = from_addr.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_addr, dict) else FieldStatus.NOT_COLLECTED.value
    to_status = to_addr.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(to_addr, dict) else FieldStatus.NOT_COLLECTED.value

    if not is_done(from_status) or not is_done(to_status):
        return Phase.ADDRESS

    # Check date
    move_date = fields_status.get("move_date", {})
    date_status = move_date.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(move_date, dict) else FieldStatus.NOT_COLLECTED.value

    if not is_done(date_status):
        return Phase.DATE

    # Check items (requires people, addresses, date to be done first)
    items = fields_status.get("items", {})
    items_status = items.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(items, dict) else FieldStatus.NOT_COLLECTED.value

    if not is_done(items_status):
        return Phase.ITEMS

    # Check other info
    # Floor/elevator is conditionally required for apartments
    from_floor = fields_status.get("from_floor_elevator", {})
    floor_status = from_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_floor, dict) else FieldStatus.NOT_COLLECTED.value

    building_type = from_addr.get("building_type") if isinstance(from_addr, dict) else None
    apartment_types = ["マンション", "アパート", "タワーマンション"]

    # Check if floor info is required and not collected
    if building_type in apartment_types:
        if not is_skipped_or_done(floor_status):
            return Phase.OTHER_INFO

    # Check packing service
    packing = fields_status.get("packing_service")
    if packing is None:
        return Phase.OTHER_INFO

    # All done
    return Phase.CONFIRMATION


def get_next_priority_field(fields_status: Dict[str, Any]) -> Optional[str]:
    """
    获取下一个应该收集的字段

    按优先级顺序：
    1. people_count
    2. from_address
    3. to_address
    4. move_date
    5. items
    6. from_floor_elevator (公寓场景)
    7. packing_service
    8. special_notes
    """

    def is_done(status: str) -> bool:
        return status in [FieldStatus.BASELINE.value, FieldStatus.IDEAL.value]

    def is_skipped_or_done(status: str) -> bool:
        return status in [FieldStatus.BASELINE.value, FieldStatus.IDEAL.value, FieldStatus.SKIPPED.value]

    # 1. Check people_count
    people_status = fields_status.get("people_count_status", FieldStatus.NOT_COLLECTED.value)
    if not is_done(people_status):
        return "people_count"

    # 2. Check from_address
    from_addr = fields_status.get("from_address", {})
    from_status = from_addr.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_addr, dict) else FieldStatus.NOT_COLLECTED.value
    if not is_done(from_status):
        return "from_address"

    # 3. Check to_address
    to_addr = fields_status.get("to_address", {})
    to_status = to_addr.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(to_addr, dict) else FieldStatus.NOT_COLLECTED.value
    if not is_done(to_status):
        return "to_address"

    # 4. Check move_date
    move_date = fields_status.get("move_date", {})
    date_status = move_date.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(move_date, dict) else FieldStatus.NOT_COLLECTED.value
    if not is_done(date_status):
        return "move_date"

    # 5. Check items
    items = fields_status.get("items", {})
    items_status = items.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(items, dict) else FieldStatus.NOT_COLLECTED.value
    if not is_done(items_status):
        return "items"

    # 6. Check from_floor_elevator (conditionally required)
    from_floor = fields_status.get("from_floor_elevator", {})
    floor_status = from_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_floor, dict) else FieldStatus.NOT_COLLECTED.value
    building_type = from_addr.get("building_type") if isinstance(from_addr, dict) else None
    apartment_types = ["マンション", "アパート", "タワーマンション"]

    if building_type in apartment_types and not is_skipped_or_done(floor_status):
        return "from_floor_elevator"

    # 7. Check packing_service
    if fields_status.get("packing_service") is None:
        return "packing_service"

    # All done
    return None


def get_completion_info(fields_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算字段完成度信息

    Returns:
        dict with can_submit, completion_rate, missing_fields, next_priority_field
    """

    def is_done(status: str) -> bool:
        return status in [FieldStatus.BASELINE.value, FieldStatus.IDEAL.value]

    # Required fields check
    required_checks = {
        "people_count": is_done(fields_status.get("people_count_status", FieldStatus.NOT_COLLECTED.value)),
        "from_address": is_done(
            fields_status.get("from_address", {}).get("status", FieldStatus.NOT_COLLECTED.value)
            if isinstance(fields_status.get("from_address"), dict) else FieldStatus.NOT_COLLECTED.value
        ),
        "to_address": is_done(
            fields_status.get("to_address", {}).get("status", FieldStatus.NOT_COLLECTED.value)
            if isinstance(fields_status.get("to_address"), dict) else FieldStatus.NOT_COLLECTED.value
        ),
        "move_date": is_done(
            fields_status.get("move_date", {}).get("status", FieldStatus.NOT_COLLECTED.value)
            if isinstance(fields_status.get("move_date"), dict) else FieldStatus.NOT_COLLECTED.value
        ),
        "items": is_done(
            fields_status.get("items", {}).get("status", FieldStatus.NOT_COLLECTED.value)
            if isinstance(fields_status.get("items"), dict) else FieldStatus.NOT_COLLECTED.value
        ),
    }

    # Check floor for apartment buildings
    from_addr = fields_status.get("from_address", {})
    building_type = from_addr.get("building_type") if isinstance(from_addr, dict) else None
    apartment_types = ["マンション", "アパート", "タワーマンション"]

    if building_type in apartment_types:
        from_floor = fields_status.get("from_floor_elevator", {})
        floor_status = from_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_floor, dict) else FieldStatus.NOT_COLLECTED.value
        required_checks["from_floor_elevator"] = is_done(floor_status) or floor_status == FieldStatus.SKIPPED.value

    # Calculate stats
    total = len(required_checks)
    completed = sum(1 for v in required_checks.values() if v)
    missing = [k for k, v in required_checks.items() if not v]

    return {
        "can_submit": completed == total,
        "completion_rate": completed / total if total > 0 else 0.0,
        "missing_fields": missing,
        "next_priority_field": get_next_priority_field(fields_status),
        "total_required": total,
        "completed": completed
    }


def get_quick_options_for_phase(
    phase: Phase,
    fields_status: Dict[str, Any],
    context: Dict[str, Any] = None
) -> List[str]:
    """
    根据当前阶段获取快捷选项

    固定选项场景：
    - 开场白（Phase.OPENING）：介绍能做什么
    - 特殊注意事项（Phase.OTHER_INFO + asking_special_notes）：5个固定服务选项

    其他场景由LLM自主决定

    Args:
        phase: 当前阶段
        fields_status: 字段状态
        context: 上下文信息

    Returns:
        快捷选项列表
    """
    context = context or {}

    # 开场白 - 固定选项（介绍能做什么）
    if phase == Phase.OPENING:
        return ["获取搬家报价", "咨询搬家问题", "了解服务内容"]

    # 特殊注意事项 - 固定选项（业务规定的5个服务）
    if phase == Phase.OTHER_INFO:
        if context.get("asking_special_notes"):
            all_options = ["有宜家家具", "有钢琴需要搬运", "空调安装", "空调拆卸", "不用品回收", "没有了"]
            selected = fields_status.get("special_notes", [])
            return [opt for opt in all_options if opt not in selected]

    # 其他情况返回空，让LLM自主决定是否提供选项以及提供什么选项
    return []
