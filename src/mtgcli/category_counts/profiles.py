import json
import math
from pathlib import Path
from typing import Dict, Tuple, Any

_SEED_DIR = Path(__file__).resolve().parents[3] / "data" / "seed"

_profiles: Dict[str, Any] = {}
_philosophy_mods: Dict[str, Any] = {}
_meta_mods: Dict[str, Any] = {}
_archetype_demands: Dict[str, Any] = {}


def _load(path: Path) -> Dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def get_profiles() -> Dict[str, Any]:
    global _profiles
    if not _profiles:
        _profiles = _load(_SEED_DIR / "category_count_profiles.json")
    return _profiles


def get_philosophy_modifiers() -> Dict[str, Any]:
    global _philosophy_mods
    if not _philosophy_mods:
        _philosophy_mods = _load(_SEED_DIR / "philosophy_modifiers.json")
    return _philosophy_mods


def get_meta_modifiers() -> Dict[str, Any]:
    global _meta_mods
    if not _meta_mods:
        _meta_mods = _load(_SEED_DIR / "meta_modifiers.json")
    return _meta_mods


def get_archetype_demands() -> Dict[str, Any]:
    global _archetype_demands
    if not _archetype_demands:
        _archetype_demands = _load(_SEED_DIR / "archetype_count_demands.json")
    return _archetype_demands


def interpolate_target(profile: Dict[str, Any], score: float) -> float:
    s0 = profile["score_0_target"]
    s5 = profile["score_5_target"]
    s10 = profile["score_10_target"]
    if score <= 5.0:
        t = score / 5.0
        return s0 + t * (s5 - s0)
    else:
        t = (score - 5.0) / 5.0
        return s5 + t * (s10 - s5)


def score_to_range(
    target_float: float,
    score: float,
    profile: Dict[str, Any],
    priority: str,
) -> Tuple[int, int, int]:
    """Return (min_count, max_count, target_count)."""
    if score < 4.0:
        width = 2
    elif score <= 6.0:
        width = 3
    else:
        width = 4

    if priority in ("Critical",):
        target = math.ceil(target_float)
    elif priority == "Low" or priority == "Negligible":
        target = math.floor(target_float)
    else:
        target = round(target_float)

    floor = profile["protected_floor"]
    hard_cap = profile["hard_cap"]

    target = max(floor, min(hard_cap, target))

    half = width // 2
    min_count = max(floor, target - half)
    max_count = min(hard_cap, min_count + width)

    # Ensure target is inside range.
    target = max(min_count, min(max_count, target))

    return min_count, max_count, target
