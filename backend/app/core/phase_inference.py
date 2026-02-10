"""Phase Inference - 根据字段状态推断当前阶段"""

from typing import Dict, Any, Optional, List
from app.models.fields import Phase, FieldStatus


def get_skipped_fields(fields_status: Dict[str, Any]) -> List[str]:
    """
    获取所有SKIPPED状态的字段

    Returns:
        SKIPPED字段名列表
    """
    skipped = []

    # 需要询问楼层电梯的建筑类型（公寓类）
    apartment_types = ["マンション", "アパート", "タワーマンション", "団地", "ビル"]
    from_addr = fields_status.get("from_address", {})
    building_type = from_addr.get("building_type") if isinstance(from_addr, dict) else None
    needs_floor_info = building_type in apartment_types if building_type else False

    # 检查 from_floor_elevator（只有公寓类建筑才检查）
    if needs_floor_info:
        from_floor = fields_status.get("from_floor_elevator", {})
        if isinstance(from_floor, dict):
            if from_floor.get("status") == FieldStatus.SKIPPED.value:
                skipped.append("from_floor_elevator")

    # 检查 to_floor_elevator（独立检查，因为搬入地址可能是不同类型的建筑）
    to_floor = fields_status.get("to_floor_elevator", {})
    if isinstance(to_floor, dict):
        if to_floor.get("status") == FieldStatus.SKIPPED.value:
            skipped.append("to_floor_elevator")

    # 检查 packing_service
    packing_status = fields_status.get("packing_service_status", FieldStatus.NOT_COLLECTED.value)
    if packing_status == FieldStatus.SKIPPED.value:
        skipped.append("packing_service")

    return skipped


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
    move_date = fields_status.get("move_date", {})
    date_status = move_date.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(move_date, dict) else FieldStatus.NOT_COLLECTED.value
    items = fields_status.get("items", {})
    items_status = items.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(items, dict) else FieldStatus.NOT_COLLECTED.value

    # If nothing has been collected yet, stay in OPENING phase
    # 用户可以任意顺序提供信息，只要有任何字段被收集，就不再是 OPENING
    all_not_collected = (
        people_status == FieldStatus.NOT_COLLECTED.value and
        from_status == FieldStatus.NOT_COLLECTED.value and
        to_status == FieldStatus.NOT_COLLECTED.value and
        date_status == FieldStatus.NOT_COLLECTED.value and
        items_status == FieldStatus.NOT_COLLECTED.value
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

    # Check other info - 阶段5的字段按顺序检查
    # 需要询问楼层电梯的建筑类型（公寓类）
    apartment_types = ["マンション", "アパート", "タワーマンション", "団地", "ビル"]

    # 1. 检查搬出地址建筑类型（必须询问）
    building_type = from_addr.get("building_type") if isinstance(from_addr, dict) else None
    if building_type is None:
        return Phase.OTHER_INFO

    # 判断是否需要询问楼层电梯（只有公寓类建筑需要）
    needs_floor_info = building_type in apartment_types

    # 2. 检查搬出楼层电梯（只有公寓类建筑需要询问）
    if needs_floor_info:
        from_floor = fields_status.get("from_floor_elevator", {})
        floor_status = from_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_floor, dict) else FieldStatus.NOT_COLLECTED.value
        if not is_skipped_or_done(floor_status):
            return Phase.OTHER_INFO

    # 3. 检查搬入楼层电梯（非必填，但要询问，独立于搬出地址的建筑类型）
    # 因为搬入地址可能是不同类型的建筑
    to_floor = fields_status.get("to_floor_elevator", {})
    to_floor_status = to_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(to_floor, dict) else FieldStatus.NOT_COLLECTED.value
    if not is_skipped_or_done(to_floor_status):
        return Phase.OTHER_INFO

    # 4. 检查打包服务（必须询问，可跳过）
    packing_status = fields_status.get("packing_service_status", FieldStatus.NOT_COLLECTED.value)
    packing_value = fields_status.get("packing_service")
    if packing_value is None and packing_status != FieldStatus.SKIPPED.value:
        return Phase.OTHER_INFO

    # 5. 检查特殊注意事项
    # 必须用户显式表示完成（说"没有了"或点击"没有了"）才算完成
    # 这确保用户有机会添加特殊注意事项
    special_notes_done = fields_status.get("special_notes_done", False)
    if not special_notes_done:
        return Phase.OTHER_INFO

    # 6. 进入阶段6前，检查是否有SKIPPED字段需要复查
    skipped_fields_reviewed = fields_status.get("skipped_fields_reviewed", False)
    if not skipped_fields_reviewed:
        skipped_fields = get_skipped_fields(fields_status)
        if skipped_fields:
            return Phase.OTHER_INFO  # 还有SKIPPED字段需要复查

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
    6. from_floor_elevator (公寓场景，必填)
    7. to_floor_elevator (非必填，但要询问)
    8. packing_service
    9. special_notes (多选，用户点"没有了"结束)
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

    # 6. Check from_building_type (必须询问)
    building_type = from_addr.get("building_type") if isinstance(from_addr, dict) else None
    if building_type is None:
        return "from_building_type"

    # 需要询问楼层电梯的建筑类型（公寓类）
    apartment_types = ["マンション", "アパート", "タワーマンション", "団地", "ビル"]
    from_needs_floor = building_type in apartment_types

    # 7. Check from_floor_elevator (只有公寓类建筑需要询问，条件必填)
    if from_needs_floor:
        from_floor = fields_status.get("from_floor_elevator", {})
        floor_status = from_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_floor, dict) else FieldStatus.NOT_COLLECTED.value
        if not is_skipped_or_done(floor_status):
            return "from_floor_elevator"

    # 8. Check to_floor_elevator (非必填，但要询问，用户可跳过)
    # 注意：搬入地址的楼层电梯独立于搬出地址的建筑类型，因为搬入地址可能是不同建筑
    to_floor = fields_status.get("to_floor_elevator", {})
    to_floor_status = to_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(to_floor, dict) else FieldStatus.NOT_COLLECTED.value
    if not is_skipped_or_done(to_floor_status):
        return "to_floor_elevator"

    # 9. Check packing_service (必须询问，可跳过)
    packing_status = fields_status.get("packing_service_status", FieldStatus.NOT_COLLECTED.value)
    packing_value = fields_status.get("packing_service")
    if packing_value is None and packing_status != FieldStatus.SKIPPED.value:
        return "packing_service"

    # 10. Check special_notes - 必须用户显式完成
    special_notes_done = fields_status.get("special_notes_done", False)
    if not special_notes_done:
        return "special_notes"

    # 11. 复查SKIPPED字段（进入阶段6前）
    skipped_fields_reviewed = fields_status.get("skipped_fields_reviewed", False)
    if not skipped_fields_reviewed:
        skipped_fields = get_skipped_fields(fields_status)
        if skipped_fields:
            return f"review_{skipped_fields[0]}"  # 返回 review_xxx 表示复查

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

    def is_skipped_or_done(status: str) -> bool:
        return status in [FieldStatus.BASELINE.value, FieldStatus.IDEAL.value, FieldStatus.SKIPPED.value]

    # Required fields check - 阶段1-4的核心字段
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

    # 阶段5字段 - 必须询问（可跳过）才能提交
    from_addr = fields_status.get("from_address", {})
    # 需要询问楼层电梯的建筑类型（公寓类）
    apartment_types = ["マンション", "アパート", "タワーマンション", "団地", "ビル"]

    # from_building_type - 必须询问
    building_type = from_addr.get("building_type") if isinstance(from_addr, dict) else None
    required_checks["from_building_type"] = building_type is not None

    # 判断是否需要询问楼层电梯（只有公寓类建筑需要）
    # 注意：如果 building_type 还未收集，需要等待收集后才能判断
    needs_floor_info = building_type in apartment_types if building_type else None  # None = 未知

    # from_floor_elevator - 只有公寓类建筑需要询问
    if needs_floor_info is True:
        # 确定是公寓类建筑，需要询问
        from_floor = fields_status.get("from_floor_elevator", {})
        floor_status = from_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(from_floor, dict) else FieldStatus.NOT_COLLECTED.value
        required_checks["from_floor_elevator"] = is_skipped_or_done(floor_status)
    elif needs_floor_info is False:
        # 确定不是公寓类建筑（戸建て等），自动完成
        required_checks["from_floor_elevator"] = True
    else:
        # building_type 未知，暂不计入 missing_fields（等待 building_type 收集后再判断）
        required_checks["from_floor_elevator"] = True  # 暂时标记为完成，避免重复计入

    # to_floor_elevator - 非必填，但要询问（独立于搬出地址的建筑类型）
    # 因为搬入地址可能是不同类型的建筑
    to_floor = fields_status.get("to_floor_elevator", {})
    to_floor_status = to_floor.get("status", FieldStatus.NOT_COLLECTED.value) if isinstance(to_floor, dict) else FieldStatus.NOT_COLLECTED.value
    required_checks["to_floor_elevator"] = is_skipped_or_done(to_floor_status)

    # packing_service - 必须询问（可跳过）
    packing_status = fields_status.get("packing_service_status", FieldStatus.NOT_COLLECTED.value)
    packing_value = fields_status.get("packing_service")
    required_checks["packing_service"] = packing_value is not None or packing_status == FieldStatus.SKIPPED.value

    # special_notes - 必须用户显式完成（说"没有了"）
    required_checks["special_notes"] = fields_status.get("special_notes_done", False)

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
