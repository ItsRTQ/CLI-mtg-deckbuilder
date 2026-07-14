"""Card endpoints: search (with advanced filters + pagination) and exact-name
resolve (with fuzzy suggestions)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from mtgcli.cards.query_parser import QueryConflictError, empty_parsed
from mtgcli.cards.repository import CardRepository
from mtgcli.cards.search import (
    UnknownTypeFilterError,
    normalize_type_filter,
    search_commander_legal_cards,
)
from mtgcli.gui_api.deps import get_repo
from mtgcli.gui_api.schemas import CardOut, SearchResponse

router = APIRouter()

_MAX_SCAN = 500  # deepest page the UI can reach; log nothing — has_more just ends


@router.get("/cards/search", response_model=SearchResponse)
def cards_search(
    q: Optional[str] = Query(None, description="Search text; supports the structured grammar (type:/oracle:/name:/mv:)"),
    colors: Optional[str] = Query(None, description="Color identity letters, e.g. WUG"),
    type: Optional[str] = Query(None, description="Broad type filter (creature, instant, ...)"),
    oracle: Optional[str] = Query(None, description="Oracle text contains"),
    name: Optional[str] = Query(None, description="Card name contains"),
    mv_gte: Optional[float] = Query(None, ge=0),
    mv_lte: Optional[float] = Query(None, ge=0),
    pow_gte: Optional[int] = Query(None, ge=0),
    tou_gte: Optional[int] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, gt=0, description="USD cap (unpriced cards are kept)"),
    commanders_only: bool = Query(False, description="Only cards that can be your commander (exact can_be_commander flag)"),
    rarity: Optional[str] = Query(None, description="common | uncommon | rare | mythic (rarity of the kept printing)"),
    limit: int = Query(15, ge=1, le=50),
    offset: int = Query(0, ge=0, le=_MAX_SCAN),
    _repo: CardRepository = Depends(get_repo),  # 503 when the DB is missing
) -> SearchResponse:
    if not (q or colors or type or oracle or name or mv_gte is not None
            or mv_lte is not None or pow_gte is not None or tou_gte is not None):
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "Provide a search term or at least one filter."}})

    extra = empty_parsed()
    if oracle:
        extra["oracle_terms"] = [oracle]
    if name:
        extra["name_terms"] = [name]
    extra["mana_value_gte"] = mv_gte
    extra["mana_value_lte"] = mv_lte
    extra["power_gte"] = pow_gte
    extra["toughness_gte"] = tou_gte

    # Pagination without touching the CLI-shared search function: fetch one chunk
    # (oversampled when a post-filter can drop rows), filter, slice.
    chunk = offset + limit + 1
    if max_price is not None or commanders_only:
        chunk = min(_MAX_SCAN, chunk * 5)
    try:
        type_filter = normalize_type_filter(type) if type else None
        results = search_commander_legal_cards(
            query=q, colors=colors, limit=min(chunk, _MAX_SCAN),
            type_filter=type_filter, extra_filters=extra,
            rarity=rarity)   # SQL-level: a rare rarity can't starve the page
    except (UnknownTypeFilterError, QueryConflictError) as e:
        raise HTTPException(status_code=422,
                            detail={"error": {"type": "usage", "message": str(e)}})

    if max_price is not None:
        results = [c for c in results
                   if c.get("usd_price") is None or c["usd_price"] <= max_price]
    if commanders_only:
        # exact flag (incl. the curated overrides), not just "legendary creature"
        results = [c for c in results if c.get("can_be_commander")]

    page = results[offset:offset + limit]
    has_more = len(results) > offset + limit
    return SearchResponse(count=len(page), offset=offset, has_more=has_more,
                          results=page)


@router.get("/cards/{name}", response_model=CardOut)
def card_by_name(name: str, repo: CardRepository = Depends(get_repo)) -> CardOut:
    card = repo.get_card_by_exact_name(name)
    if card is None:
        suggestions = [s.get("name") for s in repo.suggest_similar_names(name, limit=5)]
        raise HTTPException(status_code=404, detail={"error": {
            "type": "validation",
            "message": f"Card not found: {name}",
            "suggestions": suggestions,
        }})
    return CardOut(**card)
