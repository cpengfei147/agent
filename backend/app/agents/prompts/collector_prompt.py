"""Collector Agent Prompt Templates"""

from typing import Dict, Any, Optional, List
from app.agents.prompts.persona import PERSONA_INJECTION, VARIETY_INSTRUCTION

# Field-specific collection prompts (作为参考，LLM会自主生成自然的问法)
FIELD_COLLECTION_PROMPTS = {
    "people_count": {
        "goal": "询问搬家人数",
        "ask_options": ["单身", "2~3人", "4人以上"],
        "note": "如果用户说范围如2-3人，确认具体数字"
    },
    "from_address": {
        "goal": "询问搬出地址，最好能获取邮编",
        "ask_postal": "询问邮编以便准确计算",
        "ask_building_type": "询问建筑类型",
        "building_options": ["マンション", "アパート", "戸建て", "その他"]
    },
    "to_address": {
        "goal": "询问搬入地址，至少需要城市/区",
        "ask_city": "询问城市或区",
        "ask_district_optional": "可选择性询问更详细的地址",
        "ask_building_type": "询问建筑类型"
    },
    "move_date": {
        "goal": "询问搬家日期",
        "ask_options": ["这个月", "下个月", "再下个月"],
        "ask_period": "如果只有月份，需要问是上旬/中旬/下旬",
        "ask_time_slot": "日期确定后可以问时间段",
        "period_options": ["上旬", "中旬", "下旬"],
        "time_options": ["上午", "下午", "没有指定时段"]
    },
    "items": {
        "goal": "收集需要搬运的物品",
        "methods": ["上传照片识别", "直接输入", "从目录选择"],
        "ask_more": "询问是否还有其他物品",
        "more_options": ["继续添加", "没有其他行李了"],
        "options": ["上传房间照片", "直接输入物品", "从目录选择"],
        "note": "物品确认后要友好过渡到下一阶段"
    },
    "from_building_type": {
        "goal": "询问搬出地址的建筑类型",
        "options": ["マンション", "アパート", "戸建て", "その他"],
        "note": "物品收集完后第一个问题"
    },
    "from_floor_elevator": {
        "goal": "询问搬出地址的楼层和电梯情况",
        "elevator_options": ["有电梯", "无电梯", "跳过"],
        "note": "所有建筑类型都要询问，用户可以选择跳过"
    },
    "to_floor_elevator": {
        "goal": "询问搬入地址的楼层和电梯情况",
        "elevator_options": ["有电梯", "无电梯", "还不清楚"],
        "note": "非必填，用户不确定可以跳过"
    },
    "packing_service": {
        "goal": "询问打包服务需求",
        "options": ["全部请公司打包", "自己打包"],
        "note": "询问是公司打包还是自己打包"
    },
    "special_notes": {
        "goal": "询问特殊物品或服务需求",
        "options": ["有宜家家具", "有钢琴需要搬运", "空调安装", "空调拆卸", "不用品回收", "没有了"],
        "note": "多选，用户说没有了才结束"
    },
    # 复查阶段 - 进入阶段6前再次询问之前跳过的字段
    "review_from_floor_elevator": {
        "goal": "在最终确认前，再次询问之前跳过的搬出楼层电梯信息",
        "elevator_options": ["有电梯", "无电梯", "确认跳过"],
        "note": "提醒用户之前选择了跳过，问是否现在可以提供。如果还是不清楚就不强求"
    },
    "review_to_floor_elevator": {
        "goal": "在最终确认前，再次询问之前跳过的搬入楼层电梯信息",
        "elevator_options": ["有电梯", "无电梯", "确认跳过"],
        "note": "提醒用户之前选择了跳过，问是否现在可以提供。如果还是不清楚就不强求"
    },
    "review_packing_service": {
        "goal": "在最终确认前，再次询问之前跳过的打包服务需求",
        "options": ["全部请公司打包", "自己打包", "确认跳过"],
        "note": "提醒用户之前选择了跳过，问是否现在可以提供。如果还是不清楚就不强求"
    }
}

