"""Golden set: pinned analyzer reads for 60+ hand-verified cards.

Every entry in data/golden/golden_cards.json was verified by a human/agent judge BEFORE being
pinned (never pin an unverified read — a golden set that pins bugs is worse than none).
Bands are pinned as ACCEPTABLE LISTS so a legitimate fix that raises a band doesn't break the
suite. `must_not_have` pins bands an archetype must NOT reach; `forbidden_signals` pins signal
IDs that must not fire. This suite is the regression net for every future analyzer change and
Fase 2 gate criterion #1 (docs/MIGRATION-archetypes.md).
"""
import json
import pytest
from pathlib import Path

GOLDEN_PATH = Path(__file__).parent.parent / "data" / "golden" / "golden_cards.json"
_GOLDEN = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["cards"]


def _analyze(name):
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    card = CardRepository(str(SQLITE_PATH)).get_card_by_exact_name(name)
    if not card:
        pytest.skip(f"card not in DB: {name}")
    return analyze_card(card)


@pytest.mark.parametrize("entry", _GOLDEN, ids=[c["name"] for c in _GOLDEN])
def test_golden_card(entry):
    r = _analyze(entry["name"])
    bands = {a["archetype"]: a["band"] for a in r["archetype_support"]}
    signals = {s["id"] for s in r["signals"]}

    for arch, ok_bands in entry.get("expected_archetypes", {}).items():
        got = bands.get(arch)
        assert got in ok_bands, (
            f"{entry['name']}: expected {arch} in {ok_bands}, got {got!r} "
            f"(all bands: {bands}) [{entry.get('note','')}]")

    for arch, bad_bands in entry.get("must_not_have", {}).items():
        got = bands.get(arch)
        assert got not in bad_bands, (
            f"{entry['name']}: {arch} must not be in {bad_bands}, got {got!r} "
            f"[{entry.get('note','')}]")

    for sig in entry.get("expected_signals", []):
        assert sig in signals, (
            f"{entry['name']}: expected signal {sig} missing (signals: {sorted(signals)})")

    for sig in entry.get("forbidden_signals", []):
        assert sig not in signals, (
            f"{entry['name']}: forbidden signal {sig} fired [{entry.get('note','')}]")


def test_golden_set_size_gate():
    """Fase 2 gate criterion #1 requires 50+ pinned cards."""
    assert len(_GOLDEN) >= 50, f"golden set has {len(_GOLDEN)} cards, gate requires 50+"
