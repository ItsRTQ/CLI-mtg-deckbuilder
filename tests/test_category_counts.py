"""
Tests for the category_counts system.

Uses injected card_data to avoid DB dependency.
"""
import pytest
from mtgcli.category_counts.calculator import (
    calculate_category_counts,
    calculate_land_count,
)
from mtgcli.category_counts.scoring import (
    score_archetype_fit,
    score_commander,
    score_mv_pressure,
)
from mtgcli.category_counts.models import CATEGORIES, score_to_priority


# ─── Card data fixtures ────────────────────────────────────────────────────────

def _make_card(
    name="Test Commander",
    oracle="",
    type_line="Legendary Creature",
    mana_cost="{W}{W}",
    mana_value=4.0,
    color_identity=None,
    can_be_commander=True,
    commander_legal=True,
):
    return {
        "name": name,
        "oracle_text": oracle,
        "type_line": type_line,
        "mana_cost": mana_cost,
        "mana_value": mana_value,
        "color_identity": color_identity or ["W"],
        "can_be_commander": can_be_commander,
        "commander_legal": commander_legal,
    }


TEYSA = _make_card(
    name="Teysa Karlov",
    oracle=(
        "If a creature dying causes a triggered ability of a permanent you control to trigger, "
        "that ability triggers an additional time.\n"
        "Creature tokens you control have vigilance and lifelink."
    ),
    mana_cost="{2}{W}{B}",
    mana_value=4.0,
    color_identity=["B", "W"],
)

KINNAN = _make_card(
    name="Kinnan, Bonder Prodigy",
    oracle=(
        "Whenever a land or nonland permanent you control produces mana, it produces that much "
        "mana plus one mana of any type that land or permanent could produce.\n"
        "{5}{G}{U}: Look at the top five cards of your library. You may put a non-Human creature "
        "card from among them onto the battlefield."
    ),
    mana_cost="{G}{U}",
    mana_value=2.0,
    color_identity=["G", "U"],
)

ARDENN = _make_card(
    name="Ardenn, Intrepid Archaeologist",
    oracle=(
        "At the beginning of combat on your turn, you may attach any number of Auras and Equipment "
        "you control to target permanent or player."
    ),
    mana_cost="{2}{W}",
    mana_value=3.0,
    color_identity=["W"],
)

ROGRAKH = _make_card(
    name="Rograkh, Son of Rohgahh",
    oracle=(
        "First strike, menace, trample\nPartner"
    ),
    mana_cost="{R}",
    mana_value=0.0,
    color_identity=["R"],
)

SHORIKAI = _make_card(
    name="Shorikai, Genesis Engine",
    oracle=(
        "{1}, {T}: Draw 2 cards, then put a card from your hand on top of or on the bottom of your library. "
        "Create a 1/1 colorless Pilot creature token."
    ),
    mana_cost="{6}{W}{U}",
    mana_value=8.0,
    color_identity=["U", "W"],
)

STELLA_LEE = _make_card(
    name="Stella Lee, Wild Card",
    oracle=(
        "Whenever you cast your second spell each turn, copy it. You may choose new targets for the copy. "
        "Whenever you cast your fifth spell each turn, you may cast a copy of a random instant or sorcery "
        "card from your graveyard without paying its mana cost."
    ),
    mana_cost="{1}{U}{R}",
    mana_value=3.0,
    color_identity=["R", "U"],
)

ZHULODOK = _make_card(
    name="Zhulodok, Void Gorger",
    oracle=(
        "Whenever you cast a colorless spell with mana value 7 or greater, it gains cascade twice."
    ),
    mana_cost="{5}{C}{C}",
    mana_value=7.0,
    color_identity=[],
)


# ─── Basic math ────────────────────────────────────────────────────────────────

class TestCommanderZoneCount:
    def test_single_commander_99_slots(self):
        result = calculate_category_counts("Test", "aristocrats", commander_card_data=TEYSA)
        assert result["commander_zone_count"] == 1
        assert result["library_slots"] == 99

    def test_partner_98_slots(self):
        result = calculate_category_counts(
            "Ardenn, Intrepid Archaeologist",
            "voltron",
            partner_name="Rograkh, Son of Rohgahh",
            commander_card_data=ARDENN,
            partner_card_data=ROGRAKH,
        )
        assert result["commander_zone_count"] == 2
        assert result["library_slots"] == 98


