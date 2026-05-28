from mtgcli.deckbuilder.theme_profiles import get_package_definition
from mtgcli.cards.search import search_commander_legal_cards, search_by_tags


def search_theme_package(
    theme: str,
    package: str,
    colors: str | None = None,
    limit: int = 50
) -> list[dict]:
    package_def = get_package_definition(theme, package)

    if not package_def:
        raise ValueError(f"Unknown package '{package}' for theme '{theme}'")

    results_by_name = {}

    tags = package_def.get("tags", [])
    search_phrases = package_def.get("search_phrases", [])

    if tags:
        tag_results = search_by_tags(tags=tags, colors=colors, limit=limit * 2)
        for card in tag_results:
            results_by_name[card["name"].lower()] = card

    for phrase in search_phrases:
        phrase_results = search_commander_legal_cards(query=phrase, colors=colors, limit=limit * 2)
        for card in phrase_results:
            results_by_name[card["name"].lower()] = card

    return list(results_by_name.values())[:limit]
