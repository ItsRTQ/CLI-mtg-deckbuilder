"""Save a finished GUI build workspace into the deck library.

Reuses the final-build machinery (naming convention `<Commander>-<TIER>-<RANK>-
<COST>`, Moxfield decklist, explanation, annotated deck JSON) but with the
DESTINATION as a parameter — the user picks it in Settings (builds_save_dir).
"""
import re
import shutil
from pathlib import Path
from typing import Any, Dict

from mtgcli.export.final_builds import (
    build_final_name,
    create_final_build_directory,
    deck_entries_to_moxfield_text,
    save_final_build_decklist,
    save_final_build_explanation,
)
from mtgcli.utils.deck_io import load_deck_file


def save_build_to_library(workspace: Path, save_dir: Path, *, repo=None) -> Dict[str, Any]:
    """Copy the workspace's finished deck into `save_dir` as a named build folder.
    The deck is assumed already validated + preflighted (the job gates ran)."""
    deck_path = workspace / "output" / "final_deck.json"
    expl_path = workspace / "output" / "explanation.md"

    loaded = load_deck_file(deck_path)
    commander = (loaded.get("commanders") or ["Unknown"])[0]

    # TIER/RANK/COST tokens via the Deck model (same recipe as `mtg final-build`;
    # a missing segment is omitted from the name, never written as 'na').
    tier_tok = rank_tok = None
    cost_val = 0.0
    try:
        from mtgcli.models import Deck as _Deck
        deck_obj = _Deck.load(deck_path, repo=repo)
        cost_val = deck_obj.total_price() or 0.0
        tier_tok = (deck_obj.tier() or {}).get("band") or None
        rank_tok = (deck_obj.rank() or {}).get("band_name") or None
    except Exception:
        pass  # tokens stay omitted; the save still happens
    cost_tok = f"{int(round(cost_val))}usd"

    build_name = build_final_name(commander, tier_tok, rank_tok, cost_tok, save_dir)
    build_dir = create_final_build_directory(build_name, save_dir)
    save_final_build_decklist(
        deck_entries_to_moxfield_text(loaded["main_deck"]), build_dir, build_name)
    if expl_path.exists():
        save_final_build_explanation(
            expl_path.read_text(encoding="utf-8", errors="replace"),
            build_dir, build_name)
    # the annotated judgment travels with the deck (final-build convention)
    shutil.copy2(deck_path, build_dir / "deck_list.json")
    return {"build_name": build_name, "saved_to": str(build_dir)}


# Moxfield export lines carry set/collector suffixes: "1 Sol Ring (C21) 263 *F*".
_MOX_SUFFIX = re.compile(r"\s*\([A-Za-z0-9]{2,6}\)(\s+[\w\-★†]+)?\s*(\*[A-Z]+\*)?\s*$")


def resolve_decklist_entries(decklist_text: str, commander_canonical: str,
                             *, repo) -> tuple:
    """Parse a pasted plain-text/Moxfield decklist and resolve every line against
    the DB (canonical name wins; Moxfield set/collector suffixes stripped as a
    fallback). The commander line is treated as command-zone and dropped.
    Returns `(resolved, skipped)` — unresolvable lines are SKIPPED and reported,
    never invented. Empty/unparseable text returns `([], [])`."""
    from mtgcli.deckbuilder.land_filler import remove_command_zone_cards_from_main_deck
    from mtgcli.utils.decklist_parser import parse_decklist_text

    entries = parse_decklist_text(decklist_text)
    if not entries:
        return [], []
    main_deck, _ = remove_command_zone_cards_from_main_deck(
        entries, [commander_canonical])

    resolved, skipped = [], []
    for e in main_deck:
        name = e.get("name", "")
        c = repo.get_card_by_exact_name(name)
        if c is None:  # retry without the Moxfield "(SET) 123 *F*" tail
            c = repo.get_card_by_exact_name(_MOX_SUFFIX.sub("", name))
        if c is None:
            skipped.append(name)
            continue
        resolved.append({"name": c["name"], "quantity": int(e.get("quantity", 1))})
    return resolved, skipped


