from mtgcli.deckbuilder.constraints import DeckConstraints, parse_constraints_from_text
from mtgcli.deckbuilder.skeleton_adjuster import apply_constraints_to_skeleton


def test_parse_exact_lands():
    constraints = parse_constraints_from_text("Create a Krenko deck with 33 lands")
    assert constraints.exact_counts["lands"] == 33


def test_parse_more_equipment_and_fewer_board_wipes():
    constraints = parse_constraints_from_text("Create a Chishiro deck with more equipment and fewer board wipes")
    assert "more_equipment" in constraints.preferences
    assert "fewer_board_wipes" in constraints.preferences


def test_parse_no_infinite_combos():
    constraints = parse_constraints_from_text("Create a Wilhelt deck with 35 lands and no infinite combos")
    assert constraints.exact_counts["lands"] == 35
    assert "infinite_combos" in constraints.avoid


def test_adjust_skeleton_to_33_lands():
    base_skeleton = {
        "commander": 1,
        "lands": 37,
        "ramp": 10,
        "card_draw": 10,
        "removal": 9,
        "board_wipes": 2,
        "protection": 5,
        "synergy": 22,
        "win_conditions": 4
    }

    adjusted = apply_constraints_to_skeleton(
        base_skeleton,
        DeckConstraints(exact_counts={"lands": 33})
    )

    assert adjusted["lands"] == 33
    assert sum(adjusted.values()) == 100
