"""Tests for field validator service"""

import pytest
from app.services.field_validator import FieldValidator, ValidationResult, get_field_validator


class TestFieldValidatorPeopleCount:
    """Tests for people_count validation"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_valid_integer(self, validator):
        """Test valid integer people count"""
        result = validator.validate_people_count(3)
        assert result.is_valid
        assert result.parsed_value == 3
        assert result.status == "ideal"

    def test_single_person_string(self, validator):
        """Test '单身' is parsed as 1"""
        result = validator.validate_people_count("单身")
        assert result.is_valid
        assert result.parsed_value == 1
        assert result.status == "ideal"

    def test_japanese_single(self, validator):
        """Test '一人暮らし' is parsed as 1"""
        result = validator.validate_people_count("一人暮らし")
        assert result.is_valid
        assert result.parsed_value == 1

    def test_range_string(self, validator):
        """Test range like '2~3人' returns baseline"""
        result = validator.validate_people_count("2~3人")
        assert result.is_valid
        assert result.parsed_value == 2  # Middle value
        assert result.status == "baseline"
        assert result.suggestions  # Should have suggestions

    def test_four_plus(self, validator):
        """Test '4人以上' handling"""
        result = validator.validate_people_count("4人以上")
        assert result.is_valid
        assert result.parsed_value == 4
        assert result.status == "baseline"

    def test_zero_invalid(self, validator):
        """Test zero is invalid"""
        result = validator.validate_people_count(0)
        assert not result.is_valid
        assert result.status == "invalid"

    def test_negative_invalid(self, validator):
        """Test negative is invalid"""
        result = validator.validate_people_count(-1)
        assert not result.is_valid

    def test_none_invalid(self, validator):
        """Test None is invalid"""
        result = validator.validate_people_count(None)
        assert not result.is_valid

    def test_extract_number_from_string(self, validator):
        """Test extracting number from string like '5人'"""
        result = validator.validate_people_count("5人")
        assert result.is_valid
        assert result.parsed_value == 5


class TestFieldValidatorAddress:
    """Tests for address validation"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_from_address_with_postal_code(self, validator):
        """Test from_address with postal code is baseline"""
        result = validator.validate_address(
            "〒150-0001 東京都渋谷区神宮前1-2-3",
            "from"
        )
        assert result.is_valid
        assert result.status == "baseline"
        assert result.parsed_value["postal_code"] is not None

    def test_from_address_without_postal_needs_verification(self, validator):
        """Test from_address without postal code needs verification"""
        result = validator.validate_address(
            "東京都渋谷区神宮前",
            "from"
        )
        assert result.is_valid
        assert result.status == "needs_verification"

    def test_to_address_with_city_is_baseline(self, validator):
        """Test to_address with city is baseline"""
        result = validator.validate_address(
            "大阪府大阪市北区",
            "to"
        )
        assert result.is_valid
        assert result.status == "baseline"
        assert result.parsed_value["prefecture"] is not None

    def test_empty_address_invalid(self, validator):
        """Test empty address is invalid"""
        result = validator.validate_address("", "from")
        assert not result.is_valid

    def test_none_address_invalid(self, validator):
        """Test None address is invalid"""
        result = validator.validate_address(None, "from")
        assert not result.is_valid


class TestFieldValidatorBuildingType:
    """Tests for building type validation"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_valid_mansion(self, validator):
        """Test マンション is valid"""
        result = validator.validate_building_type("マンション")
        assert result.is_valid
        assert result.status == "ideal"

    def test_valid_apartment(self, validator):
        """Test アパート is valid"""
        result = validator.validate_building_type("アパート")
        assert result.is_valid

    def test_valid_house(self, validator):
        """Test 戸建て is valid"""
        result = validator.validate_building_type("戸建て")
        assert result.is_valid

    def test_normalize_house_variant(self, validator):
        """Test 一戸建て is normalized to 戸建て"""
        result = validator.validate_building_type("一戸建て")
        assert result.is_valid
        assert result.parsed_value == "戸建て"

    def test_none_invalid(self, validator):
        """Test None is invalid"""
        result = validator.validate_building_type(None)
        assert not result.is_valid


class TestFieldValidatorMoveDate:
    """Tests for move date validation"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_iso_date(self, validator):
        """Test ISO format date"""
        result = validator.validate_move_date("2026-03-15")
        assert result.is_valid
        assert result.status == "baseline"
        assert result.parsed_value["year"] == 2026
        assert result.parsed_value["month"] == 3
        assert result.parsed_value["day"] == 15

    def test_japanese_date(self, validator):
        """Test Japanese format date"""
        result = validator.validate_move_date("2026年3月15日")
        assert result.is_valid
        assert result.status == "baseline"
        assert result.parsed_value["year"] == 2026

    def test_month_with_period(self, validator):
        """Test month with period (旬)"""
        result = validator.validate_move_date({"value": "3月上旬"})
        assert result.is_valid
        assert result.status == "baseline"
        assert result.parsed_value["month"] == 3
        assert result.parsed_value["period"] == "上旬"

    def test_month_only_needs_verification(self, validator):
        """Test month only needs more info"""
        result = validator.validate_move_date({"value": "3月"})
        assert result.is_valid
        assert result.status == "needs_verification"

    def test_none_invalid(self, validator):
        """Test None is invalid"""
        result = validator.validate_move_date(None)
        assert not result.is_valid


