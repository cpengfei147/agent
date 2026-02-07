"""Pytest configuration and fixtures"""

import pytest
import asyncio
from typing import Dict, Any

from app.models.fields import FieldStatus, get_default_fields


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def empty_fields_status() -> Dict[str, Any]:
    """Empty fields status fixture"""
    return get_default_fields()


@pytest.fixture
def partial_fields_status() -> Dict[str, Any]:
    """Partially filled fields status"""
    fields = get_default_fields()
    fields["people_count"] = 2
    fields["people_count_status"] = FieldStatus.IDEAL.value
    fields["from_address"] = {
        "value": "東京都渋谷区",
        "status": FieldStatus.BASELINE.value,
        "building_type": "マンション"
    }
    return fields


@pytest.fixture
def complete_fields_status() -> Dict[str, Any]:
    """Complete fields status (can submit)"""
    return {
        "people_count": 2,
        "people_count_status": FieldStatus.IDEAL.value,
        "from_address": {
            "value": "〒150-0001 東京都渋谷区神宮前1-2-3",
            "postal_code": "150-0001",
            "status": FieldStatus.IDEAL.value,
            "building_type": "マンション"
        },
        "to_address": {
            "value": "大阪府大阪市北区梅田1-1-1",
            "status": FieldStatus.BASELINE.value,
            "building_type": "戸建て"
        },
        "move_date": {
            "value": "2026-03-15",
            "time_slot": "上午",
            "status": FieldStatus.IDEAL.value
        },
        "items": {
            "list": [
                {"name": "冷蔵庫", "size": "大"},
                {"name": "洗濯機", "size": "中"}
            ],
            "status": FieldStatus.BASELINE.value
        },
        "from_floor_elevator": {
            "floor": 5,
            "has_elevator": True,
            "status": FieldStatus.BASELINE.value
        },
        "packing_service": "自己打包",
        "special_notes": ["有宜家家具"]
    }


@pytest.fixture
def sample_router_output_json() -> str:
    """Sample router LLM output"""
    return '''{
  "intent": {
    "primary": "provide_info",
    "secondary": null,
    "confidence": 0.95
  },
  "extracted_fields": {
    "people_count": {
      "raw_value": "2个人",
      "parsed_value": 2,
      "needs_verification": false,
      "confidence": 0.98
    }
  },
  "user_emotion": "neutral",
  "current_phase": 1,
  "next_actions": [
    {
      "type": "update_field",
      "target": "people_count",
      "params": {"value": 2},
      "priority": 1
    },
    {
      "type": "collect_field",
      "target": "from_address",
      "priority": 2
    }
  ],
  "response_strategy": {
    "agent_type": "collector",
    "style": "friendly",
    "should_acknowledge": true,
    "guide_to_field": "from_address",
    "include_options": false
  }
}'''


@pytest.fixture
def sample_messages() -> list:
    """Sample conversation history"""
    return [
        {"role": "assistant", "content": "你好！我是 ERABU，你的搬家顾问。"},
        {"role": "user", "content": "我想搬家"},
        {"role": "assistant", "content": "好的，请问是几个人搬家呢？"}
    ]
