"""Advisor Agent Prompt Templates"""

from typing import Dict, Any, List, Optional

# Knowledge base for common moving questions
MOVING_KNOWLEDGE = {
    "price": {
        "factors": [
            "搬家距离（同城/跨市/跨省）",
            "物品数量和大小",
            "楼层和电梯情况",
            "搬家日期（旺季/淡季）",
            "附加服务（打包、空调拆装等）"
        ],
        "estimates": {
            "single": "单身搬家：约3-8万日元（同城）",
            "couple": "2人搬家：约5-12万日元（同城）",
            "family": "家庭搬家：约8-20万日元（同城）",
            "long_distance": "跨市搬家：价格会增加50%-100%"
        },
        "tips": [
            "淡季（1-2月、6月、11月）价格更优惠",
            "平日比周末便宜约10-20%",
            "月中比月末便宜",
            "多家比价可节省10-30%"
        ]
    },
    "process": {
        "timeline": [
            "搬家前2-4周：确定搬家公司、整理物品",
            "搬家前1-2周：打包非必需品、办理地址变更",
            "搬家前1周：确认搬家细节、准备当天必需品",
            "搬家当天：监督搬运、检查物品",
            "搬家后：整理物品、完成地址变更"
        ],
        "checklist": [
            "水电煤气停/开手续",
            "邮局地址变更",
            "银行/保险地址变更",
            "驾照地址变更",
            "学校/单位地址变更"
        ]
    },
    "company": {
        "major_companies": [
            "アート引越センター - 服务全面，价格中高",
            "サカイ引越センター - 性价比高，口碑好",
            "日通 - 大型搬家专业，国际搬家强",
            "ヤマトホームコンビニエンス - 小件搬家方便",
            "アリさんマークの引越社 - 价格实惠"
        ],
        "selection_tips": [
            "建议获取3家以上报价",
            "确认保险范围和赔偿条款",
            "询问额外费用（楼梯费、距离费等）",
            "查看网上评价和口碑"
        ]
    },
    "tips": {
        "packing": [
            "提前2周开始整理，不急躁",
            "按房间分类打包，标注清楚",
            "贵重物品和重要文件自己携带",
            "易碎品用气泡膜或报纸包好",
            "重物放小箱，轻物放大箱"
        ],
        "cost_saving": [
            "淡季搬家可省10-30%",
            "自己打包可省1-3万日元",
            "处理不需要的物品减少搬运量",
            "多家比价是必须的"
        ],
        "moving_day": [
            "提前确认搬家公司联系方式",
            "准备现金支付小费（日本习惯）",
            "保持手机畅通",
            "检查水电煤关闭情况"
        ]
    }
}

# Question type to knowledge mapping
QUESTION_KNOWLEDGE_MAP = {
    "ask_price": ["price"],
    "ask_process": ["process"],
    "ask_company": ["company"],
    "ask_tips": ["tips", "cost_saving"],
    "ask_general": ["process", "tips"]
}

ADVISOR_SYSTEM_PROMPT = """# 角色
你是 ERABU 的搬家顾问（Advisor），专门回答用户关于搬家的各种问题。

# 当前时间
{current_time}

# 用户问题类型
{question_type}

# 相关知识
{relevant_knowledge}

# 当前收集进度
```json
{fields_summary}
```

# 最近对话
{recent_messages}

# 回答原则
1. **直接回答** - 先直接回答用户的问题
2. **实用信息** - 提供具体、可操作的建议
3. **适度详细** - 不要太啰嗦，但要有足够信息
4. **自然过渡** - 回答后可以自然地引导回信息收集
5. **诚实态度** - 不确定的说不确定，不要编造

# 语气风格
{style_instruction}

# 过渡策略
{transition_strategy}

# 输出要求
直接输出回复内容，像真人顾问一样自然交流。
回答问题后，可以适当引导用户继续提供搬家信息。
"""

