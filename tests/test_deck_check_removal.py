import pytest
from mtgcli.deckbuilder.deck_check import check_deck_quality, _is_targeted_tuck_removal


def _card(name, type_line, oracle_text, mana_value=2, quantity=1):
    return {
        "name": name,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "mana_value": mana_value,
        "quantity": quantity,
        "commander_legal": True,
    }


LIGHTNING_BOLT = _card("Lightning Bolt", "Instant", "Lightning Bolt deals 3 damage to any target.", mana_value=1)
CHAOS_WARP = _card("Chaos Warp", "Instant", "The owner of target permanent shuffles it into their library, then reveals the top card of their library. If it's a permanent card, they put it onto the battlefield.", mana_value=3)
DEGLAMER = _card("Deglamer", "Instant", "Choose target artifact or enchantment. Its owner shuffles it into their library.", mana_value=2)
FLAME_SLASH = _card("Flame Slash", "Sorcery", "Flame Slash deals 4 damage to target creature.", mana_value=1)
LIGHTNING_SHRIEKER = _card("Lightning Shrieker", "Creature — Dragon", "Flying, trample, haste\nAt the beginning of the end step, this creature's owner shuffles it into their library.", mana_value=5)
HEALING_SALVE = _card("Healing Salve", "Instant", "Choose one —\n• Target player gains 3 life.\n• Prevent the next 3 damage that would be dealt to any target this turn.", mana_value=1)


def _deck_with(card):
    return [card] + [_card(f"Land{i}", "Basic Land", "", 0) for i in range(35)]


def test_lightning_bolt_counts_as_removal():
    report = check_deck_quality(_deck_with(LIGHTNING_BOLT))
    assert report["stats"]["removal"] >= 1


def test_chaos_warp_counts_as_removal():
    report = check_deck_quality(_deck_with(CHAOS_WARP))
    assert report["stats"]["removal"] >= 1


def test_deglamer_tuck_counts_as_removal():
    # Two-sentence form: "Choose target X. Its owner shuffles it into their library."
    # No single substring can catch it without also catching self-shuffle drawbacks —
    # the same-line target+shuffle conjunction decides.
    report = check_deck_quality(_deck_with(DEGLAMER))
    assert report["stats"]["removal"] >= 1


def test_flame_slash_counts_as_removal():
    report = check_deck_quality(_deck_with(FLAME_SLASH))
    assert report["stats"]["removal"] >= 1


def test_lightning_shrieker_self_shuffle_is_not_removal():
    # Identical shuffle wording, but no target on that line: the card's own drawback.
    report = check_deck_quality(_deck_with(LIGHTNING_SHRIEKER))
    assert report["stats"]["removal"] == 0


def test_healing_salve_prevention_is_not_removal():
    report = check_deck_quality(_deck_with(HEALING_SALVE))
    assert report["stats"]["removal"] == 0


def test_tuck_conjunction_helper_direction():
    assert _is_targeted_tuck_removal(DEGLAMER["oracle_text"].lower())
    assert not _is_targeted_tuck_removal(LIGHTNING_SHRIEKER["oracle_text"].lower())
