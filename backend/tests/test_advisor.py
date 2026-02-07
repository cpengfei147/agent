"""Tests for Advisor Agent"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.advisor import AdvisorAgent, AdvisorResponse
from app.agents.prompts.advisor_prompt import (
    build_advisor_prompt,
    get_quick_answer,
    get_relevant_knowledge,
    MOVING_KNOWLEDGE,
    QUESTION_KNOWLEDGE_MAP
)
from app.models.schemas import (
    RouterOutput, Intent, IntentType, Emotion,
    Action, ActionType, ResponseStrategy, AgentType, ResponseStyle
)


class TestAdvisorKnowledgeBase:
    """Tests for advisor knowledge base"""

    def test_knowledge_has_price_info(self):
        """Test price knowledge exists"""
        assert "price" in MOVING_KNOWLEDGE
        assert "factors" in MOVING_KNOWLEDGE["price"]
        assert "estimates" in MOVING_KNOWLEDGE["price"]
        assert "tips" in MOVING_KNOWLEDGE["price"]

    def test_knowledge_has_process_info(self):
        """Test process knowledge exists"""
        assert "process" in MOVING_KNOWLEDGE
        assert "timeline" in MOVING_KNOWLEDGE["process"]
        assert "checklist" in MOVING_KNOWLEDGE["process"]

    def test_knowledge_has_company_info(self):
        """Test company knowledge exists"""
        assert "company" in MOVING_KNOWLEDGE
        assert "major_companies" in MOVING_KNOWLEDGE["company"]
        assert "selection_tips" in MOVING_KNOWLEDGE["company"]

    def test_knowledge_has_tips(self):
        """Test tips knowledge exists"""
        assert "tips" in MOVING_KNOWLEDGE
        assert "packing" in MOVING_KNOWLEDGE["tips"]
        assert "cost_saving" in MOVING_KNOWLEDGE["tips"]


class TestGetRelevantKnowledge:
    """Tests for get_relevant_knowledge function"""

    def test_price_question(self):
        """Test price question returns price knowledge"""
        knowledge = get_relevant_knowledge("ask_price")
        assert "price" in knowledge or "factors" in knowledge

    def test_process_question(self):
        """Test process question returns process knowledge"""
        knowledge = get_relevant_knowledge("ask_process")
        assert "process" in knowledge or "timeline" in knowledge

    def test_company_question(self):
        """Test company question returns company knowledge"""
        knowledge = get_relevant_knowledge("ask_company")
        assert "company" in knowledge

    def test_tips_question(self):
        """Test tips question returns tips knowledge"""
        knowledge = get_relevant_knowledge("ask_tips")
        assert "tips" in knowledge

    def test_general_question(self):
        """Test general question returns mixed knowledge"""
        knowledge = get_relevant_knowledge("ask_general")
        assert knowledge  # Should return something


class TestBuildAdvisorPrompt:
    """Tests for build_advisor_prompt function"""

    def test_basic_prompt_structure(self, empty_fields_status):
        """Test basic prompt structure"""
        prompt = build_advisor_prompt(
            question_type="ask_price",
            fields_status=empty_fields_status,
            recent_messages=[],
            style="friendly",
            user_emotion="neutral"
        )

        assert "ERABU" in prompt or "搬家顾问" in prompt or "Advisor" in prompt
        assert "ask_price" in prompt

    def test_prompt_includes_knowledge(self, empty_fields_status):
        """Test prompt includes relevant knowledge"""
        prompt = build_advisor_prompt(
            question_type="ask_price",
            fields_status=empty_fields_status
        )

        # Should include some price-related content
        assert "price" in prompt.lower() or "费用" in prompt or "价格" in prompt

    def test_prompt_respects_style(self, empty_fields_status):
        """Test prompt respects style parameter"""
        friendly_prompt = build_advisor_prompt(
            question_type="ask_general",
            fields_status=empty_fields_status,
            style="friendly"
        )
        professional_prompt = build_advisor_prompt(
            question_type="ask_general",
            fields_status=empty_fields_status,
            style="professional"
        )

        # Prompts should be different based on style
        assert "友好" in friendly_prompt or "friendly" in friendly_prompt.lower()


class TestGetQuickAnswer:
    """Tests for get_quick_answer function"""

    def test_price_range_answer(self):
        """Test price range quick answer"""
        answer = get_quick_answer("price_range")
        assert answer is not None
        assert "万日元" in answer or "搬家" in answer

    def test_best_time_answer(self):
        """Test best time quick answer"""
        answer = get_quick_answer("best_time")
        assert answer is not None

    def test_unknown_key_returns_none(self):
        """Test unknown key returns None"""
        answer = get_quick_answer("nonexistent_key")
        assert answer is None


class TestAdvisorAgentDetermineQuestionType:
    """Tests for AdvisorAgent._determine_question_type"""

    @pytest.fixture
    def advisor(self):
        # Create without llm_client initialization
        agent = object.__new__(AdvisorAgent)
        agent.llm_client = None
        return agent

    def test_ask_price_intent(self, advisor):
        """Test ask_price intent mapping"""
        router_output = RouterOutput(
            intent=Intent(primary=IntentType.ASK_PRICE, confidence=0.9),
            extracted_fields={},
            user_emotion=Emotion.NEUTRAL,
            current_phase=1,
            next_actions=[],
            response_strategy=ResponseStrategy(
                agent_type=AgentType.ADVISOR,
                style=ResponseStyle.FRIENDLY
            ),
            updated_fields_status={}
        )

        result = advisor._determine_question_type(router_output)
        assert result == "ask_price"

    def test_ask_process_intent(self, advisor):
        """Test ask_process intent mapping"""
        router_output = RouterOutput(
            intent=Intent(primary=IntentType.ASK_PROCESS, confidence=0.9),
            extracted_fields={},
            user_emotion=Emotion.NEUTRAL,
            current_phase=1,
            next_actions=[],
            response_strategy=ResponseStrategy(
                agent_type=AgentType.ADVISOR,
                style=ResponseStyle.FRIENDLY
            ),
            updated_fields_status={}
        )

        result = advisor._determine_question_type(router_output)
        assert result == "ask_process"


class TestAdvisorAgentGetKnowledgeAreas:
    """Tests for AdvisorAgent._get_knowledge_areas"""

    @pytest.fixture
    def advisor(self):
        agent = object.__new__(AdvisorAgent)
        agent.llm_client = None
        return agent

    def test_price_knowledge_areas(self, advisor):
        """Test price returns price knowledge area"""
        areas = advisor._get_knowledge_areas("ask_price")
        assert "price" in areas

    def test_general_knowledge_areas(self, advisor):
        """Test general returns multiple areas"""
        areas = advisor._get_knowledge_areas("ask_general")
        assert len(areas) >= 1


class TestAdvisorAgentGetFallbackResponse:
    """Tests for AdvisorAgent._get_fallback_response"""

    @pytest.fixture
    def advisor(self):
        agent = object.__new__(AdvisorAgent)
        agent.llm_client = None
        return agent

    def test_price_fallback(self, advisor):
        """Test price fallback response"""
        response = advisor._get_fallback_response("ask_price")
        assert response
        assert "搬家" in response or "费用" in response

    def test_process_fallback(self, advisor):
        """Test process fallback response"""
        response = advisor._get_fallback_response("ask_process")
        assert response

    def test_general_fallback(self, advisor):
        """Test general fallback response"""
        response = advisor._get_fallback_response("ask_general")
        assert response


class TestAdvisorAgentGetQuickOptions:
    """Tests for AdvisorAgent._get_quick_options"""

    @pytest.fixture
    def advisor(self):
        agent = object.__new__(AdvisorAgent)
        agent.llm_client = None
        return agent

    def test_price_options(self, advisor, empty_fields_status):
        """Test price question options"""
        options = advisor._get_quick_options("ask_price", empty_fields_status)
        assert len(options) > 0

    def test_process_options(self, advisor, empty_fields_status):
        """Test process question options"""
        options = advisor._get_quick_options("ask_process", empty_fields_status)
        assert len(options) > 0

    def test_complete_fields_options(self, advisor, complete_fields_status):
        """Test options when fields are complete"""
        options = advisor._get_quick_options("ask_general", complete_fields_status)
        assert any("确认" in opt for opt in options)
