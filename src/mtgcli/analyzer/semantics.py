"""Semantic disambiguation: negation polarity and verb/noun sense.

Two classic substring traps this fixes:
  - Negation: "can't be blocked" (positive evasion) vs "can't attack" / "can't block" (a
    downside). A bare "can't" tells you nothing; what follows flips the meaning.
  - Counter as VERB ("counter target spell" — stack interaction) vs counter as NOUN
    ("+1/+1 counter", "put a counter on" — a game marker). Same word, opposite archetypes.
"""
import re
from typing import List, Tuple

from mtgcli.analyzer.model import (
    CardProfile, Signal, Trace, EvidenceKind, Confidence, Polarity,
)

# (pattern, signal_id, label, tag, polarity, note)
_NEGATION_RULES: List[Tuple[str, str, str, str, Polarity, str]] = [
    (r"can't be blocked except", "CONDITIONAL_EVASION", "Conditional evasion (fear/menace-like)",
     "Evasion", Polarity.POSITIVE,
     "Conditional evasion: can be blocked by some creatures (fear/intimidate/menace), not truly unblockable."),
    (r"can't be blocked(?! except)", "UNBLOCKABLE", "Unblockable", "Evasion", Polarity.POSITIVE,
     "Absolute evasion — cannot be blocked at all."),
    (r"can't be countered", "UNCOUNTERABLE", "Can't be countered", "Resilience", Polarity.POSITIVE,
     "Resists stack interaction."),
    (r"can't be the target", "UNTARGETABLE", "Can't be targeted", "Protection", Polarity.POSITIVE,
     "Protection from targeting."),
    (r"can't attack", "ATTACK_RESTRICTION", "Can't attack", "Restriction", Polarity.NEGATIVE,
     "Prevents attacking (a downside or a stax effect on others)."),
    (r"can't block", "BLOCK_RESTRICTION", "Can't block", "Restriction", Polarity.NEGATIVE,
     "Prevents blocking."),
    (r"can't cast spells", "CAST_RESTRICTION", "Can't cast spells", "Stax", Polarity.RESTRICTIVE,
     "Restricts casting (stax)."),
    (r"don't untap|doesn't untap|can't untap", "UNTAP_RESTRICTION", "Untap restriction", "Stax",
     Polarity.RESTRICTIVE, "Restricts untapping (stax)."),
    (r"can't be regenerated", "NO_REGEN", "Can't be regenerated", "Removal Rider", Polarity.POSITIVE,
     "Removal that beats regeneration."),
]

_COUNTERSPELL_PATTERNS = [
    r"counter target (spell|activated ability|triggered ability|ability)",
    r"counter that (spell|ability)",
    r"counter all spells",
    r"counter (it|them) unless",
]
_COUNTER_MARKER_PATTERNS = [
    r"[+\-]\d+/[+\-]\d+ counter",
    r"\bput (a|x|that many|one or more|.{0,12}?) counters? on",
    r"\bwith (a|x|\d+|.{0,12}?) counters? on it",
    r"\b\w+ counter on",   # e.g. "slime counter on", "loyalty counter on"
]
# Suspend-style countdown context: time counters granted WITH a cast-when-empty clock
# (same line). Fewer counters = the card casts sooner, so proliferate/counter payoffs are
# actively ANTI-plan — this is a clock, not a counters strategy (batch-27 Jhoira of the
# Ghitu CW). Measured over all 39 "put ... time counter(s) on" cards: 12/12 countdown-grants
# excluded (Jhoira, Alaundo, The Tenth Doctor, Frie, Suspend...), 27 accumulator/payoff
# cards kept (Rose Tyler, Kate Stewart, As Foretold class — where MORE counters is the plan).
_SUSPEND_COUNTDOWN_RE = re.compile(
    r"gains? suspend|has suspend|have suspend|is suspended|last time counter is removed"
)


