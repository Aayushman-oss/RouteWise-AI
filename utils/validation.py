"""
RouteWise AI – Input Validation Utilities
"""

from __future__ import annotations

import re
from datetime import date
from typing import Tuple

import config


def validate_location_input(text: str) -> Tuple[bool, str]:
    """Return (is_valid, error_message). Empty string means valid."""
    if not text or not text.strip():
        return False, "Location cannot be empty."
    text = text.strip()
    if len(text) < 2:
        return False, "Location name is too short."
    if len(text) > 100:
        return False, "Location name is too long (max 100 characters)."
    if re.search(r"[<>\"'%;()&+]", text):
        return False, "Location contains invalid characters."
    return True, ""


def validate_budget(amount: float) -> Tuple[bool, str]:
    if amount < config.MIN_BUDGET_INR:
        return False, f"Minimum budget is ₹{config.MIN_BUDGET_INR:,}."
    if amount > config.MAX_BUDGET_INR:
        return False, f"Maximum budget is ₹{config.MAX_BUDGET_INR:,}."
    return True, ""


def validate_dates(start: date, end: date) -> Tuple[bool, str]:
    today = date.today()
    if start < today:
        return False, "Start date cannot be in the past."
    if end <= start:
        return False, "End date must be after the start date."
    if (end - start).days > 90:
        return False, "Trip duration cannot exceed 90 days."
    return True, ""


def sanitize_prompt_input(text: str) -> str:
    """Remove potential prompt-injection patterns from user-supplied text.

    Delegates to security.sanitize_for_prompt so both paths share the same
    comprehensive pattern set.
    """
    if not text:
        return ""
    from utils.security import sanitize_for_prompt
    return sanitize_for_prompt(text, max_len=config.MAX_PROMPT_CHARS)


def validate_num_travellers(n: int) -> Tuple[bool, str]:
    if n < 1:
        return False, "Must have at least 1 traveller."
    if n > 50:
        return False, "Maximum 50 travellers."
    return True, ""