# Collector system prompt template
COLLECTOR_SYSTEM_PROMPT = """
{persona}

# 当前任务：信息收集
作为 ERABU，你现在在帮用户收集搬家信息来获取报价。

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
2. 用户提供信息后，简单确认并**自然平滑地**过渡到下一个信息点
3. 不重复询问已收集的信息
4. 回复简洁自然，1-2句话
5. **每次只收集一个信息点**
6. **重要：每次回复的措辞要有变化**，不要每次都用一样的开场白
7. 可以适当使用语气词（呢、哦、吧、~）让对话更自然

# 禁止事项（非常重要！）
- **禁止**说"下一个问题是..."、"那接下来问您..."、"第X个问题..."
- **禁止**审问式的语气，不要让用户感觉在填表或考试
- **禁止**生硬的转折，要像朋友聊天一样自然过渡

# 正确的过渡方式
- 确认后直接引出下一个话题，不要说"问题"
- 用"对了"、"顺便问下"、"另外"、"说到这个"等自然过渡词
- 把询问包装成"为了给您准确报价，需要知道..."的形式

# 字段收集指南
{field_guide}

# 语气风格
{style_instruction}

# 验证规则
{validation_rules}

{variety_instruction}

# 示例（同一个场景的不同回复方式，体现 ERABU 风格）
询问人数：
- "这次搬家几个人呀？"
- "话说是自己一个人搬还是几个人一起？"
- "说实话人数会影响报价，方便告诉我几个人搬吗？"
- "一个人搬还是有家人一起？"

确认并过渡到下一个信息（自然流畅，不要说"问题"）：
- "好的，�的儿岛中央区搬到大阪西区对吧~ 对了，大概什么时候搬呢？"
- "嗯嗯，地址记下了。为了准确报价，想了解下搬家日期大概定了吗？"
- "OK收到~ 说到搬家时间，您这边有大概的计划吗？"
- "了解了解，那搬家时间方面有想法了吗？"

❌ 错误示例（禁止使用）：
- "那下一个问题是，您计划什么时候搬家呢？" ← 太生硬
- "接下来第三个问题..." ← 像审问
- "好的，下面请告诉我搬家日期" ← 像填表

✅ 正确示例（自然过渡）：
- "好的~ 对了，搬家时间定了吗？"
- "收到收到，那大概什么时候搬呢？"
- "嗯嗯记住了，搬家日期方面有计划了吗？"

"""

