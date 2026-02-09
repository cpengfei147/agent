"""
Tests for LLM-driven flow control across all phases (0-6)

This test file verifies that:
1. Router LLM correctly outputs guide_to_field for each phase
2. Collector respects Router's guide_to_field decision
3. Flow progresses correctly through all phases
4. Edge cases are handled (skip, modify, etc.)
"""

import pytest
from unittest.mock import AsyncMock, patch
import json

from app.agents.router import RouterAgent
from app.agents.collector import CollectorAgent
from app.models.schemas import (
    RouterOutput, Intent, IntentType, ExtractedField,
    Emotion, Action, ActionType, ResponseStrategy,
    AgentType, ResponseStyle
)
from app.models.fields import FieldStatus, Phase, get_default_fields
from app.core.phase_inference import infer_phase, get_next_priority_field, get_completion_info


# ============ Fixtures ============

@pytest.fixture
def router_agent():
    return RouterAgent()


@pytest.fixture
def collector_agent():
    return CollectorAgent()


@pytest.fixture
def phase0_fields():
    """Phase 0: Opening - all fields empty"""
    return get_default_fields()


@pytest.fixture
def phase1_fields():
    """Phase 1: People count needed"""
    fields = get_default_fields()
    # Nothing filled yet, but conversation has started
    return fields


@pytest.fixture
def phase2_fields():
    """Phase 2: Addresses needed"""
    fields = get_default_fields()
    fields["people_count"] = 2
    fields["people_count_status"] = FieldStatus.IDEAL.value
    return fields


@pytest.fixture
def phase3_fields():
    """Phase 3: Date needed"""
    fields = get_default_fields()
    fields["people_count"] = 2
    fields["people_count_status"] = FieldStatus.IDEAL.value
    fields["from_address"] = {
        "value": "東京都渋谷区神宮前1-2-3",
        "postal_code": "150-0001",
        "status": FieldStatus.BASELINE.value,
        "building_type": "マンション"
    }
    fields["to_address"] = {
        "value": "大阪市北区",
        "city": "大阪市",
        "status": FieldStatus.BASELINE.value
    }
    return fields


@pytest.fixture
def phase4_fields():
    """Phase 4: Items needed"""
    fields = get_default_fields()
    fields["people_count"] = 2
    fields["people_count_status"] = FieldStatus.IDEAL.value
    fields["from_address"] = {
        "value": "東京都渋谷区神宮前1-2-3",
        "postal_code": "150-0001",
        "status": FieldStatus.BASELINE.value,
        "building_type": "マンション"
    }
    fields["to_address"] = {
        "value": "大阪市北区",
        "city": "大阪市",
        "status": FieldStatus.BASELINE.value
    }
    fields["move_date"] = {
        "value": "2026-03-15",
        "year": 2026,
        "month": 3,
        "day": 15,
        "status": FieldStatus.BASELINE.value
    }
    return fields


@pytest.fixture
def phase5_fields():
    """Phase 5: Other info needed (building type, floor, packing, special notes)"""
    fields = get_default_fields()
    fields["people_count"] = 2
    fields["people_count_status"] = FieldStatus.IDEAL.value
    fields["from_address"] = {
        "value": "東京都渋谷区神宮前1-2-3",
        "postal_code": "150-0001",
        "status": FieldStatus.BASELINE.value,
        "building_type": "マンション"
    }
    fields["to_address"] = {
        "value": "大阪市北区",
        "city": "大阪市",
        "status": FieldStatus.BASELINE.value
    }
    fields["move_date"] = {
        "value": "2026-03-15",
        "year": 2026,
        "month": 3,
        "day": 15,
        "status": FieldStatus.BASELINE.value
    }
    fields["items"] = {
        "list": [{"name": "冷蔵庫", "category": "large_appliances", "count": 1}],
        "status": FieldStatus.BASELINE.value
    }
    return fields


