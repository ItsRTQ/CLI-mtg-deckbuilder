import typer
import json
from rich import print
from typing import Optional, List
from pathlib import Path
from mtgcli.config import PROJECT_ROOT, RAW_CARDS_PATH, SQLITE_PATH, SEED_DATA_DIR
from mtgcli.explore.client import build_explore_url, fetch_commander_page
from mtgcli.explore.cleaner import extract_target_cards_from_html
from mtgcli.utils.temp_cleaner import clean_output_files
from mtgcli.export.final_builds import (
    normalize_bracket, next_final_build_name, create_final_build_directory,
    save_final_build_decklist, save_final_build_explanation,
    build_minimal_explanation, deck_entries_to_moxfield_text, sanitize_filename_part
)
from mtgcli.config import FINAL_BUILDS_DIR
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
from mtgcli.deckbuilder.pricing import resolve_card_price, build_budget_summary
from mtgcli.deckbuilder.land_filler import fill_deck_with_lands
from mtgcli.utils.deck_io import normalize_deck_input
from mtgcli.utils.decklist_parser import parse_decklist_text

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

    print("[yellow]Building SQLite database (aggregating prices across all printings)...[/yellow]")
    result = build_sqlite_database()
    print(f"[green]Built SQLite database at {result['path']}[/green]")
    print(f"[green]  {result['unique_card_identities']} unique cards from {result['cards_processed']} printings[/green]")
    print(f"[green]  {result['cards_with_known_usd_price']} cards with known USD price, {result['cards_with_unknown_price']} unknown[/green]")


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
            print(f"[italic]{card_data['type_line']}[/italic]")
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
            print(f"- {card['name']} {card['mana_cost']} | {card['type_line']}")


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
            print(f"- {card['name']} {card['mana_cost']} | {card['type_line']}")


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
        # For roles with a max mana value (e.g. cheap), pre-filter in SQL
        role_max_mv = role_defs[role].get("target_mana_value_max")

        results = search_by_tags(
            tags=tags,
            colors=colors,
            limit=limit * 4,
            max_price=max_price,
            max_mana_value=role_max_mv,
            exclude_names=list(exclude_names),
            dedupe=dedupe
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

        # Sort by score descending, then mana_value ascending
        scored_results.sort(key=lambda x: (-x["suggestion_score"], x["mana_value"]))
        final_results = scored_results[:limit]

    if json_output:
        # Define output fields for clean JSON
        output_fields = [
            "name", "mana_cost", "mana_value", "type_line", "oracle_text",
            "colors", "color_identity", "commander_legal", "can_be_commander",
            "usd_price", "suggestion_score", "matched_tags", "reason_hint"
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
    partner: Optional[str] = typer.Option(None, "--partner", help="Name of the partner commander (for two-commander decks)"),
    deck_path: Path = typer.Option(..., "--deck", help="Path to the deck JSON file"),
    json_output: bool = typer.Option(False, "--json-output", help="Output validation report as JSON")
):
    """Validate a Commander deck for size, legality, and color identity."""
    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    try:
        repo = CardRepository(str(SQLITE_PATH))
        raw = read_json(deck_path)
        normalized = normalize_deck_input(raw)
        deck_entries = normalized["main_deck"]
        report = validate_commander_deck(commander, deck_entries, repo, partner_name=partner)
        
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
def deck_write(
    input_path: Path = typer.Option(..., "--input", help="Path to plain text decklist file"),
    output_path: Path = typer.Option(Path("output/deck.json"), "--output", help="Output JSON path"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing output file"),
    json_output: bool = typer.Option(False, "--json-output", help="Output result as JSON"),
):
    """Convert a plain text decklist to deck JSON."""
    if not input_path.exists():
        print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    if output_path.exists() and not force:
        print(f"[red]Output already exists: {output_path}. Use --force to overwrite.[/red]")
        raise typer.Exit(code=1)

    text = input_path.read_text(encoding="utf-8")
    entries = parse_decklist_text(text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, entries)

    if json_output:
        print(json.dumps({
            "written": True,
            "output": str(output_path),
            "entries": len(entries),
            "total_cards": sum(e.get("quantity", 1) for e in entries),
        }))
    else:
        total = sum(e.get("quantity", 1) for e in entries)
        print(f"[green]Wrote {len(entries)} entries ({total} cards) to {output_path}[/green]")


@app.command()
def deck_fill_lands(
    deck_path: Path = typer.Option(..., "--deck", help="Path to deck JSON file"),
    commander: str = typer.Option(..., "--commander", help="Commander name"),
    partner: Optional[str] = typer.Option(None, "--partner", help="Partner commander name"),
    output_path: Optional[Path] = typer.Option(None, "--output", help="Output JSON path (default: same as --deck)"),
    target_main: Optional[int] = typer.Option(None, "--target-main", help="Target main deck size (default: 99 or 98 for partner)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be added without writing"),
    force: bool = typer.Option(False, "--force", help="Allow overwriting the output file"),
    json_output: bool = typer.Option(False, "--json-output", help="Output result as JSON"),
):
    """Fill a partial deck with basic lands to reach the target main deck size."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    out_path = output_path or deck_path
    if out_path.exists() and not dry_run and not force:
        print(f"[red]Output already exists: {out_path}. Use --force to overwrite.[/red]")
        raise typer.Exit(code=1)

    # Resolve commander color identity
    repo = CardRepository(str(SQLITE_PATH))
    cmd_card = repo.get_card_by_exact_name(commander)
    if not cmd_card:
        print(f"[red]Commander '{commander}' not found in database.[/red]")
        raise typer.Exit(code=1)

    color_identity = list(cmd_card.get("color_identity", []))

    if partner:
        partner_card = repo.get_card_by_exact_name(partner)
        if not partner_card:
            print(f"[red]Partner '{partner}' not found in database.[/red]")
            raise typer.Exit(code=1)
        for c in partner_card.get("color_identity", []):
            if c not in color_identity:
                color_identity.append(c)

    # Determine target main deck size
    commander_slots = 2 if partner else 1
    if target_main is not None:
        target = target_main
    else:
        target = 100 - commander_slots  # 99 or 98

    # Load and normalize deck
    raw = read_json(deck_path)
    deck_entries = normalize_deck_input(raw)["main_deck"]

    result = fill_deck_with_lands(deck_entries, color_identity, target)

    if not result["filled"]:
        if json_output:
            print(json.dumps({"filled": False, "error": result["error"]}))
        else:
            print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)

    lands_added = result["lands_added"]
    current = result["current_main_deck_size"]
    remaining = result.get("remaining_slots", 0)

    if dry_run:
        payload = {
            "deck": str(deck_path),
            "output": str(out_path),
            "commander": commander,
            "partner": partner,
            "target_main_deck_size": target,
            "current_main_deck_size": current,
            "remaining_slots": remaining,
            "lands_added": lands_added,
            "written": False,
            "dry_run": True,
        }
        if json_output:
            print(json.dumps(payload))
        else:
            print(f"[bold blue]Dry run — no files written[/bold blue]")
            print(f"  Deck: {current} / {target} main deck cards")
            print(f"  Would add {remaining} basic land(s):")
            for name, qty in lands_added.items():
                print(f"    - {qty} {name}")
        return

    # Write updated deck
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, result["updated_deck"])

    payload = {
        "deck": str(deck_path),
        "output": str(out_path),
        "commander": commander,
        "partner": partner,
        "target_main_deck_size": target,
        "current_main_deck_size": current,
        "remaining_slots": remaining,
        "lands_added": lands_added,
        "written": True,
    }

    if json_output:
        print(json.dumps(payload))
    else:
        if remaining == 0:
            note = result.get("note", "")
            print(f"[green]{note or 'Deck is already at target size.'}[/green]")
        else:
            print(f"[bold blue]Deck has {current} / {target} main deck cards.[/bold blue]")
            print(f"Added {remaining} basic land(s):")
            for name, qty in lands_added.items():
                print(f"  - {qty} {name}")
            print(f"[green]Wrote updated deck to {out_path}[/green]")


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
        raw = read_json(input_path)
        deck_cards = normalize_deck_input(raw)["main_deck"]
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
        raw = read_json(deck_path)
        normalized = normalize_deck_input(raw)
        deck_entries = normalized["main_deck"]

        # Hydrate deck cards for analysis
        deck_cards = []
        for entry in deck_entries:
            name = entry.get("name")
            if not name: continue
            card = repo.get_card_by_exact_name(name)
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
            entry: dict = {"name": name}
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
            "commander": commander,
            "source_url": url,
            "high_synergy": hydrate(cards["high_synergy"]),
            "top_cards": hydrate(cards["top_cards"]),
            "note": NOTE,
        }
        print(json.dumps(output, indent=2))
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
def temp_clean(
    output_dir: Path = typer.Option(Path("output"), "--output-dir", help="Output directory to clean"),
    full: bool = typer.Option(False, "--full", help="Delete all files, including final deck artifacts"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation for --full"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List what would be deleted without deleting"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON"),
):
    """Clean temporary and/or generated files from the output directory."""
    if not output_dir.exists():
        msg = f"Output directory '{output_dir}' does not exist."
        if json_output:
            print(json.dumps({"error": msg, "mode": "full" if full else "normal", "dry_run": dry_run,
                              "deleted_count": 0, "matched_count": 0, "preserved_files": [], "files": []}))
        else:
            print(f"[yellow]{msg}[/yellow]")
        return

    if full and not dry_run and not yes:
        import sys
        print(f"[bold yellow]WARNING:[/bold yellow] Full clean will delete all files inside {output_dir}/ except .gitkeep.")
        print("This includes final deck artifacts like deck.json and deck.moxfield.txt.")
        if not sys.stdin.isatty():
            print("[red]Non-interactive environment. Rerun with --yes to confirm.[/red]")
            raise typer.Exit(code=1)
        confirm = typer.prompt("Continue? [y/N]", default="N")
        if confirm.strip().lower() != "y":
            print("[yellow]Cancelled.[/yellow]")
            return

    report = clean_output_files(output_dir=output_dir, full=full, dry_run=dry_run)

    if json_output:
        print(json.dumps(report, indent=2))
        return

    mode_label = "full clean" if full else "temp files"
    action = "Dry run:" if dry_run else ""
    count = report["matched_count"] if dry_run else report["deleted_count"]
    verb = "would be deleted" if dry_run else "deleted"

    if count == 0:
        print(f"[green]No files to clean in {output_dir}/[/green]")
        return

    if full:
        if dry_run:
            print(f"[yellow]Dry run: full clean would delete {count} files from {output_dir}/[/yellow]")
        else:
            print(f"[green]Full clean {verb} {count} files from {output_dir}/[/green]")
        if report["preserved_files"]:
            print("[bold]Preserved:[/bold]")
            for f in report["preserved_files"]:
                print(f"  - {f}")
        if dry_run:
            print("[bold]Would delete:[/bold]")
            for f in report["files"]:
                print(f"  - {f}")
    else:
        if dry_run:
            print(f"[yellow]Dry run: {count} temp files would be deleted from {output_dir}/[/yellow]")
        else:
            print(f"[green]{count} temp files deleted from {output_dir}/[/green]")
        for f in report["files"]:
            print(f"  - {f}")


@app.command()
def final_build(
    deck_path: Path = typer.Option(..., "--deck", help="Path to deck JSON file"),
    commander: str = typer.Option(..., "--commander", help="Commander name"),
    partner: Optional[str] = typer.Option(None, "--partner", help="Partner commander name (two-commander decks)"),
    theme: str = typer.Option(..., "--theme", help="Deck theme or archetype"),
    bracket: Optional[str] = typer.Option(None, "--bracket", help="Power bracket: T1, T2, T3, or T4"),
    power_level: Optional[str] = typer.Option(None, "--power-level", help="Power level label (e.g. casual, competitive)"),
    explanation: Optional[Path] = typer.Option(None, "--explanation", help="Path to explanation markdown file"),
    json_output: bool = typer.Option(False, "--json-output", help="Output results as JSON"),
):
    """Validate a deck and save as a versioned final build folder in final-builds/."""
    _fail_payload = {
        "validated": False, "saved": False,
        "build_name": None, "build_dir": None,
        "decklist_path": None, "explanation_path": None,
        "errors": [],
    }

    if not deck_path.exists():
        msg = f"Deck file not found: {deck_path}"
        if json_output:
            _fail_payload["errors"] = [{"message": msg}]
            print(json.dumps(_fail_payload))
        else:
            print(f"[red]{msg}[/red]")
        raise typer.Exit(code=1)

    raw = read_json(deck_path)
    deck_entries = normalize_deck_input(raw)["main_deck"]
    repo = CardRepository(str(SQLITE_PATH))
    report = validate_commander_deck(commander, deck_entries, repo, partner_name=partner)

    if not report["valid"]:
        if json_output:
            _fail_payload["errors"] = report.get("errors", [])
            print(json.dumps(_fail_payload))
        else:
            print("[bold red]Validation failed. Final build was not saved.[/bold red]")
            for err in report.get("errors", [])[:5]:
                print(f"  - [red]{err['type']}[/red]: {err.get('message', '')}")
        raise typer.Exit(code=1)

    resolved_bracket = normalize_bracket(power_level=power_level, bracket=bracket)

    # Determine explanation content
    explanation_text: str
    if explanation and explanation.exists():
        explanation_text = explanation.read_text(encoding="utf-8")
    elif explanation and not explanation.exists():
        print(f"[yellow]Warning: explanation file not found at {explanation}, generating stub.[/yellow]")
        explanation_text = build_minimal_explanation(commander, theme, resolved_bracket, partner)
    else:
        auto_path = Path("output/deck_explanation.md")
        if auto_path.exists():
            explanation_text = auto_path.read_text(encoding="utf-8")
        else:
            explanation_text = build_minimal_explanation(commander, theme, resolved_bracket, partner)

    # Create versioned build folder and save files
    build_name = next_final_build_name(commander, theme, resolved_bracket, FINAL_BUILDS_DIR)
    build_dir = create_final_build_directory(build_name, FINAL_BUILDS_DIR)
    decklist_text = deck_entries_to_moxfield_text(deck_entries)
    decklist_path = save_final_build_decklist(decklist_text, build_dir, build_name)
    explanation_path = save_final_build_explanation(explanation_text, build_dir, build_name)

    version = build_name.rsplit("-", 1)[-1]

    if json_output:
        print(json.dumps({
            "validated": True,
            "saved": True,
            "build_name": build_name,
            "build_dir": str(build_dir),
            "decklist_path": str(decklist_path),
            "explanation_path": str(explanation_path),
            "commander": commander,
            "theme": theme,
            "bracket": resolved_bracket,
            "version": version,
        }))
    else:
        print("[bold green]Deck validated successfully.[/bold green]")
        print(f"Final build folder created: [bold]{build_dir}[/bold]")
        print(f"Decklist saved to: [bold]{decklist_path}[/bold]")
        print(f"Explanation saved to: [bold]{explanation_path}[/bold]")


@app.command()
def price(
    name: str,
    json_output: bool = typer.Option(False, "--json-output", help="Output price data as JSON"),
):
    """Look up local Scryfall price data for a card."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    card_data = repo.get_card_by_exact_name(name)

    if not card_data:
        print(f"[red]Card '{name}' not found.[/red]")
        raise typer.Exit(code=1)

    result = {
        "name": card_data["name"],
        "usd_price": card_data.get("usd_price"),
        "usd_foil_price": card_data.get("usd_foil_price"),
        "eur_price": card_data.get("eur_price"),
        "tix_price": card_data.get("tix_price"),
        "price_status": card_data.get("price_status", "unknown"),
        "price_source": card_data.get("price_source", "scryfall"),
    }

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"[bold blue]{result['name']}[/bold blue]")
        if result["usd_price"] is not None:
            print(f"  USD:     [green]${result['usd_price']}[/green]")
        if result["usd_foil_price"] is not None:
            print(f"  USD Foil: [green]${result['usd_foil_price']}[/green]")
        if result["eur_price"] is not None:
            print(f"  EUR:     [green]€{result['eur_price']}[/green]")
        if result["tix_price"] is not None:
            print(f"  TIX:     [green]{result['tix_price']}[/green]")
        if result["price_status"] == "unknown":
            print("  [yellow]Price: unknown[/yellow]")


@app.command()
def cards(
    names: List[str] = typer.Argument(..., help="Card names to look up"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Batch card lookup by exact name."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    results = []
    for name in names:
        card_data = repo.get_card_by_exact_name(name)
        if card_data:
            card_data["found"] = True
            results.append(card_data)
        else:
            results.append({"name": name, "found": False})

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            if r.get("found"):
                print(f"[bold blue]{r['name']}[/bold blue] {r.get('mana_cost', '')} | {r.get('type_line', '')}")
            else:
                print(f"[red]Not found: {r['name']}[/red]")


@app.command()
def cards_batch(
    input_path: Path = typer.Argument(..., help="Path to deck JSON file"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Look up all cards in a deck JSON file."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if not input_path.exists():
        print(f"[red]File not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    try:
        raw = read_json(input_path)
        deck_entries = normalize_deck_input(raw)["main_deck"]
    except Exception as e:
        print(f"[red]Failed to read deck file: {e}[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    results = []
    for entry in deck_entries:
        name = entry.get("name") if isinstance(entry, dict) else str(entry)
        if not name:
            continue
        card_data = repo.get_card_by_exact_name(name)
        if card_data:
            card_data["found"] = True
            card_data["quantity"] = entry.get("quantity", 1) if isinstance(entry, dict) else 1
            results.append(card_data)
        else:
            results.append({"name": name, "found": False, "quantity": entry.get("quantity", 1) if isinstance(entry, dict) else 1})

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            found_str = "" if r.get("found") else " [red](not found)[/red]"
            print(f"- {r.get('quantity', 1)}x {r['name']}{found_str}")


@app.command()
def prices(
    names: List[str] = typer.Argument(..., help="Card names to look up prices for"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Batch price lookup by card name."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    results = []
    for name in names:
        card_data = repo.get_card_by_exact_name(name)
        if card_data:
            results.append({
                "name": card_data["name"],
                "found": True,
                "usd_price": card_data.get("usd_price"),
                "usd_foil_price": card_data.get("usd_foil_price"),
                "eur_price": card_data.get("eur_price"),
                "tix_price": card_data.get("tix_price"),
                "price_status": card_data.get("price_status", "unknown"),
                "price_source": card_data.get("price_source", "scryfall"),
            })
        else:
            results.append({"name": name, "found": False, "usd_price": None, "price_status": "not_found"})

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            if not r.get("found"):
                print(f"[red]{r['name']}: not found[/red]")
            elif r["usd_price"] is not None:
                print(f"{r['name']}: [green]${r['usd_price']}[/green] USD ({r['price_status']})")
            else:
                print(f"{r['name']}: [yellow]price unknown[/yellow]")


@app.command()
def prices_batch(
    input_path: Path = typer.Argument(..., help="Path to deck JSON file"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Look up prices for all cards in a deck JSON file."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if not input_path.exists():
        print(f"[red]File not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    try:
        raw = read_json(input_path)
        deck_entries = normalize_deck_input(raw)["main_deck"]
    except Exception as e:
        print(f"[red]Failed to read deck file: {e}[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    results = []
    for entry in deck_entries:
        name = entry.get("name") if isinstance(entry, dict) else str(entry)
        if not name:
            continue
        card_data = repo.get_card_by_exact_name(name)
        if card_data:
            results.append({
                "name": card_data["name"],
                "found": True,
                "quantity": entry.get("quantity", 1) if isinstance(entry, dict) else 1,
                "usd_price": card_data.get("usd_price"),
                "eur_price": card_data.get("eur_price"),
                "price_status": card_data.get("price_status", "unknown"),
                "price_source": card_data.get("price_source", "scryfall"),
            })
        else:
            results.append({
                "name": name,
                "found": False,
                "quantity": entry.get("quantity", 1) if isinstance(entry, dict) else 1,
                "usd_price": None,
                "price_status": "not_found",
            })

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            qty = r.get("quantity", 1)
            if not r.get("found"):
                print(f"[red]{qty}x {r['name']}: not found[/red]")
            elif r["usd_price"] is not None:
                print(f"{qty}x {r['name']}: [green]${r['usd_price']}[/green]")
            else:
                print(f"{qty}x {r['name']}: [yellow]unknown price[/yellow]")


@app.command()
def budget(
    deck_path: Path = typer.Argument(..., help="Path to deck JSON file"),
    budget_limit: Optional[float] = typer.Option(None, "--budget", help="Budget maximum in USD (e.g. 500)"),
    overage: float = typer.Option(10.0, "--overage", help="Allowed overage percent above budget limit (default 10)"),
    json_output: bool = typer.Option(False, "--json-output", help="Output budget summary as JSON"),
    strict: bool = typer.Option(False, "--strict", help="Fail if any card has unknown price"),
):
    """Summarize deck budget using local Scryfall price data."""
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    deck_entries = normalize_deck_input(read_json(deck_path))["main_deck"]

    hydrated = []
    for entry in deck_entries:
        name = entry.get("name")
        if not name:
            continue
        card_data = repo.get_card_by_exact_name(name)
        if card_data:
            card_data = dict(card_data)
            card_data["quantity"] = entry.get("quantity", 1)
            hydrated.append(card_data)
        else:
            hydrated.append({"name": name, "quantity": entry.get("quantity", 1), "usd_price": None})

    summary = build_budget_summary(hydrated, budget_limit=budget_limit, overage_percent=overage)

    if strict and summary["unknown_price_cards_count"] > 0:
        summary["strict_mode_failed"] = True
        summary["strict_mode_reason"] = (
            f"{summary['unknown_price_cards_count']} card(s) have unknown price."
        )

    if json_output:
        print(json.dumps(summary, indent=2))
    else:
        conf_color = "green" if summary["budget_confidence"] == "complete" else "yellow"
        print(f"[bold blue]Budget Summary[/bold blue]")
        print(f"  Total (known USD):  [green]${summary['known_price_total']}[/green]")
        if budget_limit is not None:
            status = summary.get("budget_status", "")
            status_color = "green" if status == "under_budget" else ("yellow" if status == "within_overage" else "red")
            print(f"  Budget limit:       ${summary['budget_limit']} (hard limit: ${summary['hard_budget_limit']})")
            print(f"  Budget status:      [{status_color}]{status}[/{status_color}]")
        print(f"  Known price cards:  {summary['known_price_cards_count']}")
        print(f"  Unknown price cards: [{conf_color}]{summary['unknown_price_cards_count']}[/{conf_color}]")
        print(f"  Budget confidence:  [{conf_color}]{summary['budget_confidence']}[/{conf_color}]")
        if summary["unknown_price_cards"]:
            print("[yellow]Unknown price cards:[/yellow]")
            for cname in summary["unknown_price_cards"]:
                print(f"  - {cname}")
        if budget_limit is not None and summary.get("note"):
            print(f"[dim]{summary['note']}[/dim]")
        if strict and summary.get("strict_mode_failed"):
            print(f"[red]Strict mode: {summary['strict_mode_reason']}[/red]")
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
