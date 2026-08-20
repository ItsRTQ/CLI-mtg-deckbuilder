"""Library endpoints: the user's BULK (owned cards) and saved DECKS."""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from mtgcli.cards.repository import CardRepository
from mtgcli.core import gui_settings
from mtgcli.deckbuilder.user_bulk import (
    DEFAULT_OWNED,
    default_bulk_file,
    load_user_bulk,
    save_user_bulk,
)
from mtgcli.gui_api.deps import get_repo, get_repo_optional

router = APIRouter()


# ── Bulk (owned collection) ────────────────────────────────────────────────────

class BulkCardOut(BaseModel):
    name: str
    usd_price: Optional[float] = None
    image_url: Optional[str] = None
    mana_cost: Optional[str] = None
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    rarity: Optional[str] = None   # chosen printing's rarity wins over the DB's


class BulkOut(BaseModel):
    source: str                    # the collection.txt actually read
    count: int
    known_value: float             # sum of known prices (informational)
    unknown_count: int
    cards: List[BulkCardOut]
    always_free: List[str]         # DEFAULT_OWNED — assumed even if not listed


@router.get("/bulk", response_model=BulkOut)
def get_bulk(repo: CardRepository = Depends(get_repo)) -> BulkOut:
    from mtgcli.core.print_prefs import load_print_prefs, resolve_pref

    prefs = load_print_prefs()
    owned = sorted(load_user_bulk(), key=str.lower)
    cards, known, unknown = [], 0.0, 0
    for name in owned:
        card = repo.get_card_by_exact_name(name) or {}
        price = card.get("usd_price")
        if price is None:
            unknown += 1
        else:
            known += float(price)
        cname = card.get("name", name)
        pref = resolve_pref(cname, prefs)
        cards.append(BulkCardOut(
            name=cname, usd_price=price,
            image_url=pref.get("image_url") or card.get("image_url"),
            mana_cost=card.get("mana_cost"),
            type_line=card.get("type_line"), oracle_text=card.get("oracle_text"),
            rarity=pref.get("rarity") or card.get("rarity")))
    return BulkOut(source=str(default_bulk_file()), count=len(cards),
                   known_value=round(known, 2), unknown_count=unknown,
                   cards=cards, always_free=list(DEFAULT_OWNED))


class BulkAddIn(BaseModel):
    name: str


class BulkAddOut(BaseModel):
    name: str            # canonical DB name
    added: bool          # False = it was already in the collection
    count: int           # collection size after the operation


@router.post("/bulk/add", response_model=BulkAddOut)
def bulk_add(body: BulkAddIn, repo: CardRepository = Depends(get_repo)) -> BulkAddOut:
    """Add ONE card to the owned collection (the GUI's drag-and-drop target).
    Validates against the DB (canonical name wins) and writes both collection
    forms at the configured bulk location — same behavior as `mtg bulk-add`."""
    card = repo.get_card_by_exact_name(body.name.strip())
    if card is None:
        suggestions = [s.get("name") for s in repo.suggest_similar_names(body.name, limit=5)]
        raise HTTPException(status_code=404, detail={"error": {
            "type": "validation",
            "message": f"Card not found: {body.name}",
            "suggestions": suggestions,
        }})
    owned = load_user_bulk()
    canonical = card["name"]
    already = any(n.lower() == canonical.lower() for n in owned)
    if not already:
        save_user_bulk(list(owned) + [canonical])
    return BulkAddOut(name=canonical, added=not already,
                      count=len(owned) + (0 if already else 1))


class BulkImportIn(BaseModel):
    text: str              # plain text / Moxfield export, one card per line


class BulkImportOut(BaseModel):
    added: List[str]       # canonical names newly added
    already_owned: List[str]
    skipped: List[str]     # lines that resolved to no DB card (reported, never invented)
    count: int             # collection size after the operation


@router.post("/bulk/import", response_model=BulkImportOut)
def bulk_import(body: BulkImportIn,
                repo: CardRepository = Depends(get_repo)) -> BulkImportOut:
    """Import a pasted plain-text list into the owned collection. Quantities are
    ignored — the bulk tracks OWNERSHIP, not counts (same model as `mtg bulk-add`).
    Names resolve against the DB (Moxfield set/collector suffixes stripped as a
    fallback); unresolvable lines are skipped and reported, never invented."""
    from mtgcli.core.save_build import _MOX_SUFFIX
    from mtgcli.utils.decklist_parser import parse_decklist_text

    entries = parse_decklist_text(body.text)
    if not entries:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "No cards found in the pasted text."}})
    owned = list(load_user_bulk())
    have = {n.lower() for n in owned}
    added, already, skipped = [], [], []
    for e in entries:
        name = (e.get("name") or "").strip()
        if not name:
            continue
        card = repo.get_card_by_exact_name(name)
        if card is None:  # retry without the Moxfield "(SET) 123 *F*" tail
            card = repo.get_card_by_exact_name(_MOX_SUFFIX.sub("", name))
        if card is None:
            skipped.append(name)
            continue
        canonical = card["name"]
        if canonical.lower() in have:
            already.append(canonical)
            continue
        have.add(canonical.lower())
        added.append(canonical)
    if added:
        save_user_bulk(owned + added)
    return BulkImportOut(added=added, already_owned=already, skipped=skipped,
                         count=len(owned) + len(added))


