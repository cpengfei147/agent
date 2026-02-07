"""Items API - Image upload and item catalog endpoints"""

import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

from app.services.item_service import get_item_service, ItemCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/items", tags=["items"])


# Request/Response Models
class ItemRequest(BaseModel):
    """Single item in request"""
    id: Optional[str] = None
    name: Optional[str] = None
    name_ja: Optional[str] = None
    category: Optional[str] = None
    count: int = 1
    note: Optional[str] = None


class ItemsValidationRequest(BaseModel):
    """Request to validate items selection"""
    items: List[ItemRequest]


class RecognizedItemResponse(BaseModel):
    """Single recognized item"""
    name: str
    name_ja: str
    category: str
    count: int
    confidence: float
    size_estimate: Optional[str] = None
    note: Optional[str] = None


class ImageRecognitionResponse(BaseModel):
    """Response from image recognition"""
    success: bool
    image_id: str
    items: List[RecognizedItemResponse]
    raw_description: Optional[str] = None
    error: Optional[str] = None


class CatalogItemResponse(BaseModel):
    """Single catalog item"""
    id: str
    name: str
    name_ja: str


class CatalogCategoryResponse(BaseModel):
    """Catalog category with items"""
    name: str
    name_ja: str
    items: List[CatalogItemResponse]


class CatalogResponse(BaseModel):
    """Full catalog response"""
    large_furniture: CatalogCategoryResponse
    appliances: CatalogCategoryResponse
    small_items: CatalogCategoryResponse


class ValidatedItemResponse(BaseModel):
    """Single validated item"""
    id: str
    name: str
    name_ja: str
    category: str
    count: int
    note: Optional[str] = None
    is_custom: bool = False


class ValidationResponse(BaseModel):
    """Items validation response"""
    valid: bool
    items: List[ValidatedItemResponse]
    errors: List[str]
    total_count: int


@router.post("/upload", response_model=ImageRecognitionResponse)
async def upload_image(
    file: UploadFile = File(...),
    session_token: Optional[str] = Query(None)
):
    """
    Upload an image for furniture/item recognition

    Args:
        file: Image file (JPEG, PNG, WebP supported)
        session_token: Optional session token for tracking

    Returns:
        ImageRecognitionResponse with identified items
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed types: {allowed_types}"
        )

    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is 10MB."
        )

    # Generate image ID for tracking
    image_id = str(uuid.uuid4())

    logger.info(f"Processing image upload: {image_id}, type: {file.content_type}, size: {len(contents)}")

    # Analyze image
    item_service = get_item_service()
    result = await item_service.analyze_image(
        image_data=contents,
        image_type=file.content_type
    )

    if not result.success:
        logger.error(f"Image analysis failed: {result.error}")
        return ImageRecognitionResponse(
            success=False,
            image_id=image_id,
            items=[],
            error=result.error
        )

    # Convert to response format
    items = [
        RecognizedItemResponse(
            name=item.name,
            name_ja=item.name_ja,
            category=item.category.value,
            count=item.count,
            confidence=item.confidence,
            size_estimate=item.size_estimate,
            note=item.note
        )
        for item in result.items
    ]

    logger.info(f"Image {image_id} analyzed: found {len(items)} items")

    return ImageRecognitionResponse(
        success=True,
        image_id=image_id,
        items=items,
        raw_description=result.raw_description
    )


@router.post("/upload-url", response_model=ImageRecognitionResponse)
async def analyze_image_url(
    image_url: str,
    session_token: Optional[str] = Query(None)
):
    """
    Analyze an image from URL

    Args:
        image_url: URL of the image to analyze
        session_token: Optional session token for tracking

    Returns:
        ImageRecognitionResponse with identified items
    """
    image_id = str(uuid.uuid4())

    logger.info(f"Processing image URL: {image_id}, url: {image_url}")

    item_service = get_item_service()
    result = await item_service.analyze_image_url(image_url)

    if not result.success:
        logger.error(f"Image URL analysis failed: {result.error}")
        return ImageRecognitionResponse(
            success=False,
            image_id=image_id,
            items=[],
            error=result.error
        )

    items = [
        RecognizedItemResponse(
            name=item.name,
            name_ja=item.name_ja,
            category=item.category.value,
            count=item.count,
            confidence=item.confidence,
            size_estimate=item.size_estimate,
            note=item.note
        )
        for item in result.items
    ]

    return ImageRecognitionResponse(
        success=True,
        image_id=image_id,
        items=items,
        raw_description=result.raw_description
    )


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog():
    """
    Get the full item catalog

    Returns:
        CatalogResponse with all categories and items
    """
    item_service = get_item_service()
    catalog = item_service.get_catalog()

    return CatalogResponse(
        large_furniture=CatalogCategoryResponse(
            name=catalog["large_furniture"]["name"],
            name_ja=catalog["large_furniture"]["name_ja"],
            items=[
                CatalogItemResponse(**item)
                for item in catalog["large_furniture"]["items"]
            ]
        ),
        appliances=CatalogCategoryResponse(
            name=catalog["appliances"]["name"],
            name_ja=catalog["appliances"]["name_ja"],
            items=[
                CatalogItemResponse(**item)
                for item in catalog["appliances"]["items"]
            ]
        ),
        small_items=CatalogCategoryResponse(
            name=catalog["small_items"]["name"],
            name_ja=catalog["small_items"]["name_ja"],
            items=[
                CatalogItemResponse(**item)
                for item in catalog["small_items"]["items"]
            ]
        )
    )


@router.get("/catalog/{category}")
async def get_category_items(category: str):
    """
    Get items for a specific category

    Args:
        category: Category name (large_furniture, appliances, small_items)

    Returns:
        List of items in that category
    """
    try:
        item_category = ItemCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category: {category}. Valid categories: large_furniture, appliances, small_items"
        )

    item_service = get_item_service()
    items = item_service.get_category_items(item_category)

    return {
        "category": category,
        "items": items
    }


@router.get("/search")
async def search_items(q: str = Query(..., min_length=1)):
    """
    Search for items by name

    Args:
        q: Search query (Japanese or English)

    Returns:
        List of matching items
    """
    item_service = get_item_service()
    results = item_service.search_items(q)

    return {
        "query": q,
        "results": results,
        "count": len(results)
    }


@router.post("/validate", response_model=ValidationResponse)
async def validate_items(request: ItemsValidationRequest):
    """
    Validate a list of selected items

    Args:
        request: ItemsValidationRequest with items list

    Returns:
        ValidationResponse with normalized items
    """
    item_service = get_item_service()

    items_data = [
        {
            "id": item.id,
            "name": item.name,
            "name_ja": item.name_ja,
            "category": item.category,
            "count": item.count,
            "note": item.note
        }
        for item in request.items
    ]

    result = item_service.validate_item_selection(items_data)

    return ValidationResponse(
        valid=result["valid"],
        items=[
            ValidatedItemResponse(**item)
            for item in result["items"]
        ],
        errors=result["errors"],
        total_count=result["total_count"]
    )
