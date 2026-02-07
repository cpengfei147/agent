"""Tests for Collector Agent"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.collector import CollectorAgent, CollectorResponse, get_collector_agent
from app.models.schemas import (
    RouterOutput, Intent, IntentType, ExtractedField,
    Emotion, Action, ActionType, ResponseStrategy,
    AgentType, ResponseStyle
)
from app.models.fields import FieldStatus


class TestCollectorAgentDetermineTargetField:
    """Tests for _determine_target_field"""

    @pytest.fixture
    def collector(self):
        return CollectorAgent()

    @pytest.fixture
    def basic_router_output(self):
        """Create basic router output"""
        return RouterOutput(
            intent=Intent(
                primary=IntentType.PROVIDE_INFO,
                secondary=None,
                confidence=0.9
            ),
            extracted_fields={},
            user_emotion=Emotion.NEUTRAL,
            current_phase=1,
            next_actions=[
                Action(
                    type=ActionType.COLLECT_FIELD,
                    target="people_count",
                    priority=1
                )
            ],
            response_strategy=ResponseStrategy(
                agent_type=AgentType.COLLECTOR,
                style=ResponseStyle.FRIENDLY,
                should_acknowledge=True,
                guide_to_field="people_count",
                include_options=True
            ),
            updated_fields_status={}
        )

    def test_uses_guide_to_field(self, collector, basic_router_output, empty_fields_status):
        """Test uses guide_to_field from router output"""
        result = collector._determine_target_field(basic_router_output, empty_fields_status)
        assert result == "people_count"

    def test_uses_next_actions(self, collector, empty_fields_status):
        """Test falls back to next_actions"""
        router_output = RouterOutput(
            intent=Intent(primary=IntentType.PROVIDE_INFO, confidence=0.9),
            extracted_fields={},
            user_emotion=Emotion.NEUTRAL,
            current_phase=2,
            next_actions=[
                Action(type=ActionType.COLLECT_FIELD, target="from_address", priority=1)
            ],
            response_strategy=ResponseStrategy(
                agent_type=AgentType.COLLECTOR,
                style=ResponseStyle.FRIENDLY,
                guide_to_field=None  # No guide_to_field
            ),
            updated_fields_status={}
        )
        collector_agent = CollectorAgent()
        result = collector_agent._determine_target_field(router_output, empty_fields_status)
        assert result == "from_address"


class TestCollectorAgentUpdateField:
    """Tests for _update_field"""

    @pytest.fixture
    def collector(self):
        return CollectorAgent()

    def test_update_people_count(self, collector, empty_fields_status):
        """Test updating people_count"""
        from app.services.field_validator import ValidationResult

        result = ValidationResult(
            is_valid=True,
            parsed_value=3,
            status="ideal"
        )

        updated = collector._update_field(empty_fields_status, "people_count", result)
        assert updated["people_count"] == 3
        assert updated["people_count_status"] == FieldStatus.IDEAL.value

    def test_update_from_address(self, collector, empty_fields_status):
        """Test updating from_address"""
        from app.services.field_validator import ValidationResult

        result = ValidationResult(
            is_valid=True,
            parsed_value={
                "value": "東京都渋谷区",
                "postal_code": "150-0001",
                "prefecture": "東京都"
            },
            status="baseline"
        )

        updated = collector._update_field(empty_fields_status, "from_address", result)
        assert updated["from_address"]["value"] == "東京都渋谷区"
        assert updated["from_address"]["postal_code"] == "150-0001"
        assert updated["from_address"]["status"] == FieldStatus.BASELINE.value

    def test_update_special_notes_appends(self, collector):
        """Test special_notes appends to existing list"""
        from app.services.field_validator import ValidationResult

        fields = {"special_notes": ["有钢琴"]}
        result = ValidationResult(
            is_valid=True,
            parsed_value=["有宜家家具"],
            status="ideal"
        )

        updated = collector._update_field(fields, "special_notes", result)
        assert "有钢琴" in updated["special_notes"]
        assert "有宜家家具" in updated["special_notes"]

    def test_update_removes_duplicate_notes(self, collector):
        """Test special_notes removes duplicates"""
        from app.services.field_validator import ValidationResult

        fields = {"special_notes": ["有钢琴"]}
        result = ValidationResult(
            is_valid=True,
            parsed_value=["有钢琴", "有宜家家具"],
            status="ideal"
        )

        updated = collector._update_field(fields, "special_notes", result)
        assert updated["special_notes"].count("有钢琴") == 1


class TestCollectorAgentDetermineSubTask:
    """Tests for _determine_sub_task"""

    @pytest.fixture
    def collector(self):
        return CollectorAgent()

    def test_needs_postal_for_from_address(self, collector):
        """Test sub_task for from_address missing postal"""
        fields = {
            "from_address": {
                "value": "東京都渋谷区",
                "status": "in_progress"
            }
        }
        sub_task = collector._determine_sub_task("from_address", fields, {})
        assert sub_task == "ask_postal"

    def test_needs_building_type(self, collector):
        """Test sub_task for missing building type"""
        fields = {
            "from_address": {
                "value": "東京都渋谷区",
                "postal_code": "150-0001",
                "status": "baseline"
            }
        }
        sub_task = collector._determine_sub_task("from_address", fields, {})
        assert sub_task == "ask_building_type"

    def test_needs_time_slot(self, collector):
        """Test sub_task for missing time slot"""
        fields = {
            "move_date": {
                "value": "2026-03-15",
                "status": "baseline"
            }
        }
        sub_task = collector._determine_sub_task("move_date", fields, {})
        assert sub_task == "ask_time_slot"

    def test_needs_elevator(self, collector):
        """Test sub_task for missing elevator info"""
        fields = {
            "from_floor_elevator": {
                "floor": 5,
                "has_elevator": None
            }
        }
        sub_task = collector._determine_sub_task("from_floor_elevator", fields, {})
        assert sub_task == "ask_elevator"


class TestCollectorAgentGetQuickOptions:
    """Tests for _get_quick_options"""

    @pytest.fixture
    def collector(self):
        return CollectorAgent()

    def test_people_count_options(self, collector, empty_fields_status):
        """Test quick options for people_count"""
        options = collector._get_quick_options("people_count", None, empty_fields_status)
        assert "单身" in options
        assert "2~3人" in options

    def test_building_type_options(self, collector, empty_fields_status):
        """Test quick options for building type sub-task"""
        options = collector._get_quick_options("from_address", "ask_building_type", empty_fields_status)
        assert "マンション" in options
        assert "戸建て" in options

    def test_time_slot_options(self, collector, empty_fields_status):
        """Test quick options for time slot sub-task"""
        options = collector._get_quick_options("move_date", "ask_time_slot", empty_fields_status)
        assert "上午" in options
        assert "下午" in options

    def test_special_notes_filters_selected(self, collector):
        """Test special notes filters already selected options"""
        fields = {"special_notes": ["有宜家家具"]}
        options = collector._get_quick_options("special_notes", None, fields)
        assert "有宜家家具" not in options
        assert "有钢琴需要搬运" in options


class TestCollectorAgentCheckCompletion:
    """Tests for _check_completion"""

    @pytest.fixture
    def collector(self):
        return CollectorAgent()

    def test_incomplete_returns_false(self, collector, empty_fields_status):
        """Test incomplete fields returns False"""
        result = collector._check_completion(empty_fields_status)
        assert result is False

    def test_complete_returns_true(self, collector, complete_fields_status):
        """Test complete fields returns True"""
        result = collector._check_completion(complete_fields_status)
        assert result is True


class TestCollectorAgentValidateField:
    """Tests for _validate_field"""

    @pytest.fixture
    def collector(self):
        return CollectorAgent()

    @pytest.mark.asyncio
    async def test_validate_people_count(self, collector, empty_fields_status):
        """Test people_count validation"""
        result = await collector._validate_field("people_count", 3, empty_fields_status)
        assert result.is_valid
        assert result.parsed_value == 3

    @pytest.mark.asyncio
    async def test_validate_from_address(self, collector, empty_fields_status):
        """Test from_address validation"""
        result = await collector._validate_field(
            "from_address",
            "〒150-0001 東京都渋谷区",
            empty_fields_status
        )
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_validate_building_type(self, collector, empty_fields_status):
        """Test building type validation"""
        result = await collector._validate_field(
            "from_building_type",
            "マンション",
            empty_fields_status
        )
        assert result.is_valid
        assert result.parsed_value == "マンション"


class TestCollectorAgentCollect:
    """Tests for collect method"""

    @pytest.fixture
    def collector(self):
        return CollectorAgent()

    @pytest.fixture
    def router_output_with_extraction(self):
        """Router output with extracted fields"""
        return RouterOutput(
            intent=Intent(primary=IntentType.PROVIDE_INFO, confidence=0.9),
            extracted_fields={
                "people_count": ExtractedField(
                    field_name="people_count",
                    raw_value="3人",
                    parsed_value=3,
                    needs_verification=False,
                    confidence=0.95
                )
            },
            user_emotion=Emotion.NEUTRAL,
            current_phase=1,
            next_actions=[
                Action(type=ActionType.COLLECT_FIELD, target="from_address", priority=1)
            ],
            response_strategy=ResponseStrategy(
                agent_type=AgentType.COLLECTOR,
                style=ResponseStyle.FRIENDLY,
                should_acknowledge=True,
                guide_to_field="from_address"
            ),
            updated_fields_status={}
        )

    @pytest.mark.asyncio
    async def test_collect_updates_fields(
        self,
        collector,
        router_output_with_extraction,
        empty_fields_status
    ):
        """Test collect updates fields correctly"""
        # Mock LLM client
        mock_response = {"content": "好的，3人搬家。请问您现在住在哪里呢？", "error": None}

        with patch.object(
            collector.llm_client,
            'chat_complete',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await collector.collect(
                router_output=router_output_with_extraction,
                user_message="3个人搬家",
                fields_status=empty_fields_status
            )

            assert isinstance(result, CollectorResponse)
            assert result.updated_fields["people_count"] == 3
            assert result.next_field == "from_address"


class TestGetCollectorAgent:
    """Tests for get_collector_agent singleton"""

    def test_returns_same_instance(self):
        """Should return same instance"""
        agent1 = get_collector_agent()
        agent2 = get_collector_agent()
        assert agent1 is agent2

    def test_is_collector_agent(self):
        """Should return CollectorAgent instance"""
        agent = get_collector_agent()
        assert isinstance(agent, CollectorAgent)
