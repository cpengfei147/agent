"""Item Service - Vision API integration and item catalog management"""

import base64
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class ItemCategory(str, Enum):
    """Item category types"""
    LARGE_FURNITURE = "large_furniture"  # Large furniture
    APPLIANCES = "appliances"            # Home appliances
    SMALL_ITEMS = "small_items"          # Small items and boxes


@dataclass
class RecognizedItem:
    """Recognized item from image"""
    name: str
    name_ja: str
    category: ItemCategory
    count: int = 1
    confidence: float = 0.0
    size_estimate: Optional[str] = None  # small/medium/large
    note: Optional[str] = None


@dataclass
class ImageRecognitionResult:
    """Result of image recognition"""
    success: bool
    items: List[RecognizedItem] = field(default_factory=list)
    error: Optional[str] = None
    raw_description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "items": [
                {
                    "name": item.name,
                    "name_ja": item.name_ja,
                    "category": item.category.value,
                    "count": item.count,
                    "confidence": item.confidence,
                    "size_estimate": item.size_estimate,
                    "note": item.note
                }
                for item in self.items
            ],
            "error": self.error,
            "raw_description": self.raw_description
        }


# Item catalog data with Japanese names
ITEM_CATALOG = {
    ItemCategory.LARGE_FURNITURE: {
        "name": "Large Furniture",
        "name_ja": "大型家具",
        "items": [
            {"id": "bed_single", "name": "Single Bed", "name_ja": "シングルベッド"},
            {"id": "bed_semi_double", "name": "Semi-Double Bed", "name_ja": "セミダブルベッド"},
            {"id": "bed_double", "name": "Double Bed", "name_ja": "ダブルベッド"},
            {"id": "sofa_2seat", "name": "2-Seater Sofa", "name_ja": "2人掛けソファー"},
            {"id": "sofa_3seat", "name": "3-Seater Sofa", "name_ja": "3人掛けソファー"},
            {"id": "dining_table", "name": "Dining Table", "name_ja": "ダイニングテーブル"},
            {"id": "desk", "name": "Desk", "name_ja": "デスク"},
            {"id": "bookshelf", "name": "Bookshelf", "name_ja": "本棚"},
            {"id": "wardrobe", "name": "Wardrobe", "name_ja": "タンス・ワードローブ"},
            {"id": "chest", "name": "Chest of Drawers", "name_ja": "チェスト"},
            {"id": "storage_case", "name": "Storage Case", "name_ja": "衣装ケース"},
            {"id": "tv_stand", "name": "TV Stand", "name_ja": "テレビ台"},
            {"id": "shoe_rack", "name": "Shoe Rack", "name_ja": "下駄箱"},
            {"id": "kotatsu", "name": "Kotatsu Table", "name_ja": "こたつ"},
            {"id": "dresser", "name": "Dresser", "name_ja": "ドレッサー"},
        ]
    },
    ItemCategory.APPLIANCES: {
        "name": "Home Appliances",
        "name_ja": "家電製品",
        "items": [
            {"id": "fridge_small", "name": "Refrigerator (Small)", "name_ja": "冷蔵庫（小型）"},
            {"id": "fridge_medium", "name": "Refrigerator (Medium)", "name_ja": "冷蔵庫（中型）"},
            {"id": "fridge_large", "name": "Refrigerator (Large)", "name_ja": "冷蔵庫（大型）"},
            {"id": "washing_machine", "name": "Washing Machine", "name_ja": "洗濯機"},
            {"id": "washer_dryer", "name": "Washer-Dryer Combo", "name_ja": "ドラム式洗濯乾燥機"},
            {"id": "tv_small", "name": "TV (~32\")", "name_ja": "テレビ（〜32型）"},
            {"id": "tv_medium", "name": "TV (40-50\")", "name_ja": "テレビ（40〜50型）"},
            {"id": "tv_large", "name": "TV (55\"+)", "name_ja": "テレビ（55型以上）"},
            {"id": "air_conditioner", "name": "Air Conditioner", "name_ja": "エアコン"},
            {"id": "microwave", "name": "Microwave", "name_ja": "電子レンジ"},
            {"id": "rice_cooker", "name": "Rice Cooker", "name_ja": "炊飯器"},
            {"id": "vacuum", "name": "Vacuum Cleaner", "name_ja": "掃除機"},
            {"id": "fan", "name": "Fan", "name_ja": "扇風機"},
            {"id": "heater", "name": "Heater", "name_ja": "ヒーター・ストーブ"},
            {"id": "dehumidifier", "name": "Dehumidifier/Humidifier", "name_ja": "除湿機・加湿器"},
            {"id": "pc_desktop", "name": "Desktop PC", "name_ja": "デスクトップPC"},
            {"id": "printer", "name": "Printer", "name_ja": "プリンター"},
        ]
    },
    ItemCategory.SMALL_ITEMS: {
        "name": "Small Items/Boxes",
        "name_ja": "小物・段ボール",
        "items": [
            {"id": "box_small", "name": "Small Box", "name_ja": "段ボール（小）"},
            {"id": "box_medium", "name": "Medium Box", "name_ja": "段ボール（中）"},
            {"id": "box_large", "name": "Large Box", "name_ja": "段ボール（大）"},
            {"id": "suitcase", "name": "Suitcase", "name_ja": "スーツケース"},
            {"id": "futon", "name": "Futon Set", "name_ja": "布団セット"},
            {"id": "clothes_bag", "name": "Clothes Bag", "name_ja": "衣類バッグ"},
            {"id": "books_bundle", "name": "Books Bundle", "name_ja": "本・書籍"},
            {"id": "kitchenware", "name": "Kitchenware", "name_ja": "食器類"},
            {"id": "plant", "name": "Plant", "name_ja": "観葉植物"},
            {"id": "bicycle", "name": "Bicycle", "name_ja": "自転車"},
            {"id": "golf_bag", "name": "Golf Bag", "name_ja": "ゴルフバッグ"},
            {"id": "ski_snowboard", "name": "Ski/Snowboard", "name_ja": "スキー・スノーボード"},
        ]
    }
}