# ── Preferred printings (the zoom's "switch print" persistence) ───────────────

class PrintPrefIn(BaseModel):
    set: Optional[str] = None
    collector_number: Optional[str] = None
    rarity: Optional[str] = None      # the chosen PRINTING's rarity
    image_url: str


@router.get("/prints")
def get_prints() -> dict:
    from mtgcli.core import print_prefs
    return print_prefs.load_print_prefs()


@router.put("/prints/{name}")
def put_print(name: str, body: PrintPrefIn) -> dict:
    from mtgcli.core import print_prefs
    try:
        saved = print_prefs.set_print_pref(name, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": str(e)}})
    return {"name": name, **saved}


@router.delete("/prints/{name}")
def delete_print(name: str) -> dict:
    from mtgcli.core import print_prefs
    return {"cleared": print_prefs.clear_print_pref(name)}


# ── Saved decks (the build library) ────────────────────────────────────────────

class DeckSummaryOut(BaseModel):
    name: str
    card_count: Optional[int] = None
    has_explanation: bool = False
    modified: float = 0.0
    commander: Optional[str] = None    # canonical name (from deck_list.json)
    tier: Optional[str] = None         # +S..F — parsed from the folder name
    rank: Optional[str] = None         # Scrap..Mythic
    cost_usd: Optional[int] = None
    art_url: Optional[str] = None      # commander art crop (Scryfall art_crop)


_RANK_BANDS = {"Scrap", "Dormant", "Awakened", "Charged", "Ascendant",
               "Forbidden", "Mythic"}
_TIER_RE = None  # compiled lazily below


def _parse_build_name(name: str):
    """Parse `<Commander>-<TIER>-<RANK>-<COST>` from the END (tier may be absent,
    the commander part may contain hyphens)."""
    import re
    global _TIER_RE
    if _TIER_RE is None:
        _TIER_RE = re.compile(r"^\+?-?[SABCDF]$")
    parts = name.split("-")
    tier = rank = None
    cost = None
    if parts and re.fullmatch(r"\d+usd", parts[-1] or ""):
        cost = int(parts[-1][:-3])
        parts = parts[:-1]
    if parts and parts[-1] in _RANK_BANDS:
        rank = parts[-1]
        parts = parts[:-1]
    if parts and _TIER_RE.fullmatch(parts[-1] or ""):
        tier = parts[-1]
    return tier, rank, cost


class DecksOut(BaseModel):
    dir: Optional[str] = None      # None = library saving is OFF
    decks: List[DeckSummaryOut] = []


class DeckCardOut(BaseModel):
    name: str
    quantity: int = 1
    section: str = "other"
    image_url: Optional[str] = None
    type_line: Optional[str] = None
    mana_cost: Optional[str] = None
    oracle_text: Optional[str] = None
    usd_price: Optional[float] = None
    rarity: Optional[str] = None


class DeckStatsOut(BaseModel):
    total_cards: int = 0               # main deck + commander
    known_price: float = 0.0
    avg_mv_nonland: Optional[float] = None
    section_counts: dict = {}


class DeckDetailOut(BaseModel):
    name: str
    decklist: str
    explanation: Optional[str] = None
    commander: Optional[str] = None
    color_identity: List[str] = []     # commander's identity ([] when unknown)
    cards: List[DeckCardOut] = []      # commander first, then by section
    stats: DeckStatsOut = DeckStatsOut()


def _section_of(type_line: Optional[str]) -> str:
    """Same primary-type rule as the Deck model (single source: its order const)."""
    from mtgcli.models.deck import _PRIMARY_TYPE_ORDER
    tl = (type_line or "").lower()
    sections = {"land": "lands", "creature": "creatures", "instant": "instants",
                "sorcery": "sorceries", "artifact": "artifacts",
                "enchantment": "enchantments", "planeswalker": "planeswalkers",
                "battle": "battles"}
    for t in _PRIMARY_TYPE_ORDER:
        if t in tl:
            return sections.get(t, "other")
    return "other"


def _library_dir() -> Optional[Path]:
    try:
        return gui_settings.resolve_save_dir(
            gui_settings.load_gui_settings().get("builds_save_dir"))
    except ValueError:
        return None


@router.get("/decks", response_model=DecksOut)
def list_decks(repo=Depends(get_repo_optional)) -> DecksOut:
    import json as _json

    lib = _library_dir()
    if lib is None or not lib.is_dir():
        return DecksOut(dir=str(lib) if lib else None)
    # repo is best-effort here: deck listing must work even without the card DB
    # (art crops are decoration, not data)
    decks = []
    for d in lib.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        txt = d / f"{d.name}.txt"
        count = None
        if txt.exists():
            try:
                count = sum(
                    int((ln.split(None, 1)[0] if ln.split(None, 1)[0].isdigit() else "1"))
                    for ln in txt.read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.strip().startswith("#"))
            except (OSError, ValueError):
                count = None
        tier, rank, cost = _parse_build_name(d.name)
        commander = art = None
        dl = d / "deck_list.json"
        if dl.exists():
            try:
                data = _json.loads(dl.read_text(encoding="utf-8"))
                commander = ((data.get("commanders") or [None])[0]
                             or data.get("commander"))
            except (OSError, ValueError):
                pass
        if commander and repo is not None:
            card = repo.get_card_by_exact_name(commander)
            url = (card or {}).get("image_url")
            if url:
                art = url.replace("/normal/", "/art_crop/")
        decks.append(DeckSummaryOut(
            name=d.name, card_count=count,
            has_explanation=(d / f"{d.name}.explanation.md").exists(),
            modified=d.stat().st_mtime,
            commander=commander, tier=tier, rank=rank, cost_usd=cost,
            art_url=art))
    decks.sort(key=lambda x: -x.modified)
    return DecksOut(dir=str(lib), decks=decks)


class DeckImportIn(BaseModel):
    commander: str
    decklist: str          # plain text / Moxfield export


class DeckImportOut(BaseModel):
    build_name: str
    saved_to: str
    commander: str
    imported: int
    skipped: List[str] = []


@router.post("/decks/import", response_model=DeckImportOut)
def import_deck(body: DeckImportIn,
                repo: CardRepository = Depends(get_repo)) -> DeckImportOut:
    """Import a pasted decklist (e.g. a Moxfield export) into the deck library."""
    lib = _library_dir()
    if lib is None:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": "Library saving is OFF — set a Build save folder in "
                       "Settings before importing."}})
    from mtgcli.core.save_build import import_text_to_library
    try:
        result = import_text_to_library(body.commander, body.decklist, lib, repo=repo)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": str(e)}})
    return DeckImportOut(**result)


