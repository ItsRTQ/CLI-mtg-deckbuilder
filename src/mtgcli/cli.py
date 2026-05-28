import typer
import json
from rich import print
from typing import Optional, List
from pathlib import Path
from mtgcli.config import PROJECT_ROOT, RAW_CARDS_PATH, SQLITE_PATH, SEED_DATA_DIR
from mtgcli.data.download_cards import download_default_cards
from mtgcli.data.build_sqlite import build_sqlite_database
from mtgcli.cards.repository import CardRepository
from mtgcli.cards.search import search_commander_legal_cards, search_by_tags
from mtgcli.utils.json_io import read_json, write_json
from mtgcli.export.moxfield import export_deck_to_moxfield
from mtgcli.validator.deck_validator import validate_commander_deck
from mtgcli.deckbuilder.enrich_deck import enrich_deck
from mtgcli.deckbuilder.basic_lands import suggest_basic_lands
from mtgcli.deckbuilder.deck_check import check_deck_quality
from mtgcli.deckbuilder.suggestion_scorer import score_suggestion
from mtgcli.deckbuilder.theme_profiles import list_themes, list_packages, get_theme_profile
from mtgcli.deckbuilder.package_search import search_theme_package
from mtgcli.deckbuilder.package_scorer import score_package_card

app = typer.Typer(help="Local MTG Commander deckbuilding CLI.")


@app.command()
def status():
    """Check the project status and paths."""
    print(f"[bold blue]MTG Deckbuilder Status[/bold blue]")
    print(f"Project Root: [green]{PROJECT_ROOT}[/green]")


@app.command()
def init_data():
    """Initialize or update the MTG card database."""
    if not RAW_CARDS_PATH.exists():
        print("[yellow]Downloading Scryfall bulk data...[/yellow]")
        print("[bold red]Disclaimer: This download is approximately 2GB and will take a few minutes depending on your connection.[/bold red]")
        path = download_default_cards()
        print(f"[green]Downloaded cards to {path}[/green]")
    else:
        print(f"[green]Raw card data already exists at {RAW_CARDS_PATH}[/green]")

    print("[yellow]Building SQLite database...[/yellow]")
    db_path = build_sqlite_database()
    print(f"[green]Built SQLite database at {db_path}[/green]")


@app.command()
def card(
    name: str,
    json_output: bool = typer.Option(False, "--json-output", help="Output card data as JSON")
):
    """Lookup a card by exact name."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    card_data = repo.get_card_by_exact_name(name)

    if card_data:
        if json_output:
            print(json.dumps(card_data, indent=2))
        else:
            print(f"[bold blue]{card_data['name']}[/bold blue] {card_data['mana_cost']}")
            print(f"[italic]{card_data['type_line']}[/italic] ({card_data['rarity']})")
            print("-" * 20)
            print(card_data["oracle_text"])
            if card_data["usd_price"]:
                print(f"[green]Price: ${card_data['usd_price']}[/green]")
    else:
        print(f"[red]No exact match found for '{name}'.[/red]")
        suggestions = repo.search_cards_by_name(name, limit=5)
        if suggestions:
            print("[yellow]Did you mean:[/yellow]")
            for s in suggestions:
                print(f" - {s['name']}")


@app.command()
def search(
    query: str,
    colors: Optional[str] = typer.Option(None, "--colors", help="Filter by color identity (e.g. RG)"),
    limit: int = typer.Option(20, "--limit", help="Limit number of results"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON")
):
    """Search for commander-legal cards."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    results = search_commander_legal_cards(query=query, colors=colors, limit=limit)

    if not results:
        print(f"[yellow]No cards found matching '{query}'[/yellow]")
        return

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print(f"[bold blue]Found {len(results)} cards:[/bold blue]")
        for card in results:
            print(f"- {card['name']} {card['mana_cost']} | {card['type_line']} | {card['set_code']} #{card['collector_number']}")


