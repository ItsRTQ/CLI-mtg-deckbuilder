import pytest
from mtgcli.deckbuilder.deck_check import check_deck_quality


def _card(name, type_line, oracle_text, mana_value=2, quantity=1):
    return {
        "name": name,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "mana_value": mana_value,
        "quantity": quantity,
        "commander_legal": True,
    }


SOL_RING = _card("Sol Ring", "Artifact", "{T}: Add {C}{C}.")
ARCANE_SIGNET = _card("Arcane Signet", "Artifact", "{T}: Add one mana of any color in your commander's color identity.")
TALISMAN = _card("Talisman of Progress", "Artifact", "{T}: Add {C}.\n{T}: Add {W} or {U}. Talisman of Progress deals 1 damage to you.")
CULTIVATE = _card("Cultivate", "Sorcery", "Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle.", mana_value=3)
DOCKSIDE = _card("Dockside Extortionist", "Creature — Goblin Pirate", "When Dockside Extortionist enters the battlefield, create X Treasure tokens.", mana_value=2)
LLANOWAR = _card("Llanowar Elves", "Creature — Elf Druid", "{T}: Add {G}.", mana_value=1)

VENERABLE_KNIGHT = _card("Venerable Knight", "Creature — Human Knight", "When Venerable Knight enters the battlefield, another target Knight you control gets +1/+2 until end of turn.", mana_value=1)
KOR_OUTFITTER = _card("Kor Outfitter", "Creature — Kor Soldier", "When Kor Outfitter enters the battlefield, you may attach target Equipment you control to target creature you control.", mana_value=2)
FEAR_OF_DEATH = _card("Fear of Death", "Enchantment — Aura", "Enchant creature. When Fear of Death enters the battlefield, draw a card.", mana_value=1)


def test_deck_check_sol_ring_counts_as_ramp():
    deck = [SOL_RING] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] >= 1

def test_deck_check_arcane_signet_counts_as_ramp():
    deck = [ARCANE_SIGNET] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] >= 1

def test_deck_check_talisman_counts_as_ramp():
    deck = [TALISMAN] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] >= 1

def test_deck_check_cultivate_counts_as_ramp():
    deck = [CULTIVATE] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] >= 1

def test_deck_check_dockside_counts_as_ramp():
    deck = [DOCKSIDE] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] >= 1

def test_deck_check_llanowar_counts_as_ramp():
    deck = [LLANOWAR] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] >= 1

def test_deck_check_venerable_knight_not_ramp():
    deck = [VENERABLE_KNIGHT] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] == 0

def test_deck_check_kor_outfitter_not_ramp():
    deck = [KOR_OUTFITTER] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] == 0

def test_deck_check_fear_of_death_not_ramp():
    deck = [FEAR_OF_DEATH] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] == 0

def test_deck_check_multiple_ramp_cards():
    deck = [SOL_RING, ARCANE_SIGNET, CULTIVATE, LLANOWAR]
    deck += [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["ramp"] >= 4
