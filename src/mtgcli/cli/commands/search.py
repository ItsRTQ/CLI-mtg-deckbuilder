"""Search-family commands: search, search-tags, suggest, explore, combos,
similar, complements.

Bodies split verbatim from the former monolithic ``cli.py``.
"""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _apply_max_price, _emit_json_error  # noqa: F401 -- underscore not re-exported by *

@app.command(epilog="""
Examples:

  mtg search --oracle "can't be blocked" --oracle target --oracle creature

  mtg search --oracle "draw a card" --type creature

  mtg search --card-type vampire --type creature

  mtg search --mv-lte 3 --oracle draw --oracle card --type creature

Repeated filters use AND matching. Use --oracle multiple times when you need
every text snippet to appear. This avoids shell quoting problems with complex
query strings. Filter options combine (AND) with any query string and with --type.
""")
def search(
    query: Optional[str] = typer.Argument(None, help="Optional query string with structured tokens (oracle:, type:, name:, mv:)"),
    colors: Optional[str] = typer.Option(None, "--colors", help="Filter by color identity (e.g. RG)"),
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by broad card type via type_line (e.g. creature, artifact, instant)"),
    oracle: Optional[List[str]] = typer.Option(None, "--oracle", "--text", help="Filter oracle_text; repeatable, AND-matched (alias: --text)"),
    name: Optional[List[str]] = typer.Option(None, "--name", help="Filter card name; repeatable, AND-matched"),
    card_type: Optional[List[str]] = typer.Option(None, "--card-type", "--subtype", help="Filter type_line; repeatable, AND-matched (alias: --subtype)"),
    mv: Optional[float] = typer.Option(None, "--mv", help="Exact mana value"),
    mv_lte: Optional[float] = typer.Option(None, "--mv-lte", help="Mana value <= number"),
    mv_gte: Optional[float] = typer.Option(None, "--mv-gte", help="Mana value >= number"),
    pow_lte: Optional[float] = typer.Option(None, "--pow-lte", help="Power <= number (creatures with numeric power)"),
    pow_gte: Optional[float] = typer.Option(None, "--pow-gte", help="Power >= number (creatures with numeric power)"),
    tou_lte: Optional[float] = typer.Option(None, "--tou-lte", help="Toughness <= number (creatures with numeric toughness)"),
    tou_gte: Optional[float] = typer.Option(None, "--tou-gte", help="Toughness >= number (creatures with numeric toughness)"),
    trigger: Optional[str] = typer.Option(None, "--trigger", help="Find cards with a trigger of this event family (e.g. permanent_dies, attacks_or_combat, you_cast_spell). See --list-triggers."),
    list_triggers: bool = typer.Option(False, "--list-triggers", help="List the available --trigger event families and exit."),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="Maximum USD price (budget builds)"),
    limit: int = typer.Option(20, "--limit", help="Limit number of results"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON")
):
    """Search for commander-legal cards.

    Repeated --oracle/--name/--card-type options are AND-matched and avoid the
    shell-quoting pain of long query strings. They combine with any query string.
    """
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if type_filter is not None:
        try:
            normalize_type_filter(type_filter)
        except UnknownTypeFilterError:
            _msg = (f"Unknown type filter: {type_filter}. {supported_types_message()} "
                    f"For creature types like 'Rogue', use --subtype instead.")
            if json_output:
                _emit_json_error({"error": {"type": "validation",
                                  "message": " ".join(_msg.split())}})
            else:
                print(f"[red]Unknown type filter: {type_filter}.[/red]")
                print(f"[yellow]{supported_types_message()} "
                      f"For creature types like 'Rogue', use --subtype instead.[/yellow]")
            raise typer.Exit(code=1)

    if list_triggers:
        from mtgcli.deckbuilder.oracle_hooks import _TRIGGER_FAMILIES
        fams = [f[0] for f in _TRIGGER_FAMILIES]
        if json_output:
            print_json(fams)
        else:
            print("[bold blue]Trigger event families:[/bold blue]")
            print("  " + ", ".join(fams))
        return

    if trigger:
        from mtgcli.cards.search import search_by_trigger
        from mtgcli.deckbuilder.oracle_hooks import _TRIGGER_FAMILIES
        valid = {f[0] for f in _TRIGGER_FAMILIES}
        if trigger not in valid:
            print(f"[red]Unknown trigger family '{trigger}'.[/red]")
            print(f"[yellow]Available: {', '.join(sorted(valid))}[/yellow]")
            raise typer.Exit(code=1)
        results = search_by_trigger(
            trigger, colors=colors, type_filter=type_filter,
            max_mana_value=int(mv_lte) if mv_lte is not None else None, limit=limit,
        )
        results = _apply_max_price(results, max_price)
        if not results:
            print(f"[yellow]No cards found with trigger family '{trigger}' and those filters[/yellow]")
            return
        if json_output:
            print_json(results)
        else:
            print(f"[bold blue]{len(results)} cards with trigger '{trigger}':[/bold blue]")
            for card in results:
                print(f"- {card['name']} {card['mana_cost']} | {card['type_line']}")
        return

    # Build structured filters from repeatable options (AND-merged with query).
    extra_filters = empty_parsed()
    extra_filters["oracle_terms"] = [t.lower() for t in (oracle or [])]
    extra_filters["name_terms"] = [t.lower() for t in (name or [])]
    extra_filters["type_terms"] = [t.lower() for t in (card_type or [])]
    extra_filters["mana_value_eq"] = mv
    extra_filters["mana_value_lte"] = mv_lte
    extra_filters["mana_value_gte"] = mv_gte
    extra_filters["power_lte"] = pow_lte
    extra_filters["power_gte"] = pow_gte
    extra_filters["toughness_lte"] = tou_lte
    extra_filters["toughness_gte"] = tou_gte

    if not query and not any(
        extra_filters[k] for k in ("oracle_terms", "name_terms", "type_terms")
    ) and mv is None and mv_lte is None and mv_gte is None and not type_filter \
       and pow_lte is None and pow_gte is None and tou_lte is None and tou_gte is None:
        _msg = "Provide a query string or at least one filter option."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)

    try:
        results = search_commander_legal_cards(
            query=query, colors=colors, limit=limit,
            type_filter=type_filter, extra_filters=extra_filters,
        )
        results = _apply_max_price(results, max_price)
    except QueryConflictError as e:
        print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    if not results:
        print(f"[yellow]No cards found matching the given filters[/yellow]")
        return

    if json_output:
        print_json(results)
    else:
        print(f"[bold blue]Found {len(results)} cards:[/bold blue]")
        for card in results:
            print(f"- {card['name']} {card['mana_cost']} | {card['type_line']}")



