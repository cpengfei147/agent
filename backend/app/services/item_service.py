"""Item Service - Vision API integration and item catalog management

Uses Google Gemini for image recognition of furniture and household items.
"""

import base64
import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

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
    """Service for item recognition and catalog management

    Uses Google Gemini for image recognition.
    """

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self._model = None

    def _get_model(self):
        """Lazy load Gemini model"""
        if self._model is None and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(self.model_name)
                logger.info(f"Gemini model initialized: {self.model_name}")
            except ImportError:
                logger.error("google-generativeai package not installed. Run: pip install google-generativeai")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model: {e}")
        return self._model

    async def analyze_image(
        self,
        image_data: bytes,
        image_type: str = "image/jpeg"
    ) -> ImageRecognitionResult:
        """
        Analyze an image using Google Gemini Vision API to identify furniture/items

        Args:
            image_data: Raw image bytes
            image_type: MIME type of the image

        Returns:
            ImageRecognitionResult with identified items
        """
        model = self._get_model()
        if not model:
            return ImageRecognitionResult(
                success=False,
                error="Gemini model not initialized. Check GEMINI_API_KEY."
            )

        try:
            import google.generativeai as genai
            from PIL import Image
            import io

            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))

            # Build the prompt for furniture/item recognition
            prompt = """你是一个搬家物品识别专家。请分析这张图片，识别出所有需要搬运的家具、家电和物品。

对于每个识别出的物品，请提供：
1. name_ja: 日语名称（如：ダンボール、冷蔵庫、ベッド）
2. name: 中文名称
3. category: 分类，必须是以下之一："large_furniture"（大型家具）、"appliances"（家电）、"small_items"（小物品/箱子）
4. count: 数量
5. size_estimate: 尺寸估计："small"、"medium" 或 "large"

请严格按照以下JSON格式返回，不要包含其他文字：
{
  "items": [
    {"name_ja": "ダンボール", "name": "纸箱", "category": "small_items", "count": 5, "size_estimate": "medium"},
    {"name_ja": "冷蔵庫", "name": "冰箱", "category": "appliances", "count": 1, "size_estimate": "large"}
  ],
  "description": "图片描述"
}

注意：
- 只识别需要搬运的物品（家具、家电、箱子、行李等）
- 忽略固定设施（门、窗、墙壁装饰等）
- 如果看到多个相同物品，合并计数
- 纸箱/段ボール 要准确计数"""

            # Generate content with image
            response = model.generate_content([prompt, image])

            if response and response.text:
                # Parse JSON from response
                response_text = response.text.strip()

                # Try to extract JSON if wrapped in markdown code blocks
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                result_data = json.loads(response_text)

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
                        confidence=0.85,  # Gemini doesn't return confidence
                        size_estimate=item_data.get("size_estimate"),
                        note=item_data.get("note")
                    ))

                logger.info(f"Gemini recognized {len(items)} items from image")
                return ImageRecognitionResult(
                    success=True,
                    items=items,
                    raw_description=result_data.get("description")
                )

            return ImageRecognitionResult(
                success=False,
                error="Empty response from Gemini Vision API"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            return ImageRecognitionResult(
                success=False,
                error=f"Invalid JSON response: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Gemini image analysis failed: {e}")
            return ImageRecognitionResult(
                success=False,
                error=str(e)
            )

    async def analyze_image_url(self, image_url: str) -> ImageRecognitionResult:
        """
        Analyze an image from URL using Gemini Vision API

        Args:
            image_url: URL of the image to analyze

        Returns:
            ImageRecognitionResult with identified items
        """
        try:
            import httpx

            # Download image from URL
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_data = response.content
                content_type = response.headers.get("content-type", "image/jpeg")

            # Use the analyze_image method
            return await self.analyze_image(image_data, content_type)

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
