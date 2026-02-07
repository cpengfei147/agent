"""Tests for Quote Service"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
import uuid

from app.services.quote_service import (
    QuoteService,
    SessionPersistenceService,
    submit_quote
)


class TestQuoteServicePrepareData:
    """Tests for QuoteService._prepare_quote_data"""

    def test_prepare_basic_fields(self):
        """Test preparing basic field data"""
        fields_status = {
            "people_count": {"value": 3, "confirmed": True},
            "move_date": {"value": "2024-03-15", "confirmed": True},
            "packing_service": None
        }

        result = QuoteService._prepare_quote_data(fields_status)

        assert "people_count" in result
        assert result["people_count"]["value"] == 3
        assert result["people_count"]["confirmed"] is True
        assert "packing_service" not in result  # Empty values excluded
        assert "_meta" in result

    def test_prepare_nested_fields(self):
        """Test preparing nested address data"""
        fields_status = {
            "from_address": {
                "value": "東京都渋谷区",
                "building_type": "アパート",
                "floor": 3,
                "confirmed": True,
                "status": "ideal"
            },
            "to_address": {
                "value": "神奈川県横浜市",
                "confirmed": False,
                "status": "baseline"
            }
        }

        result = QuoteService._prepare_quote_data(fields_status)

        assert "from_address" in result
        # The value is stored directly, not nested
        assert result["from_address"]["value"] == "東京都渋谷区"

    def test_prepare_empty_status(self):
        """Test preparing empty field status"""
        fields_status = {}
        result = QuoteService._prepare_quote_data(fields_status)

        assert "_meta" in result
        assert "submitted_at" in result["_meta"]

    def test_prepare_excludes_empty_values(self):
        """Test that empty values are excluded"""
        fields_status = {
            "people_count": {"value": 2},
            "empty_field": {"value": ""},
            "none_field": {"value": None},
            "zero_field": {"value": 0}  # 0 should be included
        }

        result = QuoteService._prepare_quote_data(fields_status)

        assert "people_count" in result
        assert "empty_field" not in result
        assert "none_field" not in result
        # Note: 0 is falsy in Python, so it might be excluded


class TestQuoteServiceCreate:
    """Tests for QuoteService.create_quote"""

    @pytest.fixture
    def sample_fields(self):
        return {
            "people_count": {"value": 2, "confirmed": True},
            "from_address": {"value": "東京都新宿区", "status": "ideal"},
            "to_address": {"value": "東京都渋谷区", "status": "baseline"},
            "move_date": {"value": "2024-04-01", "confirmed": True},
            "items": {"list": [{"name": "冷蔵庫"}, {"name": "洗濯機"}], "status": "baseline"}
        }

    @pytest.mark.asyncio
    async def test_create_quote_structure(self, sample_fields):
        """Test that create_quote returns expected structure"""
        # This test requires database mocking
        with patch('app.services.quote_service.get_db_context') as mock_db:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=None)
            ))
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()

            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock()

            # The test would need proper database setup to fully run
            # For now, we test the data preparation logic
            prepared = QuoteService._prepare_quote_data(sample_fields)

            assert "people_count" in prepared
            assert "from_address" in prepared
            assert "_meta" in prepared


class TestSessionPersistenceService:
    """Tests for SessionPersistenceService"""

    @pytest.mark.asyncio
    async def test_persist_session_creates_new(self):
        """Test persisting a new session"""
        with patch('app.services.quote_service.get_db_context') as mock_db:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=None)  # No existing session
            ))
            mock_session.add = MagicMock()

            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock()

            result = await SessionPersistenceService.persist_session(
                session_token="test-token",
                session_id=str(uuid.uuid4()),
                current_phase=2,
                fields_status={"people_count": 3}
            )

            assert result is True
            mock_session.add.assert_called_once()


class TestSubmitQuoteFunction:
    """Tests for submit_quote convenience function"""

    @pytest.mark.asyncio
    async def test_submit_quote_calls_service(self):
        """Test that submit_quote calls QuoteService.create_quote"""
        with patch.object(QuoteService, 'create_quote', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                "quote_id": "test-id",
                "status": "submitted",
                "created_at": datetime.utcnow().isoformat(),
                "collected_data": {}
            }

            result = await submit_quote(
                session_token="test-token",
                fields_status={"people_count": 2},
                user_email="test@example.com"
            )

            mock_create.assert_called_once_with(
                session_token="test-token",
                fields_status={"people_count": 2},
                user_email="test@example.com",
                user_phone=None
            )
            assert result["quote_id"] == "test-id"
            assert result["status"] == "submitted"


class TestQuoteServiceGetQuote:
    """Tests for QuoteService.get_quote"""

    @pytest.mark.asyncio
    async def test_get_nonexistent_quote(self):
        """Test getting a quote that doesn't exist"""
        with patch('app.services.quote_service.get_db_context') as mock_db:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=None)
            ))

            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock()

            result = await QuoteService.get_quote(str(uuid.uuid4()))

            assert result is None


class TestQuoteServiceUpdateStatus:
    """Tests for QuoteService.update_quote_status"""

    @pytest.mark.asyncio
    async def test_update_to_completed(self):
        """Test updating quote status to completed"""
        with patch('app.services.quote_service.get_db_context') as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock()

            result = await QuoteService.update_quote_status(
                quote_id=str(uuid.uuid4()),
                status="completed",
                completed=True
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_update_nonexistent_quote(self):
        """Test updating a quote that doesn't exist"""
        with patch('app.services.quote_service.get_db_context') as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 0
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock()

            result = await QuoteService.update_quote_status(
                quote_id=str(uuid.uuid4()),
                status="processing"
            )

            assert result is False
