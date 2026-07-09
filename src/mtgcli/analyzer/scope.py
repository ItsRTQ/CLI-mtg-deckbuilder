"""Scope extraction: who an effect affects, and whether it's symmetric or one-sided.

This is the GF-1 fix generalized. "Destroy each creature" (symmetric board wipe) and "Destroy
each creature you don't control" (one-sided wipe) read almost identically to substring matching
but mean opposite things strategically. Detecting scope + symmetry lets later layers tell a
punisher from plain removal, an anthem from a debuff, etc.

Order matters: the more specific phrases ("creature you don't control") must be tried before the
generic ones ("creature"), so a qualified scope isn't swallowed by the bare one.
"""
import re
from typing import List, Tuple

from mtgcli.analyzer.model import (
    CardProfile, Signal, Trace, EvidenceKind, Confidence,
)

# (regex, scope_id, symmetry, note). Ordered most-specific first: a qualified TARGET (single)
# must be matched before the bare mass "you don't control", or a targeted fight/removal gets
# mislabeled as a one-sided board effect (the GF-1 bug).
_SCOPE_RULES: List[Tuple[str, str, str, str]] = [
    (r"target creature you don't control", "TARGET_OPPOSING_CREATURE", "targeted_opponent",
     "Targets one creature you don't control."),
    (r"target creature you control", "TARGET_YOUR_CREATURE", "targeted_self",
     "Targets one of your creatures."),
    (r"target permanent you don't control", "TARGET_OPPOSING_PERMANENT", "targeted_opponent",
     "Targets one permanent you don't control."),
    (r"creatures? you don't control", "OPPOSING_CREATURES", "asymmetric_opponents",
     "Affects opponents' creatures (one-sided)."),
    (r"permanents? you don't control", "OPPOSING_PERMANENTS", "asymmetric_opponents",
     "Affects opponents' permanents (one-sided)."),
    (r"creatures? you control", "YOUR_CREATURES", "asymmetric_self",
     "Affects your own creatures."),
    (r"permanents? you control", "YOUR_PERMANENTS", "asymmetric_self",
     "Affects your own permanents."),
    (r"each other creature", "EACH_OTHER_CREATURE", "symmetric",
     "Affects every other creature."),
    (r"all creatures", "ALL_CREATURES", "symmetric", "Affects all creatures (symmetric)."),
    (r"each creature", "EACH_CREATURE", "symmetric", "Affects each creature (symmetric)."),
    (r"each opponent", "EACH_OPPONENT", "opponents_only", "Affects each opponent."),
    (r"target opponent", "TARGET_OPPONENT", "targeted_opponent", "Targets one opponent."),
    (r"each player", "EACH_PLAYER", "symmetric_players", "Affects each player (symmetric)."),
    (r"target creature", "TARGET_CREATURE", "targeted", "Targets a single creature."),
    (r"target player", "TARGET_PLAYER", "targeted_player", "Targets one player."),
]

# Phrases that, once consumed, shouldn't also match a more generic overlapping rule on the same
# span. We handle this by masking matched spans before trying the next (less specific) rule.


def detect_scope(text: str, profile: CardProfile) -> None:
    """Append SCOPE_* signals for each distinct scope phrase found. More specific phrases are
    matched first and their spans masked so a bare 'creature' rule can't re-claim them."""
    if not text:
        return
    low = text.lower()
    masked = list(low)  # we blank out consumed spans with \x00 so later regexes skip them

    for pattern, scope_id, symmetry, note in _SCOPE_RULES:
        for m in re.finditer(pattern, "".join(masked)):
            start, end = m.span()
            matched_text = low[start:end]
            profile.add_signal(Signal(
                id=f"SCOPE_{scope_id}",
                label=f"Scope: {symmetry}",
                kind=EvidenceKind.FACT,
                confidence=Confidence.STRONG,
                scope=scope_id,
                symmetry=symmetry,
                trace=Trace(
                    rule_id=f"scope.{scope_id.lower()}.v1",
                    rule_version="1.0",
                    matched_text=matched_text,
                    span=(start, end),
                    note=note,
                ),
            ))
            # mask this span so a more generic later rule won't re-match inside it
            for i in range(start, end):
                masked[i] = "\x00"


def dominant_symmetry(profile: CardProfile) -> str | None:
    """Coarse summary used by higher layers: if any one-sided opponent scope is present and no
    symmetric/self scope contradicts the read, the card leans asymmetric-against-opponents."""
    syms = {s.symmetry for s in profile.signals if s.symmetry}
    if "asymmetric_opponents" in syms or "opponents_only" in syms:
        # Only call it a punisher read if it isn't ALSO a plain targeted single removal.
        only_targeted = syms <= {"targeted_opponent", "targeted"}
        if not only_targeted:
            return "asymmetric_opponents"
    if "asymmetric_self" in syms:
        return "asymmetric_self"
    if "symmetric" in syms or "symmetric_players" in syms:
        return "symmetric"
    return None
