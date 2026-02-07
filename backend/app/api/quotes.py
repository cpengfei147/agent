"""Quote API endpoints"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.services.quote_service import QuoteService, submit_quote


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


class QuoteSubmitRequest(BaseModel):
    """Request model for quote submission"""
    session_token: str
    fields_status: Dict[str, Any]
    user_email: Optional[EmailStr] = None
    user_phone: Optional[str] = None


class QuoteResponse(BaseModel):
    """Response model for quote operations"""
    quote_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    collected_data: Dict[str, Any]


class QuoteStatusUpdate(BaseModel):
    """Request model for status update"""
    status: str


@router.post("/submit", response_model=QuoteResponse)
async def submit_quote_endpoint(request: QuoteSubmitRequest):
    """
    Submit a quote request

    This endpoint receives the collected moving information and creates
    a quote request that can be sent to moving companies.
    """
    try:
        result = await submit_quote(
            session_token=request.session_token,
            fields_status=request.fields_status,
            user_email=request.user_email,
            user_phone=request.user_phone
        )
        logger.info(f"Quote submitted: {result['quote_id']}")
        return QuoteResponse(**result)
    except Exception as e:
        logger.error(f"Quote submission failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Quote submission failed: {str(e)}"
        )


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote_endpoint(quote_id: str):
    """Get quote by ID"""
    result = await QuoteService.get_quote(quote_id)
    if not result:
        raise HTTPException(status_code=404, detail="Quote not found")
    return QuoteResponse(**result)


@router.get("/session/{session_token}")
async def get_quotes_by_session_endpoint(session_token: str):
    """Get all quotes for a session"""
    results = await QuoteService.get_quotes_by_session(session_token)
    return {"quotes": results}


@router.patch("/{quote_id}/status")
async def update_quote_status_endpoint(
    quote_id: str,
    request: QuoteStatusUpdate
):
    """Update quote status"""
    valid_statuses = ["submitted", "processing", "completed", "cancelled"]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    completed = request.status == "completed"
    success = await QuoteService.update_quote_status(
        quote_id=quote_id,
        status=request.status,
        completed=completed
    )

    if not success:
        raise HTTPException(status_code=404, detail="Quote not found")

    return {"quote_id": quote_id, "status": request.status}