@pytest.fixture
def phase6_fields():
    """Phase 6: Confirmation - all fields complete"""
    fields = get_default_fields()
    fields["people_count"] = 2
    fields["people_count_status"] = FieldStatus.IDEAL.value
    fields["from_address"] = {
        "value": "東京都渋谷区神宮前1-2-3",
        "postal_code": "150-0001",
        "status": FieldStatus.BASELINE.value,
        "building_type": "マンション"
    }
    fields["to_address"] = {
        "value": "大阪市北区",
        "city": "大阪市",
        "status": FieldStatus.BASELINE.value
    }
    fields["move_date"] = {
        "value": "2026-03-15",
        "year": 2026,
        "month": 3,
        "day": 15,
        "status": FieldStatus.BASELINE.value
    }
    fields["items"] = {
        "list": [{"name": "冷蔵庫", "category": "large_appliances", "count": 1}],
        "status": FieldStatus.BASELINE.value
    }
    fields["from_floor_elevator"] = {
        "floor": 5,
        "has_elevator": True,
        "status": FieldStatus.BASELINE.value
    }
    fields["to_floor_elevator"] = {
        "floor": 3,
        "has_elevator": False,
        "status": FieldStatus.BASELINE.value
    }
    fields["packing_service"] = "自己打包"
    fields["packing_service_status"] = FieldStatus.SKIPPED.value
    fields["special_notes"] = []
    fields["special_notes_done"] = True
    # Skipped fields have been reviewed (required for phase 6)
    fields["skipped_fields_reviewed"] = True
    return fields


# ============ Helper Functions ============

def create_router_output(guide_to_field: str, extracted_fields: dict = None, phase: int = 1) -> RouterOutput:
    """Helper to create RouterOutput with specific guide_to_field"""
    extracted = {}
    if extracted_fields:
        for field_name, value in extracted_fields.items():
            extracted[field_name] = ExtractedField(
                field_name=field_name,
                raw_value=str(value),
                parsed_value=value,
                needs_verification=False,
                confidence=0.95
            )

    return RouterOutput(
        intent=Intent(primary=IntentType.PROVIDE_INFO, confidence=0.9),
        extracted_fields=extracted,
        user_emotion=Emotion.NEUTRAL,
        current_phase=phase,
        next_actions=[
            Action(type=ActionType.COLLECT_FIELD, target=guide_to_field, priority=1)
        ],
        response_strategy=ResponseStrategy(
            agent_type=AgentType.COLLECTOR,
            style=ResponseStyle.FRIENDLY,
            should_acknowledge=True,
            guide_to_field=guide_to_field,
            include_options=True
        ),
        updated_fields_status={}
    )


def mock_llm_response(guide_to_field: str, extracted_fields: dict = None, phase: int = 1) -> dict:
    """Create mock LLM JSON response"""
    extracted = {}
    if extracted_fields:
        for field_name, value in extracted_fields.items():
            extracted[field_name] = {
                "raw_value": str(value),
                "parsed_value": value,
                "needs_verification": False,
                "confidence": 0.95
            }

    return {
        "content": json.dumps({
            "intent": {"primary": "provide_info", "confidence": 0.9},
            "extracted_fields": extracted,
            "user_emotion": "neutral",
            "current_phase": phase,
            "next_actions": [
                {"type": "collect_field", "target": guide_to_field, "priority": 1}
            ],
            "response_strategy": {
                "agent_type": "collector",
                "style": "friendly",
                "should_acknowledge": True,
                "guide_to_field": guide_to_field,
                "include_options": True
            }
        }),
        "error": None
    }


# ============ Phase Inference Tests ============

class TestPhaseInference:
    """Test that phase inference works correctly for all phases"""

    def test_phase0_opening(self, phase0_fields):
        """Phase 0: All fields empty"""
        phase = infer_phase(phase0_fields)
        assert phase == Phase.OPENING

    def test_phase1_people_count(self, phase1_fields):
        """Phase 1: Need people count"""
        # To trigger PEOPLE_COUNT phase, at least one field must have been touched
        # (not all NOT_COLLECTED), but people_count itself is still not done
        # Set from_address to in_progress to indicate conversation has started
        phase1_fields["from_address"] = {"status": FieldStatus.IN_PROGRESS.value, "value": "東京"}
        phase = infer_phase(phase1_fields)
        assert phase == Phase.PEOPLE_COUNT

    def test_phase2_address(self, phase2_fields):
        """Phase 2: Need addresses"""
        phase = infer_phase(phase2_fields)
        assert phase == Phase.ADDRESS

    def test_phase3_date(self, phase3_fields):
        """Phase 3: Need date"""
        phase = infer_phase(phase3_fields)
        assert phase == Phase.DATE

    def test_phase4_items(self, phase4_fields):
        """Phase 4: Need items"""
        phase = infer_phase(phase4_fields)
        assert phase == Phase.ITEMS

    def test_phase5_other_info(self, phase5_fields):
        """Phase 5: Need other info"""
        phase = infer_phase(phase5_fields)
        assert phase == Phase.OTHER_INFO

    def test_phase6_confirmation(self, phase6_fields):
        """Phase 6: All complete, ready for confirmation"""
        phase = infer_phase(phase6_fields)
        assert phase == Phase.CONFIRMATION


