"""Collector Agent - 信息收集专家"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass

from app.core import get_llm_client
from app.models.fields import FieldStatus, Phase
from app.models.schemas import RouterOutput, AgentType
from app.services.field_validator import get_field_validator, ValidationResult
from app.services.address_service import get_address_service
from app.agents.prompts.collector_prompt import (
    build_collector_prompt,
    build_confirmation_prompt,
    get_field_collection_prompt,
    FIELD_COLLECTION_PROMPTS
)

logger = logging.getLogger(__name__)


@dataclass
class CollectorResponse:
    """Collector agent response"""
    text: str
    updated_fields: Dict[str, Any]
    validation_results: Dict[str, ValidationResult]
    next_field: Optional[str] = None
    sub_task: Optional[str] = None
    quick_options: List[str] = None
    needs_confirmation: bool = False

    def __post_init__(self):
        if self.quick_options is None:
            self.quick_options = []


class CollectorAgent:
    """Collector Agent for field collection and validation"""

    def __init__(self):
        self.llm_client = get_llm_client()
        self.field_validator = get_field_validator()
        self.address_service = get_address_service()

    async def collect(
        self,
        router_output: RouterOutput,
        user_message: str,
        fields_status: Dict[str, Any],
        recent_messages: List[Dict[str, Any]] = None
    ) -> CollectorResponse:
        """
        Process collection based on router output

        Args:
            router_output: Router's analysis result
            user_message: User's message
            fields_status: Current fields status
            recent_messages: Recent conversation history

        Returns:
            CollectorResponse with text and updated fields
        """
        recent_messages = recent_messages or []

        # Determine target field
        target_field = self._determine_target_field(router_output, fields_status)

        # Validate and update extracted fields
        updated_fields = fields_status.copy()
        validation_results = {}

        for field_name, extracted in router_output.extracted_fields.items():
            result = await self._validate_field(field_name, extracted.parsed_value, updated_fields)
            validation_results[field_name] = result

            if result.is_valid:
                updated_fields = self._update_field(updated_fields, field_name, result)

        # Determine sub-task and next action
        sub_task = self._determine_sub_task(target_field, updated_fields, validation_results)

        # Check if we need to collect more info for current field
        needs_more_info = self._needs_more_info(target_field, updated_fields, sub_task)

        # Determine next field to collect
        if needs_more_info:
            next_field = target_field
        else:
            next_field = self._get_next_field(updated_fields)

        # Check if ready for confirmation
        needs_confirmation = self._check_completion(updated_fields)

        # Generate response
        style = router_output.response_strategy.style.value
        should_acknowledge = router_output.response_strategy.should_acknowledge

        response_text = await self._generate_response(
            target_field=next_field or target_field,
            fields_status=updated_fields,
            recent_messages=recent_messages,
            style=style,
            sub_task=sub_task,
            validation_results=validation_results,
            should_acknowledge=should_acknowledge,
            needs_confirmation=needs_confirmation
        )

        # Get quick options
        quick_options = self._get_quick_options(next_field, sub_task, updated_fields)

        return CollectorResponse(
            text=response_text,
            updated_fields=updated_fields,
            validation_results=validation_results,
            next_field=next_field,
            sub_task=sub_task,
            quick_options=quick_options,
            needs_confirmation=needs_confirmation
        )

    async def stream_collect(
        self,
        router_output: RouterOutput,
        user_message: str,
        fields_status: Dict[str, Any],
        recent_messages: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream collection response

        Yields:
            Dict with type and content (text_delta, validation, metadata, done)
        """
        recent_messages = recent_messages or []

        # Determine target field
        target_field = self._determine_target_field(router_output, fields_status)

        # Validate and update extracted fields
        updated_fields = fields_status.copy()
        validation_results = {}

        for field_name, extracted in router_output.extracted_fields.items():
            result = await self._validate_field(field_name, extracted.parsed_value, updated_fields)
            validation_results[field_name] = result

            if result.is_valid:
                updated_fields = self._update_field(updated_fields, field_name, result)

                # Yield validation result
                yield {
                    "type": "validation",
                    "field": field_name,
                    "status": result.status,
                    "message": result.message
                }

        # Determine sub-task and next action
        # First check if any validated field needs verification - override target_field
        for field_name, result in validation_results.items():
            if result.status == "needs_verification":
                target_field = field_name  # Override to the field that needs follow-up
                logger.info(f"Field {field_name} needs verification, overriding target_field")
                break

        # Check if to_address is a major city without district - should ask for more detail
        if "to_address" in validation_results and validation_results["to_address"].status == "baseline":
            to_addr = updated_fields.get("to_address", {})
            if isinstance(to_addr, dict):
                city = to_addr.get("city", "")
                major_cities = ["福岡市", "大阪市", "名古屋市", "横浜市", "札幌市", "神戸市",
                               "京都市", "広島市", "仙台市", "北九州市", "千葉市", "さいたま市",
                               "川崎市", "堺市", "新潟市", "浜松市", "熊本市", "相模原市", "岡山市", "静岡市"]
                if city in major_cities and not to_addr.get("district"):
                    target_field = "to_address"  # Stay on to_address to ask for district
                    logger.info(f"Major city {city} without district, staying on to_address")

        sub_task = self._determine_sub_task(target_field, updated_fields, validation_results)
        needs_more_info = self._needs_more_info(target_field, updated_fields, sub_task)

        if needs_more_info:
            next_field = target_field
        else:
            next_field = self._get_next_field(updated_fields)

        # Double-check: if sub_task indicates follow-up needed, ensure next_field matches
        if sub_task in ["ask_postal", "ask_city", "ask_specific", "ask_period"]:
            field_map = {
                "ask_postal": "from_address",
                "ask_city": "to_address",
                "ask_specific": "move_date",
                "ask_period": "move_date"
            }
            next_field = field_map.get(sub_task, next_field)
            logger.info(f"Sub-task {sub_task} requires next_field={next_field}")

        needs_confirmation = self._check_completion(updated_fields)

        # Build prompt
        style = router_output.response_strategy.style.value
        should_acknowledge = router_output.response_strategy.should_acknowledge

        if needs_confirmation:
            system_prompt = build_confirmation_prompt(updated_fields)
        else:
            system_prompt = build_collector_prompt(
                target_field=next_field or target_field,
                fields_status=updated_fields,
                recent_messages=recent_messages,
                style=style,
                sub_task=sub_task
            )

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add conversation history
        for msg in recent_messages[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        messages.append({
            "role": "user",
            "content": user_message
        })

        # Stream LLM response
        async for chunk in self.llm_client.chat(messages, stream=True):
            if chunk["type"] == "text_delta":
                yield {
                    "type": "text_delta",
                    "content": chunk["content"]
                }
            elif chunk["type"] == "done":
                yield {"type": "text_done"}
            elif chunk["type"] == "error":
                yield {
                    "type": "error",
                    "error": chunk.get("error", "Unknown error")
                }
                return

        # Get quick options from hardcoded logic
        quick_options = self._get_quick_options(next_field, sub_task, updated_fields)

        yield {
            "type": "metadata",
            "updated_fields": updated_fields,
            "next_field": next_field,
            "sub_task": sub_task,
            "quick_options": quick_options,
            "needs_confirmation": needs_confirmation,
            "validation_results": {
                k: {"status": v.status, "message": v.message}
                for k, v in validation_results.items()
            }
        }

    def _determine_target_field(
        self,
        router_output: RouterOutput,
        fields_status: Dict[str, Any]
    ) -> str:
        """Determine which field to target"""
        # First priority: Check if any extracted field needs verification
        # This ensures we follow up on incomplete fields before moving on
        for field_name, extracted in router_output.extracted_fields.items():
            if extracted.needs_verification:
                return field_name

        # Check router's guide_to_field
        if router_output.response_strategy.guide_to_field:
            return router_output.response_strategy.guide_to_field

        # Check next_actions
        for action in router_output.next_actions:
            if action.type.value in ["collect_field", "update_field"]:
                if action.target:
                    return action.target

        # Fall back to priority order
        return self._get_next_field(fields_status) or "people_count"

    def _get_next_field(self, fields_status: Dict[str, Any]) -> Optional[str]:
        """Get next field to collect based on priority"""
        from app.core.phase_inference import get_next_priority_field
        return get_next_priority_field(fields_status)

    async def _validate_field(
        self,
        field_name: str,
        value: Any,
        fields_status: Dict[str, Any]
    ) -> ValidationResult:
        """Validate a field value"""
        validator = self.field_validator

        if field_name == "people_count":
            return validator.validate_people_count(value)

        elif field_name in ["from_address", "to_address"]:
            address_type = "from" if field_name == "from_address" else "to"

            # First do basic validation
            result = validator.validate_address(value, address_type)

            # If we have API, enhance with address service
            if result.is_valid and isinstance(value, (str, dict)):
                addr_str = value if isinstance(value, str) else value.get("value", "")
                if addr_str:
                    try:
                        verified = await self.address_service.verify_address(addr_str)
                        if verified.is_valid:
                            # Update parsed value with verified info
                            result.parsed_value = {
                                "value": verified.formatted_address or addr_str,
                                "postal_code": verified.postal_code,
                                "prefecture": verified.prefecture,
                                "city": verified.city,
                                "district": verified.district
                            }
                            if verified.postal_code and address_type == "from":
                                result.status = "baseline"
                            elif verified.city and address_type == "to":
                                result.status = "baseline"
                    except Exception as e:
                        logger.warning(f"Address verification failed: {e}")

            return result

        elif field_name in ["from_building_type", "to_building_type"]:
            return validator.validate_building_type(value)

        elif field_name == "move_date":
            return validator.validate_move_date(value)

        elif field_name == "move_time_slot":
            return validator.validate_time_slot(value)

        elif field_name in ["from_floor", "to_floor"]:
            return validator.validate_floor(value)

        elif field_name in ["from_has_elevator", "to_has_elevator"]:
            return validator.validate_elevator(value)

        elif field_name == "packing_service":
            return validator.validate_packing_service(value)

        elif field_name == "items":
            return validator.validate_items(value)

        elif field_name == "special_notes":
            # Special notes don't need validation
            return ValidationResult(
                is_valid=True,
                parsed_value=value if isinstance(value, list) else [value],
                status="ideal"
            )

        # Default: accept as-is
        return ValidationResult(
            is_valid=True,
            parsed_value=value,
            status="baseline"
        )

    def _update_field(
        self,
        fields_status: Dict[str, Any],
        field_name: str,
        validation_result: ValidationResult
    ) -> Dict[str, Any]:
        """Update fields status with validated value"""
        updated = fields_status.copy()
        value = validation_result.parsed_value
        status = validation_result.status

        # Map status string to FieldStatus
        status_map = {
            "baseline": FieldStatus.BASELINE.value,
            "ideal": FieldStatus.IDEAL.value,
            "needs_verification": FieldStatus.IN_PROGRESS.value,
            "invalid": FieldStatus.NOT_COLLECTED.value
        }
        field_status = status_map.get(status, FieldStatus.IN_PROGRESS.value)

        if field_name == "people_count":
            updated["people_count"] = value
            updated["people_count_status"] = field_status

        elif field_name == "from_address":
            if "from_address" not in updated or not isinstance(updated["from_address"], dict):
                updated["from_address"] = {}
            if isinstance(value, dict):
                # Merge only non-empty values to avoid overwriting existing data
                for k, v in value.items():
                    if v is not None and v != "":
                        # Special case: don't overwrite existing address value with just postal code
                        if k == "value" and updated["from_address"].get("value") and len(str(v)) < 10:
                            continue
                        updated["from_address"][k] = v
            else:
                if value:
                    updated["from_address"]["value"] = value
            # R1: Force baseline status if postal_code is present
            if updated["from_address"].get("postal_code"):
                updated["from_address"]["status"] = FieldStatus.BASELINE.value
            else:
                updated["from_address"]["status"] = field_status

        elif field_name == "to_address":
            if "to_address" not in updated or not isinstance(updated["to_address"], dict):
                updated["to_address"] = {}
            if isinstance(value, dict):
                # Smart merge for to_address - combine city and district
                existing_value = updated["to_address"].get("value", "")
                existing_city = updated["to_address"].get("city", "")

                new_value = value.get("value", "")
                new_city = value.get("city", "")
                new_district = value.get("district", "")

                # Merge city
                if new_city:
                    updated["to_address"]["city"] = new_city

                # Merge district
                if new_district:
                    updated["to_address"]["district"] = new_district

                # Smart merge value: combine existing city with new district
                if existing_city and new_district and new_district not in existing_value:
                    # User added district to existing city
                    updated["to_address"]["value"] = existing_city + new_district
                elif new_value and existing_value and len(new_value) < len(existing_value):
                    # New value is shorter (just district), keep existing and add district
                    if new_value not in existing_value:
                        updated["to_address"]["value"] = existing_value + new_value
                elif new_value:
                    updated["to_address"]["value"] = new_value

                # Copy other fields
                for k, v in value.items():
                    if k not in ["value", "city", "district"] and v is not None and v != "":
                        updated["to_address"][k] = v
            else:
                if value:
                    # Check if it's just a district being added
                    existing_value = updated["to_address"].get("value", "")
                    if existing_value and "区" in str(value) and str(value) not in existing_value:
                        updated["to_address"]["value"] = existing_value + str(value)
                    else:
                        updated["to_address"]["value"] = value
            updated["to_address"]["status"] = field_status

        elif field_name == "from_building_type":
            if "from_address" not in updated or not isinstance(updated["from_address"], dict):
                updated["from_address"] = {}
            updated["from_address"]["building_type"] = value

        elif field_name == "to_building_type":
            if "to_address" not in updated or not isinstance(updated["to_address"], dict):
                updated["to_address"] = {}
            updated["to_address"]["building_type"] = value

        elif field_name == "move_date":
            if "move_date" not in updated or not isinstance(updated["move_date"], dict):
                updated["move_date"] = {}
            if isinstance(value, dict):
                updated["move_date"].update(value)
            else:
                updated["move_date"]["value"] = value
            updated["move_date"]["status"] = field_status

        elif field_name == "move_time_slot":
            if "move_date" not in updated or not isinstance(updated["move_date"], dict):
                updated["move_date"] = {}
            updated["move_date"]["time_slot"] = value

        elif field_name == "from_floor":
            if "from_floor_elevator" not in updated or not isinstance(updated["from_floor_elevator"], dict):
                updated["from_floor_elevator"] = {}
            updated["from_floor_elevator"]["floor"] = value

        elif field_name == "from_has_elevator":
            if "from_floor_elevator" not in updated or not isinstance(updated["from_floor_elevator"], dict):
                updated["from_floor_elevator"] = {}
            updated["from_floor_elevator"]["has_elevator"] = value
            updated["from_floor_elevator"]["status"] = field_status

        elif field_name == "packing_service":
            updated["packing_service"] = value

        elif field_name == "items":
            if "items" not in updated or not isinstance(updated["items"], dict):
                updated["items"] = {"list": []}
            if isinstance(value, dict):
                if "list" in value:
                    updated["items"]["list"] = value["list"]
                updated["items"]["status"] = field_status
            elif isinstance(value, list):
                updated["items"]["list"] = value
                updated["items"]["status"] = field_status

        elif field_name == "special_notes":
            if "special_notes" not in updated:
                updated["special_notes"] = []
            if isinstance(value, list):
                updated["special_notes"].extend(value)
            else:
                updated["special_notes"].append(value)
            # Remove duplicates while preserving order
            updated["special_notes"] = list(dict.fromkeys(updated["special_notes"]))

        return updated

    def _determine_sub_task(
        self,
        target_field: str,
        fields_status: Dict[str, Any],
        validation_results: Dict[str, ValidationResult]
    ) -> Optional[str]:
        """Determine sub-task based on current state"""

        # Check if any field needs verification
        for field_name, result in validation_results.items():
            if result.status == "needs_verification":
                if field_name == "from_address":
                    return "ask_postal"
                elif field_name == "to_address":
                    return "ask_city"
                elif field_name == "move_date":
                    return "ask_specific"

        # Check field-specific sub-tasks
        if target_field == "from_address":
            from_addr = fields_status.get("from_address", {})
            if isinstance(from_addr, dict):
                if from_addr.get("value") and not from_addr.get("postal_code"):
                    return "ask_postal"
                if from_addr.get("status") in ["baseline", "ideal"] and not from_addr.get("building_type"):
                    return "ask_building_type"

        elif target_field == "to_address":
            to_addr = fields_status.get("to_address", {})
            if isinstance(to_addr, dict):
                status = to_addr.get("status", "not_collected")
                # If baseline but not ideal, encourage more detail (optional)
                if status == "baseline" and not to_addr.get("district"):
                    city = to_addr.get("city", "")
                    # Only ask for detail if it's a major city that has districts
                    major_cities = ["福岡市", "大阪市", "名古屋市", "横浜市", "札幌市", "神戸市",
                                   "京都市", "広島市", "仙台市", "北九州市", "千葉市", "さいたま市",
                                   "川崎市", "堺市", "新潟市", "浜松市", "熊本市", "相模原市", "岡山市", "静岡市"]
                    if city in major_cities:
                        return "ask_district_optional"

        elif target_field == "move_date":
            move_date = fields_status.get("move_date", {})
            if isinstance(move_date, dict):
                # Check if we have month but missing day/period (R3 requirement)
                has_month = move_date.get("month") is not None
                has_day_or_period = move_date.get("day") is not None or move_date.get("period") is not None

                if has_month and not has_day_or_period:
                    return "ask_period"  # Need to ask for 旬 or specific date

                # If date is complete, ask for time slot
                if move_date.get("value") and has_day_or_period and not move_date.get("time_slot"):
                    return "ask_time_slot"

        elif target_field == "items":
            items = fields_status.get("items", {})
            if isinstance(items, dict):
                item_list = items.get("list", [])
                status = items.get("status", "not_collected")

                if status == "not_collected" and not item_list:
                    # Items not started - will show item_evaluation UI
                    return None
                elif status == "in_progress" and item_list:
                    # Some items added, ask if more
                    return "ask_more_items"
                elif status == "in_progress" and not item_list:
                    # In progress but no items yet
                    return None

        elif target_field == "from_floor_elevator":
            floor_info = fields_status.get("from_floor_elevator", {})
            if isinstance(floor_info, dict):
                if floor_info.get("floor") and floor_info.get("has_elevator") is None:
                    return "ask_elevator"
                if floor_info.get("has_elevator") is not None and not floor_info.get("floor"):
                    return "ask_floor"

        return None

    def _needs_more_info(
        self,
        target_field: str,
        fields_status: Dict[str, Any],
        sub_task: Optional[str]
    ) -> bool:
        """Check if we need more info for current field"""
        if sub_task:
            return True

        # Statuses that indicate more info is needed
        incomplete_statuses = ["not_collected", "in_progress", "needs_verification"]

        # Field-specific checks
        if target_field == "from_address":
            from_addr = fields_status.get("from_address", {})
            if isinstance(from_addr, dict):
                status = from_addr.get("status", "not_collected")
                if status in incomplete_statuses:
                    return True
                # Check if postal code is missing (needs_verification case)
                if not from_addr.get("postal_code"):
                    return True
                # Check if building type is needed
                if not from_addr.get("building_type"):
                    return True

        elif target_field == "to_address":
            to_addr = fields_status.get("to_address", {})
            if isinstance(to_addr, dict):
                status = to_addr.get("status", "not_collected")
                if status in incomplete_statuses:
                    return True
                # Check if it's a major city without district - ask for more detail (optional)
                if status == "baseline" and not to_addr.get("district"):
                    city = to_addr.get("city", "")
                    major_cities = ["福岡市", "大阪市", "名古屋市", "横浜市", "札幌市", "神戸市",
                                   "京都市", "広島市", "仙台市", "北九州市", "千葉市", "さいたま市",
                                   "川崎市", "堺市", "新潟市", "浜松市", "熊本市", "相模原市", "岡山市", "静岡市"]
                    if city in major_cities:
                        return True  # Need to ask for district detail

        elif target_field == "move_date":
            move_date = fields_status.get("move_date", {})
            if isinstance(move_date, dict):
                status = move_date.get("status", "not_collected")
                if status in incomplete_statuses:
                    return True

        return False

    def _check_completion(self, fields_status: Dict[str, Any]) -> bool:
        """Check if all required fields are complete"""
        from app.core.phase_inference import get_completion_info
        info = get_completion_info(fields_status)
        return info["can_submit"]

    async def _generate_response(
        self,
        target_field: str,
        fields_status: Dict[str, Any],
        recent_messages: List[Dict[str, Any]],
        style: str,
        sub_task: Optional[str],
        validation_results: Dict[str, ValidationResult],
        should_acknowledge: bool,
        needs_confirmation: bool
    ) -> str:
        """Generate response text using LLM"""

        if needs_confirmation:
            system_prompt = build_confirmation_prompt(fields_status)
        else:
            system_prompt = build_collector_prompt(
                target_field=target_field,
                fields_status=fields_status,
                recent_messages=recent_messages,
                style=style,
                sub_task=sub_task
            )

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add recent messages
        for msg in recent_messages[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Add context about validation
        context_parts = []
        if should_acknowledge and validation_results:
            for field_name, result in validation_results.items():
                if result.is_valid and result.message:
                    context_parts.append(f"[已确认: {result.message}]")

        if context_parts:
            messages.append({
                "role": "user",
                "content": "\n".join(context_parts) + "\n请继续对话。"
            })
        else:
            messages.append({
                "role": "user",
                "content": "请继续对话。"
            })

        # Call LLM
        response = await self.llm_client.chat_complete(messages=messages)

        if response.get("error"):
            logger.error(f"LLM error: {response['error']}")
            return self._get_fallback_response(target_field, sub_task)

        return response.get("content", self._get_fallback_response(target_field, sub_task))

    def _get_fallback_response(self, target_field: str, sub_task: Optional[str]) -> str:
        """Get fallback response when LLM fails"""
        prompts = get_field_collection_prompt(target_field)

        if sub_task and sub_task.startswith("ask_"):
            key = sub_task
            if key in prompts:
                return prompts[key]

        if "ask" in prompts:
            return prompts["ask"]

        return "请告诉我更多信息。"

    def _get_quick_options(
        self,
        target_field: Optional[str],
        sub_task: Optional[str],
        fields_status: Dict[str, Any]
    ) -> List[str]:
        """Get quick options for the current state"""
        if not target_field:
            return []

        prompts = get_field_collection_prompt(target_field)

        # Check for sub-task specific options
        if sub_task == "ask_building_type" and "building_options" in prompts:
            return prompts["building_options"]
        elif sub_task == "ask_period" and "period_options" in prompts:
            return prompts["period_options"]
        elif sub_task == "ask_time_slot" and "time_options" in prompts:
            return prompts["time_options"]
        elif sub_task == "ask_elevator" and "elevator_options" in prompts:
            return prompts["elevator_options"]
        elif sub_task == "ask_more_items" and "more_options" in prompts:
            return prompts["more_options"]
        elif sub_task == "ask_district_optional":
            # Provide common districts for major cities
            to_addr = fields_status.get("to_address", {})
            city = to_addr.get("city", "") if isinstance(to_addr, dict) else ""
            district_options = {
                "大阪市": ["北区", "中央区", "西区", "天王寺区", "不确定・继续"],
                "名古屋市": ["中区", "東区", "名東区", "千種区", "不确定・继续"],
                "横浜市": ["西区", "中区", "神奈川区", "港北区", "不确定・继续"],
                "札幌市": ["中央区", "北区", "東区", "白石区", "不确定・继续"],
                "福岡市": ["博多区", "中央区", "早良区", "東区", "不确定・继续"],
                "神戸市": ["中央区", "東灘区", "灘区", "兵庫区", "不确定・继续"],
                "京都市": ["中京区", "下京区", "東山区", "左京区", "不确定・继续"],
            }
            return district_options.get(city, ["具体告诉我", "不确定・继续"])

        # Check for field-specific options
        if target_field == "items":
            items = fields_status.get("items", {})
            if isinstance(items, dict):
                item_list = items.get("list", [])
                if item_list:
                    # Items already added, show more options
                    return prompts.get("more_options", ["Add more items", "No more items"])
                else:
                    # No items yet, show initial options
                    return prompts.get("options", ["Upload room photo", "Enter items directly", "Select from catalog"])

        if "options" in prompts:
            options = prompts["options"]

            # Filter out already selected special notes
            if target_field == "special_notes":
                selected = fields_status.get("special_notes", [])
                options = [opt for opt in options if opt not in selected]

            return options

        if "ask_options" in prompts:
            return prompts["ask_options"]

        return []


# Global collector agent instance
_collector_agent: Optional[CollectorAgent] = None


def get_collector_agent() -> CollectorAgent:
    """Get global collector agent instance"""
    global _collector_agent
    if _collector_agent is None:
        _collector_agent = CollectorAgent()
    return _collector_agent
