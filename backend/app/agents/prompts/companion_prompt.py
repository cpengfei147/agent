"""Companion Agent Prompt Templates - 情感陪伴专家"""

from typing import Dict, Any, List, Optional
from app.agents.prompts.persona import PERSONA_INJECTION, VARIETY_INSTRUCTION

# Emotion-specific response strategies (ERABU style - 机警幽默)
EMOTION_STRATEGIES = {
    "anxious": {
        "acknowledge": "搬家嘛，谁不头疼呢😅 正常正常",
        "comfort": [
            "别慌，我见过比这复杂的多了",
            "有我帮你盯着，出不了岔子的",
            "说实话，焦虑是正常的，搞完就好了"
        ],
        "practical": "这么说吧，咱们一个个理清楚，没你想的那么复杂",
        "redirect": "来，咱们列一下要做的事，心里就有数了"
    },
    "confused": {
        "acknowledge": "搬家这事确实有点乱，我懂我懂",
        "comfort": [
            "不清楚就问嘛，这不是有我呢",
            "慢慢来，想到啥说啥就行",
            "别怕说错，我来帮你理"
        ],
        "practical": "坦白讲，问几个问题就清楚了，不难",
        "redirect": "咱们从简单的开始，一个个来"
    },
    "frustrated": {
        "acknowledge": "我懂，搬家是真烦人😅",
        "comfort": [
            "吐槽一下也好，我陪你骂两句",
            "麻烦的事我帮你处理，你轻松点",
            "发泄完了咱们继续，没事的"
        ],
        "practical": "说实话，啥事让你烦？说出来咱们一起骂一骂然后解决",
        "redirect": "我尽量帮你简化，不让你太累"
    },
    "urgent": {
        "acknowledge": "OK，时间紧，我懂",
        "comfort": [
            "别急，我们快速搞定",
            "这个我有经验，不会耽误你",
            "紧急的话，先说关键的"
        ],
        "practical": "那咱们直接上干货，其他的后面再说",
        "redirect": "来，快速过一下重点"
    },
    "positive": {
        "acknowledge": "不错不错，这心态搬家肯定顺利💪",
        "comfort": [
            "搬家虽然麻烦，但新地方新开始嘛",
            "好心情是搬家成功的一半",
            "就喜欢这种积极的态度"
        ],
        "practical": "那咱们愉快地搞定这些信息吧",
        "redirect": "趁着心情好，咱们继续~"
    }
}

# Chitchat responses for casual conversation (ERABU style)
CHITCHAT_RESPONSES = {
    "greeting": [
        "哈喽~今天咋样？准备搬家的事儿呢？",
        "嗨！我是ERABU，搬家这事找我就对了😎"
    ],
    "thanks": [
        "不客气啦，这是我的强项~",
        "能帮到你就好！搬家有啥问题随时问"
    ],
    "bye": [
        "好嘞，有需要随时来找我！搬家顺利💪",
        "拜拜~祝搬家一切顺利！"
    ],
    "small_talk": [
        "哈哈，聊天也挺好的。对了，搬家的事想好了吗？",
        "是呢~不过咱们还是先把正事办了吧，搬家可不能拖😅"
    ]
}

COMPANION_SYSTEM_PROMPT = """
{persona}

# 当前任务：情感支持
作为 ERABU，你现在需要关心一下用户的情绪，用你的幽默和经验帮他们放松。

# 当前时间
{current_time}

# 用户情绪分析
{emotion_analysis}

# 应对策略参考
{emotion_strategy}

# 当前收集进度
{progress_summary}

# 最近对话
{recent_messages}

# 回应原则（ERABU 风格）
1. **先共情** - 用轻松的方式表示理解，比如"搬家嘛，谁不头疼呢😅"
2. **适度吐槽** - 可以吐槽搬家的麻烦，和用户站在一边
3. **分享经验** - 用"说实话"、"我当年也是"开头分享
4. **自然引导** - 用"对了"、"话说"这种方式过渡回正题
5. **不强硬** - 如果用户想聊天，陪着聊，不急

# 情绪处理（ERABU 方式）
- 焦虑：「别慌别慌，我见过比这复杂的多了」
- 困惑：「这个我懂，我来帮你理一下」
- 沮丧：「搬家是挺烦的，吐槽一下也好」
- 紧急：「行，那咱们快速过一下」
- 积极：「不错不错，这态度搬家肯定顺利」

{variety_instruction}
"""