class TestLandFormula:
    def test_minimum_32(self):
        land = calculate_land_count([], "control", projected_avg_mv=2.0, library_slots=99)
        assert land >= 32

    def test_single_color_adds_1(self):
        base = calculate_land_count([], "control", projected_avg_mv=3.0, library_slots=99)
        one_color = calculate_land_count(["W"], "control", projected_avg_mv=3.0, library_slots=99)
        assert one_color == base + 1

    def test_color_bonus_capped_at_3(self):
        five_colors = calculate_land_count(
            ["W", "U", "B", "R", "G"], "control", projected_avg_mv=3.0, library_slots=99
        )
        three_colors = calculate_land_count(
            ["W", "U", "B"], "control", projected_avg_mv=3.0, library_slots=99
        )
        assert five_colors == three_colors

    def test_high_mv_adds_2(self):
        low = calculate_land_count(["W", "B"], "aristocrats", projected_avg_mv=2.0, library_slots=99)
        high = calculate_land_count(["W", "B"], "aristocrats", projected_avg_mv=3.6, library_slots=99)
        assert high == low + 2

    def test_mid_mv_adds_1(self):
        low = calculate_land_count(["W", "B"], "aristocrats", projected_avg_mv=2.0, library_slots=99)
        mid = calculate_land_count(["W", "B"], "aristocrats", projected_avg_mv=2.8, library_slots=99)
        assert mid == low + 1

    def test_landfall_archetype_starts_at_38(self):
        land = calculate_land_count(["G"], "landfall", projected_avg_mv=3.0, library_slots=99)
        assert land >= 38

    def test_lands_archetype_starts_at_38(self):
        land = calculate_land_count(["G"], "lands", projected_avg_mv=3.0, library_slots=99)
        assert land >= 38

    def test_land_count_does_not_exceed_library_minus_1(self):
        # Library of 98 (partner) should not have 98 lands
        land = calculate_land_count(
            ["W", "U", "B", "R", "G"], "battlecruiser", projected_avg_mv=5.0, library_slots=98
        )
        assert land < 98


# ─── Score clamping ────────────────────────────────────────────────────────────

class TestScoreClamping:
    def test_score_to_priority_ranges(self):
        assert score_to_priority(10.0) == "Critical"
        assert score_to_priority(8.0) == "Critical"
        assert score_to_priority(7.0) == "High"
        assert score_to_priority(5.0) == "Medium"
        assert score_to_priority(3.0) == "Low"
        assert score_to_priority(0.5) == "Negligible"
        assert score_to_priority(0.0) == "Negligible"

    def test_mv_pressure_table(self):
        assert score_mv_pressure(0.0) == -1.0
        assert score_mv_pressure(2.0) == -1.0
        assert score_mv_pressure(3.0) == 0.0
        assert score_mv_pressure(4.0) == 0.75
        assert score_mv_pressure(5.0) == 1.50
        assert score_mv_pressure(6.0) == 2.50
        assert score_mv_pressure(7.0) == 3.50
        assert score_mv_pressure(9.0) == 3.50


# ─── Protected floors and hard caps ───────────────────────────────────────────

class TestFloorsAndCaps:
    def test_normal_ramp_never_below_5(self):
        result = calculate_category_counts(
            "Test", "control", commander_card_data=TEYSA, power_level=1
        )
        ramp = _get_category(result, "normal_ramp")
        assert ramp["min_count"] >= 5

    def test_draw_never_below_3(self):
        result = calculate_category_counts(
            "Test", "control", commander_card_data=SHORIKAI, power_level=1
        )
        draw = _get_category(result, "draw")
        assert draw["min_count"] >= 3

    def test_win_conditions_never_below_1(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, power_level=3
        )
        wins = _get_category(result, "win_conditions")
        assert wins["min_count"] >= 1

    def test_archetype_core_never_below_4(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, power_level=1
        )
        core = _get_category(result, "archetype_core")
        assert core["min_count"] >= 4


def _get_category(result, cat):
    for rec in result["category_recommendations"]:
        if rec["category"] == cat:
            return rec
    raise KeyError(cat)


# ─── Count interpolation ───────────────────────────────────────────────────────

class TestInterpolation:
    def test_score_5_gives_midpoint_target(self):
        from mtgcli.category_counts.profiles import get_profiles, interpolate_target
        profiles = get_profiles()
        p = profiles["normal_ramp"]
        t = interpolate_target(p, 5.0)
        assert t == pytest.approx(p["score_5_target"])

    def test_score_0_gives_min_target(self):
        from mtgcli.category_counts.profiles import get_profiles, interpolate_target
        profiles = get_profiles()
        p = profiles["normal_ramp"]
        t = interpolate_target(p, 0.0)
        assert t == pytest.approx(p["score_0_target"])

    def test_score_10_gives_max_target(self):
        from mtgcli.category_counts.profiles import get_profiles, interpolate_target
        profiles = get_profiles()
        p = profiles["draw"]
        t = interpolate_target(p, 10.0)
        assert t == pytest.approx(p["score_10_target"])


