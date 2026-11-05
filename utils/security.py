"""
RouteWise AI – Security Utilities
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict


# ── Prompt injection detection patterns ──────────────────────────────────────
# Covers common jailbreak and role-override vectors.
# Patterns are matched case-insensitively.
_INJECTION_PATTERNS = re.compile(
    r"("
    # Classic override instructions
    r"ignore (previous|all|prior) instructions?|"
    r"disregard\s+(previous|all|prior|the|any|safety|filter|restriction|instruction)|"
    r"forget (all|everything|previous|prior)|"
    # System/role manipulation
    r"system\s*prompt|"
    r"system\s*:|"                        # "system:" prefix used in chat templates
    r"you are now\b|"
    r"act\s+as\b|"                        # "act as a...", "act as if..."
    r"pretend\s+to\s+be\b|"
    r"pretend\s+you\s+are\b|"
    r"new\s+persona\b|"
    r"roleplay\s+as\b|"
    r"take\s+on\s+the\s+role\b|"
    r"from\s+now\s+on\s+(you\s+are|be)\b|"
    # Model/template injection tokens
    r"<\|.*?\|>|"
    r"\[INST\]|\[/?SYS\]|"
    r"<</?(SYS|INST)>>|"
    # Jailbreak keywords
    r"jailbreak|"
    r"DAN\s+mode|"
    r"developer\s+mode\s+enabled|"
    r"override\s+(safety|filter|restriction)"
    r")",
    re.IGNORECASE | re.DOTALL,
)


def check_prompt_injection(text: str) -> bool:
    """Return True if the text appears to contain prompt-injection patterns."""
    return bool(_INJECTION_PATTERNS.search(text))


def sanitize_for_prompt(text: str, max_len: int = 2000) -> str:
    """Strip injection patterns and truncate before embedding in a prompt."""
    if not text:
        return ""
    cleaned = _INJECTION_PATTERNS.sub("[removed]", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def mask_api_key(key: str) -> str:
    """Return a masked version safe for display (never log the real key)."""
    if not key or len(key) < 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def safe_dict_extract(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Extract a value from a dict safely, returning default if missing or None."""
    return data.get(key) or default


def hash_session_id(raw_id: str) -> str:
    """One-way hash for session tracking without storing raw session tokens."""
    return hashlib.sha256(raw_id.encode()).hexdigest()[:16]


def validate_url(url: str) -> bool:
    """Very basic check that URL is https (for external API calls)."""
    return url.startswith("https://") or url.startswith("http://router.project-osrm.org")
