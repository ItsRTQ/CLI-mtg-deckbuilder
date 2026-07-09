"""The analyzer embed carries the functional tag vocabulary.

`analyzer.tags` is the single-source archetype/tag vocabulary that replaced the legacy
`commander_tags`/`synergy_tags` (removed in v0.8.0).
"""
from mtgcli.deckbuilder.commander_analyzer import analyze_commander

KRENKO = {
    "name": "Krenko, Mob Boss",
    "oracle_text": "{T}: Create X 1/1 red Goblin creature tokens, "
                   "where X is the number of Goblins you control.",
    "type_line": "Legendary Creature — Goblin Warrior",
    "color_identity": ["R"],
    "mana_value": 4,
    "power": "3",
    "toughness": "3",
    "can_be_commander": True,
    "commander_legal": True,
}


def test_analyzer_embed_carries_tags():
    out = analyze_commander(KRENKO)
    tags = out["analyzer"]["tags"]
    assert isinstance(tags, list) and tags == sorted(tags)
    assert any("token" in t.lower() for t in tags)  # Krenko is a token engine
