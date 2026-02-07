"""Collector Agent Prompt Templates"""

from typing import Dict, Any, Optional, List

# Field-specific collection prompts
FIELD_COLLECTION_PROMPTS = {
    "people_count": {
        "ask": "请问是几个人搬家呢？单身、小家庭还是大家族？",
        "ask_options": ["单身", "2~3人", "4人以上"],
        "clarify_range": "您说的是{low}到{high}人呢，请问具体是几位呢？方便我们准备合适的车辆~",
        "confirm": "好的，{value}人搬家，记下来了！"
    },
    "from_address": {
        "ask": "请问您是从哪里搬出呢？",
        "ask_postal": "方便告诉我搬出地址的邮编吗？这样能更准确地帮您计算距离和报价哦~",
        "ask_building_type": "请问搬出的地方是什么类型的建筑呢？",
        "building_options": ["マンション", "アパート", "戸建て", "その他"],
        "confirm": "好的，从{value}搬出，记下来了！"
    },
    "to_address": {
        "ask": "请问您要搬到哪里呢？知道大概的城市或区就可以~",
        "ask_city": "请问搬入地址在哪个城市/区呢？",
        "ask_district_optional": "如果方便的话，可以告诉我更详细的区或地址吗？这样报价会更准确哦~ 当然，如果暂时不确定也没关系，我们可以先继续其他的~",
        "ask_building_type": "请问搬入的地方是什么类型的建筑呢？",
        "confirm": "好的，搬到{value}，记下来了！"
    },
    "move_date": {
        "ask": "请问您计划什么时候搬家呢？",
        "ask_specific": "请问是{month}月的上旬、中旬还是下旬呢？或者有具体日期吗？",
        "ask_period": "请问是上旬、中旬还是下旬呢？或者有具体日期吗？这样我们可以更准确地为您安排。",
        "ask_time_slot": "请问希望上午还是下午搬家呢？",
        "period_options": ["上旬", "中旬", "下旬"],
        "time_options": ["上午", "下午", "没有指定时段"],
        "confirm": "好的，搬家时间是{value}。"
    },
    "items": {
        "ask": "接下来我们来确认需要搬运的物品。您可以通过以下方式告诉我：\n1. 上传房间照片，我来帮您识别\n2. 直接告诉我有哪些大件家具家电\n3. 从物品目录中选择",
        "ask_simple": "请问有哪些大件物品需要搬运呢？比如冰箱、洗衣机、沙发等。",
        "ask_more": "还有其他需要搬运的大件物品吗？",
        "more_options": ["继续添加", "上传照片", "没有其他行李"],
        "options": ["上传房间照片", "直接输入物品", "从目录选择"],
        "confirm": "好的，已记录{count}件物品。",
        "image_prompt": "请上传房间照片，我会帮您识别其中的家具和家电。"
    },
    "from_floor_elevator": {
        "ask": "请问您现在住在几楼？有电梯吗？",
        "ask_floor": "请问是几楼呢？",
        "ask_elevator": "请问有电梯吗？",
        "elevator_options": ["有电梯", "无电梯"],
        "confirm": "好的，{floor}楼，{elevator}。"
    },
    "packing_service": {
        "ask": "请问打包工作是需要搬家公司帮忙，还是自己打包呢？",
        "options": ["全部请公司打包", "自己打包"],
        "confirm": "好的，{value}。"
    },
    "special_notes": {
        "ask": "请问有什么特殊情况或注意事项需要告知搬家公司吗？",
        "options": ["有宜家家具", "有钢琴需要搬运", "空调安装", "空调拆卸", "不用品回收", "没有了"],
        "ask_more": "还有其他需要特别注意的吗？",
        "confirm": "好的，已记录特殊注意事项。"
    }
}

# Collector system prompt template
COLLECTOR_SYSTEM_PROMPT = """# 角色
你是 ERABU 搬家服务的信息收集助手。

# 当前时间
{current_time}

# 当前收集任务
{collection_task}

# 已收集信息
```json
{fields_status}
```

# 最近对话历史
{recent_messages}

# 收集原则
1. 按优先级收集信息：人数 → 地址 → 日期 → 物品 → 其他
2. 用户提供信息后，确认并继续下一个问题
3. 不重复询问已收集的信息
4. 回复简洁，1-2句话

# 字段收集指南
{field_guide}

# 语气风格
{style_instruction}

# 验证规则
{validation_rules}

"""

