"""Card structure: split multi-face/modal cards into parts, and detect linked abilities.

Multi-face cards (MDFC, adventure, transform, split) store their faces in one oracle_text
separated by '\\n---\\n'. Each face is a different functional profile and must NOT be treated as
active simultaneously — an MDFC land/spell is "removal OR a land", not "removal AND a land at
once". `split_faces` returns the parts so each can be analyzed separately and then aggregated with
modal awareness.

Linked abilities ("do X. If you do, Y") are one conditional unit, not two independent effects —
the payoff Y only happens if the action X is completed.
"""
import re
from typing import List, NamedTuple

from mtgcli.analyzer.model import (
    CardProfile, Signal, Trace, EvidenceKind, Confidence,
)

FACE_SEPARATOR = "\n---\n"


class Face(NamedTuple):
    index: int
    part_type: str   # front_face, back_face, adventure, creature, left_split, right_split, single
    text: str


def _split_saga_chapters(oracle_text: str) -> List[Face]:
    """Split a Saga into its chapters. Chapters are marked 'I —', 'II —', 'III —' (roman numeral
    + em/en dash), optionally grouped ('I, II —'). The leading reminder line is dropped."""
    # chapter markers: start-of-line roman numerals (possibly grouped) followed by a dash
    pattern = re.compile(r"(?m)^\s*([IVX]+(?:\s*,\s*[IVX]+)*)\s*[—–-]\s*")
    matches = list(pattern.finditer(oracle_text))
    if len(matches) < 2:
        return []
    faces = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(oracle_text)
        text = oracle_text[start:end].strip()
        label = f"chapter_{m.group(1).replace(' ', '')}"
        faces.append(Face(i, label, text))
    return faces


def split_faces(oracle_text: str, layout: str = "normal") -> List[Face]:
    """Split a card's oracle text into its functional parts, labeled by layout."""
    if not oracle_text:
        return [Face(0, "single", "")]

    layout = (layout or "normal").lower()

    # Sagas: split by chapter markers (I —, II —, ...) so each chapter's distinct role is analyzed
    # separately instead of blending removal/ramp/recursion into one muddle.
    if layout == "saga":
        chapters = _split_saga_chapters(oracle_text)
        if chapters:
            return chapters

    parts = [p.strip() for p in oracle_text.split(FACE_SEPARATOR)]
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        return [Face(0, "single", oracle_text.strip())]

    labels_by_layout = {
        "modal_dfc": ["front_face", "back_face"],
        "transform": ["front_face", "back_face"],
        "adventure": ["creature", "adventure"],
        "split": ["left_split", "right_split"],
        "aftermath": ["main", "aftermath"],
    }
    labels = labels_by_layout.get(layout)
    faces = []
    for i, text in enumerate(parts):
        if labels and i < len(labels):
            ptype = labels[i]
        else:
            ptype = f"part_{i}"
        faces.append(Face(i, ptype, text))
    return faces


def is_multipart(oracle_text: str) -> bool:
    return bool(oracle_text) and FACE_SEPARATOR in oracle_text


def mark_modal_flexibility(profile: CardProfile, faces: List[Face]) -> None:
    """Add a MODAL_FLEXIBILITY signal to an aggregate profile so downstream layers know the
    functions come from different faces/modes and are not simultaneous."""
    if len(faces) <= 1:
        return
    profile.add_signal(Signal(
        id="MODAL_FLEXIBILITY",
        label="Multiple functional modes/faces",
        kind=EvidenceKind.HEURISTIC,
        confidence=Confidence.STRONG,
        trace=Trace(
            rule_id="structure.modal.v1", rule_version="1.0",
            matched_text=f"{len(faces)} parts: {', '.join(f.part_type for f in faces)}",
            span=None,
            note="Card has multiple functional profiles; modes are alternatives, not simultaneous.",
        ),
    ))


_LINKED_IF_YOU_DO = re.compile(r"([^.]+?)\.\s*if you do,\s*([^.]+)", re.IGNORECASE)


def detect_linked_abilities(text: str, profile: CardProfile) -> None:
    """Detect 'do X. If you do, Y' — Y is conditional on completing X, not guaranteed."""
    if not text:
        return
    for m in _LINKED_IF_YOU_DO.finditer(text):
        action = m.group(1).strip()[-60:]
        payoff = m.group(2).strip()[:60]
        profile.add_signal(Signal(
            id="LINKED_IF_YOU_DO",
            label="Linked ability (payoff depends on completing the action)",
            kind=EvidenceKind.RULE_RELATION,
            confidence=Confidence.STRONG,
            optional=False,
            trace=Trace(
                rule_id="structure.linked_if_you_do.v1", rule_version="1.0",
                matched_text=m.group(0)[:120], span=m.span(),
                note=f"Payoff is conditional. Action: '{action}' | Payoff: '{payoff}'",
            ),
        ))