@app.command()
def search_tags(
    tags: Optional[List[str]] = typer.Argument(None, help="Functional tags (e.g. evasion, sac_outlet, reanimation). Union-matched; results ranked by how many tag phrases each card hits."),
    colors: Optional[str] = typer.Option(None, "--colors", help="Filter by color identity (e.g. RG)"),
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by broad card type via type_line (e.g. creature, artifact, instant)"),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="Maximum USD price"),
    mv_lte: Optional[float] = typer.Option(None, "--mv-lte", help="Mana value <= number"),
    list_tags: bool = typer.Option(False, "--list-tags", help="List all available functional tags and exit."),
    limit: int = typer.Option(20, "--limit", help="Limit number of results"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON")
):
    """Search for cards by functional tag(s), e.g. ramp, card_draw, evasion, sac_outlet.

    Tags are the tool's vocabulary of card FUNCTIONS (see --list-tags). Passing several
    tags unions their phrases, and results are ranked by `tag_match_count` — how many of the
    requested tags' phrases a card actually hits — so the most on-function cards come first.
    Decompose a plan into functions (commander damage = evasion + damage_multiplier +
    protection) and pull a ranked shortlist per function instead of enumerating combinations.
    """
    if list_tags:
        import json as _json
        from mtgcli.config import SEED_DATA_DIR as _SD
        tagdefs = _json.load(open(_SD / "card_tags.json", encoding="utf-8"))
        names = sorted(tagdefs.keys())
        if json_output:
            print_json(names)
        else:
            print(f"[bold blue]Available functional tags ({len(names)}):[/bold blue]")
            print("  " + ", ".join(names))
        return

    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if not tags:
        _msg = "Provide at least one tag, or use --list-tags to see them."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)

    if type_filter is not None:
        try:
            normalize_type_filter(type_filter)
        except UnknownTypeFilterError:
            _msg = (f"Unknown type filter: {type_filter}. {supported_types_message()} "
                    f"For creature types like 'Rogue', use --subtype instead.")
            if json_output:
                _emit_json_error({"error": {"type": "validation",
                                  "message": " ".join(_msg.split())}})
            else:
                print(f"[red]Unknown type filter: {type_filter}.[/red]")
                print(f"[yellow]{supported_types_message()} "
                      f"For creature types like 'Rogue', use --subtype instead.[/yellow]")
            raise typer.Exit(code=1)

    results = search_by_tags(
        tags=tags, colors=colors, limit=limit, type_filter=type_filter,
        max_price=max_price, max_mana_value=int(mv_lte) if mv_lte is not None else None,
        rank=True,
    )

    if not results:
        print(f"[yellow]No cards found matching tags: {', '.join(tags)}[/yellow]")
        return

    if json_output:
        print_json(results)
    else:
        print(f"[bold blue]{len(results)} cards for tags {', '.join(tags)} (ranked by facets matched):[/bold blue]")
        for card in results:
            n = card.get("tag_match_count", 0)
            print(f"- [{n}x] {card['name']} {card['mana_cost']} | {card['type_line']}")



