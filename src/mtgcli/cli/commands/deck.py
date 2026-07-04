"""Deck-lifecycle commands: validate, deck-write, deck-fill-lands,
suggest-lands, deck-check, deck-swap, preflight, deck-gaps.

Bodies split verbatim from the former monolithic ``cli.py``.
"""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _apply_max_price  # noqa: F401 -- underscore not re-exported by *

@app.command()
def validate(
    commander: Optional[str] = typer.Option(None, "--commander", help="Name of the commander (overrides deck metadata)"),
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

        # Resolve commander(s): CLI flags override structured file metadata.
        if commander:
            resolved_commander = commander
            resolved_partner = partner
        else:
            meta_commanders = normalized.get("commanders") or []
            if not meta_commanders:
                raise ValueError(
                    "No commander provided. Use --commander or include commander metadata in the deck JSON."
                )
            resolved_commander = meta_commanders[0]
            resolved_partner = partner or (meta_commanders[1] if len(meta_commanders) > 1 else None)

        report = validate_commander_deck(resolved_commander, deck_entries, repo, partner_name=resolved_partner)
        
        # Save report
        report_path = Path("output/validation_report.json")
        write_json(report_path, report)
        
        if json_output:
            print_json(report)
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
    commander: Optional[str] = typer.Option(None, "--commander", help="Commander name (used with --structured)"),
    partner: Optional[str] = typer.Option(None, "--partner", help="Partner commander name (used with --structured)"),
    structured: bool = typer.Option(False, "--structured", help="Write structured JSON with commander/main_deck keys (implied when --commander is given)"),
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

    # --commander implies --structured: an unstructured write with a commander named puts
    # the commander INSIDE the main deck (illegal shape) — the Gargos build hit this trap.
    if commander:
        structured = True

    if structured and commander:
        commanders_list = [commander] + ([partner] if partner else [])
        main_deck, _ = remove_command_zone_cards_from_main_deck(entries, commanders_list)
        if partner:
            deck_data: Any = {"commanders": commanders_list, "main_deck": main_deck}
        else:
            deck_data = {"commander": commander, "main_deck": main_deck}
        write_json(output_path, deck_data)
        total = sum(e.get("quantity", 1) for e in main_deck)
        if json_output:
            print_json({
                "written": True,
                "output": str(output_path),
                "structured": True,
                "commanders": commanders_list,
                "entries": len(main_deck),
                "total_cards": total,
            })
        else:
            print(f"[green]Wrote structured deck ({len(main_deck)} entries, {total} cards) to {output_path}[/green]")
    else:
        write_json(output_path, entries)
        total = sum(e.get("quantity", 1) for e in entries)
        if json_output:
            print_json({
                "written": True,
                "output": str(output_path),
                "entries": len(entries),
                "total_cards": total,
            })
        else:
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
    # Filling in place (no separate --output, or --output == --deck) is the intended operation,
    # so it doesn't need --force. Only guard against clobbering a *different* existing file.
    writing_elsewhere = output_path is not None and output_path.resolve() != deck_path.resolve()
    if writing_elsewhere and out_path.exists() and not dry_run and not force:
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
    normalized = normalize_deck_input(raw)
    deck_entries = normalized["main_deck"]
    was_structured = isinstance(raw, dict)
    deck_metadata = normalized.get("metadata", {})

    # Remove commander/partner if they appear in the flat main deck list
    commanders_list = [commander] + ([partner] if partner else [])
    deck_entries, removed_from_main = remove_command_zone_cards_from_main_deck(deck_entries, commanders_list)

    result = fill_deck_with_lands(deck_entries, color_identity, target)

    if not result["filled"]:
        if json_output:
            print_json({"filled": False, "error": result["error"]})
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
        if removed_from_main:
            payload["command_zone_cards_removed_from_main_deck"] = removed_from_main
        if json_output:
            print_json(payload)
        else:
            if removed_from_main:
                print(f"[yellow]Removed commander from main deck count before filling lands: {', '.join(removed_from_main)}[/yellow]")
            print(f"[bold blue]Dry run — no files written[/bold blue]")
            print(f"  Deck: {current} / {target} main deck cards")
            print(f"  Would add {remaining} basic land(s):")
            for name, qty in lands_added.items():
                print(f"    - {qty} {name}")
        return

    # Write updated deck — preserve structured shape (commander metadata) when
    # the input was structured, so the output validates without manual fixups.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if was_structured:
        deck_data: Any = dict(deck_metadata)
        if partner:
            deck_data["commanders"] = commanders_list
        else:
            deck_data["commander"] = commander
        deck_data["main_deck"] = result["updated_deck"]
        write_json(out_path, deck_data)
    else:
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
    if removed_from_main:
        payload["command_zone_cards_removed_from_main_deck"] = removed_from_main

    if json_output:
        print_json(payload)
    else:
        if removed_from_main:
            print(f"[yellow]Removed commander from main deck count before filling lands: {', '.join(removed_from_main)}[/yellow]")
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
        print_json(lands)
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
            print_json(report)
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
def deck_swap(
    deck: Path = typer.Option(..., "--deck", help="Path to the decklist to edit (.txt or deck .json)"),
    swap: Optional[List[str]] = typer.Option(None, "--swap", help='A swap in the form "Old Card=New Card". Repeatable.'),
    commander: Optional[str] = typer.Option(None, "--commander", help="Commander name, to enforce color identity on incoming cards"),
    output: Optional[Path] = typer.Option(None, "--output", help="Write result here instead of editing in place"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and report changes without writing"),
    json_output: bool = typer.Option(False, "--json-output", help="Output the result as JSON"),
):
    """Swap cards in a decklist, validating each incoming card before writing.

    Each --swap "A=B" replaces A with B. Before writing anything, every B is checked:
    it must exist in the DB, be commander-legal, and (if a commander is known) fit the
    commander's color identity. If any swap is invalid the whole operation aborts and
    nothing is written — a safe replacement for hand-editing the decklist with a script.
    """
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)
    if not deck.exists():
        print(f"[red]Deck file not found: {deck}[/red]")
        raise typer.Exit(code=1)
    if not swap:
        print("[red]No --swap given. Use --swap \"Old Card=New Card\".[/red]")
        raise typer.Exit(code=1)

    loaded = load_deck_file(deck)
    entries = loaded["main_deck"]
    repo = CardRepository(str(SQLITE_PATH))

    # Resolve commander color identity (from --commander, else the deck's own commander).
    commander_name = commander or (loaded.get("commanders") or [None])[0]
    commander_ci = None
    if commander_name:
        cmd_card = repo.get_card_by_exact_name(commander_name)
        if cmd_card:
            commander_ci = set(cmd_card.get("color_identity") or [])

    # Parse and validate every swap before touching the file.
    parsed, errors, applied = [], [], []
    for raw in swap:
        if "=" not in raw:
            errors.append(f"Malformed --swap '{raw}' (expected \"Old=New\").")
            continue
        a, b = (s.strip() for s in raw.split("=", 1))
        entry = next((e for e in entries if e.get("name", "").lower() == a.lower()), None)
        if entry is None:
            errors.append(f"'{a}' is not in the deck — nothing to swap out.")
            continue
        b_card = repo.get_card_by_exact_name(b)
        if not b_card:
            sugg = [s["name"] for s in repo.suggest_similar_names(b, limit=3)]
            hint = f" (did you mean: {', '.join(sugg)}?)" if sugg else ""
            errors.append(f"Incoming card '{b}' not found in DB{hint}.")
            continue
        if not b_card.get("commander_legal", False):
            errors.append(f"Incoming card '{b_card['name']}' is not Commander-legal.")
            continue
        if commander_ci is not None:
            b_ci = set(b_card.get("color_identity") or [])
            if not b_ci.issubset(commander_ci):
                errors.append(
                    f"Incoming card '{b_card['name']}' ({''.join(sorted(b_ci)) or 'C'}) "
                    f"breaks color identity {''.join(sorted(commander_ci)) or 'C'}."
                )
                continue
        parsed.append((entry, b_card["name"]))

    if errors:
        print("[red]Swap aborted — nothing written. Issues:[/red]")
        for e in errors:
            print(f"  - {e}")
        raise typer.Exit(code=1)

    for entry, new_name in parsed:
        applied.append({"out": entry["name"], "in": new_name, "quantity": entry.get("quantity", 1)})
        entry["name"] = new_name

    # Singleton guard: the resulting deck must not contain a duplicate non-basic card.
    # (A regex replace would happily create two copies of an incoming card already in the deck.)
    from mtgcli.deckbuilder.pricing import BASIC_LANDS
    seen, dupes = set(), set()
    for e in entries:
        n = e.get("name", "")
        if n in BASIC_LANDS:
            continue
        key = n.lower()
        if key in seen:
            dupes.add(n)
        seen.add(key)
    if dupes:
        print("[red]Swap aborted — nothing written. Would create duplicate (singleton) cards:[/red]")
        for n in sorted(dupes):
            print(f"  - {n} appears more than once after the swap.")
        raise typer.Exit(code=1)

    dest = output or deck
    if not dry_run:
        if deck.suffix.lower() == ".txt" and (output is None or output.suffix.lower() == ".txt"):
            text = "\n".join(f"{e.get('quantity', 1)} {e['name']}" for e in entries) + "\n"
            dest.write_text(text, encoding="utf-8")
        else:
            payload = {"commander": commander_name, "main_deck": entries} if commander_name else {"main_deck": entries}
            write_json(dest, payload)

    if json_output:
        print_json({"swaps": applied, "written": (not dry_run), "output": str(dest)})
    else:
        verb = "Would swap" if dry_run else "Swapped"
        for a in applied:
            q = f"{a['quantity']}x " if a["quantity"] != 1 else ""
            print(f"  {verb}: {q}{a['out']} -> {a['in']}")
        if not dry_run:
            print(f"[green]Wrote {dest}[/green]")
        else:
            print("[dim]--dry-run: no file written.[/dim]")



@app.command()
def preflight(
    deck_path: Path = typer.Option(..., "--deck", help="Path to deck JSON or .txt decklist"),
    commander: Optional[str] = typer.Option(None, "--commander", help="Commander (overrides deck metadata)"),
    partner: Optional[str] = typer.Option(None, "--partner", help="Partner commander, if any"),
    budget_limit: Optional[float] = typer.Option(None, "--budget", help="If set, also gate on this USD budget"),
    json_output: bool = typer.Option(False, "--json-output", help="Output the checklist as JSON"),
):
    """Single finalization gate: run every must-pass check before a deck is considered done.

    Reuses the same validator/deck-check/budget logic as the individual commands, so an agent
    can run ONE command instead of remembering to run (and pass) each rule separately. Exits
    non-zero if the deck is not ready. This is the blessed "are we done?" check.
    """
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)
    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    normalized = load_deck_file(deck_path)
    deck_entries = normalized["main_deck"]

    if commander:
        resolved_commander, resolved_partner = commander, partner
    else:
        meta = normalized.get("commanders") or []
        if not meta:
            print("[red]No commander given. Use --commander or include it in the deck metadata.[/red]")
            raise typer.Exit(code=1)
        resolved_commander = meta[0]
        resolved_partner = partner or (meta[1] if len(meta) > 1 else None)

    report = validate_commander_deck(resolved_commander, deck_entries, repo, partner_name=resolved_partner)

    # Map validator error types to named, human-facing gates.
    gate_defs = [
        ("Commander legal & resolved", {"commander_not_found", "invalid_commander"}),
        ("Commander in command zone (not main deck)", {"commander_in_main_deck"}),
        ("Deck size correct", {"invalid_deck_size"}),
        ("All cards exist (no typos)", {"card_not_found"}),
        ("All cards Commander-legal", {"not_commander_legal"}),
        ("Singleton (no illegal duplicates)", {"singleton_violation"}),
        ("Within color identity", {"color_identity_violation"}),
    ]
    errors_by_type: Dict[str, List[str]] = {}
    for e in report.get("errors", []):
        errors_by_type.setdefault(e.get("type", "other"), []).append(e.get("message", str(e)))

    checks = []
    for label, types in gate_defs:
        msgs = [m for t in types for m in errors_by_type.get(t, [])]
        checks.append({"check": label, "status": "FAIL" if msgs else "PASS", "details": msgs})

    # Hydrate once (full card data) so quality stats and budget see real type_line/prices,
    # not just {name, quantity}. Without this, deck-check can't tell lands from spells.
    hydrated = []
    for entry in deck_entries:
        cd = repo.get_card_by_exact_name(entry.get("name", "")) if entry.get("name") else None
        row = dict(cd) if cd else {"name": entry.get("name"), "usd_price": None}
        row["quantity"] = entry.get("quantity", 1)
        hydrated.append(row)

    # Quality (informational — warnings don't fail the gate).
    quality = check_deck_quality(hydrated)
    quality_warnings = quality.get("warnings", [])

    # Budget gate (only if a limit was given).
    budget_check = None
    if budget_limit is not None:
        bsum = build_budget_summary(hydrated, budget_limit=budget_limit)
        ok = bsum.get("budget_status") in ("under_budget", "within_overage")
        budget_check = {
            "check": f"Within budget (${budget_limit})",
            "status": "PASS" if ok else "FAIL",
            "details": [] if ok else [f"${bsum['known_price_total']} ({bsum.get('budget_status')})"],
        }
        checks.append(budget_check)

    ready = all(c["status"] == "PASS" for c in checks)
    result = {
        "ready": ready,
        "commander": resolved_commander,
        "checks": checks,
        "quality_stats": quality.get("stats", {}),
        "quality_warnings": quality_warnings,
    }

    if json_output:
        print_json(result)
    else:
        print("[bold blue]Preflight checklist[/bold blue]")
        for c in checks:
            mark = "[green]✓[/green]" if c["status"] == "PASS" else "[red]✗[/red]"
            print(f"  {mark} {c['check']}")
            for d in c["details"]:
                print(f"      [red]{d}[/red]")
        if quality_warnings:
            print("  [yellow]![/yellow] Quality notes (non-blocking):")
            for w in quality_warnings:
                print(f"      [yellow]{w}[/yellow]")
        if ready:
            print("[bold green]READY: all gates passed.[/bold green]")
        else:
            print("[bold red]NOT READY: fix the ✗ items above before finalizing.[/bold red]")

    if not ready:
        raise typer.Exit(code=1)