class DeckCreateIn(BaseModel):
    commander: str
    decklist: str = ""         # empty = fresh deck (commander only, edit to fill)


@router.post("/decks", response_model=DeckImportOut)
def create_deck(body: DeckCreateIn,
                repo: CardRepository = Depends(get_repo)) -> DeckImportOut:
    """Create a library deck: commander + an OPTIONAL pasted list. An empty list
    makes a fresh deck to fill via the edit endpoints below."""
    lib = _library_dir()
    if lib is None:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": "Library saving is OFF — set a Build save folder in "
                       "Settings before creating decks."}})
    from mtgcli.core.save_build import import_text_to_library
    try:
        result = import_text_to_library(body.commander, body.decklist, lib,
                                        repo=repo, allow_empty=True)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": str(e)}})
    return DeckImportOut(**result)


def _deck_dir_or_404(name: str) -> Path:
    """Resolve a deck folder inside the library; 404 on unknown/traversal."""
    lib = _library_dir()
    if lib is None or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=404, detail={"error": {
            "type": "validation", "message": f"Unknown deck: {name}"}})
    d = lib / name
    if not d.is_dir() or d.parent.resolve() != lib.resolve():
        raise HTTPException(status_code=404, detail={"error": {
            "type": "validation", "message": f"Unknown deck: {name}"}})
    return d


# ── Deck editing (Deck-model guards: atomic, color identity/singleton/size) ───

_EDIT_AS_TEXT_HINT = "Use 'Edit as text' to paste a corrected list."


