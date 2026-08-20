"""Misc / export / report commands: export, final-build, report, note.

Bodies split verbatim from the former monolithic ``cli.py``.
"""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _apply_max_price, _emit_json_error  # noqa: F401 -- underscore not re-exported by *


@app.command()
def note(
    text: Optional[str] = typer.Argument(None, help="Note text (omit with --list/--clear)"),
    note_type: str = typer.Option("finding", "--type", help="Note type: combo | finding | decision"),
    cards: Optional[str] = typer.Option(None, "--cards", help="Comma-separated card names involved (e.g. 'Heliod, Sun-Crowned,Walking Ballista')... use ';' as separator when names contain commas"),
    combo_class: Optional[str] = typer.Option(None, "--combo-class", help="For --type combo: infinite | non_infinite | utility | auto_win"),
    list_notes: bool = typer.Option(False, "--list", help="List the current build's notes and exit"),
    clear: bool = typer.Option(False, "--clear", help="Clear the current build's notes"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Building notes — the carpenter's tally: record combos/decisions/findings during
    a build instead of memorizing them. Combo notes feed `mtg deck-power`.

    Examples:
        mtg note "Heliod + Ballista is an auto-win line" --type combo \\
            --cards "Heliod; Sun-Crowned;Walking Ballista" --combo-class auto_win
        mtg note --list
    """
    from mtgcli.deckbuilder.build_notes import (
        COMBO_CLASSES, NOTE_TYPES, add_note, load_notes, save_notes,
    )

    if clear:
        save_notes([])
        if json_output:
            print_json({"ok": True, "cleared": True})
        else:
            print("[green]Build notes cleared.[/green]")
        return

    if list_notes:
        notes = load_notes()
        if json_output:
            print_json({"notes": notes, "count": len(notes)})
        else:
            if not notes:
                print("[yellow]No build notes yet.[/yellow]")
                return
            print(f"[bold blue]Build notes ({len(notes)}):[/bold blue]")
            for n in notes:
                extra = ""
                if n.get("cards"):
                    extra += f" [dim]({', '.join(n['cards'])})[/dim]"
                if n.get("combo_class"):
                    extra += f" [magenta]({n['combo_class']})[/magenta]"
                # parens, not brackets: rich eats [combo]-style tokens as markup
                print(f"  {n['seq']}. ({n['type']}) {n['text']}{extra}")
        return

    if not text:
        _msg = "Provide note text, or use --list / --clear."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)
    if note_type not in NOTE_TYPES:
        _msg = f"Unknown --type '{note_type}'. Valid: {', '.join(NOTE_TYPES)}."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)
    if note_type == "combo" and combo_class not in COMBO_CLASSES:
        _msg = f"--type combo requires --combo-class ({', '.join(COMBO_CLASSES)})."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)

    card_list = None
    unknown = []
    if cards:
        sep = ";" if ";" in cards else ","
        card_list = [c.strip() for c in cards.split(sep) if c.strip()]
        # Light DB validation (warn, don't block): a bad separator or typo silently
        # creates ghost card names that deck-power can never match (caught live on
        # the first real use — 'Heliod; Sun-Crowned' split into two ghosts).
        try:
            repo = CardRepository(str(SQLITE_PATH))
            resolved = []
            for name in card_list:
                found = repo.get_card_by_exact_name(name)
                if found:
                    resolved.append(found["name"])
                else:
                    unknown.append(name)
                    resolved.append(name)
            card_list = resolved
        except Exception:
            pass
    entry = add_note(text, note_type=note_type, cards=card_list, combo_class=combo_class)
    if json_output:
        out = {"ok": True, "note": entry}
        if unknown:
            out["unknown_cards"] = unknown
        print_json(out)
    else:
        print(f"[green]Noted (#{entry['seq']}, {entry['type']}).[/green]")
        if unknown:
            print(f"[yellow]warning — not found in DB (typo or bad separator? names with "
                  f"commas need ';' between cards): {', '.join(unknown)}[/yellow]")

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
def export_tcgplayer(
    input_path: Path = typer.Argument(..., help="Deck file: structured .json or plain-text .txt decklist"),
    print_url: bool = typer.Option(False, "--print-url", help="Print the URL instead of opening the browser"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit a machine-readable result summary"),
):
    """Export a deck to TCGplayer Mass Entry: builds the pre-filled URL and opens it
    in the default browser (or prints it with --print-url). No API key needed."""
    from mtgcli.export.tcgplayer import (
        build_tcgplayer_mass_entry_url, normalize_deck_for_tcgplayer,
    )
    from mtgcli.utils.deck_io import load_deck_file

    if not input_path.exists():
        if json_output:
            print_json({"ok": False, "error": "input_not_found", "input": str(input_path)})
        else:
            print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    try:
        normalized = load_deck_file(input_path)
    except Exception as e:
        if json_output:
            print_json({"ok": False, "error": str(e)})
        else:
            print(f"[red]Failed to load deck: {e}[/red]")
        raise typer.Exit(code=1)

    # Layout lookup (best-effort): split/aftermath cards must keep "A // B" in the
    # export while other multi-face layouts reduce to the front face. No DB → the
    # exporter falls back to front-face for every "//" name.
    layout_lookup = None
    try:
        repo = CardRepository(str(SQLITE_PATH))

        def layout_lookup(name):  # noqa: F811
            return (repo.get_card_by_exact_name(name) or {}).get("layout")
    except Exception:
        pass

    cards, skipped = normalize_deck_for_tcgplayer(
        normalized["main_deck"], commanders=normalized.get("commanders"),
        layout_lookup=layout_lookup,
    )
    if not cards:
        _msg = "No valid cards were found to export."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]Error: {_msg}[/red]")
        raise typer.Exit(code=1)

    url = build_tcgplayer_mass_entry_url(cards)
    card_count = sum(c["quantity"] for c in cards)

    opened = False
    if not print_url:
        try:
            import webbrowser
            opened = bool(webbrowser.open(url))
        except Exception:
            opened = False

    if json_output:
        print_json({
            "ok": True, "url": url, "card_count": card_count,
            "skipped": skipped, "opened_browser": opened,
        })
        return

    print(f"[green]TCGplayer export created for {card_count} cards.[/green]")
    if skipped:
        print(f"[yellow]Skipped {len(skipped)} invalid entries.[/yellow]")
    if print_url:
        typer.echo(url)  # plain echo: rich would soft-wrap the URL mid-line
    elif opened:
        print("Opening TCGplayer Mass Entry...")
    else:
        print("[yellow]TCGplayer URL generated successfully, but the browser could not be opened.[/yellow]")
        typer.echo(url)


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

    # Folder name convention: <commander>-<TIER>-<RANK>-<COST> (guarded — a scoring
    # failure falls back to 'na' tokens so final-build never crashes). Exact-name
    # collisions get a rising number right after the commander name.
    tier_tok = rank_tok = None   # None -> segment omitted from the folder name
    cost_val = 0.0
    try:
        from mtgcli.models import Deck as _Deck
        _deck = _Deck.load(deck_path, repo=repo)
        cost_val = _deck.total_price() or 0.0
        tier_tok = (_deck.tier() or {}).get("band") or None
        rank_tok = (_deck.rank() or {}).get("band_name") or None
    except Exception:
        pass
    cost_tok = f"{int(round(cost_val))}usd"
    build_name = build_final_name(commander, tier_tok, rank_tok, cost_tok, FINAL_BUILDS_DIR)
    build_dir = create_final_build_directory(build_name, FINAL_BUILDS_DIR)
    decklist_text = deck_entries_to_moxfield_text(deck_entries)
    decklist_path = save_final_build_decklist(decklist_text, build_dir, build_name)
    explanation_path = save_final_build_explanation(explanation_text, build_dir, build_name)

    # The build ships with its ANNOTATED deck object (purposes, agent notes, combos,
    # config) as deck_list.json — the .txt is the human list, this is the judgment.
    deck_json_path = build_dir / "deck_list.json"
    import shutil as _shutil
    _shutil.copyfile(deck_path, deck_json_path)

    if json_output:
        print_json({
            "validated": True,
            "saved": True,
            "build_name": build_name,
            "build_dir": str(build_dir),
            "decklist_path": str(decklist_path),
            "explanation_path": str(explanation_path),
            "deck_json_path": str(deck_json_path),
            "commander": commander,
            "theme": theme,
            "bracket": resolved_bracket,
            "tier": tier_tok,
            "rank": rank_tok,
            "cost": cost_tok,
        })
    else:
        print("[bold green]Deck validated successfully.[/bold green]")
        print(f"Final build folder created: [bold]{build_dir}[/bold]")
        print(f"Decklist saved to: [bold]{decklist_path}[/bold]")
        print(f"Explanation saved to: [bold]{explanation_path}[/bold]")
        print(f"Deck JSON saved to: [bold]{deck_json_path}[/bold]")



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
            if s.get("status_exits"):
                print(f"    [dim]status exits ({s['status_exit_count']}, documented states — over-budget / verify-missing / not-found): "
                      + ", ".join(f"seq{f['seq']} {f['command']}" for f in s["status_exits"]) + "[/dim]")


