"""Timing & replacement detection.

Distinguishes the grammar of when things happen:
  - replacement effects  ("if X would Y, Z instead")  → modify an event, NOT a trigger
  - repeatable triggers  ("whenever ...")
  - event triggers       ("when ...")
  - scheduled triggers   ("at the beginning of ...")
  - static / activated   (cost ":" effect)
  - optionality          ("you may ..." → optional)
  - once-each-turn limit

Replacement detection is intentionally run first and exposed via `is_in_replacement_span` so a
later death-trigger detector won't misread "if it would die, exile it instead" as a dies trigger.
"""
import re
from typing import List, Tuple

from mtgcli.analyzer.model import (
    CardProfile, Signal, Trace, EvidenceKind, Confidence, Polarity,
)

_REPLACEMENT_PATTERNS = [
    (r"if [^.]*?would [^.]*?instead", "Replacement effect: modifies an event before it happens."),
    (r"as [^.]*?enters? the battlefield", "Replacement-style as-enters effect."),
]

# (regex, signal_id, label, timing, note)
_TIMING_PATTERNS: List[Tuple[str, str, str, str, str]] = [
    (r"\bat the beginning of\b", "SCHEDULED_TRIGGER", "Scheduled (step) trigger", "scheduled_trigger",
     "Fires at a scheduled step (upkeep/end step/combat)."),
    (r"\bwhenever\b", "REPEATABLE_TRIGGER", "Repeatable triggered ability", "repeatable_trigger",
     "Fires every time its event happens — repeatable."),
    (r"\bwhen\b", "EVENT_TRIGGER", "Triggered ability", "event_trigger",
     "Triggered ability on an event."),
]

_ONCE_EACH_TURN = r"only once each turn"
_OPTIONAL = r"\byou may\b"


def detect_replacement_effects(text: str, profile: CardProfile) -> List[Tuple[int, int]]:
    """Append REPLACEMENT_EFFECT signals and return their spans so later layers can skip them."""
    spans: List[Tuple[int, int]] = []
    if not text:
        return spans
    low = text.lower()
    for pattern, note in _REPLACEMENT_PATTERNS:
        for m in re.finditer(pattern, low):
            spans.append(m.span())
            profile.add_signal(Signal(
                id="REPLACEMENT_EFFECT",
                label="Replacement effect",
                kind=EvidenceKind.RULE_RELATION,
                confidence=Confidence.STRONG,
                timing="replacement",
                trace=Trace(
                    rule_id="timing.replacement.v1", rule_version="1.0",
                    matched_text=m.group(0), span=m.span(), note=note,
                ),
            ))
    return spans


def detect_timing(text: str, profile: CardProfile) -> None:
    """Detect trigger grammar + optionality. Run detect_replacement_effects first; trigger words
    that fall inside a replacement span are skipped (a replacement clause is not a trigger)."""
    if not text:
        return
    low = text.lower()
    replacement_spans = [s.trace.span for s in profile.get_signals("REPLACEMENT_EFFECT") if s.trace.span]

    def _in_replacement(pos: int) -> bool:
        return any(a <= pos < b for a, b in replacement_spans)

    # Only the FIRST matching trigger family is recorded per match position, most specific first.
    consumed: List[Tuple[int, int]] = []
    for pattern, sig_id, label, timing, note in _TIMING_PATTERNS:
        for m in re.finditer(pattern, low):
            start = m.start()
            if _in_replacement(start):
                continue
            if any(a <= start < b for a, b in consumed):
                continue
            consumed.append(m.span())
            profile.add_signal(Signal(
                id=sig_id, label=label, kind=EvidenceKind.FACT, confidence=Confidence.STRONG,
                timing=timing,
                trace=Trace(rule_id=f"timing.{sig_id.lower()}.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(), note=note),
            ))

    if re.search(_ONCE_EACH_TURN, low):
        m = re.search(_ONCE_EACH_TURN, low)
        profile.add_signal(Signal(
            id="ONCE_EACH_TURN_LIMIT", label="Limited to once each turn",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.EXACT,
            polarity=Polarity.RESTRICTIVE,
            trace=Trace(rule_id="timing.once_each_turn.v1", rule_version="1.0",
                        matched_text=m.group(0), span=m.span(),
                        note="Repeatability capped at once per turn (rewards multi-turn play)."),
        ))

    if re.search(_OPTIONAL, low):
        m = re.search(_OPTIONAL, low)
        profile.add_signal(Signal(
            id="OPTIONAL_EFFECT", label="Optional ('may')",
            kind=EvidenceKind.FACT, confidence=Confidence.EXACT, optional=True,
            trace=Trace(rule_id="timing.optional.v1", rule_version="1.0",
                        matched_text=m.group(0), span=m.span(),
                        note="Effect is optional, not forced."),
        ))


def is_in_replacement_span(profile: CardProfile, pos: int) -> bool:
    """True if `pos` falls inside any detected replacement-effect span (so a 'dies'/'would die'
    mention there should not be read as a triggered ability)."""
    for s in profile.get_signals("REPLACEMENT_EFFECT"):
        if s.trace.span and s.trace.span[0] <= pos < s.trace.span[1]:
            return True
    return False
