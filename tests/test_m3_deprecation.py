"""M3: legacy fields formally deprecated in the analysis output.

- `legacy_deprecations` is a machine-readable block naming each deprecated field, its
  replacement, and the planned removal (v0.10). The fields themselves REMAIN until v0.10
  so no consumer breaks.
- `analyzer.tags` is the single-source replacement for commander_tags/synergy_tags.
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


def test_legacy_deprecations_block_present():
    out = analyze_commander(KRENKO)
    dep = out["legacy_deprecations"]
    for field in ("archetype_fit", "commander_tags", "synergy_tags"):
        assert dep[field]["deprecated"] is True
        assert dep[field]["removal_planned"] == "v0.10"
        assert dep[field]["replaced_by"].startswith("analyzer.")
    # The deprecated fields themselves must STILL be present until v0.10.
    assert "archetype_fit" in out and "commander_tags" in out and "synergy_tags" in out


def test_analyzer_embed_carries_tags():
    out = analyze_commander(KRENKO)
    tags = out["analyzer"]["tags"]
    assert isinstance(tags, list) and tags == sorted(tags)
    assert any("token" in t.lower() for t in tags)  # Krenko is a token engine
