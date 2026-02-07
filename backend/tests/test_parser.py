"""Tests for parser utilities"""

import pytest
from app.utils.parser import (
    extract_json_from_text,
    safe_parse_json,
    parse_intent,
    parse_emotion,
    parse_extracted_fields,
    parse_next_actions,
    parse_response_strategy,
    parse_router_output
)


class TestExtractJsonFromText:
    """Tests for extract_json_from_text"""

    def test_pure_json(self):
        """Test extracting pure JSON"""
        text = '{"key": "value"}'
        result = extract_json_from_text(text)
        assert result == '{"key": "value"}'

    def test_json_in_markdown_block(self):
        """Test extracting JSON from markdown code block"""
        text = '''Here is the result:
```json
{"key": "value"}
```
End of response.'''
        result = extract_json_from_text(text)
        assert result == '{"key": "value"}'

    def test_json_in_plain_code_block(self):
        """Test extracting JSON from plain code block"""
        text = '''```
{"key": "value"}
```'''
        result = extract_json_from_text(text)
        assert result == '{"key": "value"}'

    def test_json_with_surrounding_text(self):
        """Test extracting JSON with surrounding text"""
        text = 'The answer is {"key": "value"} as shown.'
        result = extract_json_from_text(text)
        assert result == '{"key": "value"}'

    def test_nested_json(self):
        """Test extracting nested JSON"""
        text = '{"outer": {"inner": "value"}}'
        result = extract_json_from_text(text)
        assert result == '{"outer": {"inner": "value"}}'

    def test_empty_text(self):
        """Test with empty text"""
        assert extract_json_from_text("") is None
        assert extract_json_from_text(None) is None

    def test_invalid_json(self):
        """Test with invalid JSON"""
        text = 'This is not {json at all'
        result = extract_json_from_text(text)
        assert result is None


class TestSafeParseJson:
    """Tests for safe_parse_json"""

    def test_valid_json(self):
        """Test parsing valid JSON"""
        text = '{"name": "test", "value": 123}'
        result = safe_parse_json(text)
        assert result == {"name": "test", "value": 123}

    def test_invalid_json_returns_default(self):
        """Test invalid JSON returns default"""
        text = 'not json'
        result = safe_parse_json(text)
        assert result == {}

    def test_custom_default(self):
        """Test custom default value"""
        text = 'not json'
        result = safe_parse_json(text, {"default": True})
        assert result == {"default": True}


class TestParseIntent:
    """Tests for parse_intent"""

    def test_valid_intent(self):
        """Test parsing valid intent"""
        data = {
            "intent": {
                "primary": "provide_info",
                "secondary": "ask_price",
                "confidence": 0.9
            }
        }
        result = parse_intent(data)
        assert result["primary"] == "provide_info"
        assert result["secondary"] == "ask_price"
        assert result["confidence"] == 0.9

    def test_invalid_primary_intent(self):
        """Test invalid primary intent falls back to provide_info"""
        data = {"intent": {"primary": "invalid_intent"}}
        result = parse_intent(data)
        assert result["primary"] == "provide_info"

    def test_missing_intent(self):
        """Test missing intent uses defaults"""
        data = {}
        result = parse_intent(data)
        assert result["primary"] == "provide_info"
        assert result["secondary"] is None
        assert result["confidence"] == 0.8

    def test_confidence_clamping(self):
        """Test confidence is clamped to [0, 1]"""
        data = {"intent": {"confidence": 1.5}}
        result = parse_intent(data)
        assert result["confidence"] == 1.0

        data = {"intent": {"confidence": -0.5}}
        result = parse_intent(data)
        assert result["confidence"] == 0.0


class TestParseEmotion:
    """Tests for parse_emotion"""

    def test_valid_emotions(self):
        """Test valid emotion strings"""
        assert parse_emotion("neutral") == "neutral"
        assert parse_emotion("positive") == "positive"
        assert parse_emotion("anxious") == "anxious"
        assert parse_emotion("confused") == "confused"
        assert parse_emotion("frustrated") == "frustrated"
        assert parse_emotion("urgent") == "urgent"

    def test_invalid_emotion(self):
        """Test invalid emotion falls back to neutral"""
        assert parse_emotion("happy") == "neutral"
        assert parse_emotion("sad") == "neutral"
        assert parse_emotion("") == "neutral"


