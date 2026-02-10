"""Smart Quick Options Service - LLM-based context-aware option generation"""

import json
import logging
from typing import Dict, Any, List, Optional

from app.core import get_llm_client

logger = logging.getLogger(__name__)

SMART_OPTIONS_PROMPT = """根据对话上下文，判断是否需要显示快捷选项，以及显示什么选项。

# 当前收集的字段状态
{fields_summary}

# 下一个待收集字段
{next_field}

# 最近对话
{recent_context}

# 判断规则
1. 根据Agent最后一条消息的内容，判断需要什么选项
2. 选项要与Agent的问题直接相关，帮助用户快速回复
3. 如果用户刚刚提供了完整信息，可以不显示选项（返回空数组）
4. 选项要简洁实用，不超过4个
5. 不要重复显示用户已经回答过的选项

# 常见场景参考
- 开场/欢迎: ["获取搬家报价", "咨询搬家问题", "了解服务内容"]
- 询问人数: ["单身", "2~3人", "4人以上"]
- 询问日期月份: ["这个月", "下个月", "再下个月"]
- 询问日期时段: ["上旬", "中旬", "下旬"]
- 询问时间: ["上午", "下午", "没有指定"]
- 询问建筑类型: ["マンション", "アパート", "戸建て", "その他"]
- 询问电梯: ["有电梯", "无电梯", "不清楚"]
- 询问打包服务: ["全部请公司打包", "自己打包"]
- 询问是否还有物品: ["继续添加", "没有其他行李了"]
- 确认信息: ["确认无误，提交报价", "需要修改"]
- 复查跳过的字段: 在原选项基础上加"确认跳过"

请直接输出JSON格式，包含options数组：
{{"options": ["选项1", "选项2"]}} 或 {{"options": []}}"""


async def get_smart_quick_options(
    fields_status: Dict[str, Any],
    recent_messages: List[Dict[str, Any]] = None,
    next_field: Optional[str] = None,
    context_hint: Optional[str] = None
) -> List[str]:
    """
    Use LLM to intelligently decide quick options based on context.

    Args:
        fields_status: Current fields collection status
        recent_messages: Recent conversation history
        next_field: Next field to collect (optional hint)
        context_hint: Additional context hint (e.g., "items_just_confirmed")

    Returns:
        List of quick option strings, or empty list if no options needed
    """
    recent_messages = recent_messages or []

    # === 固定选项场景 ===

    # 开场白阶段：所有字段都未收集时，显示开场白选项
    from app.core.phase_inference import get_completion_info, infer_phase
    from app.models.fields import Phase

    current_phase = infer_phase(fields_status)
    if current_phase == Phase.OPENING:
        return ["获取搬家报价", "咨询搬家问题", "了解服务内容"]

    # 阶段6确认阶段：如果用户还未确认，显示确认相关选项
    completion_info = get_completion_info(fields_status)
    if completion_info["can_submit"] and not fields_status.get("user_confirmed_submit"):
        # 用户可以提交但还未确认，显示确认选项
        return ["确认无误，发送报价", "需要修改"]

    # 人数：固定选项
    if next_field == "people_count":
        return ["单身", "2~3人", "4人以上"]

    # 搬出地址建筑类型：固定选项
    if next_field == "from_building_type":
        return ["マンション", "アパート", "戸建て", "タワーマンション"]

    # 搬出楼层电梯：固定选项
    if next_field == "from_floor_elevator":
        return ["有电梯", "无电梯"]

    # 搬入楼层电梯：固定选项（包含"还不清楚"）
    if next_field == "to_floor_elevator":
        return ["有电梯", "无电梯", "还不清楚"]

    # 打包服务：固定选项
    if next_field == "packing_service":
        return ["全部请公司打包", "自己打包"]

    # 阶段5特殊注意事项：6个固定选项，动态过滤已选的
    if next_field == "special_notes":
        all_options = ["有宜家家具", "有钢琴需要搬运", "空调安装", "空调拆卸", "不用品回收", "没有了"]
        selected = fields_status.get("special_notes", [])
        if not isinstance(selected, list):
            selected = []
        return [opt for opt in all_options if opt not in selected]

    # 物品收集阶段
    if next_field == "items":
        items = fields_status.get("items", {})
        if isinstance(items, dict) and items.get("list"):
            return ["继续添加", "没有其他行李了"]
        # 没有物品时不显示快捷选项，让用户使用上传图片或从目录选择
        return []

    # === 其他所有场景由LLM智能判断 ===

    # Build recent context
    recent_context = ""
    for msg in recent_messages[-6:]:
        role = "用户" if msg.get("role") == "user" else "Agent"
        content = msg.get("content", "")[:200]
        recent_context += f"{role}: {content}\n"

    if context_hint:
        recent_context += f"\n[上下文提示: {context_hint}]\n"

    # Build fields summary
    fields_summary = {}
    for key, value in fields_status.items():
        if isinstance(value, dict):
            status = value.get("status", "not_collected")
            val = value.get("value", "")
            if val:
                fields_summary[key] = f"{val} ({status})"
            elif status != "not_collected":
                fields_summary[key] = f"({status})"
        elif value is not None and key not in ["special_notes_done", "skipped_fields_reviewed"]:
            fields_summary[key] = str(value)

    prompt = SMART_OPTIONS_PROMPT.format(
        fields_summary=json.dumps(fields_summary, ensure_ascii=False, indent=2),
        next_field=next_field or "无（可能是确认阶段或自由对话）",
        recent_context=recent_context or "(新对话)"
    )

    try:
        llm_client = get_llm_client()
        response = await llm_client.chat_complete(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        if response.get("error"):
            logger.warning(f"Smart options LLM error: {response['error']}")
            return []

        content = response.get("content", "{}").strip()

        # Parse JSON response
        data = json.loads(content)
        options = data.get("options", [])

        # Validate and return
        if isinstance(options, list):
            return [str(opt) for opt in options if opt][:4]

        return []

    except Exception as e:
        logger.warning(f"Smart options error: {e}")
        return []
