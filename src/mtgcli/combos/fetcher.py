"""
Combo data fetcher.

Loads the COMBOURL env variable and resolves a commander slug to a full URL.
Supports two URL formats:
  - Template: https://example.com/combos/{slug}.json
  - Base URL:  https://example.com/combos/   (slug.json is appended)
"""
import os
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv

from mtgcli.explore.slug import commander_to_slug

_ENV_VAR = "COMBOURL"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; mtg-deckbuilder/1.0)"}
_TIMEOUT = 20


def _load_base_url() -> str:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    url = os.getenv(_ENV_VAR, "").strip()
    if not url:
        raise ValueError(f"Configuration error: {_ENV_VAR} is not set in .env")
    return url


def build_combo_url(commander_name: str) -> str:
    """Resolve the full combo data URL for a given commander name."""
    base = _load_base_url()
    slug = commander_to_slug(commander_name)
    if "{slug}" in base:
        return base.replace("{slug}", slug)
    base = base.rstrip("/")
    return f"{base}/{slug}.json"


def fetch_combo_data(url: str) -> Dict[str, Any]:
    """
    Fetch raw combo JSON from the given URL.

    Returns the parsed JSON dict on success.
    Raises ValueError with a clean message on any failure.
    """
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    except requests.exceptions.ConnectionError as exc:
        raise ValueError(f"Connection error fetching combo data: {exc}") from exc
    except requests.exceptions.Timeout:
        raise ValueError(f"Timeout fetching combo data from {url}")

    if response.status_code != 200:
        raise ValueError(
            f"Combo data request failed: HTTP {response.status_code} for {url}"
        )

    try:
        return response.json()
    except Exception as exc:
        raise ValueError(f"Invalid JSON in combo response: {exc}") from exc