def detect_negation(text: str, profile: CardProfile, card_name: str = None) -> None:
    if not text:
        return
    low = text.lower()
    _self_subjects = ["this creature", "this permanent", "this artifact", "this land",
                      "this enchantment"]
    if card_name:
        _self_subjects.append(card_name.split(",")[0].strip().lower())
        # No-comma legends are referenced by their FIRST name in oracle text
        # ("Medomai the Ageless" -> "Medomai can't attack during extra turns") — the
        # batch-11 name class at a second site (batch-29 Medomai CW: his own drawback
        # read Stax high because the comma-split subject never matched); skip articles.
        first = card_name.split()[0].strip().lower()
        if first not in ("the", "a", "an") and len(first) > 2:
            _self_subjects.append(first)
    for pattern, sig_id, label, tag, polarity, note in _NEGATION_RULES:
        for m in re.finditer(pattern, low):
            # Scope check: "<CARDNAME> can't attack unless..." is the card's OWN drawback,
            # not a stax effect on opponents. Batch-30 Grimgrin CW: UNTAP_RESTRICTION was
            # missing from this list (the #18 audit-the-alternation lesson applied to a
            # guard's SIGNAL list) — "Grimgrin ... doesn't untap during your untap step"
            # read Stax high. For UNTAP the self-drawback additionally requires "during
            # your untap step" right AFTER the match: real stax says "their controllers'"
            # (Winter Orb) or "its controller's" (Frost Titan) and must keep its read.
            if sig_id in ("ATTACK_RESTRICTION", "BLOCK_RESTRICTION", "UNTAP_RESTRICTION"):
                before = low[max(0, m.start() - 40):m.start()]
                after = low[m.end():m.end() + 40].lstrip()
                untap_self_ok = (sig_id != "UNTAP_RESTRICTION"
                                 or after.startswith("during your untap step"))
                if untap_self_ok and any(subj in before for subj in _self_subjects):
                    profile.add_signal(Signal(
                        id="SELF_RESTRICTION", label="Own drawback (self restriction)",
                        kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                        polarity=Polarity.NEGATIVE,
                        trace=Trace(rule_id="negation.self_restriction.v1", rule_version="1.0",
                                    matched_text=m.group(0), span=m.span(),
                                    note="The card restricts ITSELF — a drawback, not stax."),
                    ))
                    break
            profile.add_signal(Signal(
                id=sig_id, label=label, kind=EvidenceKind.RULE_RELATION,
                confidence=Confidence.EXACT, polarity=polarity,
                trace=Trace(rule_id=f"neg.{sig_id.lower()}.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(), note=note),
            ))
            profile.add_tag(tag, profile.signals[-1].trace)
            break  # one match per rule is enough to assert the meaning


def detect_counter_sense(text: str, profile: CardProfile, card_name: str = None) -> None:
    """Disambiguate 'counter' the verb (counterspell) from 'counter' the noun (game marker), and
    for markers, self-growth ('a +1/+1 counter on <this card>') from a real counters strategy
    ('on target/each creature'). A self-counter is incidental growth, NOT a Counters Matter deck."""
    if not text:
        return
    low = text.lower()
    # Counterspell matching runs on RULES text only: keyword reminder text explains a
    # keyword, it isn't a counterspell plan (batch-14 Ghyrson finding — ward's reminder
    # "counter it unless that player pays {2}" read COUNTERSPELL_INTERACTION and fed a
    # false Spellslinger band). The marker branch below deliberately KEEPS reminder text:
    # dethrone's "(... put a +1/+1 counter on it.)" is a real counters read.
    low_rules = re.sub(r"\([^)]*\)", "", low)
    for pattern in _COUNTERSPELL_PATTERNS:
        m = re.search(pattern, low_rules)
        if m:
            profile.add_signal(Signal(
                id="COUNTERSPELL_INTERACTION", label="Counters spells/abilities",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.EXACT,
                trace=Trace(rule_id="sense.counterspell.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(),
                            note="'Counter' used as a verb against a spell/ability."),
            ))
            profile.add_tag("Counterspell", profile.signals[-1].trace)
            break

    # Counter-as-marker: classify by what receives the counter.
    #  - incidental/single ('on it', 'on this creature', 'on <self>', 'on that creature') → NOT a
    #    counters strategy, just a single counter placed in passing.
    #  - broad ('on target/each/all/another creature', 'on creatures you control') → Counters Matter.
    #  - '-1/-1 counter' → attrition/wither (Minus Counters), a different archetype from +1/+1.
    incidental_phrases = ["on it", "on this creature", "on this permanent", "on itself",
                          "on that creature", "on that token", "on that permanent"]
    if card_name:
        incidental_phrases.append("on " + card_name.split(",")[0].strip().lower())
    broad_phrases = ["on target", "on each", "on all ", "on another", "on one or more",
                     "on up to", "on any", "on creatures you", "on a creature you control"]

    for pattern in _COUNTER_MARKER_PATTERNS:
        m = re.search(pattern, low)
        if not m:
            continue
        # Countdown clock check FIRST: a time counter placed as part of granting a
        # suspend-style countdown (same line, reminder stripped — mirroring the batch-27
        # measurement) is a clock, never a counters strategy.
        line_start = low.rfind("\n", 0, m.start()) + 1
        line_end = low.find("\n", m.start())
        if line_end == -1:
            line_end = len(low)
        line_rules = re.sub(r"\([^)]*\)", "", low[line_start:line_end])
        if "time counter" in line_rules and _SUSPEND_COUNTDOWN_RE.search(line_rules):
            profile.add_signal(Signal(
                id="COUNTER_CLOCK", label="Suspend countdown clock (time counters)",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="sense.counter_clock.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(),
                            note="Time counters granting a suspend countdown: fewer = casts sooner; "
                                 "proliferate is anti-plan, so this is NOT a counters strategy."),
            ))
            break
        tail = low[m.start():m.start() + 70]
        is_broad = any(p in tail for p in broad_phrases)
        is_incidental = any(p in tail for p in incidental_phrases)
        if "-1/-1 counter" in low:
            # -1/-1 counters are attrition/wither, the opposite archetype from +1/+1 go-tall.
            profile.add_signal(Signal(
                id="COUNTER_MARKER_MINUS", label="Uses -1/-1 (minus) counters",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="sense.counter_minus.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(),
                            note="-1/-1 counters: attrition/wither removal, not +1/+1 go-tall."),
            ))
            profile.add_tag("Minus Counters", profile.signals[-1].trace)
        elif is_incidental and not is_broad:
            profile.add_signal(Signal(
                id="COUNTER_MARKER_SELF", label="Incidental/self counter",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="sense.counter_self.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(),
                            note="Places a counter on a single/self target (incidental, not a counters strategy)."),
            ))
        else:
            profile.add_signal(Signal(
                id="COUNTER_MARKER", label="Uses counters as game markers",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="sense.counter_marker.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(),
                            note="'Counter' used as a noun/game marker on a broad target (+1/+1, named counter)."),
            ))
            profile.add_tag("Counters Matter", profile.signals[-1].trace)
        break