class TestFieldValidatorTimeSlot:
    """Tests for time slot validation"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_morning(self, validator):
        """Test morning time slot"""
        result = validator.validate_time_slot("上午")
        assert result.is_valid
        assert result.parsed_value == "上午"

    def test_afternoon(self, validator):
        """Test afternoon time slot"""
        result = validator.validate_time_slot("下午")
        assert result.is_valid
        assert result.parsed_value == "下午"

    def test_normalize_japanese(self, validator):
        """Test Japanese time slot normalization"""
        result = validator.validate_time_slot("午前")
        assert result.is_valid
        assert result.parsed_value == "上午"

    def test_none_defaults_to_unspecified(self, validator):
        """Test None defaults to unspecified"""
        result = validator.validate_time_slot(None)
        assert result.is_valid
        assert result.parsed_value == "没有指定"


class TestFieldValidatorFloor:
    """Tests for floor validation"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_valid_floor(self, validator):
        """Test valid floor number"""
        result = validator.validate_floor(5)
        assert result.is_valid
        assert result.parsed_value == 5

    def test_floor_from_string(self, validator):
        """Test floor extraction from string"""
        result = validator.validate_floor("5階")
        assert result.is_valid
        assert result.parsed_value == 5

    def test_floor_with_f(self, validator):
        """Test floor extraction from '5F'"""
        result = validator.validate_floor("5F")
        assert result.is_valid
        assert result.parsed_value == 5

    def test_invalid_floor(self, validator):
        """Test invalid floor"""
        result = validator.validate_floor(0)
        assert not result.is_valid


class TestFieldValidatorElevator:
    """Tests for elevator validation"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_has_elevator_boolean(self, validator):
        """Test boolean True"""
        result = validator.validate_elevator(True)
        assert result.is_valid
        assert result.parsed_value is True

    def test_no_elevator_boolean(self, validator):
        """Test boolean False"""
        result = validator.validate_elevator(False)
        assert result.is_valid
        assert result.parsed_value is False

    def test_has_elevator_string(self, validator):
        """Test '有电梯' string"""
        result = validator.validate_elevator("有电梯")
        assert result.is_valid
        assert result.parsed_value is True

    def test_no_elevator_string(self, validator):
        """Test '无电梯' string"""
        result = validator.validate_elevator("无电梯")
        assert result.is_valid
        assert result.parsed_value is False

    def test_japanese_yes(self, validator):
        """Test Japanese 'あり'"""
        result = validator.validate_elevator("あり")
        assert result.is_valid
        assert result.parsed_value is True


class TestFieldValidatorItems:
    """Tests for items validation"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_valid_items_list(self, validator):
        """Test valid items list"""
        items = {
            "list": [
                {"name": "冷蔵庫", "size": "大"},
                {"name": "洗濯機", "size": "中"}
            ]
        }
        result = validator.validate_items(items)
        assert result.is_valid
        assert result.status == "baseline"
        assert result.parsed_value["count"] == 2

    def test_empty_items_invalid(self, validator):
        """Test empty items list is invalid (Red Line R4)"""
        result = validator.validate_items({"list": []})
        assert not result.is_valid
        assert result.status == "invalid"

    def test_none_items_invalid(self, validator):
        """Test None items is invalid"""
        result = validator.validate_items(None)
        assert not result.is_valid


class TestFieldValidatorRequiresFloorInfo:
    """Tests for requires_floor_info"""

    @pytest.fixture
    def validator(self):
        return FieldValidator()

    def test_mansion_requires_floor(self, validator):
        """Test マンション requires floor info"""
        assert validator.requires_floor_info("マンション") is True

    def test_apartment_requires_floor(self, validator):
        """Test アパート requires floor info"""
        assert validator.requires_floor_info("アパート") is True

    def test_house_no_floor_required(self, validator):
        """Test 戸建て doesn't require floor info"""
        assert validator.requires_floor_info("戸建て") is False

    def test_other_no_floor_required(self, validator):
        """Test その他 doesn't require floor info"""
        assert validator.requires_floor_info("その他") is False


class TestGetFieldValidator:
    """Tests for get_field_validator singleton"""

    def test_returns_same_instance(self):
        """Should return same instance"""
        v1 = get_field_validator()
        v2 = get_field_validator()
        assert v1 is v2

    def test_is_field_validator(self):
        """Should return FieldValidator instance"""
        v = get_field_validator()
        assert isinstance(v, FieldValidator)
