from mtgcli.deckbuilder.theme_profiles import get_package_definition


def score_package_card(card: dict, theme: str, package: str) -> dict:
    text = f"{card.get('name', '')} {card.get('type_line', '')} {card.get('oracle_text', '')}".lower()
    mana_value = card.get("mana_value") or 0

    score = 1
    matched = []

    package_def = get_package_definition(theme, package)

    if package_def:
        search_phrases = package_def.get("search_phrases", [])
        for phrase in search_phrases:
            if phrase.lower() in text:
                score += 2
                label = phrase[:24]
                if label not in matched:
                    matched.append(label)

    # Mana efficiency bonus
    if mana_value and mana_value <= 3:
        score += 1
        matched.append("efficient")

    finisher_packages = {"finishers", "combat_finishers", "land_finishers", "blink_finishers", "artifact_finishers"}
    if mana_value and mana_value >= 6 and package not in finisher_packages:
        score -= 2
        matched.append("expensive")

    score = max(1, min(score, 10))

    reason = "Matches " + ", ".join(matched) if matched else "Weak package match."

    return {
        "suggestion_score": score,
        "matched_tags": matched,
        "reason_hint": reason
    }
