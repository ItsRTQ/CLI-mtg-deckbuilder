import os
from pathlib import Path
from dotenv import load_dotenv
import requests

from mtgcli.explore.slug import commander_to_slug

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; mtg-deckbuilder/1.0)"}


def _load_base_url() -> str:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    url = os.getenv("URLC", "").strip()
    if not url:
        raise ValueError("URLC is not set in .env")
    return url.rstrip("/")


def build_explore_url(commander_name: str) -> str:
    base = _load_base_url()
    slug = commander_to_slug(commander_name)
    return f"{base}/{slug}"


def fetch_commander_page(url: str, timeout: int = 15) -> str:
    response = requests.get(url, headers=_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text
