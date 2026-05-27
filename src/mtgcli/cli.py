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
    limit: int = typer.Option(20, "--limit", help="Limit number of results"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON")
):
    """Suggest cards for a commander based on a specific role."""
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

    tags = role_defs[role].get("tags", [])
    colors = "".join(commander_card.get("color_identity", []))
    
    results = search_by_tags(tags=tags, colors=colors, limit=limit)

    if not results:
        print(f"[yellow]No suggestions found for role '{role}' in colors '{colors}'[/yellow]")
        return

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print(f"[bold blue]Suggestions for {commander} ({role}):[/bold blue]")
        for card in results:
            print(f"- {card['name']} {card['mana_cost']} | {card['type_line']}")


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
        deck_cards = read_json(deck_path)
        report = validate_commander_deck(commander, deck_cards)
        
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


if __name__ == "__main__":
    app()
