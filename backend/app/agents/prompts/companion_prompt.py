"""Companion Agent Prompt Templates - 情感陪伴专家"""

from typing import Dict, Any, List, Optional

# Emotion-specific response strategies
EMOTION_STRATEGIES = {
    "anxious": {
        "acknowledge": "搬家确实会让人有点紧张，这很正常",
        "comfort": [
            "别担心，一步一步来就好",
            "有我帮你整理，不会乱的",
            "很多人搬家前都会有点焦虑，处理完就轻松了"
        ],
        "practical": "让我帮你把事情理清楚，你会发现其实没那么复杂",
        "redirect": "我们一起把需要做的事情列出来，这样心里就有数了"
    },
    "confused": {
        "acknowledge": "搬家要考虑的事情确实挺多的",
        "comfort": [
            "不确定也没关系，我来帮你理清",
            "慢慢来，想到什么说什么就行",
            "我会一步步引导你的"
        ],
        "practical": "我来问你几个简单的问题，帮你整理清楚",
        "redirect": "咱们先从最基本的开始，一个一个来"
    },
    "frustrated": {
        "acknowledge": "理解你的感受，搬家确实挺烦人的",
        "comfort": [
            "深呼吸，我们一起解决",
            "麻烦的事情交给我来处理",
            "抱怨一下也好，发泄完咱们继续"
        ],
        "practical": "有什么具体让你烦心的吗？说出来我帮你想办法",
        "redirect": "我尽量帮你简化流程，让搬家没那么累"
    },
    "urgent": {
        "acknowledge": "明白，时间比较紧",
        "comfort": [
            "别着急，我们高效处理",
            "我会尽快帮你搞定",
            "紧急情况我们优先处理关键信息"
        ],
        "practical": "我们先确认最重要的几个信息，其他的可以后面补充",
        "redirect": "来，我们快速过一下关键问题"
    },
    "positive": {
        "acknowledge": "很高兴你心情不错！",
        "comfort": [
            "搬家虽然麻烦，但也是新的开始呢",
            "保持好心情，搬家会更顺利",
            "积极的态度最重要"
        ],
        "practical": "那我们就愉快地把信息整理一下吧",
        "redirect": "趁着好心情，我们继续~"
    }
}

# Chitchat responses for casual conversation
CHITCHAT_RESPONSES = {
    "greeting": [
        "你好呀！今天怎么样？",
        "嗨！有什么可以帮你的吗？"
    ],
    "thanks": [
        "不客气，这是我应该做的~",
        "能帮到你就好！"
    ],
    "bye": [
        "好的，有需要随时来找我！",
        "再见，祝搬家顺利！"
    ],
    "small_talk": [
        "哈哈，聊天也挺好的。对了，搬家的事情想好了吗？",
        "是呢~ 不过我们还是先把正事办了吧？"
    ]
}

COMPANION_SYSTEM_PROMPT = """# 角色
你是 ERABU 的情感陪伴专家（Companion），负责理解用户情绪、提供情感支持，然后温和地引导回正题。

# 当前时间
{current_time}

# 用户情绪分析
{emotion_analysis}

# 应对策略
{emotion_strategy}

# 当前收集进度
{progress_summary}

# 最近对话
{recent_messages}

# 回应原则
1. **先共情** - 首先表示理解用户的感受
2. **再安慰** - 给予适当的情感支持
3. **后引导** - 温和地引导回搬家话题
4. **不强硬** - 如果用户想聊天，适度陪聊
5. **保持温度** - 像朋友一样关心，不要太机械

# 语气风格
{style_instruction}

# 情绪处理要点
- 焦虑：帮助理清思路，降低不确定感
- 困惑：简化问题，一步步引导
- 沮丧：倾听、理解、鼓励
- 紧急：快速响应，优先关键信息
- 积极：保持愉快氛围，高效推进

# 输出要求
直接输出回复内容，像真正关心用户的朋友一样。
不要太长，2-4句话为宜。
自然过渡，不要突兀地转换话题。
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
        current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        emotion_analysis=analyze_emotion(emotion, user_message),
        emotion_strategy=get_emotion_strategy(emotion),
        progress_summary=format_progress_summary(fields_status),
        recent_messages=formatted_messages,
        style_instruction=format_style_instruction(style)
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