@app.command()
def search_tags(
    tags: List[str],
    colors: Optional[str] = typer.Option(None, "--colors", help="Filter by color identity (e.g. RG)"),
    limit: int = typer.Option(20, "--limit", help="Limit number of results"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON")
):
    """Search for cards by functional tags (e.g. ramp, card_draw)."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    results = search_by_tags(tags=tags, colors=colors, limit=limit)

    if not results:
        print(f"[yellow]No cards found matching tags: {', '.join(tags)}[/yellow]")
        return

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print(f"[bold blue]Found {len(results)} cards for tags {', '.join(tags)}:[/bold blue]")
        for card in results:
            print(f"- {card['name']} {card['mana_cost']} | {card['type_line']} | {card['set_code']} #{card['collector_number']}")


@app.command()
def suggest(
    commander: str = typer.Option(..., "--commander", help="Name of the commander"),
    role: str = typer.Option(..., "--role", help="Role to suggest cards for (e.g. ramp, synergy)"),
    theme: Optional[str] = typer.Option(None, "--theme", help="Optional deck theme, e.g. goblins, equipment, modified_creatures"),
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
                c.get("mana_value") or 99,
                c.get("name", "")
            )
        )
        final_results = scored_results[:limit]
    else:
        results = search_by_tags(
            tags=tags, 
            colors=colors, 
            limit=limit * 2, # Get more results to allow for better sorting after scoring
            max_price=max_price,
            exclude_names=list(exclude_names),
            dedupe=dedupe
        )

        if not results:
            print(f"[yellow]No suggestions found for role '{role}' in colors '{colors}'[/yellow]")
            return

        # Score and enrich results
        scored_results = []
        for card in results:
            score_data = score_suggestion(card, role, theme)
            card["suggestion_score"] = score_data["score"]
            card["matched_tags"] = score_data["matched_tags"]
            card["reason_hint"] = score_data["reason_hint"]
            scored_results.append(card)

        # Sort by score descending, then mana_value ascending
        scored_results.sort(key=lambda x: (-x["suggestion_score"], x["mana_value"]))
        final_results = scored_results[:limit]

    if json_output:
        # Define output fields for clean JSON
        output_fields = [
            "name", "mana_cost", "mana_value", "type_line", "oracle_text",
            "color_identity", "set_code", "collector_number", "usd_price",
            "suggestion_score", "matched_tags", "reason_hint"
        ]
        json_results = []
        for card in final_results:
            json_results.append({k: card.get(k) for k in output_fields})
        print(json.dumps(json_results, indent=2))
    else:
        title = f"Suggestions for {commander} ({role})"
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
def validate(
    commander: str = typer.Option(..., "--commander", help="Name of the commander"),
    deck_path: Path = typer.Option(..., "--deck", help="Path to the deck JSON file"),
    json_output: bool = typer.Option(False, "--json-output", help="Output validation report as JSON")
):
    """Validate a Commander deck for size, legality, and color identity."""
    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    try:
        repo = CardRepository(str(SQLITE_PATH))
        deck_entries = read_json(deck_path)
        report = validate_commander_deck(commander, deck_entries, repo)
        
        # Save report
        report_path = Path("output/validation_report.json")
        write_json(report_path, report)
        
        if json_output:
            print(json.dumps(report, indent=2))
        else:
            if report["valid"]:
                print("[bold green]Deck is VALID![/bold green]")
            else:
                print("[bold red]Deck is INVALID![/bold red]")
                print(f"[yellow]Found {len(report['errors'])} errors. See {report_path} for details.[/yellow]")
                for error in report["errors"][:5]:  # Show first 5 errors
                    msg = error.get('message', 'Unknown error')
                    print(f"- [red]{error['type']}[/red]: {msg}")
                if len(report["errors"]) > 5:
                    print(f"... and {len(report['errors']) - 5} more.")
                    
    except Exception as e:
        print(f"[red]Failed to validate deck: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def enrich(
    input_path: Path = typer.Argument(..., help="Path to deck JSON file"),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file path")
):
    """Enrich a deck JSON with full card data from the database."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if not input_path.exists():
        print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    try:
        final_output = enrich_deck(input_path, SQLITE_PATH, output_path)
        print(f"[green]Enriched deck saved to {final_output}[/green]")
    except Exception as e:
        print(f"[red]Failed to enrich deck: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def export(
    input_path: Path = typer.Argument(..., help="Path to deck JSON file"),
    output_path: Path = typer.Option(Path("output/deck.moxfield.txt"), "--output", "-o", help="Output text file path")
):
    """Export a deck JSON to Moxfield text format."""
    if not input_path.exists():
        print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    try:
        deck_cards = read_json(input_path)
        export_deck_to_moxfield(deck_cards, output_path)
        print(f"[green]Exported deck to {output_path}[/green]")
    except Exception as e:
        print(f"[red]Failed to export deck: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def suggest_lands(
    commander: str = typer.Option(..., "--commander", help="Name of the commander"),
    count: int = typer.Option(37, "--count", help="Number of lands to suggest"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON")
):
    """Suggest basic lands based on commander color identity."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    commander_card = repo.get_card_by_exact_name(commander)
    
    if not commander_card:
        print(f"[red]Commander '{commander}' not found.[/red]")
        raise typer.Exit(code=1)

    colors = commander_card.get("color_identity", [])
    lands = suggest_basic_lands(colors, count)

    if json_output:
        print(json.dumps(lands, indent=2))
    else:
        print(f"[bold blue]Land suggestions for {commander} ({''.join(colors)}):[/bold blue]")
        for land in lands:
            print(f"- {land['quantity']}x {land['name']}")


@app.command()
def deck_check(
    commander: str = typer.Option(..., "--commander", help="Name of the commander"),
    deck_path: Path = typer.Option(..., "--deck", help="Path to the deck JSON file"),
    theme: Optional[str] = typer.Option(None, "--theme", help="Optional theme profile for package validation"),
    json_output: bool = typer.Option(False, "--json-output", help="Output report as JSON")
):
    """Check deck quality: land count, ramp, draw, removal, and thematic packages."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    try:
        repo = CardRepository(str(SQLITE_PATH))
        deck_entries = read_json(deck_path)
        
        # Hydrate deck cards for analysis
        deck_cards = []
        for entry in deck_entries:
            name = entry.get("name")
            if not name: continue
            card = repo.get_card_by_exact_match(name, entry.get("set_code"), entry.get("collector_number"))
            if card:
                card["quantity"] = entry.get("quantity", 1)
                deck_cards.append(card)
        
        report = check_deck_quality(deck_cards, theme=theme)
        
        if json_output:
            print(json.dumps(report, indent=2))
        else:
            print(f"[bold blue]Deck Quality Report for {commander}:[/bold blue]")
            if theme:
                print(f"Theme: [bold green]{theme}[/bold green]")
                
            print("\n[bold]Core Stats:[/bold]")
            for cat, count in report["stats"].items():
                print(f"- {cat.replace('_', ' ').title()}: {count}")
            
            if "theme_check" in report:
                print("\n[bold]Theme Package Analysis:[/bold]")
                tc = report["theme_check"]
                for pkg, data in tc["package_counts"].items():
                    print(f"- {pkg}: {data['count']} (min {data['min']}, ideal {data['ideal']})")

            if report["warnings"]:
                print("\n[bold yellow]Warnings:[/bold yellow]")
                for warning in report["warnings"]:
                    print(f"- [yellow]{warning}[/yellow]")
            else:
                print("\n[bold green]No major issues found![/bold green]")
                
    except Exception as e:
        print(f"[red]Failed to check deck: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def themes(
    json_output: bool = typer.Option(False, "--json-output", help="Output themes as JSON")
):
    """List available deck themes."""
    themes_list = list_themes()

    if json_output:
        print(json.dumps(themes_list, indent=2))
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
        print(json.dumps(profile, indent=2))
    else:
        print(f"[bold blue]Theme: {theme}[/bold blue]")
        print(profile.get("description", ""))

        packages = profile.get("packages", {})
        print("\n[bold]Packages:[/bold]")
        for package_name, package_data in packages.items():
            ideal = package_data.get("ideal")
            minimum = package_data.get("min")
            print(f"- {package_name}: min {minimum}, ideal {ideal}")


if __name__ == "__main__":
    app()
