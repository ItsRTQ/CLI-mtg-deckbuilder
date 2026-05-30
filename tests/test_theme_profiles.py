from mtgcli.deckbuilder.theme_profiles import list_themes, get_theme_packages


def test_theme_profiles_load():
    themes = list_themes()
    assert len(themes) > 0
    assert "creature_type_tribal" in themes
    assert "token_engine" in themes
    assert "sacrifice_value" in themes
    assert "etb_blink_engine" in themes


def test_token_engine_has_packages():
    packages = get_theme_packages("token_engine")
    assert "token_makers" in packages
    assert "token_payoffs" in packages
    assert "token_finishers" in packages


def test_sacrifice_value_has_packages():
    packages = get_theme_packages("sacrifice_value")
    assert "sacrifice_outlets" in packages
    assert "death_payoffs" in packages


def test_etb_blink_engine_has_packages():
    packages = get_theme_packages("etb_blink_engine")
    assert "etb_value" in packages
    assert "blink_enablers" in packages


def test_landfall_landsmatter_has_land_range():
    from mtgcli.deckbuilder.theme_profiles import get_theme_profile
    profile = get_theme_profile("landfall_landsmatter")
    assert profile is not None
    land_range = profile.get("land_range", {})
    assert land_range.get("min", 0) >= 38
