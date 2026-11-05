"""
RouteWise AI – Centralized Configuration
=========================================
Reads all settings from environment variables (.env locally, st.secrets on
Streamlit Cloud).  Never exposes credentials through UI or logs.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

# Load .env in local development; no-op in Streamlit Cloud
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

# Attempt to pull from st.secrets if running inside Streamlit
def _streamlit_secret(key: str) -> Optional[str]:
    """Return a value from st.secrets without importing Streamlit at module level."""
    try:
        import streamlit as st  # type: ignore
        return st.secrets.get(key)
    except Exception:
        return None


def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    """Resolve config key: env var → st.secrets → default."""
    value = os.environ.get(key)
    if value:
        return value.strip()
    value = _streamlit_secret(key)
    if value:
        return str(value).strip()
    return default


# ─── IBM watsonx.ai settings ────────────────────────────────────────────────

WATSONX_API_KEY: Optional[str] = _get("WATSONX_API_KEY")
WATSONX_PROJECT_ID: Optional[str] = _get("WATSONX_PROJECT_ID")
WATSONX_URL: str = _get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com") or "https://us-south.ml.cloud.ibm.com"
WATSONX_MODEL_ID: str = _get("WATSONX_MODEL_ID", "ibm/granite-4-h-small") or "ibm/granite-4-h-small"

# ─── Inference parameters ────────────────────────────────────────────────────

MAX_NEW_TOKENS: int = int(_get("MAX_NEW_TOKENS", "1200") or "1200")
MODEL_TEMPERATURE: float = float(_get("MODEL_TEMPERATURE", "0.3") or "0.3")
REQUEST_TIMEOUT: int = int(_get("REQUEST_TIMEOUT", "60") or "60")

# ─── External API base URLs ─────────────────────────────────────────────────

OPEN_METEO_BASE_URL: str = _get("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1") or "https://api.open-meteo.com/v1"
OSRM_BASE_URL: str = _get("OSRM_BASE_URL", "http://router.project-osrm.org") or "http://router.project-osrm.org"

# ─── Application constants ───────────────────────────────────────────────────

APP_NAME = "RouteWise AI"
APP_VERSION = "1.0.0"
APP_TAGLINE = "Intelligent Indian Travel Planning, Powered by IBM Granite"

MAX_PROMPT_CHARS = 8_000     # hard cap on user-supplied text going into prompts
MAX_BUDGET_INR = 10_000_000  # ₹1 crore upper bound
MIN_BUDGET_INR = 500         # ₹500 minimum

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("routewise")


# ─── Validation helpers ──────────────────────────────────────────────────────

@dataclass
class ConfigStatus:
    api_key_set: bool = False
    project_id_set: bool = False
    url_set: bool = False
    model_id_set: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        return self.api_key_set and self.project_id_set and self.url_set and self.model_id_set

    @property
    def summary(self) -> str:
        if self.is_ready:
            return "✅ All IBM watsonx.ai credentials are configured."
        missing = []
        if not self.api_key_set:
            missing.append("WATSONX_API_KEY")
        if not self.project_id_set:
            missing.append("WATSONX_PROJECT_ID")
        if not self.url_set:
            missing.append("WATSONX_URL")
        if not self.model_id_set:
            missing.append("WATSONX_MODEL_ID")
        return f"❌ Missing configuration: {', '.join(missing)}"


def validate_config() -> ConfigStatus:
    """Check that all required IBM credentials are present."""
    status = ConfigStatus(
        api_key_set=bool(WATSONX_API_KEY),
        project_id_set=bool(WATSONX_PROJECT_ID),
        url_set=bool(WATSONX_URL),
        model_id_set=bool(WATSONX_MODEL_ID),
    )
    return status


def get_safe_config_display() -> dict:
    """Return config values safe to display in UI (no secrets)."""
    status = validate_config()
    return {
        "model_id": WATSONX_MODEL_ID,
        "endpoint_url": WATSONX_URL,
        "api_key_configured": status.api_key_set,
        "project_id_configured": status.project_id_set,
        "max_new_tokens": MAX_NEW_TOKENS,
        "temperature": MODEL_TEMPERATURE,
        "request_timeout": REQUEST_TIMEOUT,
        "app_version": APP_VERSION,
    }
