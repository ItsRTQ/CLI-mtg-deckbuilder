"""Misc / export / report commands: export, final-build, report.

Bodies split verbatim from the former monolithic ``cli.py``.
"""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _apply_max_price  # noqa: F401 -- underscore not re-exported by *

@app.command()
def export(
    input_path: Path = typer.Argument(..., help="Path to deck JSON file"),
    output_path: Path = typer.Option(Path("output/deck.moxfield.txt"), "--output", "-o", help="Output text file path"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit a machine-readable result summary"),
):
    """Export a deck JSON to Moxfield text format."""
    if not input_path.exists():
        if json_output:
            print_json({"ok": False, "error": "input_not_found", "input": str(input_path)})
        else:
            print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    try:
        raw = read_json(input_path)
        normalized = normalize_deck_input(raw)
        deck_cards = normalized["main_deck"]
        commanders = normalized.get("commanders") or []
        export_deck_to_moxfield(deck_cards, output_path, commanders=commanders)
        if json_output:
            print_json({"ok": True, "output": str(output_path), "format": "moxfield",
                        "commander_count": len(commanders), "main_deck_count": len(deck_cards)})
        else:
            print(f"[green]Exported deck to {output_path}[/green]")
    except Exception as e:
        if json_output:
            print_json({"ok": False, "error": str(e)})
        else:
            print(f"[red]Failed to export deck: {e}[/red]")
        raise typer.Exit(code=1)



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
            print_json(_fail_payload)
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
            print_json(_fail_payload)
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
        print_json({
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
        })
    else:
        print("[bold green]Deck validated successfully.[/bold green]")
        print(f"Final build folder created: [bold]{build_dir}[/bold]")
        print(f"Decklist saved to: [bold]{decklist_path}[/bold]")
        print(f"Explanation saved to: [bold]{explanation_path}[/bold]")



@app.command()
def report(
    name: str = typer.Option(..., "--name", help="Filename (without extension) for the consolidated report JSON, saved to the output directory."),
    note: Optional[List[str]] = typer.Option(None, "--note", help="Add a comment to the report. Repeatable."),
    keep: bool = typer.Option(False, "--keep", help="Keep the on-going log instead of clearing it after consolidation."),
    summary: bool = typer.Option(False, "--summary", help="Also compute and show a calibration summary (command counts, analyze-card calls, failures)."),
    json_output: bool = typer.Option(False, "--json-output", help="Print the consolidated report as JSON."),
):
    """Consolidate the on-going command log into a named JSON report in the logs/ directory.

    Every command run with `--log` appends to a staging file (`output/on-going-report.json`).
    `report` serializes that accumulated log into `logs/<name>.json` (persistent history, separate
    from the ephemeral output/ dir), optionally annotated with `--note` comments, then clears the
    staging file so the next build starts fresh (use `--keep` to retain).
    `--summary` derives calibration metrics (per-command counts, the cards analyzed, and any
    commands that failed) from the log without changing what was captured.
    """
    from mtgcli.logging_util import ONGOING_PATH, _load_ongoing, summarize_log
    from datetime import datetime, timezone

    entries = _load_ongoing()
    if not entries:
        print("[yellow]No logged commands found. Run commands with --log first.[/yellow]")
        raise typer.Exit(code=1)

    safe_name = name if name.endswith(".json") else f"{name}.json"
    out_path = LOGS_DIR / safe_name
    payload = {
        "report_name": name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": list(note) if note else [],
        "command_count": len(entries),
        "log": entries,
    }
    if summary:
        payload["summary"] = summarize_log(entries)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if not keep and ONGOING_PATH.exists():
        ONGOING_PATH.unlink()

    if json_output:
        print_json(payload)
    else:
        print(f"[green]Report written to {out_path}[/green] ({len(entries)} commands logged)")
        if note:
            print(f"  notes: {len(note)}")
        if not keep:
            print("  on-going log cleared.")
        if summary:
            s = payload["summary"]
            print("  [bold]summary:[/bold]")
            print(f"    total commands: {s['total_commands']}")
            print(f"    by command: " + ", ".join(f"{k}×{v}" for k, v in s["command_counts"].items()))
            if s["analyze_card_calls"]:
                print(f"    analyze-card ({s['analyze_card_count']}): {', '.join(s['analyze_card_calls'])}")
            if s["failures"]:
                print(f"    [yellow]failures ({s['failure_count']}): "
                      + ", ".join(f"seq{f['seq']} {f['command']}(exit {f['exit_code']})" for f in s["failures"]) + "[/yellow]")
            else:
                print("    failures: none")


