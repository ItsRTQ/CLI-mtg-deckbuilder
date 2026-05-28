from mtgcli.deckbuilder.theme_profiles import list_themes, get_theme_packages


def test_theme_profiles_load():
    themes = list_themes()
    assert "modified_creatures" in themes


def test_modified_creatures_has_packages():
    packages = get_theme_packages("modified_creatures")
    assert "modified_enablers" in packages
    assert "modified_payoffs" in packages