def _load_deck_or_422(d: Path, repo):
    """Load a library deck through the Deck model (guards enforce on load). A
    deck that can't load — no deck_list.json, off-color legacy card, unknown
    name — 422s honestly; the text-replace endpoint is the escape hatch."""
    from mtgcli.models import CardNotFoundError, Deck, DeckError

    dl = d / "deck_list.json"
    if not dl.exists():
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "This deck has no deck_list.json — re-import it to make "
                       "it editable."}})
    try:
        return Deck.load(dl, repo=repo)
    except (DeckError, CardNotFoundError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": f"This deck can't load as-is: {e}\n{_EDIT_AS_TEXT_HINT}"}})


def _persist_deck(d: Path, deck, repo):
    """Write deck_list.json + regenerate the .txt, then rename the folder to the
    fresh `<Commander>-<TIER>-<RANK>-<COST>` tokens (best-effort). Returns
    `(new_dir, new_name)` — responses must carry the NEW name."""
    from mtgcli.core.save_build import rename_to_current_tokens
    from mtgcli.export.final_builds import (deck_entries_to_moxfield_text,
                                            save_final_build_decklist)

    deck.save(d / "deck_list.json")
    save_final_build_decklist(
        deck_entries_to_moxfield_text([c.to_dict() for c in deck.cards]),
        d, d.name)
    return rename_to_current_tokens(d, deck.commanders[0].name, repo=repo)


class DeckEditIn(BaseModel):
    add: List[str] = []
    remove: List[str] = []


class DeckEditOut(BaseModel):
    name: str                  # the deck's (possibly renamed) folder name
    added: List[str] = []
    removed: List[str] = []


@router.patch("/decks/{name}/cards", response_model=DeckEditOut)
def edit_deck_cards(name: str, body: DeckEditIn,
                    repo: CardRepository = Depends(get_repo)) -> DeckEditOut:
    """Add/remove cards on a library deck. Removes run first (frees slots),
    adds second; disk is written only if both pass — the PATCH is atomic."""
    from mtgcli.models import Card, CardNotFoundError, DeckError

    d = _deck_dir_or_404(name)
    add = [n.strip() for n in body.add if n and n.strip()]
    remove = [n.strip() for n in body.remove if n and n.strip()]
    if not add and not remove:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "Nothing to add or remove."}})
    deck = _load_deck_or_422(d, repo)
    try:
        removed = deck.remove(remove) if remove else []
        added = deck.add([Card(n, [], repo=repo) for n in add]) if add else []
    except DeckError as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": str(e)}})
    except CardNotFoundError as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": str(e),
            "suggestions": e.suggestions}})
    _, new_name = _persist_deck(d, deck, repo)
    return DeckEditOut(name=new_name, added=added, removed=removed)


class DeckReplaceIn(BaseModel):
    decklist: str              # plain text / Moxfield export — replaces the list


class DeckReplaceOut(BaseModel):
    name: str
    imported: int
    skipped: List[str] = []


@router.put("/decks/{name}/list", response_model=DeckReplaceOut)
def replace_deck_list(name: str, body: DeckReplaceIn,
                      repo: CardRepository = Depends(get_repo)) -> DeckReplaceOut:
    """Replace the whole card list from pasted text ("Edit as text"). Builds a
    FRESH Deck (guards validate the new list), carrying annotations over by
    name — this is also the recovery path for decks that can't load as-is."""
    import json as _json

    from mtgcli.core.save_build import resolve_decklist_entries
    from mtgcli.models import Card, CardNotFoundError, Deck, DeckError

    d = _deck_dir_or_404(name)
    dl = d / "deck_list.json"
    if not dl.exists():
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "This deck has no deck_list.json — re-import it to make "
                       "it editable."}})
    try:
        old = _json.loads(dl.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": f"Unreadable deck_list.json: {e}"}})
    commander = (old.get("commanders") or [None])[0] or old.get("commander")
    if not commander:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "Deck has no commander metadata."}})

    resolved, skipped = resolve_decklist_entries(body.decklist, commander, repo=repo)
    if not resolved:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "No known cards found in the pasted text."
                       + (f" Skipped: {', '.join(skipped[:6])}" if skipped else "")}})

    old_by_name = {(e.get("name") or "").lower(): e
                   for e in old.get("main_deck", [])}
    try:
        cmd_names = old.get("commanders") or [commander]
        deck = Deck([Card(n, ["WINCON"], repo=repo) for n in cmd_names],
                    agent_note=old.get("agent_note"))
        deck.config = dict(old.get("config") or {})
        deck.print_prefs = dict(old.get("print_prefs") or {})
        deck.add([Card(e["name"],
                       (old_by_name.get(e["name"].lower(), {}).get("purpose") or []),
                       agent_note=old_by_name.get(e["name"].lower(), {}).get("agent_note"),
                       quantity=e["quantity"], repo=repo)
                  for e in resolved])
        for cls_name, combos in (old.get("combos") or {}).items():
            for cb in combos:
                if cb.get("cards_needed"):
                    deck.add_combo(cls_name, cb["cards_needed"], cb.get("how_to", ""))
    except (DeckError, CardNotFoundError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": str(e)}})
    _, new_name = _persist_deck(d, deck, repo)
    return DeckReplaceOut(name=new_name, imported=len(resolved), skipped=skipped)


# ── Deck-scoped preferred printings (deck layer; global /prints = fallback) ───
# Surgical writes on the raw deck_list.json: no .txt regen, no folder rename,
# and they work on legacy decks the Deck model's guards reject.

def _deck_list_or_422(d: Path) -> Path:
    dl = d / "deck_list.json"
    if not dl.exists():
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "This deck has no deck_list.json — re-import it to make "
                       "it editable."}})
    return dl


