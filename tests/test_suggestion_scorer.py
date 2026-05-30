import pytest
from mtgcli.deckbuilder.suggestion_scorer import score_suggestion


def _card(name="Test Card", type_line="Instant", oracle_text="", mana_value=2, legal=True):
    return {
        "name": name,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "mana_value": mana_value,
        "commander_legal": legal,
    }


# --- ramp role ---

def test_score_ramp_mana_rock_efficient():
    card = _card(
        name="Arcane Signet",
        type_line="Artifact",
        oracle_text="{T}: Add one mana of any color in your commander's color identity.",
        mana_value=2,
    )
    result = score_suggestion(card, "ramp")
    # Sub-tag match (+3), efficiency bonus (+2), legality (+1) = 6
    assert result["score"] == 6
    assert "mana_rock" in result["matched_tags"]
    assert result["score"] > 0

def test_score_ramp_requires_tag_no_empty_matched():
    """Cards with no ramp-related tags must be excluded (score 0)."""
    card = _card(
        name="Venerable Knight",
        type_line="Creature — Human Knight",
        oracle_text="When Venerable Knight enters the battlefield, another target Knight you control gets +1/+2 until end of turn.",
        mana_value=1,
    )
    result = score_suggestion(card, "ramp")
    assert result["score"] == 0
    assert result["matched_tags"] == []

def test_score_ramp_rejects_kor_outfitter():
    card = _card(
        name="Kor Outfitter",
        type_line="Creature — Kor Soldier",
        oracle_text="When Kor Outfitter enters the battlefield, you may attach target Equipment you control to target creature you control.",
        mana_value=2,
    )
    result = score_suggestion(card, "ramp")
    assert result["score"] == 0

def test_score_ramp_rejects_fear_of_death():
    card = _card(
        name="Fear of Death",
        type_line="Enchantment — Aura",
        oracle_text="Enchant creature. When Fear of Death enters the battlefield, draw a card. Enchanted creature gets -2/-0.",
        mana_value=1,
    )
    result = score_suggestion(card, "ramp")
    assert result["score"] == 0

def test_score_ramp_rejects_low_mv_no_tag():
    """Low mana value alone must not qualify a card as ramp."""
    card = _card(
        name="Siren Lookout",
        type_line="Creature — Siren Scout",
        oracle_text="Flying. When Siren Lookout enters the battlefield, it explores.",
        mana_value=1,
    )
    result = score_suggestion(card, "ramp")
    assert result["score"] == 0

def test_score_ramp_land_ramp_cultivate():
    card = _card(
        name="Cultivate",
        type_line="Sorcery",
        oracle_text="Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle.",
        mana_value=3,
    )
    result = score_suggestion(card, "ramp")
    assert result["score"] > 0
    assert "land_ramp" in result["matched_tags"]

def test_score_ramp_treasure_dockside():
    card = _card(
        name="Dockside Extortionist",
        type_line="Creature — Goblin Pirate",
        oracle_text="When Dockside Extortionist enters the battlefield, create X Treasure tokens, where X is the number of artifacts and enchantments your opponents control.",
        mana_value=2,
    )
    result = score_suggestion(card, "ramp")
    assert result["score"] > 0
    assert "treasure" in result["matched_tags"]

def test_score_ramp_mana_dork_llanowar():
    card = _card(
        name="Llanowar Elves",
        type_line="Creature — Elf Druid",
        oracle_text="{T}: Add {G}.",
        mana_value=1,
    )
    result = score_suggestion(card, "ramp")
    assert result["score"] > 0
    assert "mana_dork" in result["matched_tags"]

def test_score_ramp_efficiency_bonus_only_with_tag():
    """Efficiency bonus applies only when a ramp tag is also matched."""
    # Cultivate (MV 3) should get efficiency bonus since land_ramp matched
    card = _card(
        name="Cultivate",
        type_line="Sorcery",
        oracle_text="Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle.",
        mana_value=3,
    )
    result_3 = score_suggestion(card, "ramp")
    # Matches land_ramp (+3) + efficiency (mana_value 3) (+2) + legal (+1) = 6
    assert result_3["score"] == 6

