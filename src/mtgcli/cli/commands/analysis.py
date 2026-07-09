"""Analysis commands: commander-analyze, themes, theme-info, category-counts,
analyze-card.

Bodies split verbatim from the former monolithic ``cli.py``.
"""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _apply_max_price  # noqa: F401 -- underscore not re-exported by *

@app.command()
def commander_analyze(
    commander: str = typer.Option(..., "--commander", help="Commander card name"),
    partner: Optional[str] = typer.Option(None, "--partner", help="Partner commander card name"),
    archetype: Optional[str] = typer.Option(None, "--archetype", help="Optional archetype context (e.g. blink, aristocrats)"),
    theme: Optional[str] = typer.Option(None, "--theme", help="Optional theme context"),
    power_level: Optional[float] = typer.Option(None, "--power-level", help="Optional power level 1-10"),
    philosophy: Optional[str] = typer.Option(None, "--philosophy", help="Optional deckbuilding philosophy"),
    meta: Optional[str] = typer.Option(None, "--meta", help="Optional meta context"),
    output_path: Path = typer.Option(Path("output/commander_analysis.json"), "--output", help="Output file path"),
    no_write: bool = typer.Option(False, "--no-write", help="Print analysis only, do not write file"),
    json_output: bool = typer.Option(False, "--json-output", help="Print JSON to stdout"),
):
    """Analyze a commander and write a reusable tactical JSON artifact."""
    require_database(SQLITE_PATH, json_output)

    repo = CardRepository(str(SQLITE_PATH))
    commander_card = repo.get_card_by_exact_name(commander)
    if not commander_card:
        print(f"[red]Commander '{commander}' not found in database.[/red]")
        raise typer.Exit(code=1)

    can_be_cmd = commander_card.get("can_be_commander", False)
    is_cmd_legal = commander_card.get("commander_legal", False)
    if not (can_be_cmd or is_cmd_legal):
        print(f"[red]'{commander}' is not legal as a commander.[/red]")
        print("[yellow]Analysis will be marked invalid.[/yellow]")

    partner_card = None
    if partner:
        partner_card = repo.get_card_by_exact_name(partner)
        if not partner_card:
            print(f"[red]Partner '{partner}' not found in database.[/red]")
            raise typer.Exit(code=1)

    analysis = analyze_commander(
        commander_card,
        partner_card=partner_card,
        archetype=archetype,
        theme=theme,
        power_level=power_level,
        philosophy=philosophy,
        meta=meta,
    )

    if not no_write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(output_path, analysis)
        if not json_output:
            print(f"[green]Analysis written to {output_path}[/green]")

    if json_output:
        print_json(analysis)
    elif no_write:
        print_json(analysis)
    else:
        print(f"[bold blue]Commander: {analysis['commander']}[/bold blue]")
        if analysis.get("partner"):
            print(f"[blue]Partner: {analysis['partner']}[/blue]")
        print(f"Colors: {''.join(analysis['combined_color_identity'])}")
        print(f"Best archetype: {analysis['best_archetype']}")
        print(f"Primary pattern: {analysis['engine_profile']['primary_pattern']}")
        print(f"Engine: {analysis['engine_profile']['engine_action']}")
        if analysis.get("forced_archetype_warning"):
            print(f"[yellow]{analysis['forced_archetype_warning']}[/yellow]")



@app.command()
def themes(
    json_output: bool = typer.Option(False, "--json-output", help="Output themes as JSON")
):
    """List available deck themes."""
    themes_list = list_themes()

    if json_output:
        print_json(themes_list)
    else:
        print("[bold blue]Available themes:[/bold blue]")
        for theme in themes_list:
            print(f"- {theme}")



@app.command()
def theme_info(
    theme: str,
    json_output: bool = typer.Option(False, "--json-output", help="Output theme info as JSON")
):
    """Show a theme profile and its packages."""
    profile = get_theme_profile(theme)

    if not profile:
        print(f"[red]Unknown theme: {theme}[/red]")
        raise typer.Exit(code=1)

    if json_output:
        print_json(profile)
    else:
        print(f"[bold blue]Theme: {theme}[/bold blue]")
        print(profile.get("description", ""))

        packages = profile.get("packages", {})
        print("\n[bold]Packages:[/bold]")
        for package_name, package_data in packages.items():
            ideal = package_data.get("ideal")
            minimum = package_data.get("min")
            print(f"- {package_name}: min {minimum}, ideal {ideal}")