def _deck_card_names(dl: Path) -> set:
    """Lowercase names of every card in the deck, commander(s) included."""
    import json as _json
    try:
        data = _json.loads(dl.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": f"Unreadable deck_list.json: {e}"}})
    names = {(e.get("name") or "").lower()
             for e in data.get("main_deck", []) if e.get("name")}
    for cmd in (data.get("commanders") or
                ([data["commander"]] if data.get("commander") else [])):
        names.add(cmd.lower())
    names.discard("")
    return names


@router.get("/decks/{name}/prints")
def get_deck_prints(name: str) -> dict:
    from mtgcli.core.print_prefs import load_deck_print_prefs
    d = _deck_dir_or_404(name)
    return load_deck_print_prefs(_deck_list_or_422(d))


@router.put("/decks/{name}/prints/{card_name}")
def put_deck_print(name: str, card_name: str, body: PrintPrefIn) -> dict:
    from mtgcli.core import print_prefs
    d = _deck_dir_or_404(name)
    dl = _deck_list_or_422(d)
    if card_name.lower() not in _deck_card_names(dl):
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": f"'{card_name}' is not in this deck."}})
    try:
        saved = print_prefs.set_deck_print_pref(dl, card_name, body.model_dump())
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": str(e)}})
    return {"name": card_name, **saved}


@router.delete("/decks/{name}/prints/{card_name}")
def delete_deck_print(name: str, card_name: str) -> dict:
    from mtgcli.core import print_prefs
    d = _deck_dir_or_404(name)
    dl = _deck_list_or_422(d)
    try:
        cleared = print_prefs.clear_deck_print_pref(dl, card_name)
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": f"Unreadable deck_list.json: {e}"}})
    return {"cleared": cleared}


class ExplainIn(BaseModel):
    # The owner's context form — their answers make the agent VERIFY, not guess.
    theme: Optional[str] = None
    combos: Optional[str] = None
    bracket: Optional[str] = None
    notes: Optional[str] = None
    provider: Optional[str] = None
    timeout_seconds: int = 600


@router.post("/decks/{name}/explain", status_code=202)
def explain_deck(name: str, body: ExplainIn, request: Request,
                 repo: CardRepository = Depends(get_repo)) -> dict:
    """Start a headless agent job that annotates an existing library deck and
    writes its explanation (the imported-deck case). Same lifecycle/locks as a
    build job — poll it via GET /api/builds/{job_id}."""
    import json as _json

    from mtgcli.gui_api.jobs import TERMINAL
    from mtgcli.gui_api.routers.builds import get_registry
    from mtgcli.gui_api.routers.data import data_refresh_running
    from mtgcli.gui_api.routers.providers import get_manager, selected_provider

    d = _deck_dir_or_404(name)
    dl = d / "deck_list.json"
    if not dl.exists():
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "This deck has no deck_list.json to annotate."}})
    try:
        deck_data = _json.loads(dl.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": f"Unreadable deck_list.json: {e}"}})
    commander = ((deck_data.get("commanders") or [None])[0]
                 or deck_data.get("commander"))
    if not commander:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "Deck has no commander metadata."}})

    if data_refresh_running(request):
        raise HTTPException(status_code=409, detail={"error": {
            "type": "conflict", "message": "The card database is being refreshed — "
                                           "wait for it to finish."}})
    registry = get_registry(request)
    running = next((j for j in registry.list() if j.status not in TERMINAL), None)
    if running is not None:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "conflict",
            "message": "An agent job is already running — wait or cancel it.",
            "job_id": running.id}})

    mgr = get_manager(request)
    provider_name = body.provider or selected_provider(request, mgr)
    provider = mgr.get(provider_name) if provider_name else None
    if provider is None or not provider.supports_build:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": "No build-capable provider selected — configure one in Settings."}})
    info = provider.detect()
    if not info.installed:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": f"Provider '{provider_name}' is not installed ({info.detail})."}})

    payload = body.model_dump()
    payload["commander"] = commander
    payload["_target_dir"] = str(d)
    job = registry.create_explain(payload, deck_data, provider)
    return {"job_id": job.id, "status_url": f"/api/builds/{job.id}"}


class AdviseIn(BaseModel):
    # Optional context for the advisory pass; the deck may be an incomplete draft.
    theme: Optional[str] = None
    budget: Optional[str] = None
    notes: Optional[str] = None
    provider: Optional[str] = None
    timeout_seconds: int = 600