@app.command()
def deck_gaps(
    deck_path: Path = typer.Option(..., "--deck", help="Path to deck JSON or .txt decklist"),
    commander: str = typer.Option(..., "--commander", help="Commander name"),
    archetype: str = typer.Option("midrange", "--archetype", help="Deck archetype for category targets"),
    partner: Optional[str] = typer.Option(None, "--partner", help="Partner commander"),
    power_level: int = typer.Option(7, "--power-level", help="Power level for category targets"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Audit a deck against its commander's plan and report where it's thin.

    Cross-references the category-count targets (recommended ranges per function) and the
    commander's oracle hooks against what the deck actually contains, then lists the gaps
    ranked by need — each with a ready `search-tags` command to fill it. Closes the
    analyze -> build -> audit loop.
    """
    if not SQLITE_PATH.exists():
        print("[red]Database not found. Please run 'init-data' first.[/red]")
        raise typer.Exit(code=1)
    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    import json as _json
    from mtgcli.config import SEED_DATA_DIR as _SD
    from mtgcli.deckbuilder.deck_check import _get_category_phrases
    from mtgcli.cards.search import _load_role_definitions
    from mtgcli.deckbuilder.oracle_hooks import extract_hooks

    repo = CardRepository(str(SQLITE_PATH))
    entries = load_deck_file(deck_path)["main_deck"]
    # Hydrate so we can match phrases against real oracle text.
    deck_cards = []
    for e in entries:
        cd = repo.get_card_by_exact_name(e.get("name", "")) if e.get("name") else None
        if cd:
            cd = dict(cd); cd["quantity"] = e.get("quantity", 1)
            deck_cards.append(cd)

    tag_defs = _json.load(open(_SD / "card_tags.json", encoding="utf-8"))
    role_defs = _load_role_definitions()

    def _count_matching(phrases):
        n = 0
        for c in deck_cards:
            text = " ".join([c.get("name", "") or "", c.get("type_line", "") or "", c.get("oracle_text", "") or ""]).lower()
            if any(p.lower() in text for p in phrases):
                n += c.get("quantity", 1)
        return n

    cc = calculate_category_counts(commander, archetype, partner_name=partner,
                                   power_level=power_level, db_path=str(SQLITE_PATH))

    gaps = []
    for rec in cc.get("category_recommendations", []):
        cat = rec["category"]
        min_count = rec.get("min_count", 0)
        phrases = _get_category_phrases(cat, tag_defs, role_defs)
        if not phrases:
            continue
        have = _count_matching(phrases)
        if have < min_count:
            gaps.append({
                "category": cat,
                "display_name": rec.get("display_name", cat),
                "have": have,
                "want_at_least": min_count,
                "recommended_range": rec.get("recommended_range"),
                "need_score": rec.get("need_score", 0),
                "fill_command": f'mtg search-tags {cat} --colors {"".join((repo.get_card_by_exact_name(commander) or {}).get("color_identity", []))} --json-output',
            })

    # Oracle-hook signal gaps: things the commander's text specifically wants.
    cmd_card = repo.get_card_by_exact_name(commander)
    hook_gaps = []
    if cmd_card:
        hooks = extract_hooks(cmd_card.get("oracle_text", "") or "")
        custom = [c for c in hooks["named_counters"] if c not in ("+1/+1", "-1/-1")]
        if custom and _count_matching(_get_category_phrases("proliferate", tag_defs, role_defs)) == 0:
            hook_gaps.append(f"Commander uses '{', '.join(custom)}' counters but the deck has no proliferate — add proliferate (search-tags proliferate).")

    gaps.sort(key=lambda g: -g["need_score"])
    result = {"commander": commander, "archetype": archetype, "gaps": gaps, "hook_gaps": hook_gaps}

    if json_output:
        print_json(result)
    else:
        if not gaps and not hook_gaps:
            print("[bold green]No major gaps: the deck covers its category targets.[/bold green]")
            return
        print(f"[bold blue]Deck gaps for {commander} ({archetype})[/bold blue] [dim]— ranked by need[/dim]")
        for g in gaps:
            print(f"  [red]✗[/red] {g['display_name']}: have {g['have']}, want ≥ {g['want_at_least']} (range {g['recommended_range']})")
            print(f"      fill: [dim]mtg search-tags {g['category']} --colors {''.join((cmd_card or {}).get('color_identity', []))}[/dim]")
        for hg in hook_gaps:
            print(f"  [yellow]![/yellow] {hg}")


