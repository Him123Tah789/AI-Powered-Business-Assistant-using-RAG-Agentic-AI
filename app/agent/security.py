import re
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class SecurityGuard:
    """
    Guards against prompt injection, jailbreaking, credential harvesting,
    and unauthorized operation attempts.
    """

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"reveal\s+(your\s+)?(api|system|credential|token|key|secret|prompt)",
        r"expose\s+(your\s+)?(api|system|credential|token|key|secret)",
        r"what\s+is\s+your\s+(api\s+key|system\s+prompt|gemini\s+key|bearer\s+token)",
        r"show\s+me\s+(the\s+)?(api\s+key|bearer\s+token|secret|credentials)",
        r"without\s+(checking|verifying)\s+permission",
        r"bypass\s+(all\s+)?(permission|authorization|security|check)s?",
        r"override\s+(all\s+)?(permission|security|authorization)",
        r"you\s+are\s+now\s+in\s+dan\s+mode",
        r"jailbreak",
        r"pretend\s+you\s+have\s+no\s+rules"
    ]

    CREDENTIAL_PATTERNS = [
        r"AQ\.[A-Za-z0-9_-]{30,}",             # Gemini API key pattern
        r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", # JWT Bearer token pattern
        r"Test\?123",                          # Default credential
    ]

    def inspect_input(self, user_message: str) -> Tuple[bool, str]:
        """
        Scans incoming user message for malicious injection patterns.
        Returns (is_injection_detected, warning_message).
        """
        msg_clean = user_message.strip()

        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, msg_clean, re.IGNORECASE):
                logger.warning(f"SECURITY ALERT: Prompt injection attempt detected. Pattern: '{pattern}' in: '{user_message}'")
                return True, (
                    "Security Alert: Malicious prompt injection or credential access attempt detected. "
                    "In accordance with security policy (SRV-POL-001 Section 5.3 & 5.4), system credentials "
                    "are confidential and protected, and all authorization controls and permission verifications "
                    "remain strictly enforced. The requested override has been rejected."
                )

        return False, ""

    def sanitize_output(self, text: str) -> str:
        """
        Masks any potential credentials or sensitive tokens from model outputs.
        """
        sanitized = text
        for pattern in self.CREDENTIAL_PATTERNS:
            sanitized = re.sub(pattern, "[PROTECTED_CREDENTIAL_REDACTED]", sanitized)
        return sanitized

security_guard = SecurityGuard()

