"""Human-readable output formatter for category_counts results."""
from typing import Any, Dict, List

_PRIORITY_ORDER = ["Critical", "High", "Medium", "Low", "Negligible"]


def format_table(result: Dict[str, Any]) -> str:
    """Flat, plain-text, one-row-per-category table for terminal/pipe use.

    Unlike `format_human_readable`, this is a single ungrouped table (no box-drawing
    chars, no repeated per-priority headers, no embedded multi-line notes), and it
    surfaces `compressed_target_count` explicitly alongside `need_score` and
    `recommended_range` — the exact fields needed to judge whether compression has
    distorted a category (see BUILDER.md's Category Counts Contract). Designed to be
    read directly or piped through `column -t` / `awk`, with no JSON parsing required.
    """
    lines: List[str] = []
    recs = sorted(
        result.get("category_recommendations", []),
        key=lambda c: -c.get("need_score", 0),
    )
    name_width = max([len("Category")] + [len(c.get("display_name", c.get("category", "?"))) for c in recs]) + 1

    # Column order encodes the Category Counts Contract: Need and Range are the source
    # of truth, so they come first; the compressed target sits LAST and lowercase
    # ("comp*") because it is the least reliable number in the row (a Critical-need
    # category can compress to a misleading near-zero target — third confirmation in
    # full build #3). The footnote makes the contract self-documenting in the output.
    header = f"{'Category':<{name_width}} {'Need':>5} {'Range':>8} {'Priority':<10} {'comp*':>5}"
    lines.append(header)
    lines.append("-" * len(header))

    for c in recs:
        lines.append(
            f"{c.get('display_name', c.get('category', '?')):<{name_width}} "
            f"{c.get('need_score', 0):>5.1f} "
            f"{c.get('recommended_range', '?'):>8} "
            f"{c.get('priority', '?'):<10} "
            f"{c.get('compressed_target_count', '?'):>5}"
        )

    lines.append("-" * len(header))
    lines.append(
        f"lands={result.get('land_count', '?')} "
        f"nonland={result.get('nonland_slots', '?')} "
        f"avg_mv={result.get('projected_avg_mv', '?')} "
        f"fit={result.get('fit_confidence', '?')}"
    )
    lines.append("*comp = compressed target; guidance only — build to Need/Range "
                 "(a High/Critical category can compress to a misleading tiny target).")
    return "\n".join(lines)


def _group_by_priority(
    recommendations: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {p: [] for p in _PRIORITY_ORDER}
    for rec in recommendations:
        priority = rec.get("priority", "Low")
        if priority in groups:
            groups[priority].append(rec)
    return groups


def format_human_readable(result: Dict[str, Any]) -> str:
    lines: List[str] = []

    lines.append(f"Commander:           {result['commander']}")
    if result.get("commander_zone_count", 1) == 2:
        lines.append(f"Commander Zone Count: 2 (partner pair)")
    else:
        lines.append(f"Commander Zone Count: 1")
    lines.append(f"Library Slots:       {result['library_slots']}")
    fit = result.get("fit_confidence", "unknown")
    lines.append(f"Archetype:           {result['chosen_archetype']} (analyzer fit: {fit})")

    if result.get("forced_archetype_warning"):
        lines.append(f"WARNING:             {result['forced_archetype_warning']}")

    lines.append(f"Power Level:         {result['power_level']} ({result['power_tier']})")
    lines.append(f"Philosophy:          {result['deckbuilding_philosophy']}")
    lines.append(f"Meta:                {result['meta']}")
    ci = "".join(result.get("color_identity", []))
    lines.append(f"Color Identity:      {ci or 'Colorless'}")
    lines.append("")

    cs = result.get("commander_scores", {})
    lines.append("Commander Scores:")
    lines.append(f"  Dependency:          {cs.get('dependency', 0):.1f}/10")
    lines.append(f"  Threat Reputation:   {cs.get('threat_reputation', 0):.1f}/10")
    lines.append(f"  MV Pressure:         {cs.get('mana_value_pressure', 0):+.2f}")
    lines.append(f"  Built-in Draw:       {cs.get('built_in_card_advantage', 0):.1f}")
    lines.append(f"  Built-in Ramp:       {cs.get('built_in_ramp', 0):.1f}")
    lines.append(f"  Built-in Removal:    {cs.get('built_in_removal', 0):.1f}")
    lines.append(f"  Built-in Protection: {cs.get('built_in_protection', 0):.1f}")
    lines.append(f"  Combo Potential:     {cs.get('combo_potential', 0):.1f}/10")
    lines.append("")

    lines.append(f"Lands:               {result['land_count']}")
    lines.append(f"Nonland Slots:       {result['nonland_slots']}")
    lines.append(f"Projected Avg MV:    {result.get('projected_avg_mv', 0):.2f}")
    lines.append("")

    lines.append("Category Recommendations:")
    sep = "─" * 66

    groups = _group_by_priority(result.get("category_recommendations", []))
    for priority in _PRIORITY_ORDER:
        recs = groups[priority]
        if not recs:
            continue
        lines.append(f"\n  {priority.upper()} PRIORITY")
        lines.append(f"  {sep}")
        lines.append(f"  {'Category':<32} {'Range':<10} {'Target':<8} {'Score'}")
        lines.append(f"  {sep}")
        for rec in recs:
            name = rec.get("display_name", rec.get("category", ""))[:32]
            rng = rec.get("recommended_range", "")
            target = rec.get("target_count", 0)
            score = rec.get("need_score", 0)
            lines.append(f"  {name:<32} {rng:<10} {target:<8} {score:.1f}")
            for note in rec.get("notes", []):
                lines.append(f"    * {note}")

    lines.append("")
    sb = result.get("slot_budget", {})
    lines.append("Slot Budget:")
    lines.append(f"  Available nonland slots:   {sb.get('available_nonland_slots', 0)}")
    lines.append(
        f"  Requested before compress: {sb.get('total_requested_physical_slots_before_compression', 0)}"
    )
    lines.append(
        f"  Compression needed:        {'Yes' if sb.get('compression_needed') else 'No'}"
    )
    if sb.get("compression_notes"):
        lines.append("  Compression notes:")
        for note in sb["compression_notes"]:
            lines.append(f"    - {note}")

    lines.append("")
    lines.append("Multi-tag Policy:")
    mp = result.get("multi_tag_policy", {})
    lines.append(
        f"  A card may fill multiple categories but uses one physical slot."
    )
    lines.append(
        f"  Primary tag coverage max: {mp.get('primary_tag_max', 1.0):.2f} | "
        f"Secondary total max: {mp.get('secondary_tag_total_max', 0.75):.2f}"
    )

    return "\n".join(lines)