# ============ Router guide_to_field Tests ============

class TestRouterGuideToField:
    """Test that Router correctly outputs guide_to_field for each phase"""

    @pytest.mark.asyncio
    async def test_router_guides_to_people_count(self, router_agent, phase1_fields):
        """Router should guide to people_count when it's not collected"""
        mock_response = mock_llm_response("people_count", phase=1)

        with patch.object(router_agent.llm_client, 'chat_complete',
                         new_callable=AsyncMock, return_value=mock_response):
            result = await router_agent.analyze(
                user_message="我想搬家",
                fields_status=phase1_fields,
                recent_messages=[]
            )

            assert result.response_strategy.guide_to_field == "people_count"

    @pytest.mark.asyncio
    async def test_router_guides_to_from_address(self, router_agent, phase2_fields):
        """Router should guide to from_address after people_count"""
        mock_response = mock_llm_response("from_address", {"people_count": 2}, phase=2)

        with patch.object(router_agent.llm_client, 'chat_complete',
                         new_callable=AsyncMock, return_value=mock_response):
            result = await router_agent.analyze(
                user_message="2个人",
                fields_status=phase2_fields,
                recent_messages=[]
            )

            assert result.response_strategy.guide_to_field == "from_address"

    @pytest.mark.asyncio
    async def test_router_guides_to_move_date(self, router_agent, phase3_fields):
        """Router should guide to move_date after addresses"""
        mock_response = mock_llm_response("move_date", phase=3)

        with patch.object(router_agent.llm_client, 'chat_complete',
                         new_callable=AsyncMock, return_value=mock_response):
            result = await router_agent.analyze(
                user_message="好的",
                fields_status=phase3_fields,
                recent_messages=[]
            )

            assert result.response_strategy.guide_to_field == "move_date"

    @pytest.mark.asyncio
    async def test_router_guides_to_items(self, router_agent, phase4_fields):
        """Router should guide to items after date"""
        mock_response = mock_llm_response("items", phase=4)

        with patch.object(router_agent.llm_client, 'chat_complete',
                         new_callable=AsyncMock, return_value=mock_response):
            result = await router_agent.analyze(
                user_message="3月15日",
                fields_status=phase4_fields,
                recent_messages=[]
            )

            assert result.response_strategy.guide_to_field == "items"

    @pytest.mark.asyncio
    async def test_router_guides_to_special_notes_after_packing(self, router_agent, phase5_fields):
        """Router should guide to special_notes after packing_service"""
        # Set up fields where packing is done but special_notes is not
        phase5_fields["from_floor_elevator"] = {
            "floor": 5,
            "has_elevator": True,
            "status": FieldStatus.BASELINE.value
        }
        phase5_fields["to_floor_elevator"] = {
            "status": FieldStatus.SKIPPED.value
        }
        phase5_fields["packing_service"] = "自己打包"
        phase5_fields["packing_service_status"] = FieldStatus.SKIPPED.value

        mock_response = mock_llm_response("special_notes", phase=5)

        with patch.object(router_agent.llm_client, 'chat_complete',
                         new_callable=AsyncMock, return_value=mock_response):
            result = await router_agent.analyze(
                user_message="自己打包",
                fields_status=phase5_fields,
                recent_messages=[]
            )

            assert result.response_strategy.guide_to_field == "special_notes"


# ============ Collector Respects Router Tests ============