# Validation rules by field
VALIDATION_RULES = {
    "people_count": "人数必须是正整数。「单身」=1人。如果用户说范围（如2~3人），需要确认具体数字。",
    "from_address": "搬出地址需要有邮编才能确认。如果没有邮编，要询问。",
    "to_address": "搬入地址至少需要知道城市/区级别。",
    "move_date": "日期需要包含年、月、以及旬或具体日期。「来月」需要结合当前时间解析。",
    "items": "至少需要1件物品才能继续。用户可以通过上传照片、直接输入或从目录选择来添加物品。大件家具家电包括：床、沙发、桌子、柜子、冰箱、洗衣机、电视、空调等。",
    "from_building_type": "搬出地址的建筑类型：マンション、アパート、戸建て、その他。这会影响后续楼层和电梯信息的收集。",
    "from_floor_elevator": "公寓类建筑（マンション、アパート等）必须询问楼层和电梯情况。",
    "to_floor_elevator": "搬入地址的楼层和电梯情况。这是非必填项，如果用户不清楚可以选择「还不清楚」跳过。",
    "packing_service": "确认是公司打包还是自己打包。用户可以选择跳过。",
    "special_notes": "主动询问特殊情况：宜家家具、钢琴、空调、不用品回收等。用户点击「没有了」表示完成。"
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
        "from_building_type": "收集搬出地址建筑类型",
        "from_floor_elevator": "收集搬出地址楼层和电梯信息",
        "to_floor_elevator": "收集搬入地址楼层和电梯信息",
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
            guide_parts.append(f"- 已记录 {count} 件物品: {', '.join(item_names)}")
            guide_parts.append("- 询问是否还有其他物品")
            guide_parts.append("- 选项：继续添加 / 上传照片 / 没有其他行李")
            guide_parts.append("- 如果用户确认完成，用友好的语气过渡到下一阶段")
        else:
            guide_parts.append("- 开始收集搬运物品")
            guide_parts.append("- 提供三种方式：上传照片、直接输入、从目录选择")
            guide_parts.append("- 大件物品举例：冰箱、洗衣机、沙发、床、电视、桌子等")
            guide_parts.append("- UI会显示物品评估组件供用户操作")

    elif target_field == "from_building_type":
        # 检查是否刚从物品收集阶段过渡来
        items = fields_status.get("items", {})
        items_done = isinstance(items, dict) and items.get("status") in ["baseline", "ideal"]
        if items_done:
            guide_parts.append("- 【阶段过渡】刚完成物品收集，用友好的过渡语引出下一个问题")
        guide_parts.append("- 只问搬出地址的建筑类型这一个问题")
        guide_parts.append("- **重要：不要同时问楼层、电梯或其他信息**")
        guide_parts.append("- 选项：マンション / アパート / 戸建て / その他")

    elif target_field == "from_floor_elevator":
        floor_info = fields_status.get("from_floor_elevator", {})
        guide_parts.append("- 只问搬出地址的楼层和电梯情况")
        guide_parts.append("- **重要：不要同时问搬入地址的信息，那是下一步的事**")
        if isinstance(floor_info, dict):
            if floor_info.get("floor") and floor_info.get("has_elevator") is None:
                guide_parts.append("- 已知楼层，只需询问是否有电梯")
            elif floor_info.get("has_elevator") is not None and not floor_info.get("floor"):
                guide_parts.append("- 已知电梯情况，只需询问楼层")
            else:
                guide_parts.append("- 询问搬出地址的楼层和电梯")

    elif target_field == "to_floor_elevator":
        floor_info = fields_status.get("to_floor_elevator", {})
        guide_parts.append("- 只问搬入地址的楼层和电梯情况")
        guide_parts.append("- **重要：不要回顾或重复问搬出地址的信息**")
        guide_parts.append("- 这是非必填项，如果用户不清楚可以选「还不清楚」跳过")
        if isinstance(floor_info, dict):
            if floor_info.get("floor") and floor_info.get("has_elevator") is None:
                guide_parts.append("- 已知搬入楼层，只需询问是否有电梯")
            elif floor_info.get("has_elevator") is not None and not floor_info.get("floor"):
                guide_parts.append("- 已知电梯情况，只需询问搬入楼层")

    elif target_field == "packing_service":
        guide_parts.append("- 只问打包服务需求这一个问题")
        guide_parts.append("- **重要：不要同时问其他信息**")
        guide_parts.append("- 选项：全部请公司打包 / 自己打包")

    elif target_field == "special_notes":
        notes = fields_status.get("special_notes", [])
        if notes:
            guide_parts.append(f"- 已记录: {', '.join(notes)}")
            guide_parts.append("- 询问还有没有其他需要注意的")
        else:
            guide_parts.append("- 询问是否有特殊注意事项")
            guide_parts.append("- 可选项：宜家家具、钢琴、空调安装/拆卸、不用品回收")
        guide_parts.append("- **重要：只问这一个问题，不要列出其他问题**")

    return "\n".join(guide_parts) if guide_parts else "继续收集信息"


def format_style_instruction(style: str) -> str:
    """Format style instruction"""
    styles = {
        "friendly": "用专业又温暖的语气，适当使用语气词（呢、哦、~）。回复简洁，1-2句话。",
        "professional": "用专业、清晰的语气，简洁明了。",
        "empathetic": "用同理心、关怀的语气，先理解用户感受再引导。",
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
        persona=PERSONA_INJECTION,
        current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        collection_task=format_collection_task(target_field, sub_task, context),
        fields_status=json.dumps(simplified_fields, ensure_ascii=False, indent=2),
        recent_messages=formatted_messages,
        field_guide=format_field_guide(target_field, fields_status),
        style_instruction=format_style_instruction(style),
        validation_rules=VALIDATION_RULES.get(target_field, "确保信息准确完整"),
        variety_instruction=VARIETY_INSTRUCTION
    )


# Confirmation prompt template
CONFIRMATION_PROMPT = """
{persona}

# 当前任务：信息确认
作为 ERABU，你现在要帮用户确认收集到的信息，准备获取报价。

# 已收集信息摘要
{summary}

# 输出要求
1. 用 ERABU 的风格（轻松、幽默）列出关键信息
2. 询问用户是否需要修改，可以说"有啥要改的吗？"这种
3. 如果都正确，用轻松的语气确认是否发送报价请求
4. 不要太正式，像朋友帮忙核对信息一样
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

    # From Floor/elevator
    floor_info = fields_status.get("from_floor_elevator", {})
    if isinstance(floor_info, dict):
        if floor_info.get("floor"):
            elevator_str = "有电梯" if floor_info.get("has_elevator") else "无电梯"
            summary_parts.append(f"- 搬出楼层：{floor_info['floor']}楼，{elevator_str}")

    # To Floor/elevator
    to_floor_info = fields_status.get("to_floor_elevator", {})
    if isinstance(to_floor_info, dict):
        if to_floor_info.get("floor"):
            if to_floor_info.get("has_elevator") == "还不清楚":
                elevator_str = "电梯情况待定"
            elif to_floor_info.get("has_elevator"):
                elevator_str = "有电梯" if to_floor_info.get("has_elevator") == True or to_floor_info.get("has_elevator") == "有电梯" else "无电梯"
            else:
                elevator_str = "电梯情况待定"
            summary_parts.append(f"- 搬入楼层：{to_floor_info['floor']}楼，{elevator_str}")

    # Packing
    packing = fields_status.get("packing_service")
    if packing:
        summary_parts.append(f"- 打包服务：{packing}")

    # Special notes
    notes = fields_status.get("special_notes", [])
    if notes:
        summary_parts.append(f"- 特殊注意：{', '.join(notes)}")

    summary = "\n".join(summary_parts) if summary_parts else "暂无信息"

    return CONFIRMATION_PROMPT.format(
        persona=PERSONA_INJECTION,
        summary=summary
    )
