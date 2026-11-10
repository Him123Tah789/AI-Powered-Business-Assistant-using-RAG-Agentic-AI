import json
import logging
from typing import Dict, Any, Optional
import requests
from app.config import settings

logger = logging.getLogger(__name__)

class PassengerApiClient:
    """
    Client for interacting with the existing Passenger App REST APIs.
    Endpoints:
    - POST /login
    - GET /profile
    - PUT /profile
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.PASSENGER_API_BASE_URL).rstrip("/")

    def login(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        company_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Authenticates against the passenger login API and retrieves the access token.
        """
        url = f"{self.base_url}/login"
        payload = {
            "email": email or settings.DEFAULT_USER_EMAIL,
            "password": password or settings.DEFAULT_USER_PASSWORD,
            "company_id": company_id or settings.DEFAULT_COMPANY_ID,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=12)
            data = response.json()
            if response.status_code == 200 and data.get("status") or data.get("success"):
                token = data.get("data", {}).get("access_token") or data.get("data", {}).get("token")
                return {
                    "success": True,
                    "token": token,
                    "user": data.get("data", {}).get("passenger") or data.get("data", {}).get("user"),
                    "raw": data
                }
            return {
                "success": False,
                "error": data.get("message", "Login failed"),
                "status_code": response.status_code
            }
        except Exception as e:
            logger.error(f"Login request failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "status_code": 500
            }

    def get_profile(self, token: str) -> Dict[str, Any]:
        """
        Retrieves the authenticated user's profile information.
        Requires a valid Bearer token.
        """
        if not token:
            return {
                "success": False,
                "error": "Authentication token missing. Please authenticate first.",
                "status_code": 401
            }

        url = f"{self.base_url}/profile"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        try:
            response = requests.get(url, headers=headers, timeout=12)
            try:
                data = response.json()
            except Exception:
                data = {"raw_text": response.text}

            if response.status_code == 200:
                profile_data = data.get("data", {})
                return {
                    "success": True,
                    "data": profile_data,
                    "message": data.get("message", "Profile retrieved successfully")
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": data.get("message", "Unauthorized. Invalid or expired token."),
                    "status_code": 401
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message", f"Failed to retrieve profile: HTTP {response.status_code}"),
                    "status_code": response.status_code
                }
        except Exception as e:
            logger.error(f"Get profile request failed: {e}")
            return {
                "success": False,
                "error": f"Connection error while retrieving profile: {str(e)}",
                "status_code": 500
            }

    def update_profile(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates the authenticated user's profile information.
        Maps common fields (phone, name) to API schema.
        """
        if not token:
            return {
                "success": False,
                "error": "Authentication token missing. Operation rejected.",
                "status_code": 401
            }

        url = f"{self.base_url}/profile"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Normalize payload fields
        normalized = {}
        for k, v in payload.items():
            k_lower = k.lower().strip()
            if k_lower in ("phone", "phone_number", "mobile", "cellular_phone", "cellular_phone_1"):
                normalized["cellular_phone_1"] = str(v).strip()
            elif k_lower in ("first_name", "firstname"):
                normalized["first_name"] = str(v).strip()
            elif k_lower in ("last_name", "lastname"):
                normalized["last_name"] = str(v).strip()
            elif k_lower in ("name", "full_name"):
                parts = str(v).strip().split(" ", 1)
                normalized["first_name"] = parts[0]
                normalized["last_name"] = parts[1] if len(parts) > 1 else ""
            else:
                normalized[k] = v

        try:
            response = requests.put(url, json=normalized, headers=headers, timeout=12)
            try:
                data = response.json()
            except Exception:
                data = {"raw_text": response.text}

            if response.status_code == 200 and (data.get("status") is True or data.get("success") is True):
                return {
                    "success": True,
                    "message": data.get("message", "Profile updated successfully"),
                    "data": data.get("data", {}),
                    "updated_fields": normalized
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "Unauthorized request from backend API.",
                    "status_code": 401
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message", f"Update failed: HTTP {response.status_code}"),
                    "status_code": response.status_code,
                    "details": data
                }
        except Exception as e:
            logger.error(f"Update profile request failed: {e}")
            return {
                "success": False,
                "error": f"Connection error while updating profile: {str(e)}",
                "status_code": 500
            }

api_client = PassengerApiClient()

