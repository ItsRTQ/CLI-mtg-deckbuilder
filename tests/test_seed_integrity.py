import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed"

CATEGORY_COUNT_CATEGORIES = {
    "normal_ramp", "big_ramp", "draw", "card_selection", "tutors",
    "targeted_removal", "board_wipes", "counterspells", "protection",
    "recursion", "graveyard_hate", "win_conditions", "archetype_core",
    "synergy_enablers", "synergy_payoffs", "redundancy", "utility"
}

OVERBROAD_SINGLE_PHRASES = {"whenever", "create", "token", "instant", "sorcery", "target", "draw", "return", "exile", "destroy", "you may", "protect", "remove"}


def load_json(filename):
    path = SEED_DIR / filename
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_all_seed_files_parse():
    seed_files = [
        "card_tags.json",
        "role_definitions.json",
        "theme_profiles.json",
        "archetype_profiles.json",
        "constraint_rules.json",
        "deck_skeletons.json",
        "category_count_profiles.json",
        "archetype_count_demands.json",
        "philosophy_modifiers.json",
        "meta_modifiers.json",
    ]
    for fname in seed_files:
        data = load_json(fname)
        assert data is not None, f"{fname} failed to parse"


def test_role_definition_tags_exist_in_card_tags():
    card_tags = load_json("card_tags.json")
    role_defs = load_json("role_definitions.json")

    missing = []
    for role_name, role_def in role_defs.items():
        if not isinstance(role_def, dict):
            continue
        tags = role_def.get("tags", [])
        for tag in tags:
            if tag not in card_tags:
                missing.append(f"{role_name}.{tag}")

    assert missing == [], f"Tags missing from card_tags.json: {missing}"


def test_theme_profile_tags_exist_in_card_tags():
    card_tags = load_json("card_tags.json")
    themes = load_json("theme_profiles.json")

    missing = []
    for theme_name, theme_def in themes.items():
        if not isinstance(theme_def, dict):
            continue
        packages = theme_def.get("packages", {})
        for pkg_name, pkg_def in packages.items():
            if not isinstance(pkg_def, dict):
                continue
            tags = pkg_def.get("tags", [])
            for tag in tags:
                if tag not in card_tags:
                    missing.append(f"{theme_name}.{pkg_name}.{tag}")

    assert missing == [], f"Tags missing from card_tags.json: {missing}"


def test_category_count_profiles_have_exact_categories():
    profiles = load_json("category_count_profiles.json")
    profile_keys = set(profiles.keys())
    assert profile_keys == CATEGORY_COUNT_CATEGORIES, (
        f"Extra: {profile_keys - CATEGORY_COUNT_CATEGORIES}, "
        f"Missing: {CATEGORY_COUNT_CATEGORIES - profile_keys}"
    )


def test_archetype_count_demands_use_valid_categories():
    demands = load_json("archetype_count_demands.json")
    invalid = []
    for arch_name, arch_data in demands.items():
        if arch_name.startswith("_"):
            continue
        if not isinstance(arch_data, dict):
            continue
        for cat_key in arch_data.keys():
            if cat_key not in CATEGORY_COUNT_CATEGORIES:
                invalid.append(f"{arch_name}.{cat_key}")
    assert invalid == [], f"Invalid categories in archetype_count_demands: {invalid}"


def test_constraint_rules_has_budget_overage_rules():
    rules = load_json("constraint_rules.json")
    budget = rules.get("budget_rules", {})
    assert budget.get("budget_is_maximum_not_target") is True
    assert "default_allowed_overage_percent" in budget
    assert budget.get("under_budget_is_valid") is True


def test_constraint_rules_land_minimum_is_32():
    rules = load_json("constraint_rules.json")
    formula = rules.get("land_count_formula", {})
    safety = formula.get("absolute_safety", {})
    assert safety.get("min", 0) >= 32, f"absolute_safety.min should be >= 32, got {safety.get('min')}"
    min_safety = rules.get("minimum_safety_counts", {})
    assert min_safety.get("lands", 0) >= 32, f"minimum_safety_counts.lands should be >= 32"


def test_no_landfall_skeleton_hardcodes_lands_40():
    skeletons = load_json("deck_skeletons.json")
    landfall = skeletons.get("landfall_landsmatter", {})
    lands_value = landfall.get("lands")
    assert lands_value != 40, "landfall_landsmatter skeleton should not hardcode lands=40"
    if isinstance(lands_value, dict):
        assert lands_value.get("mode") == "flexible_range"


def test_no_overbroad_single_phrases_in_card_tags():
    card_tags = load_json("card_tags.json")
    violations = []
    for tag_name, phrases in card_tags.items():
        if not isinstance(phrases, list):
            continue
        for phrase in phrases:
            if phrase.lower().strip() in OVERBROAD_SINGLE_PHRASES:
                violations.append(f"{tag_name}: '{phrase}'")
    assert violations == [], f"Overbroad single-word phrases found: {violations}"


def test_protection_role_does_not_include_recursion():
    role_defs = load_json("role_definitions.json")
    protection = role_defs.get("protection", {})
    tags = protection.get("tags", [])
    assert "recursion" not in tags, "protection role should not include recursion tag"


def test_archetype_profiles_cover_category_count_archetypes():
    demands = load_json("archetype_count_demands.json")
    profiles = load_json("archetype_profiles.json")
    profile_keys = set(profiles.keys())

    missing = []
    for arch in demands:
        if arch.startswith("_"):
            continue
        if arch not in profile_keys:
            missing.append(arch)

    assert missing == [], f"Archetypes in category-counts but not in archetype_profiles: {missing}"