class TestParseExtractedFields:
    """Tests for parse_extracted_fields"""

    def test_valid_fields(self):
        """Test parsing valid extracted fields"""
        data = {
            "extracted_fields": {
                "people_count": {
                    "raw_value": "2人",
                    "parsed_value": 2,
                    "needs_verification": False,
                    "confidence": 0.95
                }
            }
        }
        result = parse_extracted_fields(data)
        assert "people_count" in result
        assert result["people_count"]["parsed_value"] == 2
        assert result["people_count"]["confidence"] == 0.95

    def test_invalid_field_name_ignored(self):
        """Test invalid field names are ignored"""
        data = {
            "extracted_fields": {
                "invalid_field": {"raw_value": "test"}
            }
        }
        result = parse_extracted_fields(data)
        assert "invalid_field" not in result

    def test_empty_fields(self):
        """Test empty extracted fields"""
        data = {"extracted_fields": {}}
        result = parse_extracted_fields(data)
        assert result == {}


class TestParseNextActions:
    """Tests for parse_next_actions"""

    def test_valid_actions(self):
        """Test parsing valid actions"""
        data = {
            "next_actions": [
                {
                    "type": "collect_field",
                    "target": "from_address",
                    "priority": 1
                }
            ]
        }
        result = parse_next_actions(data)
        assert len(result) == 1
        assert result[0]["type"] == "collect_field"
        assert result[0]["target"] == "from_address"

    def test_invalid_action_type_ignored(self):
        """Test invalid action types are ignored"""
        data = {
            "next_actions": [
                {"type": "invalid_action", "target": "test"}
            ]
        }
        result = parse_next_actions(data)
        assert len(result) == 0

    def test_empty_actions(self):
        """Test empty actions list"""
        data = {"next_actions": []}
        result = parse_next_actions(data)
        assert result == []


class TestParseResponseStrategy:
    """Tests for parse_response_strategy"""

    def test_valid_strategy(self):
        """Test parsing valid response strategy"""
        data = {
            "response_strategy": {
                "agent_type": "collector",
                "style": "friendly",
                "should_acknowledge": True,
                "guide_to_field": "from_address",
                "include_options": True
            }
        }
        result = parse_response_strategy(data)
        assert result["agent_type"] == "collector"
        assert result["style"] == "friendly"
        assert result["should_acknowledge"] is True

    def test_invalid_agent_type(self):
        """Test invalid agent type falls back to collector"""
        data = {"response_strategy": {"agent_type": "invalid"}}
        result = parse_response_strategy(data)
        assert result["agent_type"] == "collector"

    def test_invalid_style(self):
        """Test invalid style falls back to friendly"""
        data = {"response_strategy": {"style": "rude"}}
        result = parse_response_strategy(data)
        assert result["style"] == "friendly"


class TestParseRouterOutput:
    """Tests for parse_router_output"""

    def test_complete_output(self, sample_router_output_json):
        """Test parsing complete router output"""
        result = parse_router_output(sample_router_output_json)

        assert result["intent"]["primary"] == "provide_info"
        assert result["intent"]["confidence"] == 0.95
        assert result["user_emotion"] == "neutral"
        assert result["current_phase"] == 1
        assert "people_count" in result["extracted_fields"]
        assert len(result["next_actions"]) == 2
        assert result["response_strategy"]["agent_type"] == "collector"

    def test_malformed_json(self):
        """Test handling malformed JSON"""
        text = "not valid json at all"
        result = parse_router_output(text)

        # Should return defaults
        assert result["intent"]["primary"] == "provide_info"
        assert result["user_emotion"] == "neutral"
        assert result["current_phase"] == 0

    def test_partial_output(self):
        """Test handling partial output"""
        text = '{"intent": {"primary": "ask_price"}}'
        result = parse_router_output(text)

        assert result["intent"]["primary"] == "ask_price"
        assert result["user_emotion"] == "neutral"  # default