@app.command()
def category_counts(
    commander: str = typer.Option(..., "--commander", help="Commander card name"),
    partner: Optional[str] = typer.Option(None, "--partner", help="Partner commander card name"),
    archetype: str = typer.Option(..., "--archetype", help="Deck archetype (e.g. aristocrats, voltron, combo)"),
    power_level: Optional[float] = typer.Option(None, "--power-level", help="Numeric power level 1-10"),
    bracket: Optional[str] = typer.Option(None, "--bracket", help="Bracket label T1/T2/T3/T4"),
    philosophy: str = typer.Option("balanced", "--philosophy", help="Deckbuilding philosophy"),
    meta: str = typer.Option("universal", "--meta", help="Playgroup meta environment"),
    projected_avg_mv: Optional[float] = typer.Option(None, "--projected-average-mv", help="Projected average nonland MV"),
    analysis: Optional[Path] = typer.Option(None, "--analysis", help="Path to commander_analysis.json for richer commander scoring"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
    table: bool = typer.Option(
        False, "--table",
        help="Print a flat, one-row-per-category plain-text table (need_score, "
             "recommended_range, compressed_target_count, priority) instead of the "
             "grouped rich report or raw JSON. Pipe-friendly: no box-drawing chars, "
             "no repeated headers, no embedded notes.",
    ),
):
    """Recommend category counts for a Commander deck."""
    db_path = str(SQLITE_PATH) if SQLITE_PATH.exists() else None

    result = calculate_category_counts(
        commander,
        archetype,
        partner_name=partner,
        power_level=power_level,
        bracket=bracket,
        philosophy=philosophy,
        meta=meta,
        projected_avg_mv=projected_avg_mv,
        db_path=db_path,
        analysis_path=str(analysis) if analysis else None,
    )

    if table:
        print(format_table(result))
    elif json_output:
        print_json(result)
    else:
        print(format_human_readable(result))



@app.command()
def analyze_card(
    card_name: str = typer.Argument(..., help="Card to analyze"),
    json_output: bool = typer.Option(False, "--json-output", help="Output the full profile as JSON"),
):
    """Universal (deck-independent) functional analysis of a card, with full provenance.

    Shows the evidence-first profile from the new analyzer: detected signals (each with the
    rule and text that triggered it), scope/symmetry, archetype support as ordinal bands, and
    warnings. No scores, no include/cut verdict — that judgment is the agent's.
    """
    require_database(SQLITE_PATH, json_output)
    repo = CardRepository(str(SQLITE_PATH))
    card = repo.get_card_by_exact_name(card_name)
    if not card:
        sugg = [s["name"] for s in repo.suggest_similar_names(card_name, limit=3)]
        print(f"[red]Card '{card_name}' not found.[/red]" + (f" Did you mean: {', '.join(sugg)}?" if sugg else ""))
        raise typer.Exit(code=1)

    from mtgcli.analyzer.analyze import analyze_card as _analyze
    result = _analyze(card)

    if json_output:
        print_json(result)
    else:
        print(f"[bold blue]{result['name']}[/bold blue] [dim]({result['schema_version']})[/dim]")
        if result.get("dominant_symmetry"):
            print(f"  symmetry: {result['dominant_symmetry']}")
        if result["archetype_support"]:
            print("  [bold]archetype support:[/bold]")
            for a in result["archetype_support"]:
                ev = a["defining"] or a["supporting"] or a["weak"]
                print(f"    {a['band']:<10} {a['archetype']} [dim]({', '.join(ev[:3])})[/dim]")
        if result["signals"]:
            print("  [bold]signals:[/bold]")
            for s in result["signals"]:
                print(f"    {s['id']} [dim]<- '{s['trace']['matched_text']}'[/dim]")
        if result["tags"]:
            print(f"  [bold]tags:[/bold] {', '.join(result['tags'].keys())}")
        for w in result["warnings"]:
            print(f"  [yellow]! {w}[/yellow]")


