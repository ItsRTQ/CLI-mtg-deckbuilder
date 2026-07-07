"""DECK — the build-context deck object (Consistency-engine Fase 2, user design).

Composition over inheritance (deliberate: not a List subclass). The Deck is its own
guardian: all mutation goes through add()/remove() (batch-friendly for the agent),
which enforce size (quantity-aware, commanders excluded), singleton (basic lands
merge instead), and color identity — failing LOUD with actionable messages.

Combos live at deck level, grouped by class:
    {"infinite": [{"cards_needed": [...], "how_to": "..."}], "non_infinite": [...],
     "utility": [...], "auto_win": [...]}

Ephemeral like Card: serialization persists JUDGMENT only (names, quantities,
purposes, notes, combos) — facts re-hydrate from the DB on load.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from mtgcli.models.card import Card

COMBO_CLASSES = ("infinite", "non_infinite", "utility", "auto_win")
_COMBO_ALIASES = {"autowin": "auto_win", "non-infinite": "non_infinite",
                  "noninfinite": "non_infinite"}

# Moxfield-style PRIMARY type: a card lands in exactly one bucket, first match wins
# (Artifact Creature -> creature; Dryad Arbor -> land; Kindred is never primary).
_PRIMARY_TYPE_ORDER = ("land", "creature", "planeswalker", "battle", "instant",
                       "sorcery", "artifact", "enchantment")

# The ideal curve behind mana_curve_score — THE one judgment constant in the formula
# (user formula: 10 * max(0, 1 - TVD(deck_curve, ideal)/... )). Declared, not hidden;
# proportions of NONLAND cards per mv bucket, summing to 1.0. Commander-typical
# midrange shape; tunable (candidate for a seed file if we ever calibrate it).
IDEAL_CURVE: Dict[str, float] = {
    "0": 0.02, "1": 0.10, "2": 0.25, "3": 0.25, "4": 0.18,
    "5": 0.10, "6": 0.06, "7+": 0.04,
}


class DeckError(Exception):
    """Loud, actionable deck-mutation failure (the guardian speaking)."""


def _is_basic(card: Card) -> bool:
    return "basic" in card.type_line.lower()


class Deck:
    """Args:
        commanders: a Card or list of Cards (1-2: partner / background pairs).
        deck_list: optional initial cards (routed through add() — validated).
        agent_note: the deck's theme / gameplan / way of the deck.
    """

    def __init__(self, commanders: Union[Card, List[Card]],
                 deck_list: Optional[List[Card]] = None,
                 agent_note: Optional[str] = None):
        cmds = [commanders] if isinstance(commanders, Card) else list(commanders or [])
        if not 1 <= len(cmds) <= 2:
            raise DeckError(f"A deck needs 1 or 2 commanders (got {len(cmds)}).")
        self._commanders: List[Card] = cmds
        self._cards: List[Card] = []
        self._combos: Dict[str, List[Dict[str, Any]]] = {c: [] for c in COMBO_CLASSES}
        self.agent_note = agent_note
        # The build CONTRACT (user answers: budget, budget_mode, bracket, salt...) —
        # travels WITH the deck instead of living only in conversation memory
        # (mid-build compaction risk, Fase-4 item).
        self.config: Dict[str, Any] = {}
        if deck_list:
            self.add(deck_list)

    # ── identity helpers ─────────────────────────────────────────────────────
    @property
    def commanders(self) -> List[Card]:
        return list(self._commanders)

    @property
    def cards(self) -> List[Card]:
        return list(self._cards)

    @property
    def max_size(self) -> int:
        return 100 - len(self._commanders)

    def _color_identity(self) -> set:
        ident = set()
        for c in self._commanders:
            ident.update(c.color_identity)
        return ident

    def _find(self, name: str) -> Optional[Card]:
        low = name.lower()
        return next((c for c in self._cards if c.name.lower() == low), None)

    # ── mutation (batch-friendly, the guardian) ──────────────────────────────
    def add(self, cards: Union[Card, List[Card]]) -> List[str]:
        """Add one card or a batch. ATOMIC: the whole batch is validated first;
        any failure raises DeckError and nothing is added. Returns added names."""
        batch = [cards] if isinstance(cards, Card) else list(cards)
        ident = self._color_identity()
        problems: List[str] = []
        incoming = self.size()
        for card in batch:
            incoming += card.quantity
            if not _is_basic(card):
                if self._find(card.name) or any(
                        b is not card and b.name.lower() == card.name.lower()
                        and not _is_basic(b) for b in batch):
                    problems.append(f"duplicate (singleton): {card.name}")
                if card.quantity > 1:
                    problems.append(f"nonbasic with quantity {card.quantity}: {card.name}")
            extra = set(card.color_identity) - ident
            if extra:
                problems.append(f"color identity violation: {card.name} adds {sorted(extra)} "
                                f"outside {sorted(ident) or ['C']}")
        if incoming > self.max_size:
            problems.append(f"size would be {incoming}/{self.max_size} "
                            f"(quantity-aware; commanders excluded)")
        if problems:
            raise DeckError("Batch rejected (nothing added):\n  - " + "\n  - ".join(problems))
        for card in batch:
            existing = self._find(card.name)
            if existing is not None and _is_basic(card):
                existing._quantity += card.quantity  # basics merge
            else:
                self._cards.append(card)
        return [c.name for c in batch]

    def remove(self, names: Union[str, List[str]], quantity: int = 1) -> List[str]:
        """Remove one name or a batch. Basics decrement by `quantity` (entry drops
        at 0); nonbasics drop whole. ATOMIC: unknown names reject the whole batch."""
        batch = [names] if isinstance(names, str) else list(names)
        missing = [n for n in batch if self._find(n) is None]
        if missing:
            raise DeckError("Batch rejected (nothing removed) — not in deck: "
                            + ", ".join(missing))
        removed = []
        for n in batch:
            card = self._find(n)
            if _is_basic(card) and card.quantity > quantity:
                card._quantity -= quantity
            else:
                self._cards.remove(card)
            removed.append(card.name)
        return removed

    # ── combos ───────────────────────────────────────────────────────────────
    def add_combo(self, combo_class: str, cards_needed: List[str], how_to: str = "") -> None:
        cls = _COMBO_ALIASES.get(combo_class.strip().lower(), combo_class.strip().lower())
        if cls not in COMBO_CLASSES:
            raise DeckError(f"Unknown combo class '{combo_class}'. "
                            f"Valid: {', '.join(COMBO_CLASSES)}.")
        if not cards_needed:
            raise DeckError("A combo needs its cards_needed list.")
        self._combos[cls].append({"cards_needed": list(cards_needed), "how_to": how_to})

    @property
    def combos(self) -> Dict[str, List[Dict[str, Any]]]:
        return {k: list(v) for k, v in self._combos.items()}

    # ── metrics ──────────────────────────────────────────────────────────────
    def size(self) -> int:
        """Main-deck card count, quantity-aware. Commanders are command zone."""
        return sum(c.quantity for c in self._cards)

    def total_size(self) -> int:
        return self.size() + len(self._commanders)

    def total_by_purpose(self) -> Dict[str, int]:
        totals: Dict[str, int] = {}
        for c in self._cards:
            for p in c.purpose:
                totals[p] = totals.get(p, 0) + c.quantity
        return dict(sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])))

    def total_price(self) -> float:
        return round(sum((c.usd_price or 0.0) * c.quantity for c in self._cards), 2)

    def primary_type(self, card: Card) -> str:
        low = card.type_line.lower()
        return next((t for t in _PRIMARY_TYPE_ORDER if t in low), "other")

    def card_type_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self._cards:
            t = self.primary_type(c)
            counts[t] = counts.get(t, 0) + c.quantity
        return counts

    def card_types(self) -> str:
        """Moxfield-style primary-type totals, one per line."""
        counts = self.card_type_counts()
        order = [t for t in _PRIMARY_TYPE_ORDER if t in counts] + \
                [t for t in counts if t not in _PRIMARY_TYPE_ORDER]
        plural = {"sorcery": "sorceries"}
        return "\n".join(f"{plural.get(t, t + 's')}={counts[t]}" for t in order)

    def mana_curve(self) -> Dict[str, int]:
        """Nonland mv distribution over the user's buckets (0..6, 7+)."""
        curve = {k: 0 for k in IDEAL_CURVE}
        for c in self._cards:
            if self.primary_type(c) == "land":
                continue
            mv = int(c.mana_value)
            curve["7+" if mv >= 7 else str(max(0, mv))] += c.quantity
        return curve

    def mana_curve_score(self) -> Optional[float]:
        """User formula: 10 × max(0, 1 − (Σ |bucket_share − ideal_share|) / 2).

        The Σ/2 term is the total variation distance between the deck's nonland
        curve and IDEAL_CURVE: 10 = identical shape, 0 = maximally different.
        None when the deck has no nonland cards yet."""
        curve = self.mana_curve()
        nonland = sum(curve.values())
        if nonland == 0:
            return None
        tvd = sum(abs(curve[b] / nonland - IDEAL_CURVE[b]) for b in IDEAL_CURVE) / 2
        return round(10 * max(0.0, 1 - tvd), 2)

    # ── serialization (judgment only; facts re-hydrate on load) ─────────────
    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if len(self._commanders) == 1:
            out["commander"] = self._commanders[0].name
        else:
            out["commanders"] = [c.name for c in self._commanders]
        out["agent_note"] = self.agent_note
        if self.config:
            out["config"] = dict(self.config)
        out["main_deck"] = [c.to_dict() for c in self._cards]
        out["combos"] = self.combos
        return out

    def save(self, path: Union[str, Path]) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    @classmethod
    def load(cls, path: Union[str, Path], *, repo=None) -> "Deck":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        names = data.get("commanders") or ([data["commander"]] if data.get("commander") else [])
        cmds = [Card(n, ["WINCON"], repo=repo) for n in names]
        deck = cls(cmds, agent_note=data.get("agent_note"))
        deck.config = dict(data.get("config") or {})
        deck.add([Card.from_dict(e, repo=repo) for e in data.get("main_deck", [])])
        for cls_name, combos in (data.get("combos") or {}).items():
            for cb in combos:
                deck.add_combo(cls_name, cb.get("cards_needed", []), cb.get("how_to", ""))
        return deck

    # ── print: card count + Moxfield-format list ─────────────────────────────
    def __str__(self) -> str:
        lines = [f"{self.size()} cards"]
        lines.append("Commander")
        for c in self._commanders:
            lines.append(f"1 {c.name}")
        lines.append("")
        lines.append("Deck")
        for c in sorted(self._cards, key=lambda x: (self.primary_type(x), x.name)):
            lines.append(f"{c.quantity} {c.name}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        names = " + ".join(c.name for c in self._commanders)
        return f"Deck({names}, {self.size()} cards)"

    # ── the tier (Fase 3: consistency math over this deck's annotation) ──────
    def tier(self) -> Dict[str, Any]:
        """Consistency report: exact draw/assembly probabilities over the annotated
        purposes and combos → 0-10 score in 0.5 bands (F below 5.0). Consider-only."""
        from mtgcli.models.consistency import consistency_report
        return consistency_report(self)