@router.post("/decks/{name}/advise", status_code=202)
def advise_deck(name: str, body: AdviseIn, request: Request,
                repo: CardRepository = Depends(get_repo)) -> dict:
    """Start a headless agent job that ADVISES on an in-progress draft: read-only
    analysis, deck-size/preflight explicitly out of scope (it's a draft). Poll it
    via GET /api/builds/{job_id}; the result carries recommendations.json with
    every suggested card DB-verified."""
    import json as _json

    from mtgcli.gui_api.jobs import TERMINAL
    from mtgcli.gui_api.routers.builds import get_registry
    from mtgcli.gui_api.routers.data import data_refresh_running
    from mtgcli.gui_api.routers.providers import get_manager, selected_provider

    d = _deck_dir_or_404(name)
    dl = d / "deck_list.json"
    if not dl.exists():
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "This deck has no deck_list.json to analyze."}})
    try:
        deck_data = _json.loads(dl.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": f"Unreadable deck_list.json: {e}"}})
    commander = ((deck_data.get("commanders") or [None])[0]
                 or deck_data.get("commander"))
    if not commander:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "Deck has no commander metadata."}})

    if data_refresh_running(request):
        raise HTTPException(status_code=409, detail={"error": {
            "type": "conflict", "message": "The card database is being refreshed — "
                                           "wait for it to finish."}})
    registry = get_registry(request)
    running = next((j for j in registry.list() if j.status not in TERMINAL), None)
    if running is not None:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "conflict",
            "message": "An agent job is already running — wait or cancel it.",
            "job_id": running.id}})

    mgr = get_manager(request)
    provider_name = body.provider or selected_provider(request, mgr)
    provider = mgr.get(provider_name) if provider_name else None
    if provider is None or not provider.supports_build:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": "No build-capable provider selected — configure one in Settings."}})
    info = provider.detect()
    if not info.installed:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": f"Provider '{provider_name}' is not installed ({info.detail})."}})

    payload = body.model_dump()
    payload["commander"] = commander
    payload["_deck_name"] = name
    cmd_card = repo.get_card_by_exact_name(commander) or {}
    payload["_colors"] = "".join(cmd_card.get("color_identity") or [])
    job = registry.create_advise(payload, deck_data, provider)
    return {"job_id": job.id, "status_url": f"/api/builds/{job.id}"}


@router.delete("/decks/{name}")
def delete_deck(name: str) -> dict:
    """Delete a deck folder from the library (the GUI confirms first)."""
    import shutil

    d = _deck_dir_or_404(name)
    shutil.rmtree(d)
    return {"deleted": name}


def _read_deck_entries(d, name: str):
    """Read a deck folder's commanders + main-deck entries: prefer the annotated
    deck_list.json; fall back to the .txt list (commanders stay empty there).
    Returns (commanders, entries) with entries as (name, quantity) tuples."""
    import json as _json

    txt = d / f"{name}.txt"
    commanders: List[str] = []
    entries = []
    dl = d / "deck_list.json"
    if dl.exists():
        try:
            data = _json.loads(dl.read_text(encoding="utf-8"))
            commanders = [c for c in (data.get("commanders") or [data.get("commander")]) if c]
            entries = [(e.get("name"), int(e.get("quantity", 1)))
                       for e in data.get("main_deck", []) if e.get("name")]
        except (OSError, ValueError):
            pass
    if not entries and txt.exists():
        for ln in txt.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            head = ln.split(None, 1)
            if len(head) == 2 and head[0].isdigit():
                entries.append((head[1], int(head[0])))
            else:
                entries.append((ln, 1))
    return commanders, entries


class DeckExportUrlOut(BaseModel):
    url: str
    entries: int


@router.get("/decks/{name}/export/tcgplayer", response_model=DeckExportUrlOut)
def export_deck_tcgplayer(name: str, repo=Depends(get_repo_optional)) -> DeckExportUrlOut:
    """Build the TCGplayer Mass Entry URL for a saved deck (commander included).
    The GUI opens it in a new tab — nothing is written to disk."""
    from mtgcli.export.tcgplayer import (build_tcgplayer_mass_entry_url,
                                         normalize_deck_for_tcgplayer)

    d = _deck_dir_or_404(name)
    commanders, raw_entries = _read_deck_entries(d, name)
    layout_lookup = None
    if repo is not None:
        def layout_lookup(cname):  # noqa: F811
            return (repo.get_card_by_exact_name(cname) or {}).get("layout")
    cards, _skipped = normalize_deck_for_tcgplayer(
        [{"name": n, "quantity": q} for n, q in raw_entries],
        commanders=commanders,
        layout_lookup=layout_lookup,
    )
    if not cards:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "This deck has no cards to export."}})
    return DeckExportUrlOut(
        url=build_tcgplayer_mass_entry_url(cards),
        entries=len(cards),
    )


@router.get("/decks/{name}/gaps")
def deck_gaps_endpoint(name: str, archetype: str = "midrange",
                       repo: CardRepository = Depends(get_repo)) -> dict:
    """Audit a library deck against its commander's plan (deck-gaps core).
    Same single-source audit as `mtg deck-gaps`; each gap carries a structured
    `fill` spec the workspace can turn into a prefilled card search."""
    d = _deck_dir_or_404(name)
    commanders, entries = _read_deck_entries(d, name)
    if not commanders:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "This deck has no commander metadata — gaps need the "
                       "commander's plan to audit against."}})
    from mtgcli.deckbuilder.deck_gaps import compute_deck_gaps
    return compute_deck_gaps(
        commanders[0],
        [{"name": n, "quantity": q} for n, q in entries],
        repo,
        archetype=archetype,
        partner=commanders[1] if len(commanders) > 1 else None,
    )


