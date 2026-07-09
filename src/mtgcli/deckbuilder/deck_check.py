import json
from typing import List, Dict, Any, Optional
from mtgcli.config import SEED_DATA_DIR
from mtgcli.deckbuilder.theme_profiles import get_theme_packages
from mtgcli.deckbuilder.ramp_rules import land_matches_allowed_ramp_tags
from mtgcli.utils.phrase_match import phrase_matches


def _get_category_phrases(
    category: str,
    tag_definitions: Dict[str, List[str]],
    role_definitions: Dict[str, Any],
) -> List[str]:
    """
    Returns search phrases for a deck-check category.
    If the category maps to a role definition, expands to sub-tag phrases.
    Otherwise falls back to direct card_tags lookup.
    """
    role_def = role_definitions.get(category, {})
    sub_tags = role_def.get("tags", [])
    if sub_tags:
        phrases: List[str] = []
        for sub_tag in sub_tags:
            phrases.extend(tag_definitions.get(sub_tag, []))
        return phrases
    return tag_definitions.get(category, [])


def _is_targeted_tuck_removal(oracle_text: str) -> bool:
    """The Deglamer/Chaos Warp tuck class needs a same-line CONJUNCTION the substring
    vocabulary cannot express: "shuffles it into" is worded identically for targeted
    removal ("Choose target artifact or enchantment. Its owner shuffles it into their
    library" — Deglamer) and for a card's own drawback ("At the beginning of the end
    step, its owner shuffles it into their library" — Lightning Shrieker). The decider
    is whether the SAME oracle line names a target. Measured against the DB: 13 cards
    with target+shuffle in one line, all genuine removal; 8 without "target", all
    self-shuffle/drawback."""
    for line in oracle_text.split("\n"):
        if "shuffles it into" in line and "target" in line:
            return True
    return False


def check_theme_packages(deck_cards: List[Dict[str, Any]], theme: str) -> Dict[str, Any]:
    """
    Checks if the deck matches specific theme package requirements.
    """
    packages = get_theme_packages(theme)

    result = {
        "theme": theme,
        "package_counts": {},
        "warnings": []
    }

    for package_name, package_def in packages.items():
        search_phrases = package_def.get("search_phrases", [])
        minimum = package_def.get("min", 0)
        ideal = package_def.get("ideal", minimum)

        count = 0

        for card in deck_cards:
            quantity = card.get("quantity", 1)
            text = f"{card.get('name', '')} {card.get('type_line', '')} {card.get('oracle_text', '')}".lower()

            matched = False
            for phrase in search_phrases:
                if phrase_matches(phrase, text):
                    matched = True
                    break

            if matched:
                count += quantity

        result["package_counts"][package_name] = {
            "count": count,
            "min": minimum,
            "ideal": ideal
        }

        if count < minimum:
            result["warnings"].append(
                f"Package '{package_name}' has {count} cards; recommended minimum is {minimum}."
            )

    return result

