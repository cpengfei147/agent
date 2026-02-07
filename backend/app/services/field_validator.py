"""Field validation service for ERABU

Principle: Router (LLM) is responsible for understanding user intent and extracting field values.
Validator only does simple validation: checking if values exist and are reasonable.
No regex parsing here - all parsing is done by LLM.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Validation result"""
    is_valid: bool
    parsed_value: Any
    status: str  # "baseline" | "ideal" | "needs_verification" | "invalid"
    message: Optional[str] = None
    suggestions: List[str] = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


class FieldValidator:
    """Field validation logic - simple checks only, no parsing"""

    # Japanese building types
    BUILDING_TYPES = {
        "マンション", "アパート", "戸建て", "タワーマンション",
        "その他", "公共の建物", "一戸建て", "ビル", "団地"
    }

    # Apartment types that require floor info
    APARTMENT_TYPES = {"マンション", "アパート", "タワーマンション", "団地", "ビル"}

    def validate_people_count(self, value: Any) -> ValidationResult:
        """
        Validate people count field

        Router already parsed the value (e.g., "2~3人" -> 3)
        We just check if it's a reasonable number.
        """
        if value is None:
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="人数未提供"
            )

        # Router should have already converted to int
        if isinstance(value, int):
            if value <= 0:
                return ValidationResult(
                    is_valid=False,
                    parsed_value=None,
                    status="invalid",
                    message="人数必须大于0"
                )
            return ValidationResult(
                is_valid=True,
                parsed_value=value,
                status="ideal",
                message=f"{value}人搬家"
            )

        # If Router returned a string, accept it as-is
        if isinstance(value, str) and value.strip():
            return ValidationResult(
                is_valid=True,
                parsed_value=value,
                status="baseline",
                message=f"{value}搬家"
            )

        return ValidationResult(
            is_valid=False,
            parsed_value=None,
            status="invalid",
            message="人数格式错误"
        )

    def validate_address(
        self,
        value: Any,
        address_type: str = "from"
    ) -> ValidationResult:
        """
        Validate address field

        Router extracts: {"value": "地址", "postal_code": "xxx", "city": "xxx市", "district": "xxx区"}
        We just check if required fields exist.

        Rules (Red Lines):
        - R1: from_address needs postal_code for baseline
        - R2: to_address needs city for baseline
        """
        if value is None:
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="地址未提供"
            )

        # Convert string to dict
        if isinstance(value, str):
            value = {"value": value.strip()}

        if not isinstance(value, dict):
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="地址格式错误"
            )

        # Use Router's extracted fields directly
        parsed = {
            "value": value.get("value", ""),
            "postal_code": value.get("postal_code"),
            "city": value.get("city"),
            "district": value.get("district"),
            "prefecture": value.get("prefecture"),
        }

        if address_type == "from":
            # R1: from_address needs postal_code
            if parsed.get("postal_code"):
                return ValidationResult(
                    is_valid=True,
                    parsed_value=parsed,
                    status="baseline",
                    message="搬出地址已确认"
                )
            else:
                # Has some address info but no postal code
                if parsed.get("value"):
                    return ValidationResult(
                        is_valid=True,
                        parsed_value=parsed,
                        status="needs_verification",
                        message="需要确认邮编"
                    )
                return ValidationResult(
                    is_valid=False,
                    parsed_value=parsed,
                    status="invalid",
                    message="地址信息不足"
                )
        else:  # to_address
            # R2: to_address needs city
            if parsed.get("city"):
                # Check if we have district for ideal status
                if parsed.get("district"):
                    return ValidationResult(
                        is_valid=True,
                        parsed_value=parsed,
                        status="ideal",
                        message="搬入地址已确认"
                    )
                else:
                    return ValidationResult(
                        is_valid=True,
                        parsed_value=parsed,
                        status="baseline",
                        message="搬入地址已确认"
                    )
            elif parsed.get("value"):
                return ValidationResult(
                    is_valid=True,
                    parsed_value=parsed,
                    status="needs_verification",
                    message="需要确认城市/区域"
                )
            return ValidationResult(
                is_valid=False,
                parsed_value=parsed,
                status="invalid",
                message="地址信息不足"
            )

    def validate_building_type(self, value: Any) -> ValidationResult:
        """Validate building type - Router already extracted"""
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="建筑类型未提供"
            )

        value_str = str(value).strip()

        return ValidationResult(
            is_valid=True,
            parsed_value=value_str,
            status="ideal",
            message=f"建筑类型: {value_str}"
        )

    def validate_move_date(self, value: Any) -> ValidationResult:
        """
        Validate move date field

        Router extracts: {"value": "3月上旬", "year": 2026, "month": 3, "day": null, "period": "上旬"}
        We check if required fields exist.

        Rules (Red Line R3):
        - Must have year, month, and (day or period) for baseline
        """
        if value is None:
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="搬家日期未提供"
            )

        # Convert string to dict
        if isinstance(value, str):
            value = {"value": value.strip()}

        if not isinstance(value, dict):
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="日期格式错误"
            )

        # Use Router's extracted fields directly
        parsed = {
            "value": value.get("value", ""),
            "year": value.get("year"),
            "month": value.get("month"),
            "day": value.get("day"),
            "period": value.get("period"),
        }

        # Default year if not provided
        if parsed.get("month") and not parsed.get("year"):
            now = datetime.now()
            if parsed["month"] < now.month:
                parsed["year"] = now.year + 1
            else:
                parsed["year"] = now.year

        # Check completeness
        has_year = parsed.get("year") is not None
        has_month = parsed.get("month") is not None
        has_day_or_period = parsed.get("day") is not None or parsed.get("period") is not None

        if has_year and has_month and has_day_or_period:
            return ValidationResult(
                is_valid=True,
                parsed_value=parsed,
                status="baseline",
                message=self._format_date_message(parsed)
            )
        elif has_month:
            return ValidationResult(
                is_valid=True,
                parsed_value=parsed,
                status="needs_verification",
                message="需要确认具体日期或旬"
            )
        elif parsed.get("value"):
            return ValidationResult(
                is_valid=True,
                parsed_value=parsed,
                status="needs_verification",
                message="需要确认搬家月份"
            )
        else:
            return ValidationResult(
                is_valid=False,
                parsed_value=parsed,
                status="invalid",
                message="需要提供搬家日期"
            )

    def _format_date_message(self, parsed: Dict[str, Any]) -> str:
        """Format date message"""
        parts = []
        if parsed.get("year"):
            parts.append(f"{parsed['year']}年")
        if parsed.get("month"):
            parts.append(f"{parsed['month']}月")
        if parsed.get("day"):
            parts.append(f"{parsed['day']}日")
        elif parsed.get("period"):
            parts.append(parsed["period"])
        return "搬家日期: " + "".join(parts)

    def validate_time_slot(self, value: Any) -> ValidationResult:
        """Validate time slot - Router already extracted"""
        if value is None:
            return ValidationResult(
                is_valid=True,
                parsed_value="没有指定",
                status="baseline",
                message="时段未指定"
            )

        value_str = str(value).strip()

        return ValidationResult(
            is_valid=True,
            parsed_value=value_str,
            status="ideal",
            message=f"时段: {value_str}"
        )

    def validate_floor(self, value: Any) -> ValidationResult:
        """Validate floor number - Router already extracted as int"""
        if value is None:
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="楼层未提供"
            )

        # Router should have already converted to int
        if isinstance(value, int):
            if value < 1 or value > 100:
                return ValidationResult(
                    is_valid=False,
                    parsed_value=None,
                    status="invalid",
                    message="楼层数值不合理"
                )
            return ValidationResult(
                is_valid=True,
                parsed_value=value,
                status="ideal",
                message=f"{value}楼"
            )

        # Accept string as-is if Router didn't convert
        if isinstance(value, str) and value.strip():
            return ValidationResult(
                is_valid=True,
                parsed_value=value,
                status="baseline",
                message=f"楼层: {value}"
            )

        return ValidationResult(
            is_valid=False,
            parsed_value=None,
            status="invalid",
            message="楼层格式错误"
        )

    def validate_elevator(self, value: Any) -> ValidationResult:
        """Validate elevator availability - Router already extracted as bool"""
        if value is None:
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="电梯情况未提供"
            )

        # Router should have already converted to bool
        if isinstance(value, bool):
            return ValidationResult(
                is_valid=True,
                parsed_value=value,
                status="ideal",
                message="有电梯" if value else "无电梯"
            )

        # Accept string as-is
        if isinstance(value, str):
            return ValidationResult(
                is_valid=True,
                parsed_value=value,
                status="baseline",
                message=f"电梯: {value}"
            )

        return ValidationResult(
            is_valid=False,
            parsed_value=None,
            status="invalid",
            message="电梯情况格式错误"
        )

    def validate_packing_service(self, value: Any) -> ValidationResult:
        """Validate packing service option - Router already extracted"""
        if value is None:
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="打包服务未选择"
            )

        value_str = str(value).strip()

        return ValidationResult(
            is_valid=True,
            parsed_value=value_str,
            status="ideal",
            message=f"打包服务: {value_str}"
        )

    def validate_items(self, items: Any) -> ValidationResult:
        """
        Validate items list

        Rules (Red Line R4):
        - Must have at least 1 item for baseline
        """
        if items is None:
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="物品清单为空"
            )

        if isinstance(items, dict):
            items_list = items.get("list", items.get("items", []))
        elif isinstance(items, list):
            items_list = items
        else:
            return ValidationResult(
                is_valid=False,
                parsed_value=None,
                status="invalid",
                message="物品格式错误"
            )

        if len(items_list) == 0:
            return ValidationResult(
                is_valid=False,
                parsed_value={"list": [], "status": "not_collected"},
                status="invalid",
                message="至少需要添加1件物品"
            )

        return ValidationResult(
            is_valid=True,
            parsed_value={"list": items_list, "count": len(items_list)},
            status="baseline",
            message=f"已添加{len(items_list)}件物品"
        )

    def requires_floor_info(self, building_type: str) -> bool:
        """Check if building type requires floor info (Red Line R5)"""
        return building_type in self.APARTMENT_TYPES


# Global validator instance
_validator: Optional[FieldValidator] = None


def get_field_validator() -> FieldValidator:
    """Get global field validator instance"""
    global _validator
    if _validator is None:
        _validator = FieldValidator()
    return _validator
