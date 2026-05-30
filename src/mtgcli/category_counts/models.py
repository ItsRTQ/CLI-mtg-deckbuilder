CATEGORIES = [
    "normal_ramp",
    "big_ramp",
    "draw",
    "card_selection",
    "tutors",
    "targeted_removal",
    "board_wipes",
    "counterspells",
    "protection",
    "recursion",
    "graveyard_hate",
    "win_conditions",
    "archetype_core",
    "synergy_enablers",
    "synergy_payoffs",
    "redundancy",
    "utility",
]

CATEGORY_DISPLAY_NAMES = {
    "normal_ramp": "Normal Ramp",
    "big_ramp": "Big Ramp / Mana Amplifiers",
    "draw": "Card Draw / Advantage",
    "card_selection": "Card Selection / Filtering",
    "tutors": "Tutors / Tutor Effects",
    "targeted_removal": "Targeted Removal",
    "board_wipes": "Board Wipes",
    "counterspells": "Counterspells / Stack Interaction",
    "protection": "Protection",
    "recursion": "Recursion",
    "graveyard_hate": "Graveyard Hate",
    "win_conditions": "Win Conditions / Finishers",
    "archetype_core": "Archetype Core Cards",
    "synergy_enablers": "Synergy Enablers",
    "synergy_payoffs": "Synergy Payoffs",
    "redundancy": "Redundancy Pieces",
    "utility": "Utility / Flex Slots",
}

# Universal base needs at power level 5 with no archetype pressure.
BASE_NEEDS = {
    "normal_ramp": 5.5,
    "big_ramp": 0.5,
    "draw": 5.5,
    "card_selection": 1.5,
    "tutors": 1.0,
    "targeted_removal": 4.0,
    "board_wipes": 2.5,
    "counterspells": 1.0,
    "protection": 2.5,
    "recursion": 1.5,
    "graveyard_hate": 0.5,
    "win_conditions": 3.0,
    "archetype_core": 5.0,
    "synergy_enablers": 4.5,
    "synergy_payoffs": 4.0,
    "redundancy": 1.5,
    "utility": 2.0,
}

# Per-point delta applied when power_level differs from 5.
POWER_LEVEL_DELTAS = {
    "normal_ramp": 0.20,
    "big_ramp": 0.10,
    "draw": 0.30,
    "card_selection": 0.25,
    "tutors": 0.40,
    "targeted_removal": 0.20,
    "board_wipes": 0.10,
    "counterspells": 0.40,
    "protection": 0.20,
    "recursion": 0.15,
    "graveyard_hate": 0.10,
    "win_conditions": 0.10,
    "archetype_core": 0.10,
    "synergy_enablers": 0.15,
    "synergy_payoffs": 0.10,
    "redundancy": 0.20,
    "utility": 0.00,
}

# Compression order: first item is compressed first when slot budget is tight.
COMPRESSION_ORDER = [
    "utility",
    "redundancy",
    "synergy_payoffs",
    "win_conditions",
    "recursion",
    "big_ramp",
    "board_wipes",
    "graveyard_hate",
    "targeted_removal",
    "tutors",
    "counterspells",
    "card_selection",
    "synergy_enablers",
    "draw",
    "normal_ramp",
    "archetype_core",
]

# Priority labels derived from need_score.
def score_to_priority(score: float) -> str:
    if score >= 8.0:
        return "Critical"
    elif score >= 6.5:
        return "High"
    elif score >= 4.5:
        return "Medium"
    elif score >= 2.0:
        return "Low"
    return "Negligible"

# MV pressure modifier: added to ramp/protection need scores.
MV_PRESSURE_TABLE = {
    0: -1.0,
    1: -1.0,
    2: -1.0,
    3: 0.0,
    4: 0.75,
    5: 1.50,
    6: 2.50,
}
MV_PRESSURE_HIGH = 3.50  # 7+

