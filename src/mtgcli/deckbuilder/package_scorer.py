def score_package_card(card: dict, theme: str, package: str) -> dict:
    text = f"{card.get('name', '')} {card.get('type_line', '')} {card.get('oracle_text', '')}".lower()
    mana_value = card.get("mana_value") or 0

    score = 1
    matched = []

    # Modified creatures
    if theme == "modified_creatures":
        if package == "modified_enablers":
            if "equipment" in text:
                score += 4
                matched.append("equipment")
            if "aura" in text:
                score += 4
                matched.append("aura")
            if "+1/+1 counter" in text:
                score += 4
                matched.append("counter_enabler")
            if "modified" in text:
                score += 3
                matched.append("modified")

        if package == "modified_payoffs":
            if "modified" in text:
                score += 4
                matched.append("modified_payoff")
            if "equipped creature" in text:
                score += 3
                matched.append("equipment_payoff")
            if "enchanted creature" in text:
                score += 3
                matched.append("aura_payoff")
            if "combat damage" in text:
                score += 2
                matched.append("combat_damage")
            if "+1/+1 counter" in text:
                score += 2
                matched.append("counter_payoff")

        if package == "combat_finishers":
            if "trample" in text:
                score += 3
                matched.append("trample")
            if "additional combat" in text:
                score += 4
                matched.append("extra_combat")
            if "double strike" in text:
                score += 2
                matched.append("double_strike")
            if "creatures you control get" in text:
                score += 3
                matched.append("team_pump")

    # Goblins
    if theme == "goblins":
        if "goblin" in text:
            score += 4
            matched.append("goblin")
        if "goblins you control" in text or "goblin creatures you control" in text:
            score += 4
            matched.append("goblin_payoff")
        if "create" in text and "goblin" in text and "token" in text:
            score += 4
            matched.append("goblin_token_maker")
        if "haste" in text:
            score += 2
            matched.append("haste")

    # Zombie sacrifice
    if theme == "zombie_sacrifice":
        if "zombie" in text:
            score += 3
            matched.append("zombie")
        if "sacrifice" in text:
            score += 3
            matched.append("sacrifice")
        if "whenever" in text and "dies" in text:
            score += 3
            matched.append("death_trigger")
        if "graveyard" in text:
            score += 2
            matched.append("graveyard")

    # General mana efficiency bonus
    if mana_value and mana_value <= 3:
        score += 1
        matched.append("efficient")

    if mana_value and mana_value >= 6 and package != "combat_finishers":
        score -= 2
        matched.append("expensive")

    score = max(1, min(score, 10))

    reason = "Matches " + ", ".join(matched) if matched else "Weak package match."

    return {
        "suggestion_score": score,
        "matched_tags": matched,
        "reason_hint": reason
    }