# ─── Commander scoring ────────────────────────────────────────────────────────

class TestCommanderScoring:
    def test_expensive_commander_raises_ramp_need(self):
        """Shorikai MV 8 → ramp need significantly higher than cheap commander."""
        cheap = calculate_category_counts(
            "Rograkh", "voltron", commander_card_data=ROGRAKH, power_level=6
        )
        expensive = calculate_category_counts(
            "Shorikai", "control", commander_card_data=SHORIKAI, power_level=6
        )
        cheap_ramp = _get_category(cheap, "normal_ramp")["target_count"]
        exp_ramp = _get_category(expensive, "normal_ramp")["target_count"]
        assert exp_ramp > cheap_ramp

    def test_kinnan_high_ramp_despite_ramp_provision(self):
        """Kinnan amplifies ramp → ramp need stays very high."""
        result = calculate_category_counts(
            "Kinnan", "combo", commander_card_data=KINNAN, power_level=8
        )
        ramp = _get_category(result, "normal_ramp")["target_count"]
        assert ramp >= 9

    def test_shorikai_provides_draw_reduces_draw_score(self):
        """Shorikai draws 2 each activation → built_in_card_advantage > 0."""
        scores = score_commander(SHORIKAI, "control")
        assert scores["built_in_card_advantage"] > 0

    def test_high_dependency_increases_protection(self):
        """High-dependency commander should push protection target up."""
        result_high = calculate_category_counts(
            "Test", "combo", commander_card_data=TEYSA, power_level=6
        )
        prot = _get_category(result_high, "protection")["target_count"]
        assert prot >= 4

    def test_no_blue_zeroes_counterspells(self):
        """Non-blue color identity → counterspells target = 0."""
        mono_red = _make_card(
            oracle="Whenever ~ attacks, it gets +2/+0.",
            color_identity=["R"],
            mana_value=3.0,
        )
        result = calculate_category_counts(
            "Red Commander", "go_tall_aggro", commander_card_data=mono_red, power_level=6
        )
        counters = _get_category(result, "counterspells")
        assert counters["target_count"] == 0

    def test_expensive_commander_mv_pressure(self):
        mv_pressure = score_mv_pressure(6.0)
        assert mv_pressure == pytest.approx(2.50)

    def test_cheap_commander_negative_mv_pressure(self):
        mv_pressure = score_mv_pressure(2.0)
        assert mv_pressure == pytest.approx(-1.0)


# ─── Archetype profiles ────────────────────────────────────────────────────────

class TestArchetypeProfiles:
    def test_aristocrats_high_archetype_core(self):
        result = calculate_category_counts(
            "Teysa", "aristocrats", commander_card_data=TEYSA, power_level=6
        )
        core = _get_category(result, "archetype_core")
        assert core["target_count"] >= 16

    def test_aristocrats_high_recursion(self):
        result = calculate_category_counts(
            "Teysa", "aristocrats", commander_card_data=TEYSA, power_level=6
        )
        rec = _get_category(result, "recursion")
        # need_score reflects the aristocrats recursion demand regardless of compression.
        # target_count may be compressed in high-demand decks; the agent uses need_score
        # to judge true importance.
        assert rec["need_score"] >= 4.5

    def test_voltron_high_protection(self):
        result = calculate_category_counts(
            "Ardenn", "voltron", commander_card_data=ARDENN, power_level=6
        )
        prot = _get_category(result, "protection")
        assert prot["target_count"] >= 5

    def test_spellslinger_high_draw_and_card_selection(self):
        result = calculate_category_counts(
            "Stella Lee", "spellslinger", commander_card_data=STELLA_LEE, power_level=7
        )
        draw = _get_category(result, "draw")["target_count"]
        sel_score = _get_category(result, "card_selection")["need_score"]
        assert draw >= 8
        assert sel_score >= 4.5  # need_score (pre-compression) reflects the demand

    def test_control_high_removal_and_wipes(self):
        result = calculate_category_counts(
            "Shorikai", "control", commander_card_data=SHORIKAI, power_level=7
        )
        removal = _get_category(result, "targeted_removal")["need_score"]
        wipes = _get_category(result, "board_wipes")["need_score"]
        assert removal >= 6.0  # control demands high removal
        assert wipes >= 5.0   # control demands board wipes

    def test_stompy_high_big_ramp(self):
        stompy_card = _make_card(
            oracle="Trample. Other creatures you control get +2/+2.",
            color_identity=["G"],
            mana_value=5.0,
        )
        result = calculate_category_counts(
            "Stompy Cmdr", "stompy", commander_card_data=stompy_card, power_level=6
        )
        big_ramp = _get_category(result, "big_ramp")["need_score"]
        assert big_ramp >= 3.0  # stompy has high big_ramp demand score

    def test_zhulodok_extreme_ramp_need(self):
        """Zhulodok MV 7 colorless → extreme ramp pressure."""
        result = calculate_category_counts(
            "Zhulodok", "stompy", commander_card_data=ZHULODOK, power_level=7
        )
        ramp = _get_category(result, "normal_ramp")["target_count"]
        assert ramp >= 11


