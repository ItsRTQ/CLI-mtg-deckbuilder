"""
Main category-count calculation engine.

calculate_category_counts() is the primary public API. It accepts commander
card data directly (for testing) or a db_path for live lookups.
"""
import math
from typing import Any, Dict, List, Optional

from .models import (
    ARCHETYPE_DEFAULT_AVG_MV,
    BASE_NEEDS,
    BRACKET_TO_POWER,
    CATEGORIES,
    CATEGORY_DISPLAY_NAMES,
    COMPRESSION_ORDER,
    LANDFALL_ARCHETYPES,
    META_ALIASES,
    PHILOSOPHY_ALIASES,
    POWER_LEVEL_DELTAS,
    POWER_TIERS,
    PRACTICAL_FLOORS,
    score_to_priority,
)
from .profiles import (
    get_archetype_demands,
    get_meta_modifiers,
    get_philosophy_modifiers,
    get_profiles,
    interpolate_target,
    score_to_range,
)
from .scoring import (
    merge_partner_scores,
    score_archetype_fit,
    score_commander,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_power_level(
    power_level: Optional[float],
    bracket: Optional[str],
) -> float:
    if power_level is not None:
        return float(power_level)
    if bracket:
        b = bracket.upper().strip()
        if b in BRACKET_TO_POWER:
            return BRACKET_TO_POWER[b]
    return 6.0


def _resolve_philosophy(philosophy: str) -> str:
    key = philosophy.lower().strip()
    return PHILOSOPHY_ALIASES.get(key, "balanced")


def _resolve_meta(meta: str) -> str:
    key = meta.lower().strip()
    return META_ALIASES.get(key, "universal")


def _power_tier_label(power_level: float) -> str:
    for threshold, label in POWER_TIERS:
        if power_level >= threshold:
            return label
    return "Precon / Low casual"


def _philosophy_display(philosophy_key: str) -> str:
    mods = get_philosophy_modifiers()
    entry = mods.get(philosophy_key, {})
    return entry.get("display_name", philosophy_key)


def _meta_display(meta_key: str) -> str:
    mods = get_meta_modifiers()
    entry = mods.get(meta_key, {})
    return entry.get("display_name", meta_key)


# ─── Land formula ─────────────────────────────────────────────────────────────

def calculate_land_count(
    color_identity: List[str],
    archetype: str,
    projected_avg_mv: Optional[float],
    library_slots: int,
) -> int:
    archetype_key = archetype.lower()
    if archetype_key in LANDFALL_ARCHETYPES:
        base = 38
    else:
        base = 32

    color_bonus = min(3, len(color_identity))

    if projected_avg_mv is None:
        projected_avg_mv = ARCHETYPE_DEFAULT_AVG_MV.get(archetype_key, 3.2)

    mv_bonus = 0
    if 2.60 <= projected_avg_mv < 3.50:
        mv_bonus = 1
    elif projected_avg_mv >= 3.50:
        mv_bonus = 2

    land_count = base + color_bonus + mv_bonus
    land_count = max(32, land_count)
    land_count = min(land_count, library_slots - 1)
    return land_count


# ─── Per-category score formula ───────────────────────────────────────────────

def _compute_raw_score(
    category: str,
    *,
    archetype_key: str,
    power_level: float,
    philosophy_key: str,
    meta_key: str,
    commander_scores: Dict[str, Any],
    color_identity: List[str],
    projected_avg_mv: float,
) -> float:
    base = BASE_NEEDS.get(category, 2.0)

    # Archetype demand
    arch_demands = get_archetype_demands()
    arch_delta = arch_demands.get(archetype_key, {}).get(category, 0.0)

    # Power level modifier
    power_delta_per_point = POWER_LEVEL_DELTAS.get(category, 0.0)
    power_mod = (power_level - 5.0) * power_delta_per_point

    # Philosophy modifier
    phil_mods = get_philosophy_modifiers().get(philosophy_key, {})
    phil_mod = phil_mods.get(category, 0.0)

    # Meta modifier
    meta_mods = get_meta_modifiers().get(meta_key, {})
    meta_mod = meta_mods.get(category, 0.0)

    # Commander provides (reduces need)
    provides = commander_scores.get("provides", {})
    provides_reduction = provides.get(category, 0.0)

    # Commander requires (increases need)
    requires = commander_scores.get("requires", {})
    requires_bonus = requires.get(category, 0.0)

    # Commander rewards (increases archetype/synergy need)
    rewards = commander_scores.get("rewards", {})
    rewards_bonus = rewards.get(category, 0.0)

    # Dependency spillover to protection and recursion
    dependency = commander_scores.get("dependency", 5.0)
    dep_spillover = 0.0
    if category == "protection":
        dep_spillover = dependency * 0.30
    elif category == "recursion":
        dep_spillover = dependency * 0.20

    # MV pressure applied to ramp and protection
    mv_pressure = commander_scores.get("mana_value_pressure", 0.0)
    mv_mod = 0.0
    if category == "normal_ramp":
        mv_mod = mv_pressure
    elif category == "protection":
        # High MV → harder to recast → need more protection
        mv_mod = mv_pressure * 0.5

    # Curve speed modifier for ramp
    curve_mod = 0.0
    if category == "normal_ramp":
        if projected_avg_mv >= 3.50:
            curve_mod = 0.5
        elif projected_avg_mv <= 2.40:
            curve_mod = -0.5

    # Color access modifier
    color_mod = 0.0
    if category == "counterspells":
        if "U" not in color_identity:
            color_mod = -10.0  # Clamp to 0 after this

    raw = (
        base
        + arch_delta
        + power_mod
        + phil_mod
        + meta_mod
        + requires_bonus
        + rewards_bonus
        + dep_spillover
        + mv_mod
        + curve_mod
        + color_mod
        - provides_reduction
    )
    return max(0.0, min(10.0, raw))


# ─── Slot compression ─────────────────────────────────────────────────────────

def _compress_slots(
    targets: Dict[str, int],
    nonland_slots: int,
) -> tuple:
    """
    Reduce category targets (following COMPRESSION_ORDER) until they fit in
    nonland_slots.

    Compression happens in two phases:
      1. Reduce down to the *practical* floor (max of protected_floor and the
         PRACTICAL_FLOORS entry) — the level a normal deck should not drop below.
      2. If still over budget, reduce further down to the hard protected_floor,
         emitting a warning for every category pushed below its practical floor
         instead of silently producing a misleading count.

    Returns (compressed_targets, compression_needed, notes, floor_warnings).
    """
    profiles = get_profiles()
    total = sum(targets.values())
    if total <= nonland_slots:
        return dict(targets), False, [], []

    working = dict(targets)
    notes = [
        "Requested category targets exceeded available nonland slots.",
        "Compressed targets are slot-pressure outputs, not hard deckbuilding rules.",
    ]
    floor_warnings: List[str] = []

    def _floor(cat: str, allow_practical: bool) -> int:
        protected = profiles[cat]["protected_floor"]
        if allow_practical:
            return max(protected, PRACTICAL_FLOORS.get(cat, protected))
        return protected

    for allow_practical in (True, False):
        while sum(working.values()) > nonland_slots:
            reduced = False
            for cat in COMPRESSION_ORDER:
                if cat not in working:
                    continue
                floor = _floor(cat, allow_practical)
                if working[cat] > floor:
                    working[cat] -= 1
                    notes.append(f"Reduced {CATEGORY_DISPLAY_NAMES.get(cat, cat)} by 1.")
                    reduced = True
                    practical = PRACTICAL_FLOORS.get(cat)
                    if (
                        not allow_practical
                        and practical is not None
                        and working[cat] < practical
                    ):
                        warning = (
                            f"{CATEGORY_DISPLAY_NAMES.get(cat, cat)} compressed below "
                            f"its practical floor of {practical} (now {working[cat]}) "
                            f"due to severe slot pressure — review manually."
                        )
                        floor_warnings.append(warning)
                        notes.append(warning)
                    break
            if not reduced:
                notes.append("Could not compress further without breaching protected floors.")
                break
        if sum(working.values()) <= nonland_slots:
            break

    return working, True, notes, floor_warnings


# ─── Commander lookup ─────────────────────────────────────────────────────────

def _lookup_card(name: str, db_path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not db_path:
        return None
    try:
        from mtgcli.cards.repository import CardRepository
        repo = CardRepository(db_path)
        return repo.get_card_by_exact_name(name)
    except Exception:
        return None


def _default_card_data(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "oracle_text": "",
        "type_line": "Legendary Creature",
        "mana_value": 4.0,
        "color_identity": [],
        "can_be_commander": True,
        "commander_legal": True,
    }


# ─── Main entry point ─────────────────────────────────────────────────────────

def _load_analysis_scores(analysis_path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load pre-computed commander scores from a commander_analysis.json file."""
    if not analysis_path:
        return None
    try:
        import json as _json
        from pathlib import Path as _Path
        p = _Path(analysis_path)
        if not p.exists():
            return None
        with open(p, "r", encoding="utf-8") as f:
            analysis = _json.load(f)
        scores = dict(analysis.get("commander_scores", {}))
        scores["provides"] = analysis.get("provides", {})
        scores["requires"] = analysis.get("requires", {})
        scores["rewards"] = analysis.get("rewards", {})
        return scores
    except Exception:
        return None


def calculate_category_counts(
    commander_name: str,
    archetype: str,
    *,
    partner_name: Optional[str] = None,
    power_level: Optional[float] = None,
    bracket: Optional[str] = None,
    philosophy: str = "balanced",
    meta: str = "universal",
    projected_avg_mv: Optional[float] = None,
    commander_card_data: Optional[Dict[str, Any]] = None,
    partner_card_data: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
    analysis_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate recommended category counts for a Commander deck.

    Returns a fully structured output dict. Category recommendations are
    soft targets — not hard locks. The AI agent should use these as ranges
    and apply its own deckbuilding judgment.
    """
    resolved_power = _resolve_power_level(power_level, bracket)
    philosophy_key = _resolve_philosophy(philosophy)
    meta_key = _resolve_meta(meta)
    archetype_key = archetype.lower().strip().replace(" ", "_").replace("-", "_")

    # ── Commander zone count ───────────────────────────────────────────────
    commander_zone_count = 2 if partner_name else 1
    library_slots = 100 - commander_zone_count

    # ── Load commander card data ───────────────────────────────────────────
    if commander_card_data is None:
        commander_card_data = _lookup_card(commander_name, db_path) or _default_card_data(
            commander_name
        )

    color_identity: List[str] = []
    if isinstance(commander_card_data.get("color_identity"), list):
        color_identity = list(commander_card_data["color_identity"])
    elif isinstance(commander_card_data.get("color_identity"), str):
        import json as _json
        try:
            color_identity = _json.loads(commander_card_data["color_identity"])
        except Exception:
            color_identity = []

    if partner_name:
        if partner_card_data is None:
            partner_card_data = _lookup_card(partner_name, db_path) or _default_card_data(
                partner_name
            )
        partner_identity: List[str] = []
        if isinstance(partner_card_data.get("color_identity"), list):
            partner_identity = list(partner_card_data["color_identity"])
        elif isinstance(partner_card_data.get("color_identity"), str):
            import json as _json
            try:
                partner_identity = _json.loads(partner_card_data["color_identity"])
            except Exception:
                partner_identity = []
        # Combined identity (union, WUBRG order)
        combined = []
        for c in ["W", "U", "B", "R", "G"]:
            if c in color_identity or c in partner_identity:
                combined.append(c)
        color_identity = combined
    else:
        color_identity = [c for c in ["W", "U", "B", "R", "G"] if c in color_identity]

    # ── Commander scores ───────────────────────────────────────────────────
    analysis_scores = _load_analysis_scores(analysis_path)
    if analysis_scores:
        commander_scores = analysis_scores
    else:
        primary_scores = score_commander(commander_card_data, archetype_key)
        if partner_name and partner_card_data:
            partner_scores = score_commander(partner_card_data, archetype_key)
            commander_scores = merge_partner_scores(primary_scores, partner_scores)
        else:
            commander_scores = primary_scores

    # ── Archetype fit ──────────────────────────────────────────────────────
    oracle = (commander_card_data.get("oracle_text") or "")
    type_line = (commander_card_data.get("type_line") or "")
    fit_score = score_archetype_fit(oracle, type_line, archetype_key)

    if partner_name and partner_card_data:
        partner_oracle = (partner_card_data.get("oracle_text") or "")
        partner_type = (partner_card_data.get("type_line") or "")
        partner_fit = score_archetype_fit(partner_oracle, partner_type, archetype_key)
        fit_score = max(fit_score, partner_fit)

    forced_warning = None
    forced_archetype_notes: List[str] = []
    if fit_score < 4.0:
        fit_confidence = "low"
        penalty = round(10.0 - fit_score, 1)
        forced_warning = (
            f"This commander has a low fit score ({fit_score:.1f}/10) for '{archetype}'. "
            f"The deck can still be built this way, but category counts are adjusted for "
            f"the forced-archetype penalty ({penalty} point gap)."
        )
        forced_archetype_notes = [
            f"Forced low-fit archetype: '{archetype}' scores only {fit_score:.1f}/10 for this commander.",
            "This is not a natural plan — apply extra deckbuilding judgment.",
            "Consider alternate archetypes (see commander-analyze) before committing.",
        ]
    elif fit_score < 6.5:
        fit_confidence = "medium"
    else:
        fit_confidence = "high"

    # ── Land count and nonland slots ───────────────────────────────────────
    eff_avg_mv = projected_avg_mv
    land_count = calculate_land_count(color_identity, archetype_key, eff_avg_mv, library_slots)
    nonland_slots = library_slots - land_count

    if eff_avg_mv is None:
        eff_avg_mv = ARCHETYPE_DEFAULT_AVG_MV.get(archetype_key, 3.2)

    # ── Per-category scores and ranges ────────────────────────────────────
    profiles = get_profiles()
    recommendations = []
    initial_targets: Dict[str, int] = {}

    for cat in CATEGORIES:
        if cat not in profiles:
            continue
        raw_score = _compute_raw_score(
            cat,
            archetype_key=archetype_key,
            power_level=resolved_power,
            philosophy_key=philosophy_key,
            meta_key=meta_key,
            commander_scores=commander_scores,
            color_identity=color_identity,
            projected_avg_mv=eff_avg_mv,
        )
        priority = score_to_priority(raw_score)
        profile = profiles[cat]
        target_float = interpolate_target(profile, raw_score)
        min_c, max_c, target_c = score_to_range(target_float, raw_score, profile, priority)
        initial_targets[cat] = target_c

        # Build notes
        notes: List[str] = []
        mv = float(commander_card_data.get("mana_value") or 0)
        if cat == "normal_ramp" and mv >= 5:
            notes.append(f"Commander mana value is {int(mv)} — ramp demand is elevated.")
        if cat in ("protection", "recursion") and commander_scores["dependency"] >= 7:
            notes.append("Commander dependency is high — protection/recursion are important.")
        if cat == "counterspells" and "U" not in color_identity:
            notes.append("No blue in color identity — counterspells set to 0.")
        if cat == "archetype_core" and fit_score >= 7.0:
            notes.append(f"Commander is a natural fit for {archetype} (fit {fit_score:.1f}/10).")
        if cat == "archetype_core" and forced_warning:
            notes.append("Archetype is forced — core count adjusted for low natural fit.")

        recommendations.append({
            "category": cat,
            "display_name": CATEGORY_DISPLAY_NAMES.get(cat, cat),
            "need_score": round(raw_score, 2),
            "recommended_range": f"{min_c}-{max_c}",
            "min_count": min_c,
            "max_count": max_c,
            "uncompressed_target_count": target_c,
            "compressed_target_count": target_c,
            "effective_target_count": target_c,
            "compression_applied": False,
            "target_count": target_c,
            "priority": priority,
            "notes": notes,
        })

    # ── Slot compression ──────────────────────────────────────────────────
    compressed_targets, compression_needed, compression_notes, floor_warnings = _compress_slots(
        initial_targets, nonland_slots
    )

    total_requested_before = sum(initial_targets.values())

    # Surface compressed vs uncompressed targets on every recommendation so the
    # agent can plan from uncompressed targets / ranges and treat compressed
    # counts as slot-pressure outputs, not hard locks.
    for rec in recommendations:
        cat = rec["category"]
        uncompressed = initial_targets.get(cat, rec["uncompressed_target_count"])
        compressed = compressed_targets.get(cat, uncompressed)
        rec["compressed_target_count"] = compressed
        rec["effective_target_count"] = compressed
        rec["target_count"] = compressed
        if compressed != uncompressed:
            rec["compression_applied"] = True
            rec["notes"].append(
                f"Compressed from {uncompressed} to {compressed} due to slot pressure."
            )
            rec["notes"].append("Do not treat compressed target as a hard minimum.")
            practical = PRACTICAL_FLOORS.get(cat)
            if practical is not None and compressed < practical:
                rec["notes"].append(
                    f"Below practical floor of {practical} — review manually."
                )

    slot_budget = {
        "total_requested_physical_slots_before_compression": total_requested_before,
        "available_nonland_slots": nonland_slots,
        "compression_needed": compression_needed,
        "compression_notes": compression_notes + [
            "Compressed targets are not hard deckbuilding rules.",
            "Use recommended ranges and deckbuilding judgment when forced archetype fit is low.",
        ] if compression_needed else compression_notes,
        "practical_floor_warnings": floor_warnings,
    }

    commander_label = commander_name
    if partner_name:
        commander_label = f"{commander_name} + {partner_name}"

    return {
        "commander": commander_label,
        "commander_zone_count": commander_zone_count,
        "library_slots": library_slots,
        "chosen_archetype": archetype,
        "archetype_fit_score": round(fit_score, 2),
        "fit_confidence": fit_confidence,
        "forced_archetype_warning": forced_warning,
        "forced_archetype_notes": forced_archetype_notes,
        "power_level": resolved_power,
        "power_tier": _power_tier_label(resolved_power),
        "deckbuilding_philosophy": _philosophy_display(philosophy_key),
        "meta": _meta_display(meta_key),
        "color_identity": color_identity,
        "commander_scores": commander_scores,
        "land_count": land_count,
        "nonland_slots": nonland_slots,
        "projected_avg_mv": round(eff_avg_mv, 2),
        "category_recommendations": recommendations,
        "slot_budget": slot_budget,
        "multi_tag_policy": {
            "primary_tag_max": 1.0,
            "secondary_tag_total_max": 0.75,
            "total_coverage_max_per_card": 1.75,
            "note": (
                "A card may contribute to multiple categories but uses one physical slot. "
                "Do not count one card as fully satisfying multiple category targets."
            ),
        },
    }