class ItemService:
    """Service for item recognition and catalog management"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client"""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def analyze_image(
        self,
        image_data: bytes,
        image_type: str = "image/jpeg"
    ) -> ImageRecognitionResult:
        """
        Analyze an image using OpenAI Vision API to identify furniture/items

        Args:
            image_data: Raw image bytes
            image_type: MIME type of the image

        Returns:
            ImageRecognitionResult with identified items
        """
        try:
            client = self._get_client()

            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode("utf-8")

            # Build the prompt for furniture/item recognition
            system_prompt = """You are an expert at identifying furniture and household items in images for a moving service.
Analyze the image and identify all furniture, appliances, and other movable items.

For each item found, provide:
1. name_ja: Japanese name of the item
2. name: English name
3. category: one of "large_furniture", "appliances", or "small_items"
4. count: number of this item visible
5. size_estimate: "small", "medium", or "large"
6. confidence: your confidence level from 0 to 1

Respond in JSON format with an "items" array. Example:
{
  "items": [
    {"name_ja": "Single Bed", "name": "Single bed", "category": "large_furniture", "count": 1, "size_estimate": "large", "confidence": 0.95},
    {"name_ja": "TV Stand", "name": "TV stand", "category": "large_furniture", "count": 1, "size_estimate": "medium", "confidence": 0.8}
  ],
  "description": "A bedroom with a single bed, TV stand, and small desk."
}

Focus on items relevant for moving: furniture, appliances, boxes, storage items.
Ignore small items like books, decorations, or fixed fixtures."""

            response = await client.chat.completions.create(
                model="gpt-4o",  # Using GPT-4o which has vision capabilities
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please identify all furniture and household items in this image that would need to be moved."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_type};base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            # Parse the response
            content = response.choices[0].message.content
            if content:
                import json
                result_data = json.loads(content)

                items = []
                for item_data in result_data.get("items", []):
                    category_str = item_data.get("category", "small_items")
                    try:
                        category = ItemCategory(category_str)
                    except ValueError:
                        category = ItemCategory.SMALL_ITEMS

                    items.append(RecognizedItem(
                        name=item_data.get("name", "Unknown"),
                        name_ja=item_data.get("name_ja", "Unknown"),
                        category=category,
                        count=item_data.get("count", 1),
                        confidence=item_data.get("confidence", 0.5),
                        size_estimate=item_data.get("size_estimate"),
                        note=item_data.get("note")
                    ))

                return ImageRecognitionResult(
                    success=True,
                    items=items,
                    raw_description=result_data.get("description")
                )

            return ImageRecognitionResult(
                success=False,
                error="Empty response from Vision API"
            )

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return ImageRecognitionResult(
                success=False,
                error=str(e)
            )

    async def analyze_image_url(self, image_url: str) -> ImageRecognitionResult:
        """
        Analyze an image from URL using OpenAI Vision API

        Args:
            image_url: URL of the image to analyze

        Returns:
            ImageRecognitionResult with identified items
        """
        try:
            client = self._get_client()

            system_prompt = """You are an expert at identifying furniture and household items in images for a moving service.
Analyze the image and identify all furniture, appliances, and other movable items.

For each item found, provide:
1. name_ja: Japanese name of the item
2. name: English name
3. category: one of "large_furniture", "appliances", or "small_items"
4. count: number of this item visible
5. size_estimate: "small", "medium", or "large"
6. confidence: your confidence level from 0 to 1

Respond in JSON format with an "items" array. Focus on items relevant for moving."""

            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please identify all furniture and household items in this image that would need to be moved."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            if content:
                import json
                result_data = json.loads(content)

                items = []
                for item_data in result_data.get("items", []):
                    category_str = item_data.get("category", "small_items")
                    try:
                        category = ItemCategory(category_str)
                    except ValueError:
                        category = ItemCategory.SMALL_ITEMS

                    items.append(RecognizedItem(
                        name=item_data.get("name", "Unknown"),
                        name_ja=item_data.get("name_ja", "Unknown"),
                        category=category,
                        count=item_data.get("count", 1),
                        confidence=item_data.get("confidence", 0.5),
                        size_estimate=item_data.get("size_estimate"),
                        note=item_data.get("note")
                    ))

                return ImageRecognitionResult(
                    success=True,
                    items=items,
                    raw_description=result_data.get("description")
                )

            return ImageRecognitionResult(
                success=False,
                error="Empty response from Vision API"
            )

        except Exception as e:
            logger.error(f"Image URL analysis failed: {e}")
            return ImageRecognitionResult(
                success=False,
                error=str(e)
            )

    def get_catalog(self) -> Dict[str, Any]:
        """
        Get the full item catalog

        Returns:
            Dict with categories and their items
        """
        return {
            category.value: {
                "name": data["name"],
                "name_ja": data["name_ja"],
                "items": data["items"]
            }
            for category, data in ITEM_CATALOG.items()
        }

    def get_category_items(self, category: ItemCategory) -> List[Dict[str, Any]]:
        """
        Get items for a specific category

        Args:
            category: ItemCategory enum value

        Returns:
            List of items in that category
        """
        if category in ITEM_CATALOG:
            return ITEM_CATALOG[category]["items"]
        return []

    def search_items(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for items by name (Japanese or English)

        Args:
            query: Search query string

        Returns:
            List of matching items with their categories
        """
        query_lower = query.lower()
        results = []

        for category, data in ITEM_CATALOG.items():
            for item in data["items"]:
                if (query_lower in item["name"].lower() or
                    query in item["name_ja"]):
                    results.append({
                        **item,
                        "category": category.value,
                        "category_name": data["name"],
                        "category_name_ja": data["name_ja"]
                    })

        return results

    def validate_item_selection(
        self,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate a list of selected items

        Args:
            items: List of item dicts with id, count, and optional note

        Returns:
            Validation result with normalized items
        """
        validated_items = []
        errors = []

        # Build a lookup of all valid item IDs
        valid_items = {}
        for category, data in ITEM_CATALOG.items():
            for item in data["items"]:
                valid_items[item["id"]] = {
                    **item,
                    "category": category.value
                }

        for item in items:
            item_id = item.get("id")
            count = item.get("count", 1)
            note = item.get("note")

            if item_id in valid_items:
                validated_items.append({
                    "id": item_id,
                    "name": valid_items[item_id]["name"],
                    "name_ja": valid_items[item_id]["name_ja"],
                    "category": valid_items[item_id]["category"],
                    "count": max(1, int(count)),
                    "note": note
                })
            elif item.get("name") or item.get("name_ja"):
                # Custom item not in catalog
                validated_items.append({
                    "id": f"custom_{len(validated_items)}",
                    "name": item.get("name", item.get("name_ja", "Custom Item")),
                    "name_ja": item.get("name_ja", item.get("name", "Custom item")),
                    "category": item.get("category", "small_items"),
                    "count": max(1, int(count)),
                    "note": note,
                    "is_custom": True
                })
            else:
                errors.append(f"Unknown item ID: {item_id}")

        return {
            "valid": len(errors) == 0,
            "items": validated_items,
            "errors": errors,
            "total_count": sum(item["count"] for item in validated_items)
        }


# Global service instance
_item_service: Optional[ItemService] = None


def get_item_service() -> ItemService:
    """Get global item service instance"""
    global _item_service
    if _item_service is None:
        _item_service = ItemService()
    return _item_service