# ─── Philosophy modifiers ─────────────────────────────────────────────────────

class TestPhilosophy:
    def test_consistency_first_increases_draw(self):
        balanced = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, philosophy="balanced", power_level=6
        )
        consistency = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, philosophy="consistency_first", power_level=6
        )
        b_draw = _get_category(balanced, "draw")["target_count"]
        c_draw = _get_category(consistency, "draw")["target_count"]
        assert c_draw >= b_draw

    def test_low_salt_caps_tutors(self):
        high = calculate_category_counts(
            "Test", "combo", commander_card_data=KINNAN, philosophy="win_optimization", power_level=7
        )
        low = calculate_category_counts(
            "Test", "combo", commander_card_data=KINNAN, philosophy="low_salt", power_level=7
        )
        h_tutors = _get_category(high, "tutors")["need_score"]
        l_tutors = _get_category(low, "tutors")["need_score"]
        assert l_tutors < h_tutors

    def test_synergy_max_increases_archetype_core(self):
        balanced = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, philosophy="balanced", power_level=6
        )
        synergy = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, philosophy="synergy_max", power_level=6
        )
        b_core = _get_category(balanced, "archetype_core")["target_count"]
        s_core = _get_category(synergy, "archetype_core")["target_count"]
        assert s_core >= b_core

    def test_interaction_heavy_increases_removal_and_wipes(self):
        balanced = calculate_category_counts(
            "Test", "control", commander_card_data=SHORIKAI, philosophy="balanced", power_level=6
        )
        interaction = calculate_category_counts(
            "Test", "control", commander_card_data=SHORIKAI, philosophy="interaction_heavy", power_level=6
        )
        b_rem = _get_category(balanced, "targeted_removal")["target_count"]
        i_rem = _get_category(interaction, "targeted_removal")["target_count"]
        assert i_rem >= b_rem

    def test_resilient_increases_protection_and_recursion(self):
        balanced = calculate_category_counts(
            "Test", "voltron", commander_card_data=ARDENN, philosophy="balanced", power_level=6
        )
        resilient = calculate_category_counts(
            "Test", "voltron", commander_card_data=ARDENN, philosophy="resilient", power_level=6
        )
        b_prot = _get_category(balanced, "protection")["target_count"]
        r_prot = _get_category(resilient, "protection")["target_count"]
        assert r_prot >= b_prot


# ─── Meta modifiers ───────────────────────────────────────────────────────────

class TestMeta:
    def test_graveyard_heavy_increases_graveyard_hate(self):
        universal = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, meta="universal", power_level=6
        )
        grave = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, meta="graveyard_heavy", power_level=6
        )
        u_hate = _get_category(universal, "graveyard_hate")["target_count"]
        g_hate = _get_category(grave, "graveyard_hate")["target_count"]
        assert g_hate >= u_hate

    def test_creature_heavy_increases_wipes(self):
        universal = calculate_category_counts(
            "Test", "control", commander_card_data=SHORIKAI, meta="universal", power_level=6
        )
        creature = calculate_category_counts(
            "Test", "control", commander_card_data=SHORIKAI, meta="creature_heavy", power_level=6
        )
        u_wipes = _get_category(universal, "board_wipes")["target_count"]
        c_wipes = _get_category(creature, "board_wipes")["target_count"]
        assert c_wipes >= u_wipes

    def test_combo_heavy_increases_counterspells(self):
        """Combo-heavy meta increases stack interaction even without blue color."""
        blue_card = _make_card(
            oracle="Draw a card.", color_identity=["U", "W"], mana_value=3.0
        )
        universal = calculate_category_counts(
            "Test", "control", commander_card_data=blue_card, meta="universal", power_level=6
        )
        combo = calculate_category_counts(
            "Test", "control", commander_card_data=blue_card, meta="combo_heavy", power_level=6
        )
        u_ctrs = _get_category(universal, "counterspells")["target_count"]
        c_ctrs = _get_category(combo, "counterspells")["target_count"]
        assert c_ctrs >= u_ctrs

    def test_board_wipe_heavy_increases_protection_and_recursion(self):
        universal = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, meta="universal", power_level=6
        )
        wipe_heavy = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, meta="board_wipe_heavy", power_level=6
        )
        u_prot = _get_category(universal, "protection")["target_count"]
        w_prot = _get_category(wipe_heavy, "protection")["target_count"]
        assert w_prot >= u_prot


