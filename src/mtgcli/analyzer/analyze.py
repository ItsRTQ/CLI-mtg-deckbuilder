"""analyze_card: the universal (deck-independent) orchestrator.

Ties the parallel analyzer layers together for one card, fuses them with the existing 97-tag
content vocabulary (via card_function_profile, so we don't duplicate content detection), and
returns one CardProfile with full provenance and ordinal archetype bands — no scores, no verdict.

Multi-face cards are split; each face is analyzed separately and then aggregated with modal
awareness (modes are alternatives, not simultaneous).
"""
from typing import Any, Dict, List

from mtgcli.analyzer.model import CardProfile, Trace
from mtgcli.analyzer.scope import detect_scope, dominant_symmetry
from mtgcli.analyzer.timing import detect_replacement_effects, detect_timing
from mtgcli.analyzer.semantics import detect_negation, detect_counter_sense
from mtgcli.analyzer.structure import split_faces, mark_modal_flexibility, detect_linked_abilities
from mtgcli.analyzer.content import detect_trigger_families, detect_scaling, detect_tribal, detect_keywords, detect_repeatable_token_making, detect_trigger_doubler, detect_modal_structure, detect_sac_outlet, detect_control_change, detect_power_matters, detect_provides, detect_graveyard_clone, detect_lost_life_payoff, detect_graveyard_scaling, detect_theft_exile
from mtgcli.analyzer.mapping import map_archetypes


def _run_extraction(text: str, profile: CardProfile, card_name: str = None) -> None:
    """Run the per-face extraction layers in dependency order (replacement before timing)."""
    detect_replacement_effects(text, profile)
    detect_timing(text, profile)
    detect_scope(text, profile)
    detect_negation(text, profile, card_name=card_name)
    detect_counter_sense(text, profile, card_name=card_name)
    detect_linked_abilities(text, profile)
    detect_trigger_families(text, profile, card_name=card_name)
    detect_scaling(text, profile)
    detect_tribal(text, profile)
    detect_repeatable_token_making(text, profile)
    detect_trigger_doubler(text, profile)
    detect_sac_outlet(text, profile)
    detect_control_change(text, profile)
    detect_power_matters(text, profile)
    detect_provides(text, profile)
    detect_graveyard_clone(text, profile)
    detect_lost_life_payoff(text, profile)
    detect_graveyard_scaling(text, profile)
    detect_theft_exile(text, profile)


def analyze_card(card: Dict[str, Any]) -> Dict[str, Any]:
    """Universal functional analysis of a single card. `card` is a DB row dict (name, oracle_text,
    type_line, mana_value, layout, power, toughness, color_identity, ...)."""
    name = card.get("name", "")
    oracle = card.get("oracle_text", "") or ""
    layout = card.get("layout", "normal")

    profile = CardProfile(name=name)
    profile.facts = {
        "mana_value": card.get("mana_value"),
        "type_line": card.get("type_line"),
        "color_identity": card.get("color_identity"),
        "power": card.get("power"),
        "toughness": card.get("toughness"),
        "layout": layout,
    }

    # Per-face extraction, then aggregate.
    faces = split_faces(oracle, layout)
    face_reports = []
    for face in faces:
        fp = CardProfile(name=f"{name} [{face.part_type}]")
        _run_extraction(face.text, fp, card_name=name)
        # merge face signals + tags into the aggregate
        for s in fp.signals:
            profile.add_signal(s)
        for tag, traces in fp.tags.items():
            for tr in traces:
                profile.add_tag(tag, tr)
        face_reports.append({"part_type": face.part_type, "signal_ids": [s.id for s in fp.signals]})
    mark_modal_flexibility(profile, faces)

    # Card-level keyword/type detection (needs the whole card, not per-face).
    detect_keywords(oracle, profile, type_line=card.get("type_line", ""))
    detect_modal_structure(oracle, profile)

    # Content evidence from the existing 97-tag vocabulary (no parallel content detector).
    try:
        from mtgcli.deckbuilder.card_profile import matched_tags
        content_tags = matched_tags(card)
    except Exception:
        content_tags = []
    for t in content_tags:
        profile.add_tag(t, Trace(rule_id="content.tag.v1", rule_version="1.0",
                                 matched_text=t, note="Matched existing functional tag vocabulary."))

    # Fuse structural signals + content tags into archetype support (ordinal bands, no sums).
    evidence = {s.id for s in profile.signals} | set(content_tags)
    archetypes = [a.to_dict() for a in map_archetypes(evidence)]

    # Composite reads that need cross-layer info.
    symmetry = dominant_symmetry(profile)
    if symmetry == "asymmetric_opponents":
        # Polarity matters: one-sided TOWARD opponents can be punishment (damage/loss) or a
        # GIFT (group hug hands them cards/lands). The scope layer knows the reach, not the
        # polarity — a hug commander must not get punisher build advice.
        if "group_hug" in evidence:
            profile.warnings.append(
                "Affects opponents one-sided but GIVES resources (group hug read): build "
                "politics/pillowfort payoffs, not attrition.")
        else:
            profile.warnings.append(
                "Affects opponents one-sided (punisher read): build attrition/protection, not go-wide.")

    if "MODAL_TOOLBOX" in {s.id for s in profile.signals}:
        profile.warnings.append(
            "Multi-mode commander (toolbox): per-mode archetype bands are OPTIONS, not the "
            "theme. Align the chosen mode with the user's requested direction from the build "
            "questions (e.g. user wants aggro -> lean the aggro-adjacent mode); if unknown, ask.")

    result = profile.to_dict()
    result["faces"] = face_reports
    result["dominant_symmetry"] = symmetry
    result["archetype_support"] = archetypes
    return result