def import_text_to_library(commander: str, decklist_text: str, save_dir: Path,
                           *, repo, allow_empty: bool = False) -> Dict[str, Any]:
    """Import a pasted plain-text/Moxfield decklist into the deck library as a
    named build folder (see `resolve_decklist_entries` for the name rules).
    With `allow_empty=True` an empty list is fine — that's the GUI's "create a
    fresh deck" path (commander only, cards added by editing afterwards)."""
    import json
    import tempfile

    card = repo.get_card_by_exact_name(commander.strip())
    if card is None:
        raise ValueError(f"Commander not found: {commander}")
    if not card.get("can_be_commander"):
        raise ValueError(f"'{card['name']}' can't be your commander per the local data.")
    canonical = card["name"]

    resolved, skipped = resolve_decklist_entries(decklist_text, canonical, repo=repo)
    if not allow_empty:
        if not resolved and not skipped:
            raise ValueError("No cards found in the pasted decklist.")
        if not resolved:
            raise ValueError("None of the pasted card names were found in the database.")

    loaded = {"commander": canonical, "main_deck": resolved}

    # TIER/RANK/COST tokens, best-effort (same recipe as save_build_to_library).
    tier_tok = rank_tok = None
    cost_val = 0.0
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            json.dump(loaded, f)
            tmp = Path(f.name)
        from mtgcli.models import Deck as _Deck
        deck_obj = _Deck.load(tmp, repo=repo)
        cost_val = deck_obj.total_price() or 0.0
        tier_tok = (deck_obj.tier() or {}).get("band") or None
        rank_tok = (deck_obj.rank() or {}).get("band_name") or None
    except Exception:
        pass
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    cost_tok = f"{int(round(cost_val))}usd"

    build_name = build_final_name(canonical, tier_tok, rank_tok, cost_tok, save_dir)
    build_dir = create_final_build_directory(build_name, save_dir)
    save_final_build_decklist(deck_entries_to_moxfield_text(resolved),
                              build_dir, build_name)
    # NO explanation stub on purpose: an imported deck genuinely has none — the
    # GUI offers the "✨ Explain" agent job exactly when explanation.md is absent.
    (build_dir / "deck_list.json").write_text(
        json.dumps(loaded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"build_name": build_name, "saved_to": str(build_dir),
            "commander": canonical, "imported": len(resolved), "skipped": skipped}


def rename_to_current_tokens(target: Path, commander: str, *, repo=None):
    """Rename a library deck folder (and its name-bearing files) to the freshly
    computed `<Commander>-<TIER>-<RANK>-<COST>`. Best-effort: any failure keeps
    the old name — never break a finished operation over a rename."""
    old_name = target.name
    try:
        from mtgcli.export.final_builds import (_safe_token, build_final_name,
                                                sanitize_filename_part)
        from mtgcli.models import Deck as _Deck

        deck_obj = _Deck.load(target / "deck_list.json", repo=repo)
        cost_tok = f"{int(round(deck_obj.total_price() or 0.0))}usd"
        tier_tok = (deck_obj.tier() or {}).get("band") or None
        rank_tok = (deck_obj.rank() or {}).get("band_name") or None

        tokens = [_safe_token(x) for x in (tier_tok, rank_tok, cost_tok)
                  if x is not None and _safe_token(x) != "na"]
        expected = sanitize_filename_part(commander)
        if tokens:
            expected = f"{expected}-{'-'.join(tokens)}"
        if expected == old_name:
            return target, old_name

        new_name = build_final_name(commander, tier_tok, rank_tok, cost_tok,
                                    target.parent)
        new_dir = target.parent / new_name
        target.rename(new_dir)
        for suffix in (".txt", ".explanation.md"):
            old_file = new_dir / f"{old_name}{suffix}"
            if old_file.exists():
                old_file.rename(new_dir / f"{new_name}{suffix}")
        return new_dir, new_name
    except Exception:
        return target, old_name