def check_deck_quality(deck_cards: List[Dict[str, Any]], theme: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyzes deck composition based on functional tags and optional thematic packages.
    """
    tag_file = SEED_DATA_DIR / "card_tags.json"
    tag_definitions = {}
    if tag_file.exists():
        with open(tag_file, "r", encoding="utf-8") as f:
            tag_definitions = json.load(f)

    role_file = SEED_DATA_DIR / "role_definitions.json"
    role_definitions = {}
    if role_file.exists():
        with open(role_file, "r", encoding="utf-8") as f:
            role_definitions = json.load(f)

    stats = {
        "lands": 0,
        "ramp": 0,
        "card_draw": 0,
        "removal": 0,
        "board_wipe": 0,
        "protection": 0,
        "synergy": 0
    }
    
    core_categories = ["ramp", "card_draw", "removal", "board_wipe", "protection"]
    
    for card in deck_cards:
        name = card.get("name", "").lower()
        type_line = card.get("type_line", "").lower()
        oracle_text = card.get("oracle_text", "").lower()
        quantity = card.get("quantity", 1)
        
        if "land" in type_line:
            stats["lands"] += quantity
            # Lands count as ramp only when they actually ramp (fetch/extra land),
            # never just for tapping for mana. This keeps basic lands out of the
            # ramp count while still crediting true ramp-lands (e.g. Myriad Landscape).
            if land_matches_allowed_ramp_tags(card, tag_definitions):
                stats["ramp"] += quantity
            continue

        is_synergy = False
        found_core = False
        
        for category in list(tag_definitions.keys()) + [c for c in core_categories if c not in tag_definitions]:
            phrases = _get_category_phrases(category, tag_definitions, role_definitions)
            matches = False
            for phrase in phrases:
                if (phrase_matches(phrase, name) or phrase_matches(phrase, type_line)
                        or phrase_matches(phrase, oracle_text)):
                    matches = True
                    break

            # Conjunction rule: targeted tuck (see _is_targeted_tuck_removal).
            if not matches and category == "removal" and _is_targeted_tuck_removal(oracle_text):
                matches = True

            if matches:
                if category in core_categories:
                    stats[category] += quantity
                    found_core = True
                else:
                    is_synergy = True
        
        if is_synergy and not found_core:
            stats["synergy"] += quantity

    warnings = []
    if stats["lands"] < 35:
        warnings.append("Low land count (less than 35)")
    if stats["ramp"] < 8:
        warnings.append("Low ramp count (less than 8)")
    if stats["card_draw"] < 8:
        warnings.append("Low card draw count (less than 8)")
    if stats["removal"] < 5:
        warnings.append("Low removal count (less than 5)")

    report = {
        "stats": stats,
        "warnings": warnings
    }

    # Popularity signal — CONSIDERATION ONLY, deliberately NOT a warning and never a
    # gate: edhrec_rank measures how PLAYED a card is, not how strong (Command Tower
    # is #2 because it goes everywhere). It exists to catch gross bracket mismatches
    # ("asked T1, 0% staples"), and synergy-dense decks READ LOW BY DESIGN (their
    # on-plan niche cards rank poorly while playing strong in context — Ragost class).
    density = staple_density(deck_cards)
    if density is not None:
        report["staple_density"] = density

    if theme:
        theme_check = check_theme_packages(deck_cards, theme)
        report["theme_check"] = theme_check
        # Merge theme warnings
        report["warnings"].extend(theme_check["warnings"])

    return report


def staple_density(deck_cards: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Aggregate edhrec_rank over NONLAND cards into a popularity signal.

    Returns None when no ranks are known. Lands are excluded (the most-played cards
    in the format are lands and say nothing about the build). Labels are qualitative
    on purpose — no bracket claims (there is no judged-decks dataset to calibrate
    real bracket thresholds against)."""
    ranks: List[float] = []
    unranked = 0
    for card in deck_cards:
        if "land" in (card.get("type_line") or "").lower():
            continue
        qty = card.get("quantity", 1)
        r = card.get("edhrec_rank")
        if isinstance(r, (int, float)):
            ranks.extend([float(r)] * qty)
        else:
            unranked += qty
    if not ranks:
        return None
    ranks.sort()
    n = len(ranks)
    median = ranks[n // 2] if n % 2 else (ranks[n // 2 - 1] + ranks[n // 2]) / 2
    pct_top_2000 = round(100 * sum(1 for r in ranks if r <= 2000) / n, 1)
    # Thresholds calibrated against the 4 real agent builds (2026-07-06): Felothar T3
    # 43.3%, Galadriel T3 65.6%, Mendicant T2 71.4%, Ragost T1 72.6% — real built
    # decks live in the 43-73% band (rocks/removal/draw are staples by count), and the
    # signal orders the brackets correctly. n=4 calibration: labels are coarse on
    # purpose; below 40% is an OUTLIER vs anything ever built here, worth a look.
    if pct_top_2000 >= 65:
        read = "staple-dense"
    elif pct_top_2000 >= 40:
        read = "mixed"
    else:
        read = "niche/synergy-dense (unusually low — worth a look if a high bracket was requested)"
    return {
        "median_rank": int(median),
        "pct_top_2000": pct_top_2000,
        "ranked_nonland_count": n,
        "unranked_nonland_count": unranked,
        "read": read,
        "note": ("popularity signal, consider-only — NOT a power verdict and never a gate; "
                 "synergy-dense decks read low by design"),
    }
