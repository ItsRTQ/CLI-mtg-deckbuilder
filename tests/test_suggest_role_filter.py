"""
Role-filter regression tests for `suggest`.

Ramp must be real acceleration (not normal lands); card_draw must be actual
card advantage. These assert the scorer drops off-role candidates so the CLI
never surfaces them.
"""
from mtgcli.deckbuilder.suggestion_scorer import score_suggestion


def _card(name, type_line, oracle, mana_value=2.0, commander_legal=True):
    return {
        "name": name,
        "type_line": type_line,
        "oracle_text": oracle,
        "mana_value": mana_value,
        "commander_legal": commander_legal,
    }


# ─── ramp ──────────────────────────────────────────────────────────────────

def test_ramp_rejects_basic_land():
    forest = _card("Forest", "Basic Land — Forest", "({T}: Add {G}.)")
    result = score_suggestion(forest, "ramp")
    assert result["score"] == 0
    assert result["matched_tags"] == []


def test_ramp_rejects_command_tower():
    tower = _card(
        "Command Tower",
        "Land",
        "{T}: Add one mana of any color in your commander's color identity.",
    )
    result = score_suggestion(tower, "ramp")
    assert result["score"] == 0


def test_ramp_rejects_tapped_dual_land():
    dual = _card(
        "Tranquil Cove",
        "Land",
        "Tranquil Cove enters the battlefield tapped.\n"
        "When Tranquil Cove enters, you gain 1 life.\n"
        "{T}: Add {W} or {U}.",
    )
    result = score_suggestion(dual, "ramp")
    assert result["score"] == 0


def test_ramp_accepts_sol_ring():
    sol_ring = _card("Sol Ring", "Artifact", "{T}: Add {C}{C}.", mana_value=1.0)
    result = score_suggestion(sol_ring, "ramp")
    assert result["score"] > 0
    assert "mana_rock" in result["matched_tags"]


def test_ramp_accepts_arcane_signet():
    signet = _card(
        "Arcane Signet",
        "Artifact",
        "{T}: Add one mana of any color in your commander's color identity.",
        mana_value=2.0,
    )
    result = score_suggestion(signet, "ramp")
    assert result["score"] > 0
    assert result["matched_tags"]


def test_ramp_accepts_land_ramp_land():
    """A land that *searches* for lands is real ramp."""
    land = _card(
        "Wanderer Land",
        "Land",
        "{T}: Add {C}.\nWhen this land enters, search your library for a basic land "
        "card, put it onto the battlefield tapped, then shuffle.",
    )
    result = score_suggestion(land, "ramp")
    assert result["score"] > 0
    assert "land_ramp" in result["matched_tags"]


# ─── card_draw ───────────────────────────────────────────────────────────────

def test_card_draw_requires_real_draw_tag():
    real = _card("Divination", "Sorcery", "Draw two cards.")
    result = score_suggestion(real, "card_draw")
    assert result["score"] > 0
    assert result["matched_tags"]


def test_card_draw_rejects_unrelated_card():
    """A cheap, legal, generic card with no draw text must not qualify."""
    vanilla = _card(
        "Grizzly Bears", "Creature — Bear", "", mana_value=2.0
    )
    result = score_suggestion(vanilla, "card_draw")
    assert result["score"] == 0
    assert result["matched_tags"] == []


def test_card_draw_rejects_offrole_removal():
    removal = _card("Murder", "Instant", "Destroy target creature.", mana_value=3.0)
    result = score_suggestion(removal, "card_draw")
    assert result["score"] == 0


# ─── role suggestions never surface score-0 cards ────────────────────────────

def test_strict_roles_drop_empty_matched_tags():
    vanilla = _card("Hill Giant", "Creature — Giant", "", mana_value=4.0)
    for role in ("ramp", "card_draw", "removal", "protection", "engine",
                 "enabler", "payoff"):
        result = score_suggestion(vanilla, role)
        assert result["score"] == 0, f"{role} should reject empty matched_tags"
