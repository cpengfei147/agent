"""Tests for Companion Agent"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.companion import CompanionAgent, CompanionResponse
from app.agents.prompts.companion_prompt import (
    build_companion_prompt,
    get_chitchat_response,
    detect_chitchat_type,
    analyze_emotion,
    EMOTION_STRATEGIES,
    CHITCHAT_RESPONSES
)
from app.models.schemas import (
    RouterOutput, Intent, IntentType, Emotion,
    Action, ActionType, ResponseStrategy, AgentType, ResponseStyle
)


class TestEmotionStrategies:
    """Tests for emotion strategies"""

    def test_anxious_strategy_exists(self):
        """Test anxious strategy exists"""
        assert "anxious" in EMOTION_STRATEGIES
        strategy = EMOTION_STRATEGIES["anxious"]
        assert "acknowledge" in strategy
        assert "comfort" in strategy
        assert "practical" in strategy
        assert "redirect" in strategy

    def test_confused_strategy_exists(self):
        """Test confused strategy exists"""
        assert "confused" in EMOTION_STRATEGIES
        assert "acknowledge" in EMOTION_STRATEGIES["confused"]

    def test_frustrated_strategy_exists(self):
        """Test frustrated strategy exists"""
        assert "frustrated" in EMOTION_STRATEGIES
        assert "acknowledge" in EMOTION_STRATEGIES["frustrated"]

    def test_urgent_strategy_exists(self):
        """Test urgent strategy exists"""
        assert "urgent" in EMOTION_STRATEGIES
        assert "acknowledge" in EMOTION_STRATEGIES["urgent"]

    def test_positive_strategy_exists(self):
        """Test positive strategy exists"""
        assert "positive" in EMOTION_STRATEGIES


class TestChitchatResponses:
    """Tests for chitchat responses"""

    def test_greeting_responses_exist(self):
        """Test greeting responses exist"""
        assert "greeting" in CHITCHAT_RESPONSES
        assert len(CHITCHAT_RESPONSES["greeting"]) > 0

    def test_thanks_responses_exist(self):
        """Test thanks responses exist"""
        assert "thanks" in CHITCHAT_RESPONSES
        assert len(CHITCHAT_RESPONSES["thanks"]) > 0

    def test_bye_responses_exist(self):
        """Test bye responses exist"""
        assert "bye" in CHITCHAT_RESPONSES
        assert len(CHITCHAT_RESPONSES["bye"]) > 0


class TestDetectChitchatType:
    """Tests for detect_chitchat_type function"""

    def test_detect_greeting_chinese(self):
        """Test Chinese greetings"""
        assert detect_chitchat_type("你好") == "greeting"
        assert detect_chitchat_type("您好") == "greeting"
        assert detect_chitchat_type("早上好") == "greeting"

    def test_detect_greeting_english(self):
        """Test English greetings"""
        assert detect_chitchat_type("hi") == "greeting"
        assert detect_chitchat_type("hello") == "greeting"
        assert detect_chitchat_type("Hi there") == "greeting"

    def test_detect_thanks(self):
        """Test thanks detection"""
        assert detect_chitchat_type("谢谢") == "thanks"
        assert detect_chitchat_type("感谢") == "thanks"
        assert detect_chitchat_type("thanks") == "thanks"

    def test_detect_bye(self):
        """Test bye detection"""
        assert detect_chitchat_type("再见") == "bye"
        assert detect_chitchat_type("拜拜") == "bye"
        assert detect_chitchat_type("bye") == "bye"

    def test_non_chitchat_returns_none(self):
        """Test non-chitchat messages return None"""
        assert detect_chitchat_type("我要搬家") is None
        assert detect_chitchat_type("搬家多少钱") is None
        assert detect_chitchat_type("3个人") is None


class TestGetChitchatResponse:
    """Tests for get_chitchat_response function"""

    def test_greeting_response(self):
        """Test greeting returns response"""
        response = get_chitchat_response("greeting")
        assert response is not None
        assert isinstance(response, str)

    def test_thanks_response(self):
        """Test thanks returns response"""
        response = get_chitchat_response("thanks")
        assert response is not None

    def test_bye_response(self):
        """Test bye returns response"""
        response = get_chitchat_response("bye")
        assert response is not None

    def test_unknown_type_returns_none(self):
        """Test unknown type returns None"""
        response = get_chitchat_response("unknown")
        assert response is None


class TestAnalyzeEmotion:
    """Tests for analyze_emotion function"""

    def test_anxious_analysis(self):
        """Test anxious emotion analysis"""
        analysis = analyze_emotion("anxious")
        assert "焦虑" in analysis or "紧张" in analysis or "anxious" in analysis.lower()

    def test_confused_analysis(self):
        """Test confused emotion analysis"""
        analysis = analyze_emotion("confused")
        assert "困惑" in analysis or "confused" in analysis.lower()

    def test_frustrated_analysis(self):
        """Test frustrated emotion analysis"""
        analysis = analyze_emotion("frustrated")
        assert "沮丧" in analysis or "frustrated" in analysis.lower()

    def test_analysis_with_keywords(self):
        """Test analysis detects keywords in message"""
        analysis = analyze_emotion("neutral", "好担心搬家")
        # Should detect anxiety keyword
        assert "担心" in analysis or "焦虑" in analysis


class TestBuildCompanionPrompt:
    """Tests for build_companion_prompt function"""

    def test_basic_prompt_structure(self, empty_fields_status):
        """Test basic prompt structure"""
        prompt = build_companion_prompt(
            emotion="anxious",
            user_message="搬家好烦",
            fields_status=empty_fields_status,
            recent_messages=[],
            style="empathetic"
        )

        assert "情感陪伴" in prompt or "Companion" in prompt

    def test_prompt_includes_emotion(self, empty_fields_status):
        """Test prompt includes emotion info"""
        prompt = build_companion_prompt(
            emotion="anxious",
            user_message="test",
            fields_status=empty_fields_status
        )

        assert "anxious" in prompt.lower() or "焦虑" in prompt

    def test_prompt_includes_strategy(self, empty_fields_status):
        """Test prompt includes strategy"""
        prompt = build_companion_prompt(
            emotion="frustrated",
            user_message="test",
            fields_status=empty_fields_status
        )

        # Strategy should be included
        assert "acknowledge" in prompt or "comfort" in prompt or "理解" in prompt


class TestCompanionAgentDetermineStrategy:
    """Tests for CompanionAgent._determine_strategy"""

    @pytest.fixture
    def companion(self):
        agent = object.__new__(CompanionAgent)
        agent.llm_client = None
        return agent

    def test_chitchat_strategy(self, companion):
        """Test chitchat intent returns casual_chat strategy"""
        result = companion._determine_strategy("neutral", IntentType.CHITCHAT)
        assert result == "casual_chat"

    def test_anxious_strategy(self, companion):
        """Test anxious emotion returns comfort strategy"""
        result = companion._determine_strategy("anxious", IntentType.EXPRESS_ANXIETY)
        assert "comfort" in result or "clarify" in result

    def test_confused_strategy(self, companion):
        """Test confused emotion returns simplify strategy"""
        result = companion._determine_strategy("confused", IntentType.EXPRESS_CONFUSION)
        assert "simplify" in result or "guide" in result

    def test_frustrated_strategy(self, companion):
        """Test frustrated emotion returns listen strategy"""
        result = companion._determine_strategy("frustrated", IntentType.EXPRESS_FRUSTRATION)
        assert "listen" in result or "support" in result


class TestCompanionAgentShouldTransition:
    """Tests for CompanionAgent._should_transition"""

    @pytest.fixture
    def companion(self):
        agent = object.__new__(CompanionAgent)
        agent.llm_client = None
        return agent

    def test_chitchat_no_transition(self, companion):
        """Test chitchat doesn't trigger transition"""
        result = companion._should_transition("neutral", IntentType.CHITCHAT)
        assert result is False

    def test_frustrated_no_transition(self, companion):
        """Test frustrated doesn't push transition"""
        result = companion._should_transition("frustrated", IntentType.EXPRESS_FRUSTRATION)
        assert result is False

    def test_anxious_allows_transition(self, companion):
        """Test anxious allows gentle transition"""
        result = companion._should_transition("anxious", IntentType.EXPRESS_ANXIETY)
        assert result is True

    def test_positive_allows_transition(self, companion):
        """Test positive allows transition"""
        result = companion._should_transition("positive", IntentType.PROVIDE_INFO)
        assert result is True


