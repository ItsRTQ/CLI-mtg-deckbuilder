"""CARD — the build-context card object (Consistency-engine Fase 2, user design).

Constructor contract: the NAME ARRIVES PRE-VERIFIED — the tool must have confirmed
the card exists in the DB before a Card is built. If hydration still finds nothing
(contract violation), the object fails LOUD in the Krenkooo style: a
CardNotFoundError that tells the caller what happened, offers fuzzy did-you-mean
suggestions, and says how to fix it.

Judgment fields come from the agent (purpose — one or MANY, a card's purpose
depends on the gameplan/commander — and an optional agent_note). Facts come from
the DB, hydrated fresh at construction: these objects are EPHEMERAL (they live for
the build session; the user keeps the DB updated, so facts are never trusted from
old copies).
"""
import json
from typing import Any, Dict, List, Optional

# Controlled purpose vocabulary — free text would make counts incomparable.
PURPOSES = (
    "RAMP", "DRAW", "SEARCH", "REMOVAL", "WIPE", "WINCON", "SYNERGY",
    "COMBO_PIECE", "PROTECTION", "GC", "FLEX",
)

# MTG card types for the build-facing summary (kindred = the current name for tribal).
CARD_TYPES = (
    "land", "creature", "artifact", "sorcery", "instant", "enchantment",
    "planeswalker", "battle", "kindred",
)


class CardNotFoundError(Exception):
    """Raised when a Card is built for a name the DB doesn't know (contract
    violation — names must arrive pre-verified). Carries fuzzy suggestions."""

    def __init__(self, name: str, suggestions: Optional[List[str]] = None):
        self.name = name
        self.suggestions = suggestions or []
        hint = f" Did you mean: {', '.join(self.suggestions)}?" if self.suggestions else ""
        super().__init__(
            f"Card not found in DB: '{name}'.{hint} "
            f"Card names must be verified BEFORE building a Card object — check with "
            f"`mtg card \"{name}\"` or `mtg cards-batch --verify` and use the exact DB name."
        )