# Validation rules by field
VALIDATION_RULES = {
    "people_count": "人数必须是正整数。「单身」=1人。如果用户说范围（如2~3人），需要确认具体数字。",
    "from_address": "搬出地址需要有邮编才能确认。如果没有邮编，要询问。",
    "to_address": "搬入地址至少需要知道城市/区级别。",
    "move_date": "日期需要包含年、月、以及旬或具体日期。「来月」需要结合当前时间解析。",
    "items": "至少需要1件物品才能继续。用户可以通过上传照片、直接输入或从目录选择来添加物品。大件家具家电包括：床、沙发、桌子、柜子、冰箱、洗衣机、电视、空调等。",
    "from_floor_elevator": "公寓类建筑（マンション、アパート等）必须询问楼层和电梯情况。",
    "packing_service": "确认是公司打包还是自己打包。",
    "special_notes": "主动询问特殊情况：宜家家具、钢琴、空调、不用品回收等。"
}


def get_field_collection_prompt(field_name: str) -> Dict[str, Any]:
    """Get collection prompt for a specific field"""
    return FIELD_COLLECTION_PROMPTS.get(field_name, {})


def format_collection_task(
    target_field: str,
    sub_task: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Format the current collection task description"""
    prompts = get_field_collection_prompt(target_field)
    context = context or {}

    task_descriptions = {
        "people_count": "收集搬家人数",
        "from_address": "收集搬出地址",
        "to_address": "收集搬入地址",
        "move_date": "收集搬家日期",
        "items": "收集搬运物品清单",
        "from_floor_elevator": "收集楼层和电梯信息",
        "packing_service": "确认打包服务需求",
        "special_notes": "收集特殊注意事项"
    }

    base_task = task_descriptions.get(target_field, f"收集{target_field}")

    # Add sub-task details
    if sub_task == "ask_postal":
        return f"{base_task} - Asking postal code"
    elif sub_task == "ask_building_type":
        return f"{base_task} - Asking building type"
    elif sub_task == "ask_district_optional":
        return f"{base_task} - Optionally asking for more detailed district/address"
    elif sub_task == "ask_period":
        return f"{base_task} - Asking for 旬 (上旬/中旬/下旬) or specific date"
    elif sub_task == "ask_time_slot":
        return f"{base_task} - Asking time slot"
    elif sub_task == "ask_floor":
        return f"{base_task} - Asking floor"
    elif sub_task == "ask_elevator":
        return f"{base_task} - Asking about elevator"
    elif sub_task == "clarify":
        return f"{base_task} - Needs confirmation"
    elif sub_task == "confirm":
        return f"{base_task} - Confirm information"
    elif sub_task == "ask_more_items":
        return f"{base_task} - Ask for more items"
    elif sub_task == "confirm_items":
        return f"{base_task} - Confirm item list"
    elif sub_task == "image_recognition":
        return f"{base_task} - Processing image recognition results"

    return base_task


def format_field_guide(target_field: str, fields_status: Dict[str, Any]) -> str:
    """Format field-specific collection guide"""
    prompts = get_field_collection_prompt(target_field)

    guide_parts = []

    if target_field == "people_count":
        guide_parts.append("- 询问搬家人数")
        guide_parts.append("- 可提供选项：单身 / 2~3人 / 4人以上")
        guide_parts.append("- 如果用户说范围，需要确认具体数字")

    elif target_field == "from_address":
        from_addr = fields_status.get("from_address", {})
        if isinstance(from_addr, dict):
            if from_addr.get("value") and not from_addr.get("postal_code"):
                guide_parts.append("- 已有地址但缺少邮编，请询问邮编")
            elif not from_addr.get("building_type"):
                guide_parts.append("- 需要询问建筑类型（マンション/アパート/戸建て/その他）")
            else:
                guide_parts.append("- 询问搬出地址")
        else:
            guide_parts.append("- 询问搬出地址")

    elif target_field == "to_address":
        to_addr = fields_status.get("to_address", {})
        if isinstance(to_addr, dict):
            status = to_addr.get("status", "not_collected")
            city = to_addr.get("city", "")
            if status == "baseline" and city and not to_addr.get("district"):
                guide_parts.append(f"- 已有城市信息：{city}")
                guide_parts.append("- 可以询问更详细的区，但这是可选的")
                guide_parts.append("- 提供该城市常见的区作为选项")
                guide_parts.append("- 告诉用户如果不确定也可以继续")
            else:
                guide_parts.append("- 询问搬入地址")
                guide_parts.append("- 至少需要知道城市/区级别")
        else:
            guide_parts.append("- 询问搬入地址")
            guide_parts.append("- 至少需要知道城市/区级别")

    elif target_field == "move_date":
        move_date = fields_status.get("move_date", {})
        if isinstance(move_date, dict):
            has_month = move_date.get("month") is not None
            has_day_or_period = move_date.get("day") is not None or move_date.get("period") is not None

            if has_month and not has_day_or_period:
                guide_parts.append(f"- 已有月份（{move_date.get('month')}月），但缺少旬或具体日期")
                guide_parts.append("- 必须询问：是上旬、中旬还是下旬？或者有具体日期吗？")
                guide_parts.append("- 这是达到底线的必要条件")
            elif move_date.get("value") and has_day_or_period and not move_date.get("time_slot"):
                guide_parts.append("- 已有日期，询问时间段（上午/下午）")
            else:
                guide_parts.append("- 询问搬家日期")
        else:
            guide_parts.append("- 询问搬家日期")

    elif target_field == "items":
        items = fields_status.get("items", {})
        if isinstance(items, dict) and items.get("list"):
            count = len(items["list"])
            item_names = [item.get("name_ja", item.get("name", "item")) for item in items["list"][:5]]
            guide_parts.append(f"- Already recorded {count} items: {', '.join(item_names)}")
            guide_parts.append("- Ask if there are other items")
            guide_parts.append("- Options: continue adding / upload photo / no more items")
        else:
            guide_parts.append("- Start collecting items for moving")
            guide_parts.append("- Provide three ways: upload photo, enter directly, or select from catalog")
            guide_parts.append("- Examples of large items: fridge, washing machine, sofa, bed, TV, desk, etc.")
            guide_parts.append("- UI shows item_evaluation component for user to interact with")

    elif target_field == "from_floor_elevator":
        floor_info = fields_status.get("from_floor_elevator", {})
        if isinstance(floor_info, dict):
            if floor_info.get("floor") and floor_info.get("has_elevator") is None:
                guide_parts.append("- 已知楼层，询问是否有电梯")
            elif floor_info.get("has_elevator") is not None and not floor_info.get("floor"):
                guide_parts.append("- 已知电梯情况，询问楼层")
            else:
                guide_parts.append("- 询问楼层和电梯情况")
        else:
            guide_parts.append("- 询问楼层和电梯情况")

    elif target_field == "packing_service":
        guide_parts.append("- 询问打包服务需求")
        guide_parts.append("- 选项：全部请公司打包 / 自己打包")

    elif target_field == "special_notes":
        notes = fields_status.get("special_notes", [])
        if notes:
            guide_parts.append(f"- 已记录: {', '.join(notes)}")
        guide_parts.append("- 询问是否有特殊注意事项")
        guide_parts.append("- 提示：宜家家具、钢琴、空调安装/拆卸、不用品回收")

    return "\n".join(guide_parts) if guide_parts else "继续收集信息"


def format_style_instruction(style: str) -> str:
    """Format style instruction"""
    styles = {
        "friendly": "用友好的语气，回复简洁。",
        "professional": "用专业、清晰的语气。",
        "empathetic": "用同理心、关怀的语气。",
        "concise": "用简洁的语气，直接问问题。"
    }
    return styles.get(style, styles["friendly"])


def build_collector_prompt(
    target_field: str,
    fields_status: Dict[str, Any],
    recent_messages: List[Dict[str, Any]] = None,
    style: str = "friendly",
    sub_task: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Build complete collector system prompt"""
    from datetime import datetime
    import json

    recent_messages = recent_messages or []

    # Format recent messages
    if recent_messages:
        msg_lines = []
        for msg in recent_messages[-10:]:
            role = "用户" if msg.get("role") == "user" else "Agent"
            content = msg.get("content", "")[:200]
            msg_lines.append(f"{role}: {content}")
        formatted_messages = "\n".join(msg_lines)
    else:
        formatted_messages = "（无历史对话）"

    # Format fields status (simplified)
    simplified_fields = {}
    for key, value in fields_status.items():
        if isinstance(value, dict):
            status = value.get("status", "not_collected")
            val = value.get("value")
            if val is not None:
                simplified_fields[key] = {"value": val, "status": status}
            else:
                simplified_fields[key] = {"status": status}
        else:
            simplified_fields[key] = value

    return COLLECTOR_SYSTEM_PROMPT.format(
        current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        collection_task=format_collection_task(target_field, sub_task, context),
        fields_status=json.dumps(simplified_fields, ensure_ascii=False, indent=2),
        recent_messages=formatted_messages,
        field_guide=format_field_guide(target_field, fields_status),
        style_instruction=format_style_instruction(style),
        validation_rules=VALIDATION_RULES.get(target_field, "确保信息准确完整")
    )


# Confirmation prompt template
CONFIRMATION_PROMPT = """# 角色
你是 ERABU 的信息确认专家，负责向用户确认收集到的信息。

# 已收集信息摘要
{summary}

# 任务
请用自然、友好的语气向用户确认以上信息是否正确。

# 输出要求
1. 用简洁的方式列出关键信息
2. 询问用户是否需要修改
3. 如果都正确，询问是否可以发送报价请求
"""


def build_confirmation_prompt(fields_status: Dict[str, Any]) -> str:
    """Build confirmation prompt"""
    summary_parts = []

    # People count
    people = fields_status.get("people_count")
    if people:
        summary_parts.append(f"- 搬家人数：{people}人")

    # From address
    from_addr = fields_status.get("from_address", {})
    if isinstance(from_addr, dict) and from_addr.get("value"):
        addr_str = from_addr["value"]
        if from_addr.get("building_type"):
            addr_str += f"（{from_addr['building_type']}）"
        summary_parts.append(f"- 搬出地址：{addr_str}")

    # To address
    to_addr = fields_status.get("to_address", {})
    if isinstance(to_addr, dict) and to_addr.get("value"):
        summary_parts.append(f"- 搬入地址：{to_addr['value']}")

    # Move date
    move_date = fields_status.get("move_date", {})
    if isinstance(move_date, dict) and move_date.get("value"):
        date_str = move_date["value"]
        if move_date.get("time_slot"):
            date_str += f" {move_date['time_slot']}"
        summary_parts.append(f"- 搬家时间：{date_str}")

    # Items
    items = fields_status.get("items", {})
    if isinstance(items, dict) and items.get("list"):
        item_names = [item.get("name", str(item)) for item in items["list"][:5]]
        items_str = "、".join(item_names)
        if len(items["list"]) > 5:
            items_str += f" 等{len(items['list'])}件"
        summary_parts.append(f"- 搬运物品：{items_str}")

    # Floor/elevator
    floor_info = fields_status.get("from_floor_elevator", {})
    if isinstance(floor_info, dict):
        if floor_info.get("floor"):
            elevator_str = "有电梯" if floor_info.get("has_elevator") else "无电梯"
            summary_parts.append(f"- 楼层情况：{floor_info['floor']}楼，{elevator_str}")

    # Packing
    packing = fields_status.get("packing_service")
    if packing:
        summary_parts.append(f"- 打包服务：{packing}")

    # Special notes
    notes = fields_status.get("special_notes", [])
    if notes:
        summary_parts.append(f"- 特殊注意：{', '.join(notes)}")

    summary = "\n".join(summary_parts) if summary_parts else "暂无信息"

    return CONFIRMATION_PROMPT.format(summary=summary)