# ─── Power level scaling ──────────────────────────────────────────────────────

class TestPowerLevel:
    def test_power_10_tutors_higher_than_power_4(self):
        low = calculate_category_counts(
            "Test", "control", commander_card_data=SHORIKAI, power_level=4
        )
        high = calculate_category_counts(
            "Test", "control", commander_card_data=SHORIKAI, power_level=10
        )
        l_tut = _get_category(low, "tutors")["need_score"]
        h_tut = _get_category(high, "tutors")["need_score"]
        assert h_tut > l_tut

    def test_bracket_resolves_to_power_level(self):
        bracket = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, bracket="T3"
        )
        explicit = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, power_level=6.5
        )
        assert bracket["power_level"] == explicit["power_level"]

    def test_explicit_power_level_overrides_bracket(self):
        result = calculate_category_counts(
            "Test", "aristocrats",
            commander_card_data=TEYSA,
            power_level=8.0,
            bracket="T4",
        )
        assert result["power_level"] == 8.0


# ─── Partner decks ────────────────────────────────────────────────────────────

class TestPartnerDecks:
    def test_partner_color_identity_is_union(self):
        result = calculate_category_counts(
            "Ardenn, Intrepid Archaeologist",
            "voltron",
            partner_name="Rograkh, Son of Rohgahh",
            commander_card_data=ARDENN,
            partner_card_data=ROGRAKH,
        )
        ci = set(result["color_identity"])
        assert "W" in ci
        assert "R" in ci

    def test_partner_voltron_high_protection(self):
        result = calculate_category_counts(
            "Ardenn",
            "voltron",
            partner_name="Rograkh",
            commander_card_data=ARDENN,
            partner_card_data=ROGRAKH,
            power_level=6,
        )
        prot = _get_category(result, "protection")["target_count"]
        assert prot >= 5

    def test_partner_archetype_core_high(self):
        result = calculate_category_counts(
            "Ardenn",
            "voltron",
            partner_name="Rograkh",
            commander_card_data=ARDENN,
            partner_card_data=ROGRAKH,
            power_level=6,
        )
        core = _get_category(result, "archetype_core")["target_count"]
        assert core >= 12


# ─── Archetype fit scoring ────────────────────────────────────────────────────

class TestArchetypeFit:
    def test_teysa_high_aristocrats_fit(self):
        fit = score_archetype_fit(TEYSA["oracle_text"], TEYSA["type_line"], "aristocrats")
        assert fit >= 4.0

    def test_ardenn_high_voltron_fit(self):
        fit = score_archetype_fit(ARDENN["oracle_text"], ARDENN["type_line"], "voltron")
        assert fit >= 4.0

    def test_vanilla_low_fit_for_specific_archetype(self):
        vanilla = _make_card(oracle="", type_line="Legendary Creature — Human")
        fit = score_archetype_fit(vanilla["oracle_text"], vanilla["type_line"], "spellslinger")
        assert fit < 4.0

    def test_forced_archetype_warning_set(self):
        """Vanilla commander with spellslinger archetype → forced_archetype_warning."""
        vanilla = _make_card(oracle="", type_line="Legendary Creature — Human", color_identity=["W"])
        result = calculate_category_counts(
            "Vanilla", "spellslinger", commander_card_data=vanilla, power_level=6
        )
        assert result["forced_archetype_warning"] is not None

    def test_good_fit_no_warning(self):
        result = calculate_category_counts(
            "Teysa", "aristocrats", commander_card_data=TEYSA, power_level=6
        )
        assert result["forced_archetype_warning"] is None


# ─── Output shape ─────────────────────────────────────────────────────────────