def _parse_json_field(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class Card:
    """A card in build context: agent judgment + DB facts.

    Args:
        name: exact card name (PRE-VERIFIED — see module docstring).
        purpose: one purpose or a list of purposes from PURPOSES (a card can serve
            several depending on the gameplan: Sol Ring under Ragost is RAMP+SYNERGY).
        agent_note: optional brief WHY — skippable when the use is obvious (Sol Ring).
        quantity: copies in the deck (basics run >1); default 1.
        db_row: pre-fetched DB card dict (skips the lookup).
        repo: a CardRepository; defaults to the configured SQLite DB.
    """

    def __init__(self, name: str, purpose, agent_note: Optional[str] = None,
                 quantity: int = 1, *, db_row: Optional[Dict[str, Any]] = None,
                 repo=None):
        purposes = [purpose] if isinstance(purpose, str) else list(purpose or [])
        normalized = [str(p).strip().upper() for p in purposes if str(p).strip()]
        unknown = [p for p in normalized if p not in PURPOSES]
        if unknown:
            raise ValueError(
                f"Unknown purpose(s) {unknown} for '{name}'. Valid purposes: {', '.join(PURPOSES)}."
            )
        self._purpose: List[str] = normalized
        self._agent_note = agent_note
        self._quantity = max(1, int(quantity))

        row = db_row
        if row is None:
            if repo is None:
                from mtgcli.cards.repository import CardRepository
                from mtgcli.config import SQLITE_PATH
                repo = CardRepository(str(SQLITE_PATH))
            row = repo.get_card_by_exact_name(name)
            if not row:
                try:
                    sugg = [s["name"] for s in repo.suggest_similar_names(name)]
                except Exception:
                    sugg = []
                raise CardNotFoundError(name, sugg)
        self._row: Dict[str, Any] = dict(row)

        # GC is derivable: the DB flag auto-adds the purpose so the agent never has
        # to remember WotC's list.
        if self._row.get("game_changer") and "GC" not in self._purpose:
            self._purpose.append("GC")

    # ── judgment getters ─────────────────────────────────────────────────────
    @property
    def purpose(self) -> List[str]:
        return list(self._purpose)

    def add_purposes(self, purposes) -> List[str]:
        """Merge purposes in (annotation refinement — auto-seed and batch passes
        ADD, they never remove; the agent's existing judgment survives)."""
        incoming = [purposes] if isinstance(purposes, str) else list(purposes or [])
        normalized = [str(p).strip().upper() for p in incoming if str(p).strip()]
        unknown = [p for p in normalized if p not in PURPOSES]
        if unknown:
            raise ValueError(
                f"Unknown purpose(s) {unknown} for '{self.name}'. Valid: {', '.join(PURPOSES)}."
            )
        for p in normalized:
            if p not in self._purpose:
                self._purpose.append(p)
        return self.purpose

    @property
    def agent_note(self) -> Optional[str]:
        return self._agent_note

    @property
    def quantity(self) -> int:
        return self._quantity

    # ── DB fact getters ──────────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return self._row.get("name", "")

    @property
    def oracle_text(self) -> str:
        return self._row.get("oracle_text") or ""

    @property
    def type_line(self) -> str:
        return self._row.get("type_line") or ""

    @property
    def card_types(self) -> List[str]:
        low = self.type_line.lower()
        return [t for t in CARD_TYPES if t in low]

    @property
    def power(self) -> Optional[str]:
        return self._row.get("power")

    @property
    def toughness(self) -> Optional[str]:
        return self._row.get("toughness")

    @property
    def loyalty(self) -> Optional[str]:
        return self._row.get("loyalty")

    @property
    def keywords(self) -> List[str]:
        return _parse_json_field(self._row.get("keywords"), [])

    @property
    def produced_mana(self) -> Optional[List[str]]:
        return _parse_json_field(self._row.get("produced_mana"), None)

    @property
    def edhrec_rank(self) -> Optional[int]:
        return self._row.get("edhrec_rank")

    @property
    def all_parts(self) -> Dict[str, List[str]]:
        """Related cards grouped by component (the 'clean dictionary'):
        {'token': ['Food'], 'combo_piece': [...], 'meld_part': [...]}."""
        parts = _parse_json_field(self._row.get("all_parts"), []) or []
        grouped: Dict[str, List[str]] = {}
        for p in parts:
            comp = (p or {}).get("component") or "related"
            name = (p or {}).get("name")
            if name and name != self.name:
                grouped.setdefault(comp, []).append(name)
        return grouped

    @property
    def image_src(self) -> Optional[str]:
        return self._row.get("image_url")

    @property
    def mana_cost(self) -> str:
        return self._row.get("mana_cost") or ""

    @property
    def mana_value(self) -> float:
        try:
            return float(self._row.get("mana_value") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @property
    def color_identity(self) -> List[str]:
        return _parse_json_field(self._row.get("color_identity"), [])

    @property
    def usd_price(self) -> Optional[float]:
        p = self._row.get("usd_price")
        try:
            return float(p) if p is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def game_changer(self) -> bool:
        return bool(self._row.get("game_changer"))

    # ── serialization (consumed by DECK; ephemeral, facts re-hydrate on load) ─
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "quantity": self._quantity,
            "purpose": self.purpose,
            "agent_note": self._agent_note,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, repo=None) -> "Card":
        return cls(data["name"], data.get("purpose") or [],
                   agent_note=data.get("agent_note"),
                   quantity=data.get("quantity", 1), repo=repo)

    # ── build-facing summary ─────────────────────────────────────────────────
    def __str__(self) -> str:
        lines = [f"{self.name} {self.mana_cost}".rstrip()
                 + (f" x{self._quantity}" if self._quantity > 1 else "")]
        lines.append(f"  type: {', '.join(self.card_types) or self.type_line}")
        stats = []
        if self.power is not None or self.toughness is not None:
            stats.append(f"P/T {self.power or '?'}/{self.toughness or '?'}")
        if self.loyalty is not None:
            stats.append(f"loyalty {self.loyalty}")
        if self.produced_mana:
            stats.append(f"produces {{{'}{'.join(self.produced_mana)}}}")
        if self.usd_price is not None:
            stats.append(f"${self.usd_price:.2f}")
        if stats:
            lines.append("  " + " | ".join(stats))
        if self.oracle_text:
            lines.append("  " + self.oracle_text.replace("\n", "\n  "))
        # the agent's WHY wins; purpose is the fallback when the use was obvious
        lines.append(f"  >> {self._agent_note}" if self._agent_note
                     else f"  >> purpose: {', '.join(self.purpose)}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Card({self.name!r}, purpose={self.purpose}, qty={self._quantity})"