class TestCollectorRespectsRouter:
    """Test that Collector respects Router's guide_to_field decision"""

    @pytest.fixture
    def collector(self):
        return CollectorAgent()

    def test_collector_uses_router_guide_to_field_phase1(self, collector, phase1_fields):
        """Collector should use Router's guide_to_field for phase 1"""
        router_output = create_router_output("people_count", phase=1)

        target = collector._determine_target_field(router_output, phase1_fields)
        assert target == "people_count"

    def test_collector_uses_router_guide_to_field_phase2(self, collector, phase2_fields):
        """Collector should use Router's guide_to_field for phase 2"""
        router_output = create_router_output("from_address", phase=2)

        target = collector._determine_target_field(router_output, phase2_fields)
        assert target == "from_address"

    def test_collector_uses_router_guide_to_field_phase3(self, collector, phase3_fields):
        """Collector should use Router's guide_to_field for phase 3"""
        router_output = create_router_output("move_date", phase=3)

        target = collector._determine_target_field(router_output, phase3_fields)
        assert target == "move_date"

    def test_collector_uses_router_guide_to_field_phase4(self, collector, phase4_fields):
        """Collector should use Router's guide_to_field for phase 4"""
        router_output = create_router_output("items", phase=4)

        target = collector._determine_target_field(router_output, phase4_fields)
        assert target == "items"

    def test_collector_uses_router_guide_to_field_phase5_packing(self, collector, phase5_fields):
        """Collector should use Router's guide_to_field for packing_service"""
        phase5_fields["from_floor_elevator"] = {
            "floor": 5,
            "has_elevator": True,
            "status": FieldStatus.BASELINE.value
        }
        phase5_fields["to_floor_elevator"] = {
            "status": FieldStatus.SKIPPED.value
        }
        router_output = create_router_output("packing_service", phase=5)

        target = collector._determine_target_field(router_output, phase5_fields)
        assert target == "packing_service"

    def test_collector_uses_router_guide_to_field_phase5_special_notes(self, collector, phase5_fields):
        """Collector should use Router's guide_to_field for special_notes"""
        phase5_fields["from_floor_elevator"] = {
            "floor": 5,
            "has_elevator": True,
            "status": FieldStatus.BASELINE.value
        }
        phase5_fields["to_floor_elevator"] = {
            "status": FieldStatus.SKIPPED.value
        }
        phase5_fields["packing_service"] = "自己打包"
        phase5_fields["packing_service_status"] = FieldStatus.SKIPPED.value

        router_output = create_router_output("special_notes", phase=5)

        target = collector._determine_target_field(router_output, phase5_fields)
        assert target == "special_notes"

    def test_collector_fallback_when_no_guide_to_field(self, collector, phase2_fields):
        """Collector should fallback to get_next_priority_field when no guide_to_field"""
        router_output = RouterOutput(
            intent=Intent(primary=IntentType.PROVIDE_INFO, confidence=0.9),
            extracted_fields={},
            user_emotion=Emotion.NEUTRAL,
            current_phase=2,
            next_actions=[],
            response_strategy=ResponseStrategy(
                agent_type=AgentType.COLLECTOR,
                style=ResponseStyle.FRIENDLY,
                should_acknowledge=True,
                guide_to_field=None,  # No guide_to_field
                include_options=True
            ),
            updated_fields_status={}
        )

        target = collector._determine_target_field(router_output, phase2_fields)
        # Should fallback to get_next_priority_field
        assert target == "from_address"


# ============ Full Flow Integration Tests ============