class TestCompanionAgentGetFallbackResponse:
    """Tests for CompanionAgent._get_fallback_response"""

    @pytest.fixture
    def companion(self):
        agent = object.__new__(CompanionAgent)
        agent.llm_client = None
        return agent

    def test_anxious_fallback(self, companion):
        """Test anxious fallback response"""
        response = companion._get_fallback_response("anxious")
        assert response
        assert "紧张" in response or "担心" in response

    def test_confused_fallback(self, companion):
        """Test confused fallback response"""
        response = companion._get_fallback_response("confused")
        assert response

    def test_frustrated_fallback(self, companion):
        """Test frustrated fallback response"""
        response = companion._get_fallback_response("frustrated")
        assert response


class TestCompanionAgentGetQuickOptions:
    """Tests for CompanionAgent._get_quick_options"""

    @pytest.fixture
    def companion(self):
        agent = object.__new__(CompanionAgent)
        agent.llm_client = None
        return agent

    def test_anxious_options(self, companion, empty_fields_status):
        """Test anxious emotion options"""
        options = companion._get_quick_options("anxious", empty_fields_status)
        assert len(options) > 0
        assert any("理清" in opt or "休息" in opt for opt in options)

    def test_confused_options(self, companion, empty_fields_status):
        """Test confused emotion options"""
        options = companion._get_quick_options("confused", empty_fields_status)
        assert len(options) > 0

    def test_frustrated_options(self, companion, empty_fields_status):
        """Test frustrated emotion options"""
        options = companion._get_quick_options("frustrated", empty_fields_status)
        assert len(options) > 0
        assert any("继续" in opt or "冷静" in opt for opt in options)

    def test_urgent_options(self, companion, empty_fields_status):
        """Test urgent emotion options"""
        options = companion._get_quick_options("urgent", empty_fields_status)
        assert len(options) > 0
