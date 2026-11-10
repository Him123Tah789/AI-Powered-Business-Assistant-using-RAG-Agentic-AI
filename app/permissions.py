import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

class PermissionManager:
    """
    Manages and verifies user permissions for restricted system operations.
    Standard Permissions:
    - profile.view: Retrieve user profile
    - profile.update: Modify user profile
    - service.view: View service catalogue records
    - service.create: Create new service offerings
    - service.update: Update service details
    """

    PERMISSION_PROFILE_VIEW = "profile.view"
    PERMISSION_PROFILE_UPDATE = "profile.update"
    PERMISSION_SERVICE_VIEW = "service.view"
    PERMISSION_SERVICE_CREATE = "service.create"
    PERMISSION_SERVICE_UPDATE = "service.update"

    # Pre-defined user roles
    DEFAULT_ROLES = {
        "admin": [
            PERMISSION_PROFILE_VIEW,
            PERMISSION_PROFILE_UPDATE,
            PERMISSION_SERVICE_VIEW,
            PERMISSION_SERVICE_CREATE,
            PERMISSION_SERVICE_UPDATE,
        ],
        "authorized_user": [
            PERMISSION_PROFILE_VIEW,
            PERMISSION_PROFILE_UPDATE,
            PERMISSION_SERVICE_VIEW,
        ],
        "read_only_user": [
            PERMISSION_PROFILE_VIEW,
            PERMISSION_SERVICE_VIEW,
        ],
        "unauthorized_user": []
    }

    def __init__(self):
        # Audit log for permission decisions
        self.audit_log: List[Dict[str, Any]] = []

    def check_permission(
        self,
        required_permission: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Verifies if the current user has the required permission.
        user_context can contain:
        - permissions: List[str]
        - role: str
        - can_update_profile: bool (direct convenience toggle for scenario testing)
        """
        if not user_context:
            user_context = {}

        # 1. Direct permission override flag if provided (e.g. for Scenario 4 vs 5 testing)
        if required_permission == self.PERMISSION_PROFILE_UPDATE:
            if "can_update_profile" in user_context:
                allowed = bool(user_context["can_update_profile"])
                msg = "Permission granted for profile update." if allowed else (
                    "Permission Denied: User account is not authorized to update profile information (lacks 'profile.update' permission)."
                )
                self._record_audit(user_context, required_permission, allowed, msg)
                return allowed, msg

        # 2. Check explicit permissions list
        user_perms = user_context.get("permissions")
        if user_perms is not None:
            if isinstance(user_perms, list) and required_permission in user_perms:
                msg = f"Permission granted for '{required_permission}'."
                self._record_audit(user_context, required_permission, True, msg)
                return True, msg
            else:
                msg = f"Permission Denied: Missing required permission '{required_permission}'."
                self._record_audit(user_context, required_permission, False, msg)
                return False, msg

        # 3. Check role-based permissions
        role = user_context.get("role", "authorized_user")
        allowed_perms = self.DEFAULT_ROLES.get(role, self.DEFAULT_ROLES["authorized_user"])
        if required_permission in allowed_perms:
            msg = f"Permission granted for '{required_permission}' via role '{role}'."
            self._record_audit(user_context, required_permission, True, msg)
            return True, msg

        msg = f"Permission Denied: Role '{role}' does not possess permission '{required_permission}'."
        self._record_audit(user_context, required_permission, False, msg)
        return False, msg

    def _record_audit(self, context: Dict[str, Any], permission: str, granted: bool, reason: str):
        from datetime import datetime
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": context.get("user_id", "authenticated_user"),
            "permission": permission,
            "decision": "GRANTED" if granted else "DENIED",
            "reason": reason
        }
        self.audit_log.append(entry)
        if granted:
            logger.info(f"AUDIT [PERMISSION GRANTED]: {entry}")
        else:
            logger.warning(f"AUDIT [PERMISSION DENIED]: {entry}")

permission_manager = PermissionManager()