class TestFullFlowIntegration:
    """Integration tests for complete flow through all phases"""

    @pytest.mark.asyncio
    async def test_packing_to_special_notes_flow(self, collector_agent, phase5_fields):
        """Test that flow goes from packing_service to special_notes correctly"""
        # Setup: floor/elevator done, packing not done
        phase5_fields["from_floor_elevator"] = {
            "floor": 5,
            "has_elevator": True,
            "status": FieldStatus.BASELINE.value
        }
        phase5_fields["to_floor_elevator"] = {
            "status": FieldStatus.SKIPPED.value
        }

        # User selects packing service
        router_output = create_router_output(
            "special_notes",  # Router should guide to special_notes after packing
            {"packing_service": "自己打包"},
            phase=5
        )

        # Mock LLM response
        mock_response = {"content": "好的，自己打包。还有什么特殊需要注意的吗？", "error": None}

        with patch.object(collector_agent.llm_client, 'chat_complete',
                         new_callable=AsyncMock, return_value=mock_response):
            result = await collector_agent.collect(
                router_output=router_output,
                user_message="自己打包",
                fields_status=phase5_fields,
                recent_messages=[]
            )

            # Should guide to special_notes (from Router's guide_to_field)
            assert result.next_field == "special_notes"

    @pytest.mark.asyncio
    async def test_special_notes_done_triggers_confirmation(self, collector_agent, phase5_fields):
        """Test that saying '没有了' for special_notes triggers confirmation"""
        # Setup: all fields complete except special_notes_done
        phase5_fields["from_floor_elevator"] = {
            "floor": 5,
            "has_elevator": True,
            "status": FieldStatus.BASELINE.value
        }
        phase5_fields["to_floor_elevator"] = {
            "status": FieldStatus.SKIPPED.value
        }
        phase5_fields["packing_service"] = "自己打包"
        phase5_fields["packing_service_status"] = FieldStatus.SKIPPED.value
        phase5_fields["special_notes"] = []

        # Router recognizes "没有了" as complete intent
        router_output = RouterOutput(
            intent=Intent(primary=IntentType.COMPLETE, confidence=0.95),
            extracted_fields={
                "special_notes": ExtractedField(
                    field_name="special_notes",
                    raw_value="没有了",
                    parsed_value=["没有了"],
                    needs_verification=False,
                    confidence=0.95
                )
            },
            user_emotion=Emotion.NEUTRAL,
            current_phase=6,
            next_actions=[],
            response_strategy=ResponseStrategy(
                agent_type=AgentType.COLLECTOR,
                style=ResponseStyle.FRIENDLY,
                should_acknowledge=True,
                guide_to_field=None,  # All done
                include_options=False
            ),
            updated_fields_status={}
        )

        mock_response = {"content": "好的，让我确认一下您的搬家信息...", "error": None}

        with patch.object(collector_agent.llm_client, 'chat_complete',
                         new_callable=AsyncMock, return_value=mock_response):
            result = await collector_agent.collect(
                router_output=router_output,
                user_message="没有了",
                fields_status=phase5_fields,
                recent_messages=[]
            )

            # special_notes_done should be True after "没有了"
            assert result.updated_fields.get("special_notes_done") == True
            # Should trigger confirmation
            assert result.needs_confirmation == True


# ============ Edge Case Tests ============