@app.command()
def suggest(
    commander: str = typer.Option(..., "--commander", help="Name of the commander"),
    role: str = typer.Option(..., "--role", help="Role to suggest cards for (e.g. ramp, card_draw, removal, engine)"),
    synergy: bool = typer.Option(False, "--synergy", help="Narrow results to cards that also connect with the commander's strategy (applied after role match)"),
    analysis: Optional[Path] = typer.Option(None, "--analysis", help="Path to commander_analysis.json; improves --synergy matching (default: output/commander_analysis.json)"),
    theme: Optional[str] = typer.Option(None, "--theme", help="Optional deck theme, e.g. goblins, equipment, modified_creatures"),
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by broad card type via type_line, applied after role match (e.g. creature, artifact)"),
    package: Optional[str] = typer.Option(None, "--package", help="Optional theme package, e.g. modified_enablers"),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="Maximum USD price"),
    exclude_deck: Optional[Path] = typer.Option(None, "--exclude", help="Deck JSON file with cards to exclude"),
    limit: int = typer.Option(20, "--limit", help="Limit number of results"),
    dedupe: bool = typer.Option(True, "--dedupe/--no-dedupe", help="Deduplicate repeated printings"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON")
):
    """Suggest cards for a commander based on a specific role, theme, and package."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if type_filter is not None:
        try:
            normalize_type_filter(type_filter)
        except UnknownTypeFilterError:
            _msg = (f"Unknown type filter: {type_filter}. {supported_types_message()} "
                    f"For creature types like 'Rogue', use --subtype instead.")
            if json_output:
                _emit_json_error({"error": {"type": "validation",
                                  "message": " ".join(_msg.split())}})
            else:
                print(f"[red]Unknown type filter: {type_filter}.[/red]")
                print(f"[yellow]{supported_types_message()} "
                      f"For creature types like 'Rogue', use --subtype instead.[/yellow]")
            raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    commander_card = repo.get_card_by_exact_name(commander)
    
    if not commander_card:
        print(f"[red]Commander '{commander}' not found.[/red]")
        raise typer.Exit(code=1)

    # Load role definitions
    role_file = SEED_DATA_DIR / "role_definitions.json"
    if not role_file.exists():
        print(f"[red]Role definitions not found at {role_file}[/red]")
        raise typer.Exit(code=1)

    role_defs = read_json(role_file)
    if role == "synergy":
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message":
                "'synergy' is not a valid role. Use --synergy as a modifier flag on a real "
                "role, e.g. mtg suggest --commander 'Atraxa' --role ramp --synergy"}})
        else:
            print("[red]'synergy' is not a valid role.[/red]")
            print("[yellow]Use --synergy as a modifier flag to narrow role results by commander synergy.[/yellow]")
            print("[yellow]Example: mtg suggest --commander 'Atraxa' --role ramp --synergy[/yellow]")
        raise typer.Exit(code=1)
    if role not in role_defs:
        print(f"[red]Unknown role: {role}[/red]")
        print(f"[yellow]Available roles: {', '.join(role_defs.keys())}[/yellow]")
        raise typer.Exit(code=1)

    tags = list(role_defs[role].get("tags", []))
    if theme and not package:
        tags.append(theme)
        
    colors = "".join(commander_card.get("color_identity", []))
    
    # Handle exclusions
    exclude_names = set()
    if exclude_deck and exclude_deck.exists():
        try:
            deck_data = read_json(exclude_deck)
            for entry in deck_data:
                if isinstance(entry, dict) and "name" in entry:
                    exclude_names.add(entry["name"])
                elif isinstance(entry, str):
                    exclude_names.add(entry)
        except Exception as e:
            print(f"[yellow]Warning: Could not read exclude deck: {e}[/yellow]")

    if package:
        if not theme:
            print("[red]--package requires --theme[/red]")
            raise typer.Exit(code=1)

        results = search_theme_package(
            theme=theme,
            package=package,
            colors=colors,
            limit=limit * 2
        )

        # Filter by price and exclusions manually for package results for now
        # search_theme_package doesn't support them directly yet
        filtered_results = []
        for card in results:
            if max_price is not None and card.get("usd_price") is not None and card["usd_price"] > max_price:
                continue
            if card["name"] in exclude_names:
                continue
            if type_filter is not None and not card_matches_type(card, type_filter):
                continue
            filtered_results.append(card)
        results = filtered_results

        scored_results = []
        for card in results:
            scoring = score_package_card(card, theme, package)
            card.update(scoring)
            scored_results.append(card)

        # Sort by score descending, then mana_value ascending
        scored_results.sort(
            key=lambda c: (
                -c.get("suggestion_score", 0),
                c.get("edhrec_rank") if isinstance(c.get("edhrec_rank"), int) else 10**9,
                c.get("name", "")
            )
        )
        final_results = scored_results[:limit]
    else:
        # For roles with a max mana value (e.g. cheap), pre-filter in SQL
        role_max_mv = role_defs[role].get("target_mana_value_max")

        results = search_by_tags(
            tags=tags,
            colors=colors,
            limit=limit * 4,
            max_price=max_price,
            max_mana_value=role_max_mv,
            exclude_names=list(exclude_names),
            dedupe=dedupe,
            type_filter=type_filter
        )

        if not results:
            print(f"[yellow]No suggestions found for role '{role}' in colors '{colors}'[/yellow]")
            return

        # Score and enrich results; drop score-0 (failed requires_tag_match)
        scored_results = []
        for card in results:
            score_data = score_suggestion(card, role, theme)
            if score_data["score"] == 0:
                continue
            card["suggestion_score"] = score_data["score"]
            card["matched_tags"] = score_data["matched_tags"]
            card["reason_hint"] = score_data["reason_hint"]
            scored_results.append(card)

        if not scored_results:
            print(f"[yellow]No qualifying suggestions found for role '{role}' in colors '{colors}'[/yellow]")
            return

        # Apply --synergy filter: narrow to cards that connect with the commander's strategy
        if synergy:
            analysis_path = analysis or Path("output/commander_analysis.json")
            commander_signals = extract_commander_synergy_signals(commander_card, analysis_path=analysis_path)
            synergy_results = []
            for card in scored_results:
                matched_synergy = check_card_synergy(card, commander_signals)
                if not matched_synergy:
                    continue
                card["suggestion_score"] = min(10, card["suggestion_score"] + 2)
                card["matched_tags"] = list(set(card.get("matched_tags", []) + matched_synergy))
                existing_hint = card.get("reason_hint", "")
                card["reason_hint"] = f"{existing_hint}; Commander synergy: {', '.join(matched_synergy)}" if existing_hint else f"Commander synergy: {', '.join(matched_synergy)}"
                synergy_results.append(card)
            if not synergy_results:
                print(f"[yellow]No role-matching cards with commander synergy found for '{commander}' ({role})[/yellow]")
                return
            scored_results = synergy_results

        # Sort by score descending, then mana_value ascending
        scored_results.sort(key=lambda x: (
            -x["suggestion_score"],
            x.get("edhrec_rank") if isinstance(x.get("edhrec_rank"), int) else 10**9))
        final_results = scored_results[:limit]

    if json_output:
        # Define output fields for clean JSON
        output_fields = [
            "name", "mana_cost", "mana_value", "type_line", "oracle_text",
            "power", "toughness",
            "colors", "color_identity", "commander_legal", "can_be_commander",
            "usd_price", "edhrec_rank", "suggestion_score", "matched_tags", "reason_hint"
        ]
        json_results = []
        for card in final_results:
            json_results.append({k: card.get(k) for k in output_fields})
        print_json(json_results)
    else:
        title = f"Suggestions for {commander} ({role})"
        if synergy:
            title += " [+Synergy]"
        if theme:
            title += f" [Theme: {theme}]"
        if package:
            title += f" [Package: {package}]"
        if max_price:
            title += f" [Max Price: ${max_price}]"
            
        print(f"[bold blue]{title}:[/bold blue]")
        for card in final_results:
            price_str = f" [green]${card['usd_price']}[/green]" if card['usd_price'] else ""
            score_str = f" [yellow](Score: {card['suggestion_score']})[/yellow]"
            print(f"- {card['name']} {card['mana_cost']} | {card['type_line']}{price_str}{score_str}")
            print(f"  [italic white]{card['reason_hint']}[/italic white]")



@app.command()
def explore(
    commander: str = typer.Option(..., "--commander", help="Name of the commander"),
    save_raw: Optional[Path] = typer.Option(None, "--save-raw", help="Save raw HTML to this path for debugging"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON")
):
    """Fetch community card recommendations for a commander from EDHREC."""
    if not commander.strip():
        print("[red]Commander name cannot be empty.[/red]")
        raise typer.Exit(code=1)

    try:
        url = build_explore_url(commander)
    except ValueError as e:
        print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1)

    try:
        html = fetch_commander_page(url)
    except Exception as e:
        print(f"[red]Failed to fetch page: {e}[/red]")
        raise typer.Exit(code=1)

    if save_raw:
        save_raw.parent.mkdir(parents=True, exist_ok=True)
        save_raw.write_text(html, encoding="utf-8")

    cards = extract_target_cards_from_html(html)

    # Optional: hydrate card names against local DB
    repo = CardRepository(str(SQLITE_PATH)) if SQLITE_PATH.exists() else None

    def hydrate(names: List[str]) -> List[dict]:
        result = []
        for name in names:
            entry: dict = {"name": sanitize_json_string(name)}
            if repo:
                card_data = repo.get_card_by_exact_name(name)
                if card_data:
                    entry["found_in_database"] = True
                    entry["commander_legal"] = card_data.get("commander_legal", False)
                    entry["color_identity"] = card_data.get("color_identity", [])
                else:
                    entry["found_in_database"] = False
            result.append(entry)
        return result

    NOTE = "Community recommendations only. These are candidates, not mandatory includes."

    if json_output:
        output = {
            "commander": sanitize_json_string(commander),
            "source_url": sanitize_json_string(url),
            "high_synergy": hydrate(cards["high_synergy"]),
            "top_cards": hydrate(cards["top_cards"]),
            "note": sanitize_json_string(NOTE),
        }
        print_json(output)
    else:
        print(f"[bold blue]Commander:[/bold blue] {commander}")
        print(f"[bold blue]Source:[/bold blue] {url}")
        print()
        print("[bold]High Synergy:[/bold]")
        for name in cards["high_synergy"]:
            print(f"- {name}")
        print()
        print("[bold]Top Cards:[/bold]")
        for name in cards["top_cards"]:
            print(f"- {name}")
        print()
        print(f"[italic yellow]Note: {NOTE}[/italic yellow]")



@app.command()
def combos(
    commander: str = typer.Option(..., "--commander", help="Commander card name"),
    output_path: Path = typer.Option(Path("output/commander_combos.json"), "--output", help="Output file path"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of combos returned"),
    bracket: Optional[str] = typer.Option(None, "--bracket", help="Exact bracket filter (e.g. 2)"),
    max_bracket: Optional[str] = typer.Option(None, "--max-bracket", help="Maximum bracket value (numeric)"),
    include_raw: bool = typer.Option(False, "--include-raw", help="Include raw source payload in output"),
    no_write: bool = typer.Option(False, "--no-write", help="Print only, do not write file"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Fetch and parse combo data for a commander."""
    try:
        url = build_combo_url(commander)
    except ValueError as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    try:
        raw = fetch_combo_data(url)
    except ValueError as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    all_combos = parse_combos(raw)
    filtered = filter_combos(all_combos, bracket=bracket, max_bracket=max_bracket, limit=limit)
    slug = commander_to_slug(commander)

    result = {
        "commander": commander,
        "slug": slug,
        "source_url": url,
        "combo_count": len(filtered),
        "written": False,
        "output": None,
        "combos": filtered,
        "use_guidance": USE_GUIDANCE,
    }

    if include_raw:
        result["raw"] = raw

    if not filtered:
        result["message"] = f"No combos found for {commander}."

    if not no_write and filtered:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(output_path, result)
        result["written"] = True
        result["output"] = str(output_path)

    if json_output:
        typer.echo(json.dumps(result, indent=2))
    else:
        count = result["combo_count"]
        if count == 0:
            print(f"[yellow]No combos found for {commander}.[/yellow]")
        else:
            print(f"[bold blue]Combos found for {commander}: {count}[/bold blue]")
            for i, combo in enumerate(filtered, 1):
                print(f"\n[Combo #{i}] [Bracket: {combo['bracket']}]")
                print("Cards:")
                for card in combo["cards"]:
                    print(f"  - {card}")
                if combo["results"]:
                    print("Results:")
                    for r in combo["results"]:
                        print(f"  - {r}")
            print(
                "\n[italic]Note: Combo data is optional deckbuilding context, "
                "not mandatory includes.[/italic]"
            )
        if result["written"]:
            print(f"[green]Saved to {output_path}[/green]")



