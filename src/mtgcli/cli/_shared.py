"""Shared imports and helpers for the CLI command modules.

This module carries the exact import surface the former monolithic ``cli.py``
had at module level, plus the small display/helpers (``print_json``,
``has_power_toughness``, ``_apply_max_price``) and the shared Typer ``app``.
Command modules do ``from mtgcli.cli._shared import *`` so a command's body is
byte-for-byte the code it was before the split, with the same names in scope.

Because these names become real globals of each command module, the test
suite's ``monkeypatch.setattr``/``patch`` on e.g. ``SQLITE_PATH`` /
``CardRepository`` still works — it just targets the module that now owns
the command.
"""
import typer
import json
import sys
from rich import print
from typing import Optional, List, Any, Dict
from pathlib import Path
from mtgcli.config import PROJECT_ROOT, RAW_CARDS_PATH, SQLITE_PATH, SEED_DATA_DIR, OUTPUT_DIR, LOGS_DIR
from mtgcli.utils.temp_cleaner import clean_output_files
from mtgcli.export.final_builds import (
    normalize_bracket, next_final_build_name, create_final_build_directory,
    save_final_build_decklist, save_final_build_explanation,
    build_minimal_explanation, deck_entries_to_moxfield_text, sanitize_filename_part
)
from mtgcli.config import FINAL_BUILDS_DIR
from mtgcli.data.download_cards import download_default_cards
from mtgcli.data.build_sqlite import build_sqlite_database
from mtgcli.cards.repository import CardRepository
from mtgcli.cards.search import (
    search_commander_legal_cards,
    search_by_tags,
    normalize_type_filter,
    card_matches_type,
    supported_types_message,
    UnknownTypeFilterError,
)
from mtgcli.cards.query_parser import QueryConflictError, empty_parsed
from mtgcli.utils.json_io import read_json, write_json
from mtgcli.export.moxfield import export_deck_to_moxfield
from mtgcli.validator.deck_validator import validate_commander_deck
from mtgcli.deckbuilder.enrich_deck import enrich_deck
from mtgcli.deckbuilder.basic_lands import suggest_basic_lands
from mtgcli.deckbuilder.deck_check import check_deck_quality
from mtgcli.deckbuilder.suggestion_scorer import (
    score_suggestion, extract_commander_synergy_signals, check_card_synergy
)
from mtgcli.deckbuilder.commander_analyzer import analyze_commander
from mtgcli.deckbuilder.theme_profiles import list_themes, list_packages, get_theme_profile
from mtgcli.deckbuilder.package_search import search_theme_package
from mtgcli.deckbuilder.package_scorer import score_package_card
from mtgcli.deckbuilder.pricing import resolve_card_price, build_budget_summary
from mtgcli.deckbuilder.land_filler import fill_deck_with_lands, remove_command_zone_cards_from_main_deck
from mtgcli.utils.deck_io import normalize_deck_input, load_deck_file
from mtgcli.utils.decklist_parser import parse_decklist_text
from mtgcli.category_counts import calculate_category_counts, format_human_readable
from mtgcli.category_counts.output import format_table

from mtgcli.cli._app import app


# ── helpers (moved verbatim from the former cli.py) ──────────────────────────
def _emit_json_error(payload: dict) -> None:
    """Write error JSON RAW to stdout — rich.print would word-wrap long lines and inject
    newlines inside the JSON string, breaking agent parsers."""
    import sys as _s, json as _j
    _s.stdout.write(_j.dumps(payload) + "\n")


def require_database(db_path, json_output: bool) -> None:
    """Exit(1) when the SQLite DB is missing — structured JSON under --json-output.

    Takes the caller's ``SQLITE_PATH`` as an argument (instead of reading the
    module global here) so the test suite's monkeypatch of a command module's
    ``SQLITE_PATH`` keeps controlling this check.
    """
    if db_path.exists():
        return
    if json_output:
        _emit_json_error({"error": {"type": "environment",
                          "message": "Database not found. Please run 'init-data' first."}})
    else:
        print("[red]Database not found. Please run 'init-data' first.[/red]")
    raise typer.Exit(code=1)


def print_json(payload) -> None:
    """Emit JSON to stdout WITHOUT rich formatting.

    rich's ``print`` wraps long lines and can inject newlines into JSON string
    values, producing invalid control characters that break strict
    ``json.loads()``. Use this for all machine-readable JSON output.
    """
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def has_power_toughness(card: dict) -> bool:
    """True if the card has any power/toughness data to display."""
    return bool(card.get("power") or card.get("toughness"))

def _apply_max_price(results, max_price):
    """Budget filter shared by all search branches (cards with unknown price are kept)."""
    if max_price is None:
        return results
    def ok(c):
        p = c.get("usd_price")
        try:
            return p is None or float(p) <= max_price
        except (TypeError, ValueError):
            return True
    return [c for c in results if ok(c)]


def _apply_max_rank(results, max_rank):
    """Popularity filter shared by the search family (cards with unknown rank are kept —
    17% of the DB is digital-only/unranked; dropping them would silently hide real cards).
    CONSIDER-ONLY tooling: rank measures how played a card is, not how strong."""
    if max_rank is None:
        return results
    def ok(c):
        r = c.get("edhrec_rank")
        try:
            return r is None or float(r) <= max_rank
        except (TypeError, ValueError):
            return True
    return [c for c in results if ok(c)]


def fmt_price(card):
    """Price chip for search-family result lines: ' [green]$1.23[/green]', or ' [dim]$?[/dim]'
    when unknown. Shown on every shortlist row so package allocation can happen AT PICK TIME
    (full build #3 friction: --max-price filtered by price but never showed it, so hand
    allocation ran on memory prices)."""
    p = card.get("usd_price")
    try:
        return f" [green]${float(p):.2f}[/green]"
    except (TypeError, ValueError):
        return " [dim]$?[/dim]"
