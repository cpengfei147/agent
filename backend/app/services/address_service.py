"""Address verification service using Google Maps API

Note: Address parsing is done by Router (LLM).
This service only verifies and enriches addresses using Google Maps API.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AddressVerificationResult:
    """Address verification result"""
    is_valid: bool
    formatted_address: Optional[str] = None
    postal_code: Optional[str] = None
    prefecture: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    confidence: float = 0.0
    error: Optional[str] = None
    suggestions: List[str] = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "formatted_address": self.formatted_address,
            "postal_code": self.postal_code,
            "prefecture": self.prefecture,
            "city": self.city,
            "district": self.district,
            "lat": self.lat,
            "lng": self.lng,
            "confidence": self.confidence,
            "error": self.error,
            "suggestions": self.suggestions
        }


class AddressService:
    """Address verification and geocoding service"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        """Lazy load Google Maps client"""
        if self._client is None and self.api_key:
            try:
                import googlemaps
                self._client = googlemaps.Client(key=self.api_key)
            except ImportError:
                logger.warning("googlemaps package not installed")
            except Exception as e:
                logger.error(f"Failed to initialize Google Maps client: {e}")
        return self._client

    async def verify_address(
        self,
        address: str,
        region: str = "jp"
    ) -> AddressVerificationResult:
        """
        Verify and geocode an address

        Args:
            address: Address string to verify
            region: Region bias (default: Japan)

        Returns:
            AddressVerificationResult with parsed components
        """
        if not address or not address.strip():
            return AddressVerificationResult(
                is_valid=False,
                error="地址为空"
            )

        # First try local parsing
        local_result = self._parse_address_locally(address)

        # If we have API key, enhance with Google Maps
        client = self._get_client()
        if client:
            try:
                return await self._verify_with_google(address, region, local_result)
            except Exception as e:
                logger.error(f"Google Maps API error: {e}")
                # Fall back to local result
                return local_result

        return local_result

    async def _verify_with_google(
        self,
        address: str,
        region: str,
        local_result: AddressVerificationResult
    ) -> AddressVerificationResult:
        """Verify address using Google Maps Geocoding API"""
        client = self._get_client()
        if not client:
            return local_result

        try:
            # Geocode the address
            geocode_result = client.geocode(
                address,
                region=region,
                language="ja"
            )

            if not geocode_result:
                return AddressVerificationResult(
                    is_valid=False,
                    error="地址无法识别",
                    suggestions=["请检查地址是否正确"]
                )

            # Use the first result
            result = geocode_result[0]

            # Parse address components
            components = self._parse_google_components(result.get("address_components", []))

            # Get location
            location = result.get("geometry", {}).get("location", {})

            return AddressVerificationResult(
                is_valid=True,
                formatted_address=result.get("formatted_address"),
                postal_code=components.get("postal_code"),
                prefecture=components.get("prefecture"),
                city=components.get("city"),
                district=components.get("district"),
                lat=location.get("lat"),
                lng=location.get("lng"),
                confidence=0.9 if result.get("geometry", {}).get("location_type") == "ROOFTOP" else 0.7
            )

        except Exception as e:
            logger.error(f"Google geocoding failed: {e}")
            return local_result

    def _parse_google_components(self, components: List[Dict]) -> Dict[str, str]:
        """Parse Google Maps address components"""
        result = {}

        for comp in components:
            types = comp.get("types", [])
            long_name = comp.get("long_name", "")

            if "postal_code" in types:
                result["postal_code"] = long_name
            elif "administrative_area_level_1" in types:
                result["prefecture"] = long_name
            elif "locality" in types:
                result["city"] = long_name
            elif "sublocality_level_1" in types or "ward" in types:
                result["district"] = long_name
            elif "sublocality" in types and "district" not in result:
                result["district"] = long_name

        return result

    def _parse_address_locally(self, address: str) -> AddressVerificationResult:
        """
        Simple local address validation (no API, no regex parsing).

        Note: Detailed parsing (postal_code, city, district) is done by Router (LLM).
        This method only does basic validation by checking for prefecture names.
        """
        result = AddressVerificationResult(is_valid=True, confidence=0.5)

        address = address.strip()
        result.formatted_address = address

        if not address:
            result.is_valid = False
            result.error = "地址为空"
            result.confidence = 0.0
            return result

        # Japanese prefectures - simple string matching
        prefectures = [
            "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
            "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
            "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
            "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
            "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
            "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
            "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
        ]

        # Check for prefecture (simple string contains check)
        for pref in prefectures:
            if pref in address:
                result.prefecture = pref
                result.confidence = 0.6
                break

        # Check for common address markers (simple string contains check)
        address_markers = ["市", "区", "町", "村", "丁目", "番地"]
        has_marker = any(marker in address for marker in address_markers)

        if has_marker:
            result.confidence += 0.2

        # Address is considered valid if it has some content
        # Detailed parsing is done by Router (LLM)
        result.is_valid = True

        return result

    async def get_distance(
        self,
        origin: str,
        destination: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get distance and duration between two addresses

        Returns:
            Dict with distance_km, duration_minutes, or None if failed
        """
        client = self._get_client()
        if not client:
            return None

        try:
            result = client.distance_matrix(
                origins=[origin],
                destinations=[destination],
                mode="driving",
                language="ja"
            )

            if result["status"] == "OK":
                element = result["rows"][0]["elements"][0]
                if element["status"] == "OK":
                    return {
                        "distance_km": element["distance"]["value"] / 1000,
                        "distance_text": element["distance"]["text"],
                        "duration_minutes": element["duration"]["value"] / 60,
                        "duration_text": element["duration"]["text"]
                    }

        except Exception as e:
            logger.error(f"Distance calculation failed: {e}")

        return None

    async def autocomplete(
        self,
        input_text: str,
        session_token: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Get address autocomplete suggestions

        Returns:
            List of suggestions with description and place_id
        """
        client = self._get_client()
        if not client:
            return []

        try:
            result = client.places_autocomplete(
                input_text,
                components={"country": "jp"},
                language="ja",
                session_token=session_token
            )

            return [
                {
                    "description": item["description"],
                    "place_id": item["place_id"]
                }
                for item in result[:5]  # Limit to 5 suggestions
            ]

        except Exception as e:
            logger.error(f"Autocomplete failed: {e}")
            return []


# Global service instance
_address_service: Optional[AddressService] = None


def get_address_service() -> AddressService:
    """Get global address service instance"""
    global _address_service
    if _address_service is None:
        from app.config import settings
        _address_service = AddressService(api_key=settings.google_maps_api_key)
    return _address_service
