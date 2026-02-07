from enum import Enum
from typing import Optional, List, Any, Dict
from pydantic import BaseModel


class FieldStatus(str, Enum):
    """Field collection status"""
    NOT_COLLECTED = "not_collected"
    IN_PROGRESS = "in_progress"
    BASELINE = "baseline"
    IDEAL = "ideal"
    SKIPPED = "skipped"


class Phase(int, Enum):
    """UI Phase indicators"""
    OPENING = 0
    PEOPLE_COUNT = 1
    ADDRESS = 2
    DATE = 3
    ITEMS = 4
    OTHER_INFO = 5
    CONFIRMATION = 6


class AddressField(BaseModel):
    """Address field structure"""
    value: Optional[str] = None
    postal_code: Optional[str] = None
    prefecture: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    building_type: Optional[str] = None
    room_type: Optional[str] = None
    floor: Optional[int] = None
    has_elevator: Optional[bool] = None
    status: FieldStatus = FieldStatus.NOT_COLLECTED


class DateField(BaseModel):
    """Date field structure"""
    value: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    period: Optional[str] = None  # 上旬/中旬/下旬
    time_slot: Optional[str] = None  # 上午/下午/没有指定
    status: FieldStatus = FieldStatus.NOT_COLLECTED


class ItemField(BaseModel):
    """Single item structure"""
    name: str
    count: int = 1
    category: str = "other"  # furniture | appliance | box | other
    note: Optional[str] = None


class ItemsField(BaseModel):
    """Items field structure"""
    items: List[ItemField] = []
    boxes_needed: int = 0
    status: FieldStatus = FieldStatus.NOT_COLLECTED


class FloorElevatorField(BaseModel):
    """Floor and elevator field structure"""
    floor: Optional[int] = None
    has_elevator: Optional[bool] = None
    status: FieldStatus = FieldStatus.NOT_COLLECTED


class CollectedFields(BaseModel):
    """All collected fields"""
    # Required fields
    people_count: Optional[int] = None
    people_count_status: FieldStatus = FieldStatus.NOT_COLLECTED

    from_address: AddressField = AddressField()
    to_address: AddressField = AddressField()

    move_date: DateField = DateField()

    items: ItemsField = ItemsField()

    from_floor_elevator: FloorElevatorField = FloorElevatorField()
    to_floor_elevator: FloorElevatorField = FloorElevatorField()

    # Optional fields
    packing_service: Optional[str] = None
    special_notes: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CollectedFields":
        """Create from dictionary"""
        return cls(**data)

    def get_completion_summary(self) -> Dict[str, Any]:
        """Get completion summary"""
        required_fields = {
            "people_count": self.people_count_status,
            "from_address": self.from_address.status,
            "to_address": self.to_address.status,
            "move_date": self.move_date.status,
            "items": self.items.status,
        }

        completed = sum(
            1 for status in required_fields.values()
            if status in [FieldStatus.BASELINE, FieldStatus.IDEAL]
        )

        return {
            "total_required": len(required_fields),
            "completed": completed,
            "completion_rate": completed / len(required_fields),
            "can_submit": completed == len(required_fields),
            "missing_fields": [
                field for field, status in required_fields.items()
                if status not in [FieldStatus.BASELINE, FieldStatus.IDEAL]
            ]
        }


def get_default_fields() -> Dict[str, Any]:
    """Get default fields status"""
    return CollectedFields().to_dict()