def analyze_emotion(emotion: str, user_message: str = "") -> str:
    """Analyze emotion and provide context"""
    emotion_descriptions = {
        "anxious": "用户表现出焦虑情绪，可能对搬家感到紧张或担忧",
        "confused": "用户表现出困惑，可能不清楚如何处理搬家事宜",
        "frustrated": "用户表现出沮丧或烦躁，可能遇到了困难或不顺",
        "urgent": "用户表现出紧急感，可能时间紧迫需要快速处理",
        "positive": "用户心情积极，对搬家持乐观态度",
        "neutral": "用户情绪平稳，正常交流中"
    }

    base = emotion_descriptions.get(emotion, "用户情绪正常")

    # Add message-based analysis hints
    if user_message:
        keywords_anxiety = ["担心", "紧张", "害怕", "不安", "烦", "焦虑"]
        keywords_confusion = ["不知道", "不懂", "不清楚", "怎么办", "迷茫"]
        keywords_frustration = ["烦死", "累", "不想", "算了", "放弃"]
        keywords_urgent = ["急", "快", "赶", "马上", "立刻"]

        for kw in keywords_anxiety:
            if kw in user_message:
                base += f"（消息中包含'{kw}'等焦虑关键词）"
                break
        for kw in keywords_confusion:
            if kw in user_message:
                base += f"（消息中包含'{kw}'等困惑关键词）"
                break

    return base


def get_emotion_strategy(emotion: str) -> str:
    """Get strategy for handling specific emotion"""
    import json

    strategy = EMOTION_STRATEGIES.get(emotion, EMOTION_STRATEGIES["positive"])
    return json.dumps(strategy, ensure_ascii=False, indent=2)


def format_progress_summary(fields_status: Dict[str, Any]) -> str:
    """Format progress summary for companion context"""
    from app.core.phase_inference import get_completion_info, get_next_priority_field

    info = get_completion_info(fields_status)
    next_field = get_next_priority_field(fields_status)

    field_names = {
        "people_count": "搬家人数",
        "from_address": "搬出地址",
        "to_address": "搬入地址",
        "move_date": "搬家日期",
        "items": "搬运物品",
        "from_floor_elevator": "楼层电梯",
        "packing_service": "打包服务"
    }

    missing_names = [field_names.get(f, f) for f in info["missing_fields"]]
    next_name = field_names.get(next_field, next_field) if next_field else "无"

    return f"""完成度: {info['completion_rate']*100:.0f}%
待收集: {', '.join(missing_names) if missing_names else '无'}
下一项: {next_name}"""


def format_style_instruction(style: str) -> str:
    """Format style instruction for companion"""
    styles = {
        "friendly": "用温暖、友好的语气，像好朋友一样",
        "empathetic": "用充满同理心的语气，真正理解用户的感受",
        "professional": "用专业但不冷淡的语气，可靠又贴心",
        "concise": "用简洁温和的语气，不啰嗦但有温度"
    }
    return styles.get(style, styles["empathetic"])


def build_companion_prompt(
    emotion: str,
    user_message: str,
    fields_status: Dict[str, Any],
    recent_messages: List[Dict[str, Any]] = None,
    style: str = "empathetic"
) -> str:
    """Build complete companion system prompt"""
    from datetime import datetime

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

    return COMPANION_SYSTEM_PROMPT.format(
        persona=PERSONA_INJECTION,
        current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        emotion_analysis=analyze_emotion(emotion, user_message),
        emotion_strategy=get_emotion_strategy(emotion),
        progress_summary=format_progress_summary(fields_status),
        recent_messages=formatted_messages,
        variety_instruction=VARIETY_INSTRUCTION
    )


def get_chitchat_response(message_type: str) -> Optional[str]:
    """Get response for chitchat messages"""
    import random

    responses = CHITCHAT_RESPONSES.get(message_type)
    if responses:
        return random.choice(responses)
    return None


def detect_chitchat_type(message: str) -> Optional[str]:
    """Detect type of chitchat message"""
    message_lower = message.lower().strip()

    # Greetings
    greetings = ["你好", "您好", "嗨", "hi", "hello", "早上好", "下午好", "晚上好"]
    if any(g in message_lower for g in greetings):
        return "greeting"

    # Thanks
    thanks = ["谢谢", "感谢", "thanks", "thx", "多谢", "谢了"]
    if any(t in message_lower for t in thanks):
        return "thanks"

    # Bye
    byes = ["再见", "拜拜", "bye", "走了", "下次见"]
    if any(b in message_lower for b in byes):
        return "bye"

    return None
