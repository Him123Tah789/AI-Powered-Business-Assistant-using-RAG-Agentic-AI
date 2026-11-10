import re
import logging
from typing import Dict, Any, Optional
from app.api_client import api_client
from app.permissions import permission_manager
from app.rag.policy_engine import policy_engine

logger = logging.getLogger(__name__)

# Gemini Function Declarations Schema
TOOL_DECLARATIONS = [
    {
        "name": "search_policy",
        "description": "Searches the official Service Management & Creation Policy (SRV-POL-001) for rules, maximum prices, categories, requirements, or permissions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "The specific policy question or topic to search for."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_user_profile",
        "description": "Retrieves the authenticated user's profile information from the business management system.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "update_user_profile",
        "description": "Updates a specific field in the authenticated user's profile (e.g., phone number, first name, last name). Requires 'profile.update' permission.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "field": {
                    "type": "STRING",
                    "description": "The profile field to update, e.g. 'phone' or 'name'."
                },
                "value": {
                    "type": "STRING",
                    "description": "The new value for the specified field."
                }
            },
            "required": ["field", "value"]
        }
    }
]

class ToolExecutor:
    """
    Executes tool calls with strict permission validation and error handling.
    """

    def execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
        auth_token: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Routes and executes the specified tool.
        """
        if not user_context:
            user_context = {}

        if tool_name == "search_policy":
            query = args.get("query", "")
            return self._execute_search_policy(query)

        elif tool_name == "get_user_profile":
            return self._execute_get_profile(auth_token, user_context)

        elif tool_name == "update_user_profile":
            field = args.get("field")
            value = args.get("value")
            return self._execute_update_profile(field, value, auth_token, user_context)

        else:
            return {
                "success": False,
                "error": f"Unknown tool '{tool_name}'."
            }

    def _execute_search_policy(self, query: str) -> Dict[str, Any]:
        """
        Executes policy RAG retrieval.
        """
        result = policy_engine.query(query)
        return {
            "success": True,
            "tool": "search_policy",
            "is_found": result.get("is_found", False),
            "answer": result.get("answer", ""),
            "sources": result.get("sources", [])
        }

    def _execute_get_profile(
        self,
        auth_token: Optional[str],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieves the authenticated user profile after verifying authentication and permissions.
        """
        if not auth_token:
            return {
                "success": False,
                "tool": "get_user_profile",
                "error": "Authentication required. Please log in or provide a valid Bearer token.",
                "status_code": 401
            }

        # Check permission
        has_perm, reason = permission_manager.check_permission(
            permission_manager.PERMISSION_PROFILE_VIEW,
            user_context
        )
        if not has_perm:
            return {
                "success": False,
                "tool": "get_user_profile",
                "error": reason,
                "permission_denied": True
            }

        # Call existing REST API
        api_res = api_client.get_profile(auth_token)
        if not api_res.get("success"):
            return {
                "success": False,
                "tool": "get_user_profile",
                "error": api_res.get("error", "Failed to retrieve profile from application API.")
            }

        data = api_res.get("data", {})
        account_info = data.get("account_info", {})
        contact_info = data.get("contact_info", {})
        settings_info = data.get("settings", {})
        emails = data.get("emails", [])
        primary_email = emails[0].get("email") if emails else ""

        formatted_profile = {
            "account_id": account_info.get("account_id"),
            "account_number": account_info.get("account_number"),
            "full_name": account_info.get("full_name") or f"{account_info.get('first_name', '')} {account_info.get('last_name', '')}".strip(),
            "first_name": account_info.get("first_name"),
            "last_name": account_info.get("last_name"),
            "email": primary_email,
            "phone": contact_info.get("cellular_phone_1") or contact_info.get("office_phone") or "N/A",
            "priority": settings_info.get("priority", "VIP"),
            "status": settings_info.get("status_label", "ACTIVE")
        }

        return {
            "success": True,
            "tool": "get_user_profile",
            "profile": formatted_profile,
            "raw": data
        }

    def _execute_update_profile(
        self,
        field: Optional[str],
        value: Optional[str],
        auth_token: Optional[str],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Updates profile information.
        Enforces input validation and strict permission checks.
        """
        # 1. Missing information check (Scenario 06)
        if not field or not str(field).strip() or value is None or not str(value).strip():
            return {
                "success": False,
                "tool": "update_user_profile",
                "missing_information": True,
                "message": (
                    "Please specify which profile field you would like to update "
                    "(e.g., phone number or name) and provide the new value."
                )
            }

        field_clean = str(field).strip().lower()
        val_clean = str(value).strip()

        # 2. Input validation
        if field_clean in ("phone", "phone_number", "cellular_phone", "cellular_phone_1"):
            digits = re.sub(r"[^\d+]", "", val_clean)
            if len(digits) < 7:
                return {
                    "success": False,
                    "tool": "update_user_profile",
                    "error": f"Invalid phone number format: '{val_clean}'. Please provide a valid telephone number."
                }

        # 3. Permission verification (Scenario 04 vs Scenario 05)
        has_perm, reason = permission_manager.check_permission(
            permission_manager.PERMISSION_PROFILE_UPDATE,
            user_context
        )
        if not has_perm:
            logger.warning(f"BLOCKED unauthorized profile update attempt: {reason}")
            return {
                "success": False,
                "tool": "update_user_profile",
                "permission_denied": True,
                "error": reason,
                "message": (
                    "Permission Denied: Your account does not have permission to update profile information "
                    "('profile.update' permission required). The operation was rejected and the update API was not called."
                )
            }

        # 4. Authentication token check
        if not auth_token:
            return {
                "success": False,
                "tool": "update_user_profile",
                "error": "Authentication token missing. Please log in first.",
                "status_code": 401
            }

        # 5. Execute Update Profile API (Scenario 04)
        payload = {field_clean: val_clean}
        api_res = api_client.update_profile(auth_token, payload)

        if api_res.get("success"):
            return {
                "success": True,
                "tool": "update_user_profile",
                "message": f"Successfully updated your {field_clean} to '{val_clean}'.",
                "field": field_clean,
                "new_value": val_clean,
                "api_response": api_res.get("data")
            }
        else:
            return {
                "success": False,
                "tool": "update_user_profile",
                "error": api_res.get("error", "Profile update failed on the application server.")
            }

tool_executor = ToolExecutor()

