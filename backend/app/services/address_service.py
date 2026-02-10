"""Address verification service using Google Maps API

Note: Address parsing is done by Router (LLM).
This service only verifies and enriches addresses using Google Maps API.
"""

import asyncio
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
    # 新增：多个候选地址
    multiple_results: List[Dict[str, Any]] = None
    # 新增：验证状态 - verified(成功), needs_selection(多个结果), needs_more_info(信息不足), failed(失败)
    verification_status: str = "pending"

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []
        if self.multiple_results is None:
            self.multiple_results = []

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
            "suggestions": self.suggestions,
            "multiple_results": self.multiple_results,
            "verification_status": self.verification_status
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
                import requests
                import os

                # Create a session with explicit HTTP proxy (avoid SOCKS proxy issues)
                session = requests.Session()
                session.trust_env = False  # Don't use environment proxy settings

                # Use HTTP proxy if available (SOCKS proxy causes issues)
                http_proxy = os.environ.get('http_proxy')
                if http_proxy and not http_proxy.startswith('socks'):
                    session.proxies = {
                        'http': http_proxy,
                        'https': http_proxy
                    }
                    logger.info(f"Using HTTP proxy for Google Maps: {http_proxy}")

                self._client = googlemaps.Client(
                    key=self.api_key,
                    requests_session=session,
                    timeout=10  # Add timeout to avoid hanging
                )
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
        """Verify address using Google Maps Geocoding API

        Returns different verification_status based on result:
        - "verified": 成功找到唯一地址且有邮编
        - "needs_selection": 找到多个候选地址，需要用户选择
        - "needs_more_info": 地址信息不足（无邮编），需要补充
        - "failed": 完全无法识别
        """
        client = self._get_client()
        if not client:
            local_result.verification_status = "no_api"
            return local_result

        try:
            # Geocode the address - run in thread pool to avoid blocking
            geocode_result = await asyncio.to_thread(
                client.geocode,
                address,
                region=region,
                language="ja"
            )

            if not geocode_result:
                return AddressVerificationResult(
                    is_valid=False,
                    error="地址无法识别，请检查输入是否正确",
                    suggestions=["请提供更详细的地址", "可以尝试输入邮编"],
                    verification_status="failed"
                )

            # 如果有多个结果，返回候选列表让用户选择
            if len(geocode_result) > 1:
                multiple_results = []
                for idx, r in enumerate(geocode_result[:5]):  # 最多5个候选
                    components = self._parse_google_components(r.get("address_components", []))
                    location = r.get("geometry", {}).get("location", {})
                    multiple_results.append({
                        "index": idx,
                        "formatted_address": r.get("formatted_address"),
                        "postal_code": components.get("postal_code"),
                        "prefecture": components.get("prefecture"),
                        "city": components.get("city"),
                        "district": components.get("district"),
                        "lat": location.get("lat"),
                        "lng": location.get("lng")
                    })

                return AddressVerificationResult(
                    is_valid=True,
                    formatted_address=None,  # 多个结果时不设置
                    multiple_results=multiple_results,
                    verification_status="needs_selection",
                    suggestions=["请从以下地址中选择正确的一个"]
                )

            # 只有一个结果
            result = geocode_result[0]
            components = self._parse_google_components(result.get("address_components", []))
            location = result.get("geometry", {}).get("location", {})

            # 检查是否有邮编（搬出地址必须有邮编）
            postal_code = components.get("postal_code")
            if not postal_code:
                return AddressVerificationResult(
                    is_valid=True,
                    formatted_address=result.get("formatted_address"),
                    prefecture=components.get("prefecture"),
                    city=components.get("city"),
                    district=components.get("district"),
                    lat=location.get("lat"),
                    lng=location.get("lng"),
                    confidence=0.6,
                    verification_status="needs_more_info",
                    suggestions=["地址已识别，但缺少邮编信息", "请提供邮编或更详细的地址"]
                )

            # 成功验证
            return AddressVerificationResult(
                is_valid=True,
                formatted_address=result.get("formatted_address"),
                postal_code=postal_code,
                prefecture=components.get("prefecture"),
                city=components.get("city"),
                district=components.get("district"),
                lat=location.get("lat"),
                lng=location.get("lng"),
                confidence=0.9 if result.get("geometry", {}).get("location_type") == "ROOFTOP" else 0.7,
                verification_status="verified"
            )

        except Exception as e:
            logger.error(f"Google geocoding failed: {e}")
            local_result.verification_status = "api_error"
            local_result.error = f"地址验证服务暂时不可用: {str(e)}"
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