class TestEdgeCases:
    """Test edge cases in flow control"""

    def test_skip_packing_should_still_ask_special_notes(self):
        """When user skips packing, should still ask special_notes"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "value": "東京都",
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value,
            "building_type": "戸建て"  # 戸建て skips floor/elevator
        }
        fields["to_address"] = {
            "value": "大阪市",
            "city": "大阪市",
            "status": FieldStatus.BASELINE.value
        }
        fields["move_date"] = {
            "value": "2026-03-15",
            "year": 2026,
            "month": 3,
            "day": 15,
            "status": FieldStatus.BASELINE.value
        }
        fields["items"] = {
            "list": [{"name": "冷蔵庫"}],
            "status": FieldStatus.BASELINE.value
        }
        fields["to_floor_elevator"] = {
            "status": FieldStatus.SKIPPED.value
        }
        fields["packing_service"] = "不需要"
        fields["packing_service_status"] = FieldStatus.SKIPPED.value

        # Should still need special_notes
        next_field = get_next_priority_field(fields)
        assert next_field == "special_notes"

    def test_kodate_skips_from_floor_elevator(self):
        """戸建て (detached house) should skip from_floor_elevator"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "value": "東京都",
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value,
            "building_type": "戸建て"  # Detached house
        }
        fields["to_address"] = {
            "value": "大阪市",
            "city": "大阪市",
            "status": FieldStatus.BASELINE.value
        }
        fields["move_date"] = {
            "value": "2026-03-15",
            "year": 2026,
            "month": 3,
            "day": 15,
            "status": FieldStatus.BASELINE.value
        }
        fields["items"] = {
            "list": [{"name": "冷蔵庫"}],
            "status": FieldStatus.BASELINE.value
        }

        # 戸建て should skip to to_floor_elevator, not from_floor_elevator
        next_field = get_next_priority_field(fields)
        assert next_field == "to_floor_elevator"

    def test_mansion_requires_from_floor_elevator(self):
        """マンション should require from_floor_elevator"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "value": "東京都",
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value,
            "building_type": "マンション"  # Apartment
        }
        fields["to_address"] = {
            "value": "大阪市",
            "city": "大阪市",
            "status": FieldStatus.BASELINE.value
        }
        fields["move_date"] = {
            "value": "2026-03-15",
            "year": 2026,
            "month": 3,
            "day": 15,
            "status": FieldStatus.BASELINE.value
        }
        fields["items"] = {
            "list": [{"name": "冷蔵庫"}],
            "status": FieldStatus.BASELINE.value
        }

        # マンション should require from_floor_elevator
        next_field = get_next_priority_field(fields)
        assert next_field == "from_floor_elevator"

    def test_completion_info_all_fields(self):
        """Test completion info returns correct missing fields"""
        fields = get_default_fields()

        info = get_completion_info(fields)

        assert info["can_submit"] == False
        assert "people_count" in info["missing_fields"]
        assert "from_address" in info["missing_fields"]
        assert "to_address" in info["missing_fields"]
        assert "move_date" in info["missing_fields"]
        assert "items" in info["missing_fields"]

    def test_completion_requires_special_notes_done(self, phase6_fields):
        """Test that completion requires special_notes_done=True"""
        # Remove special_notes_done
        phase6_fields["special_notes_done"] = False

        info = get_completion_info(phase6_fields)

        assert info["can_submit"] == False
        assert "special_notes" in info["missing_fields"]


# ============ Priority Order Tests ============

class TestPriorityOrder:
    """Test that fields are collected in the correct priority order"""

    def test_priority_1_people_count(self):
        """Priority 1: people_count"""
        fields = get_default_fields()
        assert get_next_priority_field(fields) == "people_count"

    def test_priority_2_from_address(self):
        """Priority 2: from_address"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        assert get_next_priority_field(fields) == "from_address"

    def test_priority_3_to_address(self):
        """Priority 3: to_address"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value
        }
        assert get_next_priority_field(fields) == "to_address"

    def test_priority_4_move_date(self):
        """Priority 4: move_date"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value
        }
        fields["to_address"] = {
            "city": "大阪市",
            "status": FieldStatus.BASELINE.value
        }
        assert get_next_priority_field(fields) == "move_date"

    def test_priority_5_items(self):
        """Priority 5: items"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value
        }
        fields["to_address"] = {
            "city": "大阪市",
            "status": FieldStatus.BASELINE.value
        }
        fields["move_date"] = {
            "day": 15,
            "status": FieldStatus.BASELINE.value
        }
        assert get_next_priority_field(fields) == "items"

    def test_priority_6_from_building_type(self):
        """Priority 6: from_building_type"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value
            # No building_type
        }
        fields["to_address"] = {
            "city": "大阪市",
            "status": FieldStatus.BASELINE.value
        }
        fields["move_date"] = {
            "day": 15,
            "status": FieldStatus.BASELINE.value
        }
        fields["items"] = {
            "list": [{"name": "冷蔵庫"}],
            "status": FieldStatus.BASELINE.value
        }
        assert get_next_priority_field(fields) == "from_building_type"

    def test_priority_9_packing_service(self):
        """Priority 9: packing_service"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value,
            "building_type": "戸建て"
        }
        fields["to_address"] = {
            "city": "大阪市",
            "status": FieldStatus.BASELINE.value
        }
        fields["move_date"] = {
            "day": 15,
            "status": FieldStatus.BASELINE.value
        }
        fields["items"] = {
            "list": [{"name": "冷蔵庫"}],
            "status": FieldStatus.BASELINE.value
        }
        fields["to_floor_elevator"] = {
            "status": FieldStatus.SKIPPED.value
        }
        assert get_next_priority_field(fields) == "packing_service"

    def test_priority_10_special_notes(self):
        """Priority 10: special_notes"""
        fields = get_default_fields()
        fields["people_count"] = 2
        fields["people_count_status"] = FieldStatus.IDEAL.value
        fields["from_address"] = {
            "postal_code": "150-0001",
            "status": FieldStatus.BASELINE.value,
            "building_type": "戸建て"
        }
        fields["to_address"] = {
            "city": "大阪市",
            "status": FieldStatus.BASELINE.value
        }
        fields["move_date"] = {
            "day": 15,
            "status": FieldStatus.BASELINE.value
        }
        fields["items"] = {
            "list": [{"name": "冷蔵庫"}],
            "status": FieldStatus.BASELINE.value
        }
        fields["to_floor_elevator"] = {
            "status": FieldStatus.SKIPPED.value
        }
        fields["packing_service"] = "自己打包"
        fields["packing_service_status"] = FieldStatus.SKIPPED.value
        assert get_next_priority_field(fields) == "special_notes"

    def test_all_complete_returns_none(self, phase6_fields):
        """All fields complete should return None"""
        assert get_next_priority_field(phase6_fields) is None