TRANSITION_STRATEGIES = {
    "natural": "回答后自然过渡，不强硬。例如：'对了，您现在方便告诉我...'",
    "question_first": "优先完整回答问题，之后再考虑是否引导",
    "relate_to_quote": "将问题和报价联系起来。例如：'具体价格需要根据您的情况来定，方便告诉我...'",
    "no_transition": "只回答问题，不引导（适用于用户明确只想问问题的情况）"
}


def get_relevant_knowledge(question_type: str) -> str:
    """Get relevant knowledge for question type"""
    import json

    knowledge_keys = QUESTION_KNOWLEDGE_MAP.get(question_type, ["tips"])
    relevant = {}

    for key in knowledge_keys:
        if key in MOVING_KNOWLEDGE:
            relevant[key] = MOVING_KNOWLEDGE[key]

    return json.dumps(relevant, ensure_ascii=False, indent=2)


def format_style_instruction(style: str) -> str:
    """Format style instruction"""
    styles = {
        "friendly": "用友好、亲切的语气，像朋友给建议一样",
        "professional": "用专业、权威的语气，提供可靠信息",
        "empathetic": "用理解、关心的语气，考虑用户的顾虑",
        "concise": "用简洁明了的语气，直接给出答案"
    }
    return styles.get(style, styles["friendly"])


def get_transition_strategy(
    question_type: str,
    fields_status: Dict[str, Any],
    user_emotion: str
) -> str:
    """Determine transition strategy"""
    from app.core.phase_inference import get_completion_info

    completion = get_completion_info(fields_status)

    # If almost complete, don't push for more info
    if completion["completion_rate"] > 0.8:
        return TRANSITION_STRATEGIES["question_first"]

    # If user seems anxious or frustrated, be gentle
    if user_emotion in ["anxious", "frustrated", "confused"]:
        return TRANSITION_STRATEGIES["question_first"]

    # For price questions, relate to quote
    if question_type == "ask_price":
        return TRANSITION_STRATEGIES["relate_to_quote"]

    return TRANSITION_STRATEGIES["natural"]


def build_advisor_prompt(
    question_type: str,
    fields_status: Dict[str, Any],
    recent_messages: List[Dict[str, Any]] = None,
    style: str = "friendly",
    user_emotion: str = "neutral"
) -> str:
    """Build complete advisor system prompt"""
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

    # Simplify fields summary
    from app.core.phase_inference import get_completion_info
    completion = get_completion_info(fields_status)
    fields_summary = json.dumps({
        "completion_rate": f"{completion['completion_rate']*100:.0f}%",
        "missing_fields": completion["missing_fields"],
        "next_field": completion["next_priority_field"]
    }, ensure_ascii=False, indent=2)

    return ADVISOR_SYSTEM_PROMPT.format(
        current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        question_type=question_type,
        relevant_knowledge=get_relevant_knowledge(question_type),
        fields_summary=fields_summary,
        recent_messages=formatted_messages,
        style_instruction=format_style_instruction(style),
        transition_strategy=get_transition_strategy(question_type, fields_status, user_emotion)
    )


# Quick answer templates for common questions
QUICK_ANSWERS = {
    "price_range": """搬家费用主要取决于：
• 物品数量和距离
• 楼层和电梯情况
• 搬家日期

大概范围：
• 单身：3-8万日元
• 2人：5-12万日元
• 家庭：8-20万日元

想要准确报价的话，告诉我您的具体情况哦~""",

    "best_time": """搬家最佳时间：
• 淡季（1-2月、6月、11月）更便宜
• 平日比周末便宜10-20%
• 月中比月末便宜

如果时间灵活，选淡季平日能省不少~""",

    "what_to_prepare": """搬家前需要准备：
• 提前2-4周确定搬家公司
• 提前整理、处理不需要的物品
• 办理水电煤、地址变更手续
• 准备搬家当天必需品袋

需要详细的清单吗？"""
}


def get_quick_answer(question_key: str) -> Optional[str]:
    """Get quick answer for common questions"""
    return QUICK_ANSWERS.get(question_key)