# Average MV defaults by archetype (used when --projected-average-mv not provided).
ARCHETYPE_DEFAULT_AVG_MV = {
    "aristocrats": 3.2,
    "voltron": 2.8,
    "tokens": 3.0,
    "spellslinger": 2.5,
    "control": 3.2,
    "combo": 2.4,
    "stompy": 3.8,
    "reanimator": 3.5,
    "graveyard_value": 3.2,
    "artifacts": 3.0,
    "enchantress": 3.2,
    "equipment": 2.8,
    "auras": 2.6,
    "lands": 3.5,
    "landfall": 3.5,
    "lifegain": 3.0,
    "group_slug": 3.2,
    "mill": 3.0,
    "blink": 3.2,
    "theft": 3.5,
    "go_wide_aggro": 2.8,
    "go_tall_aggro": 3.0,
    "tribal": 3.2,
    "pillowfort": 3.5,
    "stax": 3.0,
    "value_engine": 3.3,
    "battlecruiser": 4.0,
}

# Landfall/land-matters archetypes that start with higher base lands.
LANDFALL_ARCHETYPES = {"lands", "landfall", "land_matters"}

POWER_TIERS = [
    (10.0, "cEDH-ish"),
    (9.0, "cEDH-ish"),
    (8.0, "High power"),
    (7.0, "Tuned casual"),
    (6.0, "Tuned casual"),
    (5.0, "Upgraded precon / Casual"),
    (4.0, "Upgraded precon / Casual"),
    (3.0, "Precon / Low casual"),
    (2.0, "Precon / Low casual"),
    (1.0, "Precon / Low casual"),
]

BRACKET_TO_POWER = {
    "T1": 9.5,
    "T2": 8.0,
    "T3": 6.5,
    "T4": 4.0,
}

PHILOSOPHY_ALIASES = {
    "balanced": "balanced",
    "balanced / default": "balanced",
    "default": "balanced",
    "consistency_first": "consistency_first",
    "consistency first": "consistency_first",
    "explosive_fast": "explosive_fast",
    "explosive / fast": "explosive_fast",
    "explosive": "explosive_fast",
    "fast": "explosive_fast",
    "resilient": "resilient",
    "resilient / hard to kill": "resilient",
    "hard to kill": "resilient",
    "synergy_max": "synergy_max",
    "synergy max": "synergy_max",
    "synergy": "synergy_max",
    "interaction_heavy": "interaction_heavy",
    "interaction heavy": "interaction_heavy",
    "interaction": "interaction_heavy",
    "win_optimization": "win_optimization",
    "win optimization": "win_optimization",
    "win": "win_optimization",
    "casual_do_the_thing": "casual_do_the_thing",
    "casual do-the-thing": "casual_do_the_thing",
    "do the thing": "casual_do_the_thing",
    "casual": "casual_do_the_thing",
    "theme_flavor": "theme_flavor",
    "theme / flavor preservation": "theme_flavor",
    "theme": "theme_flavor",
    "flavor": "theme_flavor",
    "low_salt": "low_salt",
    "low salt / friendly table": "low_salt",
    "low salt": "low_salt",
    "friendly": "low_salt",
    "control_grind": "control_grind",
    "control / grind": "control_grind",
    "grind": "control_grind",
    "combo_focus": "combo_focus",
    "combo focus": "combo_focus",
    "combat_pressure": "combat_pressure",
    "combat pressure": "combat_pressure",
    "combat": "combat_pressure",
    "value_engine": "value_engine",
    "value engine": "value_engine",
    "value": "value_engine",
}

META_ALIASES = {
    "universal": "universal",
    "creature_heavy": "creature_heavy",
    "creature heavy": "creature_heavy",
    "combo_heavy": "combo_heavy",
    "combo heavy": "combo_heavy",
    "graveyard_heavy": "graveyard_heavy",
    "graveyard heavy": "graveyard_heavy",
    "artifact_enchantment_heavy": "artifact_enchantment_heavy",
    "artifact enchantment heavy": "artifact_enchantment_heavy",
    "board_wipe_heavy": "board_wipe_heavy",
    "board wipe heavy": "board_wipe_heavy",
    "removal_heavy": "removal_heavy",
    "removal heavy": "removal_heavy",
    "stax_heavy": "stax_heavy",
    "stax heavy": "stax_heavy",
    "fast_high_power": "fast_high_power",
    "fast high power": "fast_high_power",
    "slow_battlecruiser": "slow_battlecruiser",
    "slow battlecruiser": "slow_battlecruiser",
    "battlecruiser": "slow_battlecruiser",
    "low_interaction_casual": "low_interaction_casual",
    "low interaction casual": "low_interaction_casual",
    "casual": "low_interaction_casual",
}
