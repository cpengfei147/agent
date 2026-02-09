"""Router Agent - 意图识别、信息提取、策略决策"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.core import get_llm_client
from app.models.schemas import (
    RouterOutput, Intent, IntentType, ExtractedField,
    Emotion, Action, ActionType, ResponseStrategy,
    AgentType, ResponseStyle
)
from app.models.fields import FieldStatus, Phase
from app.agents.prompts.router_prompt import (
    ROUTER_SYSTEM_PROMPT,
    format_recent_messages,
    format_fields_status
)

logger = logging.getLogger(__name__)


class RouterAgent:
    """Router Agent for intent recognition and decision making"""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def analyze(
        self,
        user_message: str,
        fields_status: Dict[str, Any],
        recent_messages: List[Dict[str, Any]] = None
    ) -> RouterOutput:
        """
        Analyze user message and return routing decision

        Args:
            user_message: User's input message
            fields_status: Current fields collection status
            recent_messages: Recent conversation history

        Returns:
            RouterOutput with intent, extracted fields, and strategy
        """
        try:
            # Build prompt
            system_prompt = ROUTER_SYSTEM_PROMPT.format(
                current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
                fields_status=format_fields_status(fields_status),
                recent_messages=format_recent_messages(recent_messages or [])
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]

            # Call LLM with JSON mode and Langfuse tracing
            response = await self.llm_client.chat_complete(
                messages=messages,
                response_format={"type": "json_object"},
                trace_name="router_analyze",
                trace_metadata={
                    "user_message": user_message[:100],
                    "fields_collected": len([k for k, v in fields_status.items()
                                            if isinstance(v, dict) and v.get("status") in ["baseline", "ideal"]])
                }
            )

            if response.get("error"):
                logger.error(f"LLM error: {response['error']}")
                return self._get_fallback_output(user_message, fields_status)

            # Parse response
            content = response.get("content", "{}")
            logger.debug(f"Router LLM response content: {content[:500]}")
            return self._parse_response(content, fields_status)

        except Exception as e:
            logger.error(f"Router analysis error: {e}")
            return self._get_fallback_output(user_message, fields_status)

    def _parse_response(self, content: str, fields_status: Dict[str, Any]) -> RouterOutput:
        """Parse LLM response into RouterOutput"""
        try:
            # Clean markdown code blocks if present
            cleaned_content = content.strip()
            if cleaned_content.startswith("```"):
                # Remove markdown code block markers
                lines = cleaned_content.split("\n")
                # Remove first line (```json or ```)
                if lines[0].startswith("```"):
                    lines = lines[1:]
                # Remove last line if it's ```)
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_content = "\n".join(lines)

            data = json.loads(cleaned_content)

            # Parse intent
            intent_data = data.get("intent", {})
            # Handle secondary intent - could be None, null string, or valid intent
            secondary_value = intent_data.get("secondary")
            secondary_intent = None
            if secondary_value and secondary_value != "null" and secondary_value != "None":
                try:
                    secondary_intent = IntentType(secondary_value)
                except ValueError:
                    logger.warning(f"Unknown secondary intent type: {secondary_value}")
                    secondary_intent = None

            intent = Intent(
                primary=IntentType(intent_data.get("primary", "provide_info")),
                secondary=secondary_intent,
                confidence=float(intent_data.get("confidence", 0.8))
            )

            # Parse extracted fields
            extracted_fields = {}
            for field_name, field_data in data.get("extracted_fields", {}).items():
                extracted_fields[field_name] = ExtractedField(
                    field_name=field_name,
                    raw_value=str(field_data.get("raw_value", "")),
                    parsed_value=field_data.get("parsed_value"),
                    needs_verification=field_data.get("needs_verification", False),
                    confidence=float(field_data.get("confidence", 0.8))
                )

            # Parse emotion
            emotion_str = data.get("user_emotion", "neutral")
            try:
                emotion = Emotion(emotion_str)
            except ValueError:
                emotion = Emotion.NEUTRAL

            # Parse current phase
            current_phase = int(data.get("current_phase", 0))

            # Parse next actions
            next_actions = []
            for action_data in data.get("next_actions", []):
                try:
                    action_type = ActionType(action_data.get("type", "collect_field"))
                    next_actions.append(Action(
                        type=action_type,
                        target=action_data.get("target"),
                        params=action_data.get("params"),
                        priority=int(action_data.get("priority", 1))
                    ))
                except ValueError:
                    continue

            # Parse response strategy
            strategy_data = data.get("response_strategy", {})
            try:
                agent_type = AgentType(strategy_data.get("agent_type", "collector"))
            except ValueError:
                agent_type = AgentType.COLLECTOR

            try:
                style = ResponseStyle(strategy_data.get("style", "friendly"))
            except ValueError:
                style = ResponseStyle.FRIENDLY

            response_strategy = ResponseStrategy(
                agent_type=agent_type,
                style=style,
                should_acknowledge=strategy_data.get("should_acknowledge", True),
                guide_to_field=strategy_data.get("guide_to_field"),
                include_options=strategy_data.get("include_options", True)
            )

            # Build updated fields status
            updated_fields_status = self._update_fields_status(
                fields_status,
                extracted_fields
            )

            return RouterOutput(
                intent=intent,
                extracted_fields=extracted_fields,
                user_emotion=emotion,
                current_phase=current_phase,
                next_actions=next_actions,
                response_strategy=response_strategy,
                updated_fields_status=updated_fields_status
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Content that failed to parse: {cleaned_content[:500]}")
            return self._get_fallback_output("", fields_status)
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return self._get_fallback_output("", fields_status)

    def _update_fields_status(
        self,
        current_status: Dict[str, Any],
        extracted_fields: Dict[str, ExtractedField]
    ) -> Dict[str, Any]:
        """Update fields status with extracted fields"""
        updated = current_status.copy()

        for field_name, extracted in extracted_fields.items():
            if extracted.parsed_value is not None:
                # Map field names to status structure
                if field_name == "people_count":
                    updated["people_count"] = extracted.parsed_value
                    updated["people_count_status"] = FieldStatus.IDEAL.value

                elif field_name == "from_address":
                    if "from_address" not in updated or not isinstance(updated["from_address"], dict):
                        updated["from_address"] = {}
                    # Handle parsed_value as dict with value and postal_code
                    if isinstance(extracted.parsed_value, dict):
                        # Merge: only update value if new value is provided
                        new_value = extracted.parsed_value.get("value", "")
                        if new_value:
                            updated["from_address"]["value"] = new_value
                        # Merge postal_code
                        if extracted.parsed_value.get("postal_code"):
                            updated["from_address"]["postal_code"] = extracted.parsed_value["postal_code"]
                        # R1: from_address 只有在有 postal_code 时才能标记为 baseline
                        if updated["from_address"].get("postal_code"):
                            updated["from_address"]["status"] = FieldStatus.BASELINE.value
                        else:
                            updated["from_address"]["status"] = FieldStatus.IN_PROGRESS.value
                    else:
                        # Simple value - only update if not empty
                        if extracted.parsed_value:
                            updated["from_address"]["value"] = extracted.parsed_value
                        if extracted.needs_verification:
                            updated["from_address"]["status"] = FieldStatus.IN_PROGRESS.value
                        else:
                            updated["from_address"]["status"] = FieldStatus.BASELINE.value

                elif field_name == "to_address":
                    if "to_address" not in updated or not isinstance(updated["to_address"], dict):
                        updated["to_address"] = {}
                    # Handle parsed_value as dict with value and city - smart merge
                    if isinstance(extracted.parsed_value, dict):
                        existing_value = updated["to_address"].get("value", "")
                        existing_city = updated["to_address"].get("city", "")

                        new_value = extracted.parsed_value.get("value", "")
                        new_city = extracted.parsed_value.get("city", "")
                        new_district = extracted.parsed_value.get("district", "")

                        # Merge city (keep existing if new is empty)
                        if new_city:
                            updated["to_address"]["city"] = new_city
                        elif existing_city:
                            updated["to_address"]["city"] = existing_city

                        # Merge district
                        if new_district:
                            updated["to_address"]["district"] = new_district

                        # Smart merge value: combine existing city with new district
                        if existing_city and new_district and new_district not in existing_value:
                            updated["to_address"]["value"] = existing_city + new_district
                        elif new_value and existing_value and len(new_value) < len(existing_value):
                            if new_value not in existing_value:
                                updated["to_address"]["value"] = existing_value + new_value
                        elif new_value:
                            updated["to_address"]["value"] = new_value
                        elif existing_value:
                            updated["to_address"]["value"] = existing_value

                        # R2: to_address 需要 city 才能标记为 baseline
                        if updated["to_address"].get("city"):
                            updated["to_address"]["status"] = FieldStatus.BASELINE.value
                        else:
                            updated["to_address"]["status"] = FieldStatus.IN_PROGRESS.value
                    else:
                        # Simple value - check if adding to existing
                        existing_value = updated["to_address"].get("value", "")
                        new_value = extracted.parsed_value or ""
                        if existing_value and "区" in str(new_value) and str(new_value) not in existing_value:
                            updated["to_address"]["value"] = existing_value + str(new_value)
                        elif new_value:
                            updated["to_address"]["value"] = new_value
                        if extracted.needs_verification:
                            updated["to_address"]["status"] = FieldStatus.IN_PROGRESS.value
                        else:
                            updated["to_address"]["status"] = FieldStatus.BASELINE.value

                elif field_name == "from_building_type":
                    if "from_address" not in updated or not isinstance(updated["from_address"], dict):
                        updated["from_address"] = {}
                    updated["from_address"]["building_type"] = extracted.parsed_value

                elif field_name == "move_date":
                    if "move_date" not in updated or not isinstance(updated["move_date"], dict):
                        updated["move_date"] = {}
                    # Merge parsed value if it's a dict
                    if isinstance(extracted.parsed_value, dict):
                        for k, v in extracted.parsed_value.items():
                            if v is not None:
                                updated["move_date"][k] = v
                    else:
                        updated["move_date"]["value"] = extracted.parsed_value
                    # R3: move_date needs year, month, AND day/period for baseline
                    has_day_or_period = (
                        updated["move_date"].get("day") is not None or
                        updated["move_date"].get("period") is not None
                    )
                    if has_day_or_period and not extracted.needs_verification:
                        updated["move_date"]["status"] = FieldStatus.BASELINE.value
                    else:
                        updated["move_date"]["status"] = FieldStatus.IN_PROGRESS.value

                elif field_name == "move_time_slot":
                    if "move_date" not in updated or not isinstance(updated["move_date"], dict):
                        updated["move_date"] = {}
                    updated["move_date"]["time_slot"] = extracted.parsed_value

                elif field_name == "from_floor":
                    if "from_floor_elevator" not in updated or not isinstance(updated["from_floor_elevator"], dict):
                        updated["from_floor_elevator"] = {}
                    updated["from_floor_elevator"]["floor"] = extracted.parsed_value
                    # If we already have elevator info, mark as baseline
                    if updated["from_floor_elevator"].get("has_elevator") is not None:
                        updated["from_floor_elevator"]["status"] = FieldStatus.BASELINE.value
                    else:
                        updated["from_floor_elevator"]["status"] = FieldStatus.IN_PROGRESS.value

                elif field_name == "from_has_elevator":
                    if "from_floor_elevator" not in updated or not isinstance(updated["from_floor_elevator"], dict):
                        updated["from_floor_elevator"] = {}
                    updated["from_floor_elevator"]["has_elevator"] = extracted.parsed_value
                    # If we already have floor info, mark as baseline
                    if updated["from_floor_elevator"].get("floor") is not None:
                        updated["from_floor_elevator"]["status"] = FieldStatus.BASELINE.value
                    else:
                        updated["from_floor_elevator"]["status"] = FieldStatus.IN_PROGRESS.value

                elif field_name == "to_floor":
                    if "to_floor_elevator" not in updated or not isinstance(updated["to_floor_elevator"], dict):
                        updated["to_floor_elevator"] = {}
                    updated["to_floor_elevator"]["floor"] = extracted.parsed_value
                    if updated["to_floor_elevator"].get("has_elevator") is not None:
                        updated["to_floor_elevator"]["status"] = FieldStatus.BASELINE.value
                    else:
                        updated["to_floor_elevator"]["status"] = FieldStatus.IN_PROGRESS.value

                elif field_name == "to_has_elevator":
                    if "to_floor_elevator" not in updated or not isinstance(updated["to_floor_elevator"], dict):
                        updated["to_floor_elevator"] = {}
                    updated["to_floor_elevator"]["has_elevator"] = extracted.parsed_value
                    if updated["to_floor_elevator"].get("floor") is not None:
                        updated["to_floor_elevator"]["status"] = FieldStatus.BASELINE.value
                    else:
                        updated["to_floor_elevator"]["status"] = FieldStatus.IN_PROGRESS.value

                elif field_name == "packing_service":
                    updated["packing_service"] = extracted.parsed_value

                elif field_name == "special_notes":
                    if "special_notes" not in updated:
                        updated["special_notes"] = []
                    if isinstance(extracted.parsed_value, list):
                        for v in extracted.parsed_value:
                            if v == "没有了" or v == "没有其他":
                                updated["special_notes_done"] = True
                            elif v not in updated["special_notes"]:
                                updated["special_notes"].append(v)
                    else:
                        if extracted.parsed_value == "没有了" or extracted.parsed_value == "没有其他":
                            updated["special_notes_done"] = True
                        elif extracted.parsed_value not in updated["special_notes"]:
                            updated["special_notes"].append(extracted.parsed_value)

        return updated

    def _get_fallback_output(
        self,
        user_message: str,
        fields_status: Dict[str, Any]
    ) -> RouterOutput:
        """Get fallback output when parsing fails"""
        # Infer phase from fields status
        current_phase = self._infer_phase(fields_status)

        return RouterOutput(
            intent=Intent(
                primary=IntentType.PROVIDE_INFO,
                secondary=None,
                confidence=0.5
            ),
            extracted_fields={},
            user_emotion=Emotion.NEUTRAL,
            current_phase=current_phase,
            next_actions=[
                Action(
                    type=ActionType.COLLECT_FIELD,
                    target=self._get_next_field(fields_status),
                    priority=1
                )
            ],
            response_strategy=ResponseStrategy(
                agent_type=AgentType.COLLECTOR,
                style=ResponseStyle.FRIENDLY,
                should_acknowledge=True,
                guide_to_field=self._get_next_field(fields_status),
                include_options=True
            ),
            updated_fields_status=fields_status
        )

    def _infer_phase(self, fields_status: Dict[str, Any]) -> int:
        """Infer current phase from fields status"""
        # Check people_count
        people_status = fields_status.get("people_count_status", "not_collected")
        if people_status not in ["baseline", "ideal"]:
            return Phase.PEOPLE_COUNT.value

        # Check addresses
        from_addr = fields_status.get("from_address", {})
        to_addr = fields_status.get("to_address", {})
        from_status = from_addr.get("status", "not_collected") if isinstance(from_addr, dict) else "not_collected"
        to_status = to_addr.get("status", "not_collected") if isinstance(to_addr, dict) else "not_collected"

        if from_status not in ["baseline", "ideal"] or to_status not in ["baseline", "ideal"]:
            return Phase.ADDRESS.value

        # Check date
        move_date = fields_status.get("move_date", {})
        date_status = move_date.get("status", "not_collected") if isinstance(move_date, dict) else "not_collected"

        if date_status not in ["baseline", "ideal"]:
            return Phase.DATE.value

        # Check items
        items = fields_status.get("items", {})
        items_status = items.get("status", "not_collected") if isinstance(items, dict) else "not_collected"

        if items_status not in ["baseline", "ideal"]:
            return Phase.ITEMS.value

        # Check other info (floor, elevator, packing, special_notes)
        from_floor = fields_status.get("from_floor_elevator", {})
        floor_status = from_floor.get("status", "not_collected") if isinstance(from_floor, dict) else "not_collected"

        # Check if building type requires floor info
        building_type = from_addr.get("building_type") if isinstance(from_addr, dict) else None
        apartment_types = ["マンション", "アパート", "タワーマンション"]

        if building_type in apartment_types and floor_status not in ["baseline", "ideal", "skipped"]:
            return Phase.OTHER_INFO.value

        # Check to_floor_elevator (非必填，但要询问)
        to_floor = fields_status.get("to_floor_elevator", {})
        to_floor_status = to_floor.get("status", "not_collected") if isinstance(to_floor, dict) else "not_collected"
        if to_floor_status not in ["baseline", "ideal", "skipped"]:
            return Phase.OTHER_INFO.value

        # Check packing_service
        if fields_status.get("packing_service") is None:
            return Phase.OTHER_INFO.value

        # Check special_notes (用户点"没有了"才算完成)
        special_notes_done = fields_status.get("special_notes_done", False)
        if not special_notes_done:
            return Phase.OTHER_INFO.value

        # All complete
        return Phase.CONFIRMATION.value

    def _get_next_field(self, fields_status: Dict[str, Any]) -> Optional[str]:
        """Get next field to collect based on priority"""
        from app.core.phase_inference import get_next_priority_field
        return get_next_priority_field(fields_status)


# Global router agent instance
_router_agent: Optional[RouterAgent] = None


def get_router_agent() -> RouterAgent:
    """Get global router agent instance"""
    global _router_agent
    if _router_agent is None:
        _router_agent = RouterAgent()
    return _router_agent
