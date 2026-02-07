"""Tests for Router Agent"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.router import RouterAgent, get_router_agent
from app.models.schemas import IntentType, Emotion, AgentType
from app.models.fields import FieldStatus, Phase


class TestRouterAgent:
    """Tests for RouterAgent class"""

    @pytest.fixture
    def router_agent(self):
        """Create router agent fixture"""
        return RouterAgent()

    @pytest.mark.asyncio
    async def test_analyze_returns_router_output(
        self,
        router_agent,
        empty_fields_status,
        sample_router_output_json
    ):
        """Test analyze returns valid RouterOutput"""
        # Mock LLM client
        mock_response = {
            "content": sample_router_output_json,
            "error": None
        }

        with patch.object(
            router_agent.llm_client,
            'chat_complete',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await router_agent.analyze(
                user_message="2个人搬家",
                fields_status=empty_fields_status,
                recent_messages=[]
            )

            assert result.intent.primary == IntentType.PROVIDE_INFO
            assert result.intent.confidence == 0.95
            assert result.user_emotion == Emotion.NEUTRAL
            assert "people_count" in result.extracted_fields

    @pytest.mark.asyncio
    async def test_analyze_handles_llm_error(
        self,
        router_agent,
        empty_fields_status
    ):
        """Test analyze handles LLM errors gracefully"""
        mock_response = {
            "content": "",
            "error": "API timeout"
        }

        with patch.object(
            router_agent.llm_client,
            'chat_complete',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await router_agent.analyze(
                user_message="test message",
                fields_status=empty_fields_status,
                recent_messages=[]
            )

            # Should return fallback output
            assert result.intent.primary == IntentType.PROVIDE_INFO
            assert result.intent.confidence == 0.5  # Lower confidence for fallback

    @pytest.mark.asyncio
    async def test_analyze_handles_malformed_json(
        self,
        router_agent,
        empty_fields_status
    ):
        """Test analyze handles malformed JSON from LLM"""
        mock_response = {
            "content": "This is not valid JSON",
            "error": None
        }

        with patch.object(
            router_agent.llm_client,
            'chat_complete',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await router_agent.analyze(
                user_message="test message",
                fields_status=empty_fields_status,
                recent_messages=[]
            )

            # Should return fallback output
            assert result.intent is not None
            assert result.response_strategy is not None


class TestRouterAgentUpdateFields:
    """Tests for RouterAgent._update_fields_status"""

    @pytest.fixture
    def router_agent(self):
        return RouterAgent()

    def test_update_people_count(self, router_agent, empty_fields_status):
        """Test updating people_count field"""
        from app.models.schemas import ExtractedField

        extracted = {
            "people_count": ExtractedField(
                field_name="people_count",
                raw_value="3人",
                parsed_value=3,
                needs_verification=False,
                confidence=0.95
            )
        }

        result = router_agent._update_fields_status(empty_fields_status, extracted)

        assert result["people_count"] == 3
        assert result["people_count_status"] == FieldStatus.IDEAL.value

    def test_update_from_address(self, router_agent, empty_fields_status):
        """Test updating from_address field"""
        from app.models.schemas import ExtractedField

        extracted = {
            "from_address": ExtractedField(
                field_name="from_address",
                raw_value="渋谷区神宮前",
                parsed_value="東京都渋谷区神宮前",
                needs_verification=True,  # Address needs verification
                confidence=0.8
            )
        }

        result = router_agent._update_fields_status(empty_fields_status, extracted)

        assert result["from_address"]["value"] == "東京都渋谷区神宮前"
        # With needs_verification=True, should be IN_PROGRESS
        assert result["from_address"]["status"] == FieldStatus.IN_PROGRESS.value

    def test_update_special_notes_appends(self, router_agent):
        """Test special_notes appends to list"""
        from app.models.schemas import ExtractedField

        fields = {"special_notes": ["有钢琴"]}
        extracted = {
            "special_notes": ExtractedField(
                field_name="special_notes",
                raw_value="宜家家具",
                parsed_value=["有宜家家具"],
                needs_verification=False,
                confidence=0.9
            )
        }

        result = router_agent._update_fields_status(fields, extracted)

        assert "有钢琴" in result["special_notes"]
        assert "有宜家家具" in result["special_notes"]


class TestRouterAgentInferPhase:
    """Tests for RouterAgent._infer_phase"""

    @pytest.fixture
    def router_agent(self):
        return RouterAgent()

    def test_infer_phase_empty(self, router_agent, empty_fields_status):
        """Empty fields should infer people count phase"""
        result = router_agent._infer_phase(empty_fields_status)
        assert result == Phase.PEOPLE_COUNT.value

    def test_infer_phase_with_people(self, router_agent):
        """With people count, should infer address phase"""
        fields = {"people_count_status": "ideal"}
        result = router_agent._infer_phase(fields)
        assert result == Phase.ADDRESS.value

    def test_infer_phase_confirmation(self, router_agent, complete_fields_status):
        """Complete fields should infer confirmation phase"""
        result = router_agent._infer_phase(complete_fields_status)
        assert result == Phase.CONFIRMATION.value


class TestGetRouterAgent:
    """Tests for get_router_agent singleton"""

    def test_returns_same_instance(self):
        """Should return the same instance"""
        agent1 = get_router_agent()
        agent2 = get_router_agent()
        assert agent1 is agent2

    def test_is_router_agent_instance(self):
        """Should return RouterAgent instance"""
        agent = get_router_agent()
        assert isinstance(agent, RouterAgent)


class TestRouterAgentIntentRecognition:
    """Integration tests for intent recognition scenarios"""

    @pytest.fixture
    def router_agent(self):
        return RouterAgent()

    @pytest.mark.asyncio
    async def test_provide_info_intent(self, router_agent, empty_fields_status):
        """Test recognition of provide_info intent"""
        # This would require actual LLM call, so we mock it
        mock_response = {
            "content": '{"intent": {"primary": "provide_info", "confidence": 0.9}}',
            "error": None
        }

        with patch.object(
            router_agent.llm_client,
            'chat_complete',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await router_agent.analyze(
                user_message="3个人搬家",
                fields_status=empty_fields_status,
                recent_messages=[]
            )

            assert result.intent.primary == IntentType.PROVIDE_INFO

    @pytest.mark.asyncio
    async def test_ask_price_intent(self, router_agent, empty_fields_status):
        """Test recognition of ask_price intent"""
        mock_response = {
            "content": '{"intent": {"primary": "ask_price", "confidence": 0.85}}',
            "error": None
        }

        with patch.object(
            router_agent.llm_client,
            'chat_complete',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await router_agent.analyze(
                user_message="大概要多少钱？",
                fields_status=empty_fields_status,
                recent_messages=[]
            )

            assert result.intent.primary == IntentType.ASK_PRICE

    @pytest.mark.asyncio
    async def test_emotion_detection(self, router_agent, empty_fields_status):
        """Test emotion detection in messages"""
        mock_response = {
            "content": '{"intent": {"primary": "express_anxiety"}, "user_emotion": "anxious"}',
            "error": None
        }

        with patch.object(
            router_agent.llm_client,
            'chat_complete',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await router_agent.analyze(
                user_message="搬家好烦啊，不知道怎么弄",
                fields_status=empty_fields_status,
                recent_messages=[]
            )

            assert result.user_emotion == Emotion.ANXIOUS