@router.get("/decks/{name}", response_model=DeckDetailOut)
def deck_detail(name: str, repo=Depends(get_repo_optional)) -> DeckDetailOut:
    d = _deck_dir_or_404(name)

    txt = d / f"{name}.txt"
    expl = d / f"{name}.explanation.md"

    commanders, entries = _read_deck_entries(d, name)
    commander = commanders[0] if commanders else None
    dl = d / "deck_list.json"

    from mtgcli.core.print_prefs import (load_deck_print_prefs,
                                         load_print_prefs, resolve_pref)
    global_prefs = load_print_prefs()
    deck_prefs = load_deck_print_prefs(dl)

    def _card_out(cname: str, qty: int, section: Optional[str] = None) -> DeckCardOut:
        card = (repo.get_card_by_exact_name(cname) or {}) if repo else {}
        real = card.get("name", cname)
        pref = resolve_pref(real, deck_prefs, global_prefs)
        return DeckCardOut(
            name=real, quantity=qty,
            section=section or _section_of(card.get("type_line")),
            image_url=pref.get("image_url") or card.get("image_url"),
            type_line=card.get("type_line"),
            mana_cost=card.get("mana_cost"), oracle_text=card.get("oracle_text"),
            usd_price=card.get("usd_price"),
            rarity=pref.get("rarity") or card.get("rarity"))

    cards: List[DeckCardOut] = []
    if commander:
        cards.append(_card_out(commander, 1, section="commander"))
    cards.extend(_card_out(n, q) for n, q in entries
                 if not (commander and n.lower() == commander.lower()))

    section_counts: dict = {}
    total = known = mv_sum = mv_n = 0
    for c in cards:
        section_counts[c.section] = section_counts.get(c.section, 0) + c.quantity
        total += c.quantity
        if c.usd_price is not None:
            known += c.usd_price * c.quantity
        if c.section not in ("lands",) and c.type_line:
            card_full = (repo.get_card_by_exact_name(c.name) or {}) if repo else {}
            mv = card_full.get("mana_value")
            if mv is not None:
                mv_sum += mv * c.quantity
                mv_n += c.quantity

    # Deck color identity = union over commanders (WUBRG order); [] when unknown.
    identity: set = set()
    if repo:
        for cname in commanders:
            card = repo.get_card_by_exact_name(cname) or {}
            identity.update(card.get("color_identity") or [])
    color_identity = [c for c in ("W", "U", "B", "R", "G") if c in identity]

    return DeckDetailOut(
        name=name,
        decklist=txt.read_text(encoding="utf-8", errors="replace") if txt.exists() else "",
        explanation=expl.read_text(encoding="utf-8", errors="replace") if expl.exists() else None,
        commander=commander,
        color_identity=color_identity,
        cards=cards,
        stats=DeckStatsOut(
            total_cards=total, known_price=round(known, 2),
            avg_mv_nonland=round(mv_sum / mv_n, 2) if mv_n else None,
            section_counts=section_counts),
    )


# ── Workspace page: rich stats + import preview ───────────────────────────────

class DeckRichStatsOut(BaseModel):
    total_cards: int = 0               # main deck + commanders
    mana_curve: dict = {}              # nonland mv buckets "0".."6", "7+"
    mana_curve_score: Optional[float] = None
    ideal_curve: dict = {}             # IDEAL_CURVE shares (frontend overlay)
    avg_mv: Optional[float] = None     # nonland, quantity-aware
    median_mv: Optional[float] = None
    land_count: int = 0
    total_price: float = 0.0
    total_price_by_type: dict = {}     # USD per Moxfield primary type
    card_type_counts: dict = {}
    color_pips: dict = {}              # WUBRG: colored symbols in nonland costs
    color_cards: dict = {}             # WUBRG: nonland cards per color identity
    color_sources: dict = {}           # WUBRG: mana producers (lands + rocks/dorks)
    # DB-facts only by design: the consistency TIER and the purpose table read
    # the deck's ANNOTATIONS (agent judgment — e.g. what counts as a wincon),
    # so they are deliberately NOT part of the workspace stats. RANK stays: it
    # reads DB facts (fast mana / tutors / curve), heuristic but grounded.
    rank: Optional[dict] = None        # {score, band, band_name} — deck-rank