class TestOutputShape:
    def test_all_expected_top_level_keys(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA
        )
        for key in [
            "commander", "commander_zone_count", "library_slots", "chosen_archetype",
            "archetype_fit_score", "forced_archetype_warning", "power_level",
            "power_tier", "deckbuilding_philosophy", "meta", "color_identity",
            "commander_scores", "land_count", "nonland_slots",
            "category_recommendations", "slot_budget", "multi_tag_policy",
        ]:
            assert key in result, f"Missing key: {key}"

    def test_all_categories_present(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA
        )
        found_cats = {rec["category"] for rec in result["category_recommendations"]}
        for cat in CATEGORIES:
            assert cat in found_cats, f"Missing category: {cat}"

    def test_each_recommendation_has_required_fields(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA
        )
        for rec in result["category_recommendations"]:
            for field in ["category", "need_score", "recommended_range", "min_count",
                          "max_count", "target_count", "priority", "notes"]:
                assert field in rec, f"Missing field {field} in {rec['category']}"

    def test_commander_scores_has_expected_fields(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA
        )
        cs = result["commander_scores"]
        for field in [
            "dependency", "threat_reputation", "mana_value_pressure",
            "built_in_card_advantage", "built_in_ramp", "built_in_removal",
            "built_in_protection", "combo_potential", "provides", "requires", "rewards",
        ]:
            assert field in cs

    def test_slot_budget_fields(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA
        )
        sb = result["slot_budget"]
        assert "total_requested_physical_slots_before_compression" in sb
        assert "available_nonland_slots" in sb
        assert "compression_needed" in sb
        assert "compression_notes" in sb

    def test_nonland_slots_equals_library_minus_lands(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA
        )
        assert result["nonland_slots"] == result["library_slots"] - result["land_count"]

    def test_recommended_range_format(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA
        )
        for rec in result["category_recommendations"]:
            parts = rec["recommended_range"].split("-")
            assert len(parts) == 2
            low, high = int(parts[0]), int(parts[1])
            assert low <= high
            # target_count may be compressed below range; check it is non-negative
            assert rec["target_count"] >= 0
            assert rec["target_count"] <= rec["max_count"]


# ─── Slot compression ─────────────────────────────────────────────────────────

class TestSlotCompression:
    def test_targets_fit_in_nonland_slots_after_compression(self):
        """After compression, sum of targets must not exceed nonland slots."""
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, power_level=9
        )
        total_targets = sum(
            rec["target_count"] for rec in result["category_recommendations"]
        )
        assert total_targets <= result["nonland_slots"]

    def test_compression_noted_in_slot_budget(self):
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, power_level=9
        )
        sb = result["slot_budget"]
        if sb["compression_needed"]:
            assert len(sb["compression_notes"]) > 0

    def test_floors_respected_after_compression(self):
        from mtgcli.category_counts.profiles import get_profiles
        result = calculate_category_counts(
            "Test", "aristocrats", commander_card_data=TEYSA, power_level=10
        )
        profiles = get_profiles()
        for rec in result["category_recommendations"]:
            cat = rec["category"]
            floor = profiles[cat]["protected_floor"]
            assert rec["target_count"] >= floor, (
                f"{cat}: target {rec['target_count']} < floor {floor}"
            )


# ─── Human-readable output smoke test ────────────────────────────────────────

class TestHumanOutput:
    def test_human_output_is_string(self):
        from mtgcli.category_counts.output import format_human_readable
        result = calculate_category_counts(
            "Teysa Karlov", "aristocrats", commander_card_data=TEYSA, power_level=6
        )
        output = format_human_readable(result)
        assert isinstance(output, str)
        assert "Teysa Karlov" in output
        assert "PRIORITY" in output
        assert "Lands:" in output

    def test_partner_output_mentions_partner(self):
        from mtgcli.category_counts.output import format_human_readable
        result = calculate_category_counts(
            "Ardenn",
            "voltron",
            partner_name="Rograkh",
            commander_card_data=ARDENN,
            partner_card_data=ROGRAKH,
        )
        output = format_human_readable(result)
        assert "2 (partner pair)" in output

    def test_forced_archetype_warning_appears_in_output(self):
        from mtgcli.category_counts.output import format_human_readable
        vanilla = _make_card(oracle="", type_line="Legendary Creature", color_identity=["W"])
        result = calculate_category_counts(
            "Vanilla", "spellslinger", commander_card_data=vanilla
        )
        output = format_human_readable(result)
        assert "WARNING" in output
