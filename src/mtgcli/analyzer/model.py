"""Data model for the universal card analyzer (parallel to oracle_hooks/card_profile).

Design principle: evidence first, scores never. Every conclusion the analyzer draws is a
`Signal` that carries WHY it was drawn (`Trace`: which rule, what text matched, where) and WHAT
KIND of claim it is (`EvidenceKind`: a hard fact vs a true rules relation vs a design heuristic
vs a meta opinion). No magic numbers: confidence is an explicit ordinal band, not an invented
decimal, and downstream layers classify support qualitatively (defining/supporting/weak) rather
than summing heterogeneous signals.

This module is intentionally standalone — pure dataclasses + serialization, no DB, no regex —
so it can be unit-tested deterministically and evolved without touching the existing pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class EvidenceKind(str, Enum):
    """What kind of claim a signal makes — keeps facts, rules-relations, heuristics, and meta
    opinions from being mixed into one indistinguishable 'score'."""
    FACT = "fact"                    # mana value, type line, colors — objectively true
    RULE_RELATION = "rule_relation"  # true by MTG rules ("deals combat damage" ⇒ must connect)
    HEURISTIC = "heuristic"          # design assumption ("combat trigger wants evasion")
    META_OPINION = "meta_opinion"    # table psychology (salt, hate-pull) — subjective, meta-dependent


class Confidence(str, Enum):
    """Ordinal confidence — deliberately NOT a decimal. A '0.97' implies a precision we can't
    justify; these bands say what we actually mean."""
    EXACT = "exact"          # an unambiguous Oracle phrase ("can't be blocked")
    STRONG = "strong"        # strong phrase match, little ambiguity
    LIKELY = "likely"        # broad but probably right
    AMBIGUOUS = "ambiguous"  # could be several things; needs context
    WEAK = "weak"            # a faint hint only

    @property
    def rank(self) -> int:
        return {"weak": 1, "ambiguous": 2, "likely": 3, "strong": 4, "exact": 5}[self.value]


class Polarity(str, Enum):
    POSITIVE = "positive"        # grants/enables something (e.g. can't be blocked ⇒ evasion)
    NEGATIVE = "negative"        # denies/prevents something (e.g. can't attack)
    RESTRICTIVE = "restrictive"  # a tax/limit (e.g. only once each turn)


@dataclass
class Trace:
    """Provenance for a single conclusion: which rule fired, on what text, where, and why."""
    rule_id: str
    rule_version: str
    matched_text: str
    note: str
    span: Optional[Tuple[int, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.span is not None:
            d["span"] = list(self.span)
        return d


@dataclass
class Signal:
    """One detected feature of a card, with full provenance. Never a bare number."""
    id: str
    label: str
    kind: EvidenceKind
    confidence: Confidence
    trace: Trace
    scope: Optional[str] = None       # YOUR_CREATURES, OPPOSING_CREATURES, EACH_OPPONENT, ...
    symmetry: Optional[str] = None     # asymmetric_self, asymmetric_opponents, symmetric, targeted
    timing: Optional[str] = None       # repeatable_trigger, event_trigger, scheduled, replacement, static
    optional: Optional[bool] = None    # "may" ⇒ True; forced ⇒ False
    polarity: Polarity = Polarity.POSITIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind.value,
            "confidence": self.confidence.value,
            "scope": self.scope,
            "symmetry": self.symmetry,
            "timing": self.timing,
            "optional": self.optional,
            "polarity": self.polarity.value,
            "trace": self.trace.to_dict(),
        }


@dataclass
class NegativeAssertion:
    """Absence of evidence, framed honestly — 'no draw SIGNAL detected', not 'does not draw'."""
    claim: str
    confidence: Confidence
    basis: str

    def to_dict(self) -> Dict[str, Any]:
        return {"claim": self.claim, "confidence": self.confidence.value, "basis": self.basis}


# Schema/ruleset versions so cached profiles can be invalidated when rules change.
ANALYZER_SCHEMA_VERSION = "card-analyzer.v0.1.0"
RULESET_VERSION = "rules.v0.1.0"


@dataclass
class CardProfile:
    """Universal (deck-independent) functional profile of one card part/face.

    Holds raw signals + derived tags/roles (each tag/role keeps the traces that justify it).
    Deliberately has NO scores and NO include/cut verdict — that is the deck-fit layer's job,
    and ultimately the agent's judgment."""
    name: str
    facts: Dict[str, Any] = field(default_factory=dict)
    signals: List[Signal] = field(default_factory=list)
    tags: Dict[str, List[Trace]] = field(default_factory=dict)
    roles: Dict[str, List[Trace]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    needs: List[str] = field(default_factory=list)
    negative_assertions: List[NegativeAssertion] = field(default_factory=list)
    schema_version: str = ANALYZER_SCHEMA_VERSION
    ruleset_version: str = RULESET_VERSION

    def has_signal(self, signal_id: str) -> bool:
        return any(s.id == signal_id for s in self.signals)

    def get_signals(self, signal_id: str) -> List[Signal]:
        return [s for s in self.signals if s.id == signal_id]

    def add_signal(self, signal: Signal) -> None:
        self.signals.append(signal)

    def add_tag(self, tag: str, trace: Trace) -> None:
        self.tags.setdefault(tag, []).append(trace)

    def add_role(self, role: str, trace: Trace) -> None:
        self.roles.setdefault(role, []).append(trace)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schema_version": self.schema_version,
            "ruleset_version": self.ruleset_version,
            "facts": self.facts,
            "signals": [s.to_dict() for s in self.signals],
            "tags": {t: [tr.to_dict() for tr in traces] for t, traces in self.tags.items()},
            "roles": {r: [tr.to_dict() for tr in traces] for r, traces in self.roles.items()},
            "warnings": self.warnings,
            "needs": self.needs,
            "negative_assertions": [na.to_dict() for na in self.negative_assertions],
        }