@router.get("/decks/{name}/stats", response_model=DeckRichStatsOut)
def deck_stats(name: str, repo: CardRepository = Depends(get_repo)) -> DeckRichStatsOut:
    """Rich stats straight from the Deck model (the workspace Stats modal).
    Fetched lazily on open — deliberately NOT part of the deck-detail payload,
    which refetches after every edit."""
    d = _deck_dir_or_404(name)
    deck = _load_deck_or_422(d, repo)
    from mtgcli.models.deck import IDEAL_CURVE
    mv = deck.mana_value_stats()
    colors = deck.color_stats()
    # rank is a consider-only extra: a scorer failure (e.g. missing seed)
    # must never take the whole stats modal down with it.
    try:
        r = deck.rank()
        rank = {"score": r["score"], "band": r["band"], "band_name": r["band_name"]}
    except Exception:
        rank = None
    return DeckRichStatsOut(
        total_cards=deck.total_size(),
        mana_curve=deck.mana_curve(),
        mana_curve_score=deck.mana_curve_score(),
        ideal_curve=dict(IDEAL_CURVE),
        avg_mv=mv["avg"],
        median_mv=mv["median"],
        land_count=deck.card_type_counts().get("land", 0),
        total_price=deck.total_price(),
        total_price_by_type=deck.total_price_by_type(),
        card_type_counts=deck.card_type_counts(),
        color_pips=colors["pips"],
        color_cards=colors["cards"],
        color_sources=colors["sources"],
        rank=rank,
    )


class DeckPreviewIn(BaseModel):
    decklist: str
    mode: str = "merge"                # "merge" | "replace"


class DeckPreviewEntryOut(BaseModel):
    name: str
    quantity: int = 1
    section: str = "other"
    image_url: Optional[str] = None
    usd_price: Optional[float] = None


class DeckPreviewOut(BaseModel):
    resolved: List[DeckPreviewEntryOut] = []
    skipped: List[str] = []            # unknown names (never invented)
    already_in_deck: List[str] = []    # nonbasic dupes vs deck OR within the paste
    color_violations: List[str] = []   # outside the commander's identity
    projected_size: int = 0            # main-deck size IF applied in `mode`
    max_size: int = 99


@router.post("/decks/{name}/list/preview", response_model=DeckPreviewOut)
def preview_deck_list(name: str, body: DeckPreviewIn,
                      repo: CardRepository = Depends(get_repo)) -> DeckPreviewOut:
    """Dry-run of a plain-text import: parse + resolve + flag EVERY problem
    (unlike Deck.add's first-exception). Persists nothing. `merge` projections
    exclude dupes/violations (what the frontend would PATCH); `replace`
    projects the full pasted list (applied via PUT /list, which validates)."""
    import json as _json

    if body.mode not in ("merge", "replace"):
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "mode must be 'merge' or 'replace'."}})
    d = _deck_dir_or_404(name)
    dl = d / "deck_list.json"
    if not dl.exists():
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": "This deck has no deck_list.json — re-import it to make "
                       "it editable."}})
    try:
        data = _json.loads(dl.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "deck_list.json is unreadable."}})
    commanders = [c for c in (data.get("commanders") or [data.get("commander")]) if c]
    commander = commanders[0] if commanders else ""
    current = {(e.get("name") or "").lower(): int(e.get("quantity", 1))
               for e in data.get("main_deck", []) if e.get("name")}
    current_size = sum(current.values())
    max_size = 100 - max(1, len(commanders))

    identity: set = set()
    for cname in commanders:
        card = repo.get_card_by_exact_name(cname) or {}
        identity.update(card.get("color_identity") or [])

    from mtgcli.core.save_build import resolve_decklist_entries
    resolved_raw, skipped = resolve_decklist_entries(
        body.decklist, commander, repo=repo)
    if not resolved_raw and not skipped:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": "No cards found in the pasted decklist."}})

    resolved: List[DeckPreviewEntryOut] = []
    already: List[str] = []
    violations: List[str] = []
    seen_nonbasic: set = set()
    addition = 0                       # merge-mode quantities that would apply
    for e in resolved_raw:
        card = repo.get_card_by_exact_name(e["name"]) or {}
        tl = card.get("type_line") or ""
        is_basic = "basic" in tl.lower()
        low = e["name"].lower()
        resolved.append(DeckPreviewEntryOut(
            name=e["name"], quantity=e["quantity"], section=_section_of(tl),
            image_url=card.get("image_url"), usd_price=card.get("usd_price")))
        extra = set(card.get("color_identity") or []) - identity
        if extra:
            violations.append(e["name"])
            continue
        if not is_basic and (low in current or low in seen_nonbasic):
            already.append(e["name"])
            continue
        seen_nonbasic.update([] if is_basic else [low])
        addition += e["quantity"]

    projected = (current_size + addition if body.mode == "merge"
                 else sum(e.quantity for e in resolved))
    return DeckPreviewOut(
        resolved=resolved, skipped=skipped, already_in_deck=already,
        color_violations=violations, projected_size=projected, max_size=max_size)
