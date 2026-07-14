"""Pydantic (v2) response/request models for the GUI API."""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class HealthOut(BaseModel):
    status: str
    version: str


class CardOut(BaseModel):
    """Typed on the fields the UI uses; extra="allow" passes the canonical
    row_to_card dict (cards/repository.py) through unclipped."""
    model_config = ConfigDict(extra="allow")

    name: str
    mana_cost: Optional[str] = None
    mana_value: Optional[float] = None
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    color_identity: Optional[List[str]] = None
    usd_price: Optional[float] = None


class SearchResponse(BaseModel):
    count: int
    offset: int = 0
    has_more: bool = False
    results: List[CardOut]


class ProjectStatusOut(BaseModel):
    project_root: str
    database_path: str
    database_exists: bool
    raw_cards_path: str
    raw_cards_exists: bool
