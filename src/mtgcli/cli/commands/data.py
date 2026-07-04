"""Data / setup commands: status, init-data, enrich, temp-clean.

Bodies split verbatim from the former monolithic ``cli.py``.
"""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _apply_max_price  # noqa: F401 -- underscore not re-exported by *

@app.command()
def status(
    json_output: bool = typer.Option(False, "--json-output", help="Emit status as JSON"),
):
    """Check the project status and paths."""
    info = {
        "project_root": str(PROJECT_ROOT),
        "database_path": str(SQLITE_PATH),
        "database_exists": SQLITE_PATH.exists(),
        "raw_cards_path": str(RAW_CARDS_PATH),
        "raw_cards_exists": RAW_CARDS_PATH.exists(),
    }
    if json_output:
        print_json(info)
    else:
        print(f"[bold blue]MTG Deckbuilder Status[/bold blue]")
        print(f"Project Root: [green]{PROJECT_ROOT}[/green]")
        db_color = "green" if info["database_exists"] else "red"
        print(f"Database: [{db_color}]{SQLITE_PATH} ({'present' if info['database_exists'] else 'MISSING'})[/{db_color}]")



@app.command()
def init_data(
    json_output: bool = typer.Option(False, "--json-output", help="Suppress progress; emit a final JSON summary"),
):
    """Initialize or update the MTG card database."""
    downloaded = False
    if not RAW_CARDS_PATH.exists():
        if not json_output:
            print("[yellow]Downloading Scryfall bulk data...[/yellow]")
            print("[bold red]Disclaimer: This download is approximately 2GB and will take a few minutes depending on your connection.[/bold red]")
        path = download_default_cards()
        downloaded = True
        if not json_output:
            print(f"[green]Downloaded cards to {path}[/green]")
    elif not json_output:
        print(f"[green]Raw card data already exists at {RAW_CARDS_PATH}[/green]")

    if not json_output:
        print("[yellow]Building SQLite database (aggregating prices across all printings)...[/yellow]")
    result = build_sqlite_database()
    if json_output:
        print_json({
            "ok": True,
            "downloaded": downloaded,
            "database_path": result["path"],
            "unique_card_identities": result["unique_card_identities"],
            "cards_processed": result["cards_processed"],
            "cards_with_known_usd_price": result["cards_with_known_usd_price"],
            "cards_with_unknown_price": result["cards_with_unknown_price"],
        })
    else:
        print(f"[green]Built SQLite database at {result['path']}[/green]")
        print(f"[green]  {result['unique_card_identities']} unique cards from {result['cards_processed']} printings[/green]")
        print(f"[green]  {result['cards_with_known_usd_price']} cards with known USD price, {result['cards_with_unknown_price']} unknown[/green]")



@app.command()
def enrich(
    input_path: Path = typer.Argument(..., help="Path to deck JSON file"),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file path"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit a machine-readable result summary"),
):
    """Enrich a deck JSON with full card data from the database."""
    if not SQLITE_PATH.exists():
        if json_output:
            print_json({"ok": False, "error": "database_not_found"})
        else:
            print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)

    if not input_path.exists():
        if json_output:
            print_json({"ok": False, "error": "input_not_found", "input": str(input_path)})
        else:
            print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    try:
        final_output = enrich_deck(input_path, SQLITE_PATH, output_path)
        if json_output:
            print_json({"ok": True, "output": str(final_output)})
        else:
            print(f"[green]Enriched deck saved to {final_output}[/green]")
    except Exception as e:
        if json_output:
            print_json({"ok": False, "error": str(e)})
        else:
            print(f"[red]Failed to enrich deck: {e}[/red]")
        raise typer.Exit(code=1)



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
            print_json({"error": msg, "mode": "full" if full else "normal", "dry_run": dry_run,
                        "deleted_count": 0, "matched_count": 0, "preserved_files": [], "files": []})
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
        print_json(report)
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


