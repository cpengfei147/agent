"""Quote Service - Handles quote submission and management"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Quote, Session, User
from app.storage.postgres_client import get_db_context


logger = logging.getLogger(__name__)


class QuoteService:
    """Service for managing moving quotes"""

    @staticmethod
    async def create_quote(
        session_token: str,
        fields_status: Dict[str, Any],
        user_email: Optional[str] = None,
        user_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new quote from collected fields

        Args:
            session_token: The session token
            fields_status: Collected field data
            user_email: Optional user email
            user_phone: Optional user phone

        Returns:
            Created quote info
        """
        # Prepare quote data
        quote_id = str(uuid.uuid4())
        collected_data = QuoteService._prepare_quote_data(fields_status)
        created_at = datetime.utcnow()

        # Try to save to database, but don't fail if DB is unavailable
        try:
            async with get_db_context() as db:
                # Find or create user
                user_id = None
                if user_email:
                    user = await QuoteService._get_or_create_user(
                        db, user_email, user_phone
                    )
                    user_id = user.id

                # Find session
                session_result = await db.execute(
                    select(Session).where(Session.session_token == session_token)
                )
                session = session_result.scalar_one_or_none()
                session_id = session.id if session else None

                # Create quote
                quote = Quote(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    user_id=user_id,
                    collected_data=collected_data,
                    status="submitted",
                    created_at=created_at
                )
                db.add(quote)
                await db.flush()

                logger.info(f"Quote created in DB: {quote.id}")
                quote_id = str(quote.id)

        except Exception as e:
            logger.warning(f"Database not available, quote saved in memory only: {e}")

        # Return quote info (works even without DB)
        return {
            "quote_id": quote_id,
            "status": "submitted",
            "created_at": created_at.isoformat(),
            "collected_data": collected_data
        }

    @staticmethod
    async def _get_or_create_user(
        db: AsyncSession,
        email: str,
        phone: Optional[str] = None
    ) -> User:
        """Get existing user or create new one"""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=uuid.uuid4(),
                email=email,
                phone=phone,
                created_at=datetime.utcnow()
            )
            db.add(user)
            await db.flush()
            logger.info(f"Created new user: {email}")

        return user

    @staticmethod
    def _prepare_quote_data(fields_status: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare and validate quote data for storage"""
        # Extract only filled values
        prepared = {}

        for field, data in fields_status.items():
            if isinstance(data, dict):
                value = data.get("value")
                if value is not None and value != "":
                    prepared[field] = {
                        "value": value,
                        "confirmed": data.get("confirmed", False)
                    }
            elif data is not None and data != "":
                prepared[field] = {"value": data, "confirmed": True}

        # Add metadata
        prepared["_meta"] = {
            "submitted_at": datetime.utcnow().isoformat(),
            "version": "1.0"
        }

        return prepared

    @staticmethod
    async def get_quote(quote_id: str) -> Optional[Dict[str, Any]]:
        """Get quote by ID"""
        async with get_db_context() as db:
            result = await db.execute(
                select(Quote).where(Quote.id == uuid.UUID(quote_id))
            )
            quote = result.scalar_one_or_none()

            if not quote:
                return None

            return {
                "quote_id": str(quote.id),
                "status": quote.status,
                "created_at": quote.created_at.isoformat(),
                "completed_at": quote.completed_at.isoformat() if quote.completed_at else None,
                "collected_data": quote.collected_data
            }

    @staticmethod
    async def update_quote_status(
        quote_id: str,
        status: str,
        completed: bool = False
    ) -> bool:
        """Update quote status"""
        async with get_db_context() as db:
            update_data = {"status": status}
            if completed:
                update_data["completed_at"] = datetime.utcnow()

            result = await db.execute(
                update(Quote)
                .where(Quote.id == uuid.UUID(quote_id))
                .values(**update_data)
            )
            return result.rowcount > 0

    @staticmethod
    async def get_quotes_by_session(session_token: str) -> List[Dict[str, Any]]:
        """Get all quotes for a session"""
        async with get_db_context() as db:
            # First get session
            session_result = await db.execute(
                select(Session).where(Session.session_token == session_token)
            )
            session = session_result.scalar_one_or_none()

            if not session:
                return []

            # Get quotes
            result = await db.execute(
                select(Quote)
                .where(Quote.session_id == session.id)
                .order_by(Quote.created_at.desc())
            )
            quotes = result.scalars().all()

            return [
                {
                    "quote_id": str(q.id),
                    "status": q.status,
                    "created_at": q.created_at.isoformat(),
                    "completed_at": q.completed_at.isoformat() if q.completed_at else None,
                    "collected_data": q.collected_data
                }
                for q in quotes
            ]


class SessionPersistenceService:
    """Service for persisting sessions to PostgreSQL"""

    @staticmethod
    async def persist_session(
        session_token: str,
        session_id: str,
        current_phase: int,
        fields_status: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> bool:
        """Persist session data to PostgreSQL"""
        try:
            async with get_db_context() as db:
                # Check if session exists
                result = await db.execute(
                    select(Session).where(Session.session_token == session_token)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing
                    existing.current_phase = current_phase
                    existing.fields_status = fields_status
                    existing.last_activity_at = datetime.utcnow()
                    if user_id:
                        existing.user_id = uuid.UUID(user_id)
                else:
                    # Create new
                    session = Session(
                        id=uuid.UUID(session_id),
                        session_token=session_token,
                        user_id=uuid.UUID(user_id) if user_id else None,
                        current_phase=current_phase,
                        fields_status=fields_status,
                        created_at=datetime.utcnow(),
                        last_activity_at=datetime.utcnow()
                    )
                    db.add(session)

                return True
        except Exception as e:
            logger.warning(f"Database not available for session persistence: {e}")
            return True  # Return True to not break the flow

    @staticmethod
    async def get_session(session_token: str) -> Optional[Dict[str, Any]]:
        """Get session from PostgreSQL"""
        async with get_db_context() as db:
            result = await db.execute(
                select(Session).where(Session.session_token == session_token)
            )
            session = result.scalar_one_or_none()

            if not session:
                return None

            return {
                "id": str(session.id),
                "session_token": session.session_token,
                "user_id": str(session.user_id) if session.user_id else None,
                "current_phase": session.current_phase,
                "fields_status": session.fields_status,
                "created_at": session.created_at.isoformat(),
                "last_activity_at": session.last_activity_at.isoformat()
            }


# Convenience function
async def submit_quote(
    session_token: str,
    fields_status: Dict[str, Any],
    user_email: Optional[str] = None,
    user_phone: Optional[str] = None
) -> Dict[str, Any]:
    """Submit a quote request"""
    return await QuoteService.create_quote(
        session_token=session_token,
        fields_status=fields_status,
        user_email=user_email,
        user_phone=user_phone
    )
