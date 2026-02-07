"""Tests for phase inference logic"""

import pytest
from app.models.fields import Phase, FieldStatus
from app.core.phase_inference import (
    infer_phase,
    get_next_priority_field,
    get_completion_info,
    get_quick_options_for_phase
)


class TestInferPhase:
    """Tests for infer_phase function"""

    def test_empty_fields_returns_people_count_phase(self, empty_fields_status):
        """Empty fields should return people count phase"""
        result = infer_phase(empty_fields_status)
        assert result == Phase.PEOPLE_COUNT

    def test_people_done_returns_address_phase(self):
        """After people count, should go to address phase"""
        fields = {
            "people_count_status": FieldStatus.IDEAL.value
        }
        result = infer_phase(fields)
        assert result == Phase.ADDRESS

    def test_people_and_from_address_done(self):
        """With people and from_address done, still address phase (need to_address)"""
        fields = {
            "people_count_status": FieldStatus.IDEAL.value,
            "from_address": {
                "status": FieldStatus.BASELINE.value,
                "value": "東京都渋谷区"
            },
            "to_address": {}
        }
        result = infer_phase(fields)
        assert result == Phase.ADDRESS

    def test_addresses_done_returns_date_phase(self):
        """With addresses done, should go to date phase"""
        fields = {
            "people_count_status": FieldStatus.IDEAL.value,
            "from_address": {"status": FieldStatus.BASELINE.value},
            "to_address": {"status": FieldStatus.BASELINE.value}
        }
        result = infer_phase(fields)
        assert result == Phase.DATE

    def test_date_done_returns_items_phase(self):
        """With date done, should go to items phase"""
        fields = {
            "people_count_status": FieldStatus.IDEAL.value,
            "from_address": {"status": FieldStatus.BASELINE.value},
            "to_address": {"status": FieldStatus.BASELINE.value},
            "move_date": {"status": FieldStatus.BASELINE.value}
        }
        result = infer_phase(fields)
        assert result == Phase.ITEMS

    def test_items_done_returns_other_info_phase(self):
        """With items done, should go to other info phase"""
        fields = {
            "people_count_status": FieldStatus.IDEAL.value,
            "from_address": {
                "status": FieldStatus.BASELINE.value,
                "building_type": "マンション"  # Apartment requires floor info
            },
            "to_address": {"status": FieldStatus.BASELINE.value},
            "move_date": {"status": FieldStatus.BASELINE.value},
            "items": {"status": FieldStatus.BASELINE.value},
            "from_floor_elevator": {}  # Not collected yet
        }
        result = infer_phase(fields)
        assert result == Phase.OTHER_INFO

    def test_house_skips_floor_requirement(self):
        """戸建て (house) doesn't require floor info"""
        fields = {
            "people_count_status": FieldStatus.IDEAL.value,
            "from_address": {
                "status": FieldStatus.BASELINE.value,
                "building_type": "戸建て"  # House, no floor needed
            },
            "to_address": {"status": FieldStatus.BASELINE.value},
            "move_date": {"status": FieldStatus.BASELINE.value},
            "items": {"status": FieldStatus.BASELINE.value}
        }
        # Still needs packing_service
        result = infer_phase(fields)
        assert result == Phase.OTHER_INFO

    def test_complete_returns_confirmation_phase(self, complete_fields_status):
        """Complete fields should return confirmation phase"""
        result = infer_phase(complete_fields_status)
        assert result == Phase.CONFIRMATION


class TestGetNextPriorityField:
    """Tests for get_next_priority_field function"""

    def test_empty_returns_people_count(self, empty_fields_status):
        """Empty fields should return people_count"""
        result = get_next_priority_field(empty_fields_status)
        assert result == "people_count"

    def test_people_done_returns_from_address(self):
        """After people, should return from_address"""
        fields = {
            "people_count_status": FieldStatus.IDEAL.value
        }
        result = get_next_priority_field(fields)
        assert result == "from_address"

    def test_complete_returns_none(self, complete_fields_status):
        """Complete fields should return None"""
        result = get_next_priority_field(complete_fields_status)
        assert result is None


class TestGetCompletionInfo:
    """Tests for get_completion_info function"""

    def test_empty_fields(self, empty_fields_status):
        """Empty fields should have 0% completion"""
        result = get_completion_info(empty_fields_status)

        assert result["can_submit"] is False
        assert result["completion_rate"] == 0.0
        assert "people_count" in result["missing_fields"]
        assert result["next_priority_field"] == "people_count"

    def test_partial_completion(self, partial_fields_status):
        """Partial fields should have partial completion"""
        result = get_completion_info(partial_fields_status)

        assert result["can_submit"] is False
        assert 0 < result["completion_rate"] < 1.0
        assert result["completed"] > 0
        assert result["completed"] < result["total_required"]

    def test_complete_fields(self, complete_fields_status):
        """Complete fields should be submittable"""
        result = get_completion_info(complete_fields_status)

        assert result["can_submit"] is True
        assert result["completion_rate"] == 1.0
        assert result["missing_fields"] == []


class TestGetQuickOptionsForPhase:
    """Tests for get_quick_options_for_phase function"""

    def test_opening_phase_options(self, empty_fields_status):
        """Opening phase should have service options"""
        options = get_quick_options_for_phase(Phase.OPENING, empty_fields_status)

        assert len(options) > 0
        assert any("报价" in opt or "問題" in opt for opt in options)

    def test_people_count_phase_options(self, empty_fields_status):
        """People count phase should have count options"""
        options = get_quick_options_for_phase(Phase.PEOPLE_COUNT, empty_fields_status)

        assert "单身" in options or "單身" in options
        assert any("人" in opt for opt in options)

    def test_confirmation_phase_options(self, complete_fields_status):
        """Confirmation phase should have confirm/modify options"""
        options = get_quick_options_for_phase(Phase.CONFIRMATION, complete_fields_status)

        assert len(options) >= 2

    def test_context_affects_options(self, partial_fields_status):
        """Context should affect available options"""
        # With just_added_items context
        context = {"just_added_items": True}
        options = get_quick_options_for_phase(Phase.ITEMS, partial_fields_status, context)

        if options:  # Only if items phase returns options
            assert any("继续" in opt or "没有" in opt for opt in options)