def test_score_ramp_matched_tags_not_empty_for_valid():
    card = _card(
        name="Sol Ring",
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        mana_value=1,
    )
    result = score_suggestion(card, "ramp")
    assert result["matched_tags"] != []
    assert result["score"] > 0


# --- cheap role ---

def test_score_cheap_role_exists():
    card = _card(
        name="Brainstorm",
        type_line="Instant",
        oracle_text="Draw three cards, then put two cards from your hand on top of your library in any order.",
        mana_value=1,
    )
    result = score_suggestion(card, "cheap")
    assert isinstance(result["score"], int)

def test_score_cheap_low_mv_synergy():
    """Low-cost card with synergy tag should score well."""
    card = _card(
        name="Swords to Plowshares",
        type_line="Instant",
        oracle_text="Exile target creature. Its controller gains life equal to its power.",
        mana_value=1,
    )
    result = score_suggestion(card, "cheap")
    assert result["score"] > 0
    assert result["matched_tags"] != []

def test_score_cheap_no_synergy_returns_zero():
    """A cheap but completely generic card with no synergy tags should score 0."""
    card = _card(
        name="Vanilla Bear",
        type_line="Creature — Bear",
        oracle_text="",
        mana_value=2,
    )
    result = score_suggestion(card, "cheap")
    assert result["score"] == 0

def test_score_cheap_high_mv_rejected():
    """Cards with mana_value > 3 must be rejected by cheap role."""
    card = _card(
        name="Some Big Card",
        type_line="Creature",
        oracle_text="Exile target creature.",
        mana_value=5,
    )
    result = score_suggestion(card, "cheap")
    assert result["score"] == 0

def test_score_cheap_etb_low_mv():
    """ETB effect + low mana value = good cheap candidate."""
    card = _card(
        name="Screaming Nemesis",
        type_line="Creature",
        oracle_text="When Screaming Nemesis enters the battlefield, draw a card.",
        mana_value=2,
    )
    result = score_suggestion(card, "cheap")
    assert result["score"] > 0
    # Should match etb_value or card_draw
    assert len(result["matched_tags"]) > 0


# --- theme matching ---

def test_score_theme_goblin():
    card = _card(
        name="Goblin Chieftain",
        type_line="Creature — Goblin",
        oracle_text="Haste. Other Goblin creatures you control get +1/+1 and have haste.",
        mana_value=3,
    )
    result = score_suggestion(card, "synergy", theme="goblins")
    assert result["score"] == 4
    assert "goblins" in result["matched_tags"]


# --- other roles ---

def test_score_expensive_removal():
    card = _card(
        name="Expensive Removal",
        type_line="Instant",
        oracle_text="Destroy target creature.",
        mana_value=7,
    )
    result = score_suggestion(card, "removal")
    # Role match (+3), High cost (-2), Legality (+1) = 2
    assert result["score"] == 2

def test_score_no_text_penalty():
    card = _card(
        name="Vanilla Creature",
        type_line="Creature",
        oracle_text="",
        mana_value=2,
    )
    result = score_suggestion(card, "synergy")
    assert result["score"] == 1
    assert "Missing oracle text" in result["reason_hint"]


# --- reason_hint accuracy ---

def test_reason_hint_mentions_matched_tag():
    card = _card(
        name="Sol Ring",
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        mana_value=1,
    )
    result = score_suggestion(card, "ramp")
    assert "ramp" in result["reason_hint"].lower() or any(t in result["reason_hint"] for t in result["matched_tags"])

def test_reason_hint_not_empty_for_valid_ramp():
    card = _card(
        name="Arcane Signet",
        type_line="Artifact",
        oracle_text="{T}: Add one mana of any color in your commander's color identity.",
        mana_value=2,
    )
    result = score_suggestion(card, "ramp")
    assert result["reason_hint"] not in ("", "Generic match")
    assert "Efficient mana value" in result["reason_hint"]