@app.command()
def similar(
    card_name: str = typer.Argument(..., help="Card whose function to match"),
    colors: Optional[str] = typer.Option(None, "--colors", help="Override color identity filter (default: the card's own identity)"),
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by broad card type"),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="Maximum USD price"),
    limit: int = typer.Option(20, "--limit", help="Limit number of results"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Find cards that perform the SAME function as a given card.

    Profiles the card (the functional tags it satisfies) and searches for other cards sharing
    those tags, ranked by how many they share. Defaults to the source card's color identity.
    """
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)
    repo = CardRepository(str(SQLITE_PATH))
    card = repo.get_card_by_exact_name(card_name)
    if not card:
        sugg = [s["name"] for s in repo.suggest_similar_names(card_name, limit=3)]
        print(f"[red]Card '{card_name}' not found.[/red]" + (f" Did you mean: {', '.join(sugg)}?" if sugg else ""))
        raise typer.Exit(code=1)

    from mtgcli.deckbuilder.card_profile import card_function_profile
    profile = card_function_profile(card)
    tags = profile["tags"]
    if not tags:
        print(f"[yellow]Couldn't profile a function for '{card['name']}'.[/yellow]")
        return

    use_colors = colors if colors is not None else "".join(card.get("color_identity", []))
    results = search_by_tags(tags=tags, colors=use_colors or None, type_filter=type_filter,
                             max_price=max_price, limit=limit + 1, rank=True)
    results = [c for c in results if c["name"].lower() != card["name"].lower()][:limit]

    if json_output:
        print_json({"source": card["name"], "function_tags": tags, "results": results})
    else:
        print(f"[bold blue]Cards similar to {card['name']}[/bold blue] [dim](function: {', '.join(tags)})[/dim]")
        for c in results:
            print(f"- [{c.get('tag_match_count', 0)}x] {c['name']} {c['mana_cost']} | {c['type_line']}")



@app.command()
def complements(
    card_name: str = typer.Argument(..., help="Card whose synergy partners to find"),
    colors: Optional[str] = typer.Option(None, "--colors", help="Override color identity filter (default: the card's own identity)"),
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by broad card type"),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="Maximum USD price"),
    limit: int = typer.Option(20, "--limit", help="Limit number of results"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Find cards that SYNERGIZE with a given card (the other half of the interaction).

    Profiles the card, maps its functions to their payoffs/enablers via the complement map,
    and searches for those — e.g. a sacrifice outlet finds death-triggers and recursion; a
    +1/+1 placer finds proliferate and counter payoffs.
    """
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)
    repo = CardRepository(str(SQLITE_PATH))
    card = repo.get_card_by_exact_name(card_name)
    if not card:
        sugg = [s["name"] for s in repo.suggest_similar_names(card_name, limit=3)]
        print(f"[red]Card '{card_name}' not found.[/red]" + (f" Did you mean: {', '.join(sugg)}?" if sugg else ""))
        raise typer.Exit(code=1)

    from mtgcli.deckbuilder.card_profile import card_function_profile, complementary_tags
    profile = card_function_profile(card)
    comp_tags = complementary_tags(profile["tags"])
    if not comp_tags:
        print(f"[yellow]No known complements for '{card['name']}' (functions: {', '.join(profile['tags']) or 'none detected'}).[/yellow]")
        return

    use_colors = colors if colors is not None else "".join(card.get("color_identity", []))
    results = search_by_tags(tags=comp_tags, colors=use_colors or None, type_filter=type_filter,
                             max_price=max_price, limit=limit + 1, rank=True)
    results = [c for c in results if c["name"].lower() != card["name"].lower()][:limit]

    if json_output:
        print_json({"source": card["name"], "source_functions": profile["tags"],
                    "complement_tags": comp_tags, "results": results})
    else:
        print(f"[bold blue]Cards that complement {card['name']}[/bold blue] [dim](looking for: {', '.join(comp_tags)})[/dim]")
        for c in results:
            print(f"- [{c.get('tag_match_count', 0)}x] {c['name']} {c['mana_cost']} | {c['type_line']}")


