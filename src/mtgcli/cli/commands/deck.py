"""Deck-lifecycle commands: validate, deck-write, deck-fill-lands,
suggest-lands, deck-check, deck-swap, preflight, deck-gaps.

Bodies split verbatim from the former monolithic ``cli.py``.
"""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _apply_max_price, _emit_json_error  # noqa: F401 -- underscore not re-exported by *

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
    require_database(SQLITE_PATH, json_output)

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
    require_database(SQLITE_PATH, json_output)

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
    require_database(SQLITE_PATH, json_output)

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

            if report.get("staple_density"):
                sd = report["staple_density"]
                print(f"\n[dim]Staple density (consider-only, popularity ≠ power): "
                      f"median rank ~{sd['median_rank']}, {sd['pct_top_2000']}% top-2000 "
                      f"→ {sd['read']}; synergy-dense decks read low by design.[/dim]")
            
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
    require_database(SQLITE_PATH, json_output)
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

    from mtgcli.deckbuilder.pricing import BASIC_LANDS
    for entry, new_name in parsed:
        qty = entry.get("quantity", 1)
        if qty > 1 and new_name not in BASIC_LANDS:
            # Swapping out of a multi-copy entry (17x Island -> Buried Ruin must NOT
            # rename all 17 — the Mendicant build friction): take ONE copy out of the
            # stack and add the incoming card as its own singleton entry.
            entry["quantity"] = qty - 1
            entries.append({"name": new_name, "quantity": 1})
            applied.append({"out": entry["name"], "in": new_name, "quantity": 1})
        else:
            applied.append({"out": entry["name"], "in": new_name, "quantity": qty})
            entry["name"] = new_name

    # Singleton guard: the resulting deck must not contain a duplicate non-basic card —
    # neither as duplicate entries nor as a single entry with quantity > 1.
    # (A regex replace would happily create two copies of an incoming card already in the deck.)
    seen, dupes = set(), set()
    for e in entries:
        n = e.get("name", "")
        if n in BASIC_LANDS:
            continue
        if e.get("quantity", 1) > 1:
            dupes.add(n)
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
            # Preserve every top-level key of the original JSON (combos, agent_note,
            # config, annotations...) — rebuilding {commander, main_deck} from scratch
            # silently DROPPED them (caught by the Fase-4 extra-keys survival test).
            payload: Dict[str, Any] = {}
            if deck.suffix.lower() != ".txt":
                try:
                    _orig = read_json(deck)
                    if isinstance(_orig, dict):
                        payload = dict(_orig)
                except Exception:
                    payload = {}
            if commander_name and "commander" not in payload and "commanders" not in payload:
                payload["commander"] = commander_name
            payload["main_deck"] = entries
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
    require_database(SQLITE_PATH, json_output)
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
    require_database(SQLITE_PATH, json_output)
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

    from mtgcli.utils.phrase_match import any_phrase_matches as _any_pm

    def _matching(phrases):
        """(count, names) of deck cards matching any phrase — names let deck-gaps SHOW
        what it counted (full build #3 friction: 'only 4 cards serve it' without saying
        which 4 made the fix-or-justify decision guesswork)."""
        n, names = 0, []
        for c in deck_cards:
            text = " ".join([c.get("name", "") or "", c.get("type_line", "") or "", c.get("oracle_text", "") or ""]).lower()
            if _any_pm(phrases, text):
                n += c.get("quantity", 1)
                names.append(c.get("name", ""))
        return n, names

    def _count_matching(phrases):
        return _matching(phrases)[0]

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

    # ── M2 consumer #2: audit the deck against the ANALYZER's read of the commander ──
    # For every high/very_high band in analyzer.archetype_support, count how many deck
    # cards serve that plan. The plan→function map is the analyzer's OWN vocabulary
    # (mapping._ARCHETYPE_RULES defining+supporting tokens that are card_tags names), so
    # no new curation can drift out of sync with the archetype system. Tribal bands count
    # by creature type. Guarded: an analyzer failure only drops this section.
    analyzer_support = []
    plan_gaps = []
    _colors = "".join((cmd_card or {}).get("color_identity", []))
    if cmd_card:
        try:
            # Single source with deck-power's synergy density: deckbuilder.plan_coverage
            # (the multi-consumer drift lesson — one band-matching implementation).
            from mtgcli.deckbuilder.plan_coverage import plan_coverage
            _pc = plan_coverage(cmd_card, deck_cards, tag_defs)
            analyzer_support = []
            _PLAN_MIN = 5  # fewer than this many cards serving a detected plan = thin
            for b in (_pc["bands"] if _pc else []):
                arch = b["archetype"]
                if arch.endswith(" Tribal"):
                    ttype = arch[: -len(" Tribal")].lower()
                    fill = f"mtg search --subtype {ttype} --type creature --colors {_colors}"
                elif not b["plan_tags"]:
                    analyzer_support.append({"archetype": arch, "band": b["band"]})
                    continue
                else:
                    fill = f"mtg search-tags {' '.join(b['plan_tags'][:3])} --colors {_colors}"
                # Every audited band exposes WHICH cards were counted, gap or not — the
                # fix-or-justify decision needs the list, not just the number.
                analyzer_support.append({"archetype": arch, "band": b["band"],
                                         "have": b["have"], "cards": b["cards"]})
                if b["have"] < _PLAN_MIN:
                    plan_gaps.append({
                        "archetype": arch,
                        "band": b["band"],
                        "have": b["have"],
                        "cards": b["cards"],
                        "want_at_least": _PLAN_MIN,
                        "fill_command": fill,
                    })
        except Exception:
            analyzer_support = []
            plan_gaps = []

    gaps.sort(key=lambda g: -g["need_score"])
    result = {"commander": commander, "archetype": archetype, "gaps": gaps, "hook_gaps": hook_gaps,
              "analyzer_support": analyzer_support, "plan_gaps": plan_gaps}

    if json_output:
        print_json(result)
    else:
        if not gaps and not hook_gaps and not plan_gaps:
            print("[bold green]No major gaps: the deck covers its category targets and the commander's plan.[/bold green]")
            return
        print(f"[bold blue]Deck gaps for {commander} ({archetype})[/bold blue] [dim]— ranked by need[/dim]")
        for g in gaps:
            print(f"  [red]✗[/red] {g['display_name']}: have {g['have']}, want ≥ {g['want_at_least']} (range {g['recommended_range']})")
            print(f"      fill: [dim]mtg search-tags {g['category']} --colors {_colors}[/dim]")
        for hg in hook_gaps:
            print(f"  [yellow]![/yellow] {hg}")
        if plan_gaps:
            _reads = ", ".join("{} {}".format(a["archetype"], a["band"]) for a in analyzer_support) or "none"
            print(f"[bold blue]Commander plan check[/bold blue] [dim](analyzer reads: {_reads})[/dim]")
            for pg in plan_gaps:
                print(f"  [yellow]![/yellow] Analyzer reads [bold]{pg['archetype']}: {pg['band']}[/bold] "
                      f"but only {pg['have']} deck cards serve it (want ≥ {pg['want_at_least']})")
                _cards = pg.get("cards") or []
                if _cards:
                    shown = ", ".join(_cards[:8]) + (f", +{len(_cards) - 8} more" if len(_cards) > 8 else "")
                    print(f"      counted: [dim]{shown}[/dim]")
                print(f"      fill: [dim]{pg['fill_command']}[/dim]")




@app.command()
def deck_power(
    commander: str = typer.Option(..., "--commander", help="Name of the commander"),
    deck_path: Path = typer.Option(..., "--deck", help="Path to the deck JSON or .txt decklist"),
    bracket: Optional[str] = typer.Option(None, "--bracket", help="Target official bracket (1-5) to check compliance against; omit (n/a) to skip the verdict"),
    no_fetch: bool = typer.Option(False, "--no-fetch", help="Skip the external combo fetch (offline mode; noted combos still count)"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """The two categorizers: official BRACKET compliance (deterministic rules) and a
    TIER score (synergy + combos + game changers; 0.0-10.0 in 0.5 bands, F below 5.0).

    The tier is CONSIDER-ONLY — a heuristic efficiency read, never a gate. Combo
    sources: the agent's build notes (`mtg note --type combo`) plus the external
    fetch (degrades gracefully offline).
    """
    require_database(SQLITE_PATH, json_output)

    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    import json as _json
    from mtgcli.config import SEED_DATA_DIR as _SD
    from mtgcli.deckbuilder.build_notes import combo_notes
    from mtgcli.deckbuilder.deck_power import (
        bracket_compliance, compute_tier, cross_check_combos,
    )
    from mtgcli.deckbuilder.plan_coverage import plan_coverage
    from mtgcli.utils.deck_io import load_deck_file

    repo = CardRepository(str(SQLITE_PATH))
    cmd_card = repo.get_card_by_exact_name(commander)
    if not cmd_card:
        print(f"[red]Commander not found: {commander}[/red]")
        raise typer.Exit(code=1)

    try:
        deck_entries = load_deck_file(deck_path)["main_deck"]
    except Exception as e:
        print(f"[red]Failed to read deck file: {e}[/red]")
        raise typer.Exit(code=1)

    deck_cards = []
    for entry in deck_entries:
        name = entry.get("name") if isinstance(entry, dict) else str(entry)
        if not name:
            continue
        card = repo.get_card_by_exact_name(name)
        if card:
            card["quantity"] = entry.get("quantity", 1) if isinstance(entry, dict) else 1
            deck_cards.append(card)

    tag_defs = _json.load(open(_SD / "card_tags.json", encoding="utf-8"))
    deck_names = {c.get("name", "") for c in deck_cards}

    # Combos: external fetch (graceful) + the agent's noted combos.
    fetched = []
    external_status = "skipped" if no_fetch else "unavailable"
    if not no_fetch:
        try:
            from mtgcli.combos.fetcher import build_combo_url, fetch_combo_data
            from mtgcli.combos.parser import parse_combos
            fetched = parse_combos(fetch_combo_data(build_combo_url(commander)))
            external_status = "ok"
        except Exception:
            fetched = []
    combos = cross_check_combos(fetched, combo_notes(), deck_names, cmd_card.get("name", commander))

    # Synergy density (guarded: analyzer failure only drops the component).
    coverage = None
    try:
        coverage = plan_coverage(cmd_card, deck_cards, tag_defs)
    except Exception:
        coverage = None
    density = coverage["synergy_density"] if coverage else None

    gc_cards = [c.get("name", "") for c in deck_cards if c.get("game_changer")]

    # Fase 4: an ANNOTATED deck (purposes on entries) gets the consistency tier —
    # exact probabilities over the agent's judgment (models.Deck.tier()); an
    # unannotated deck falls back to the legacy census-based tier.
    consistency = None
    if any(isinstance(e, dict) and e.get("purpose") for e in deck_entries):
        try:
            from mtgcli.models import Deck as _DeckModel
            consistency = _DeckModel.load(deck_path, repo=repo).tier()
        except Exception:
            consistency = None
    tier = compute_tier(density, combos["complete"], len(gc_cards))
    if bracket is None:
        # the build contract may travel in the deck itself (deck-add --set-config)
        try:
            _cfg = read_json(deck_path).get("config") or {}
            if str(_cfg.get("bracket", "")).strip().lower() not in ("", "n/a", "na", "none"):
                bracket = str(_cfg["bracket"])
        except Exception:
            pass
    brackets = bracket_compliance(deck_cards, combos["complete"], tag_defs, target=bracket)

    # Draw odds (user framing, 2026-07-06): exact hypergeometric probabilities are
    # interpretable where raw density is not. Counts are QUANTITY-weighted over the
    # whole deck (draws include lands); the commander is NOT drawable (command zone),
    # so combo pieces that are the commander stay out of k.
    from mtgcli.deckbuilder.deck_power import draw_odds
    deck_size = sum(c.get("quantity", 1) for c in deck_cards)
    _qty = {c.get("name", ""): c.get("quantity", 1) for c in deck_cards}
    k_syn = sum(_qty.get(n, 0) for n in (coverage["covered_cards"] if coverage else []))
    _cmd_low = cmd_card.get("name", commander).lower()
    combo_piece_names = {p for cb in combos["complete"] for p in cb.get("cards", [])
                         if p.lower() != _cmd_low and p in _qty}
    k_combo = sum(_qty[p] for p in combo_piece_names)
    k_gc = sum(_qty.get(n, 0) for n in gc_cards)
    odds = {
        "synergy": draw_odds(k_syn, deck_size) if coverage else None,
        "combo_pieces": draw_odds(k_combo, deck_size),
        "game_changers": draw_odds(k_gc, deck_size),
    }

    result = {
        "commander": cmd_card.get("name", commander),
        "bracket": brackets,
        "tier": tier,
        "consistency_tier": consistency,
        "draw_odds": odds,
        "combos": {**combos, "external_status": external_status},
        "plan_coverage": ({"synergy_density": coverage["synergy_density"],
                           "nonland_count": coverage["nonland_count"],
                           "bands": [{k: b[k] for k in ("archetype", "band", "have")}
                                     for b in coverage["bands"]]}
                          if coverage else None),
    }

    if json_output:
        print_json(result)
        return

    print(f"[bold blue]Deck power report — {result['commander']}[/bold blue]")
    if consistency and consistency.get("tier") is not None:
        cc = consistency["components"]
        print(f"\n[bold]Consistency tier (consider-only): {consistency['band']}  "
              f"({consistency['tier']}/10 — core {consistency['core']})[/bold]")
        w = cc["wincon_access"]
        print(f"  wincon access: Q={w['q']} @T{w['turn']} "
              f"({len(w['routes'])} route(s), {w['tutors_as_wildcards']} tutor wildcards)")
        for rt in w["routes"][:5]:
            print(f"    - ({rt['kind']}) {', '.join(rt['cards'])} — P={rt['p_assemble']} × s={rt['strength']}")
        for br in w.get("broken_routes", [])[:3]:
            print(f"    - [yellow]BROKEN ({br['kind']}): missing {', '.join(br['missing'])}[/yellow]")
        fb = cc["function_bundle"]
        fns = ", ".join(f"{k}@T{v['turn']}={v['p']}" for k, v in fb["functions"].items())
        print(f"  functions: p={fb['p']} ({fns})")
        print(f"  curve: {cc['curve']['score']}/10 | bonus: arsenal +{cc['bonus']['arsenal']}, "
              f"GC +{cc['bonus']['gc']} ({cc['bonus']['gc_count']})")
        print(f"  [dim]{consistency['notes'][0]}[/dim]")
    else:
        if consistency and consistency.get("tier") is None:
            print(f"\n[yellow]Consistency tier: unavailable — {consistency.get('reason')}[/yellow]")
        print(f"\n[bold]Tier (legacy census, consider-only): {tier['band']}  ({tier['score']}/10)[/bold]")
        comp = tier["components"]
        print(f"  synergy: {comp['synergy']['points']} pts (density "
              f"{comp['synergy']['density'] if comp['synergy']['density'] is not None else 'n/a'})")
        print(f"  combos:  {comp['combos']['points']} pts {comp['combos']['counts'] or '(none)'}")
        print(f"  game changers: {comp['game_changers']['points']} pts ({comp['game_changers']['count']})")
        print(f"  [dim]{tier['notes'][0]}[/dim]")

    print("\n[bold]Draw odds[/bold] [dim](exact hypergeometric; commander not drawable)[/dim]")
    for label, key in (("plan/synergy cards", "synergy"), ("combo pieces", "combo_pieces"),
                       ("game changers", "game_changers")):
        o = odds.get(key)
        if o is None:
            print(f"  {label}: n/a")
            continue
        print(f"  {label}: {o['count']}/{o['deck_size']} — {o['per_draw_pct']}% per draw, "
              f"{o['opening_at_least_one_pct']}% chance in opening 7 "
              f"(expected {o['opening_expected']})")

    b = brackets
    print(f"\n[bold]Bracket compliance:[/bold] computed minimum bracket {b['computed_min_bracket']}")
    print(f"  game changers: {b['game_changers']['count']}"
          + (f" ({', '.join(b['game_changers']['cards'][:5])})" if b['game_changers']['cards'] else ""))
    print(f"  mass land denial: {len(b['mass_land_denial'])}"
          + (f" ({', '.join(b['mass_land_denial'][:4])})" if b['mass_land_denial'] else ""))
    print(f"  extra-turn cards: {len(b['extra_turn_cards'])}"
          + (f" ({', '.join(b['extra_turn_cards'][:4])})" if b['extra_turn_cards'] else ""))
    print(f"  two-card infinite/auto-win combos: {len(b['two_card_combos'])}")
    print(f"  tutors (informational): {b['tutors']['count']}")
    if "compliant" in b:
        verdict = "[green]COMPLIANT[/green]" if b["compliant"] else "[red]NOT COMPLIANT[/red]"
        print(f"  target bracket {b['target_bracket']}: {verdict}")
        for r in b.get("reasons", []):
            print(f"    - [yellow]{r}[/yellow]")

    c = combos
    print(f"\n[bold]Combos[/bold] [dim](external: {external_status}; noted via `mtg note`)[/dim]")
    print(f"  complete: {len(c['complete'])}")
    for cb in c["complete"][:8]:
        # parens, not brackets: rich eats [class]-style tokens as markup
        print(f"    - ({cb['class']}) {', '.join(cb['cards'])} [dim]({cb['source']})[/dim]")
    print(f"  one card away: {len(c['near_misses'])}")
    for cb in c["near_misses"][:5]:
        print(f"    - missing [bold]{cb['missing']}[/bold]: {', '.join(cb['cards'])} [dim]({cb['class']})[/dim]")


@app.command()
def deck_add(
    deck_path: Path = typer.Option(..., "--deck", help="Path to the annotated deck JSON (created on first use)"),
    commander: Optional[str] = typer.Option(None, "--commander", help="Commander name (required on FIRST use; read from the file afterwards)"),
    partner: Optional[str] = typer.Option(None, "--partner", help="Partner/background commander (first use only)"),
    cards: str = typer.Option(..., "--cards", help="Card names separated by ';' (names contain commas). Basics may repeat or use 'N Name' (e.g. '12 Mountain')"),
    purpose: str = typer.Option(..., "--purpose", help="Purpose(s) for THIS batch, comma-separated (the package IS the role): ramp,synergy"),
    note: Optional[str] = typer.Option(None, "--note", help="Optional agent_note applied to every card in the batch"),
    set_config: Optional[List[str]] = typer.Option(None, "--set-config", help="key=value build-contract entries (budget=150, budget_mode=soft, bracket=n/a...) — stored IN the deck"),
    deck_note: Optional[str] = typer.Option(None, "--deck-note", help="The deck's theme/gameplan note (set/overwrite)"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """THE drafting primitive: add a PACKAGE of cards through the tool instead of
    agent memory. Batch and ATOMIC (any invalid card rejects the whole package),
    validates at entry (exists / color identity / singleton / size), annotates the
    purpose at entry, and prints the batch price + RUNNING deck total (the
    draft-TO-budget mechanism, full build #3 lesson).
    """
    require_database(SQLITE_PATH, json_output)

    import re as _re
    from mtgcli.models import Card as _Card, CardNotFoundError as _CNF, Deck as _Deck, DeckError as _DE

    # parse the batch: "Name; Name; 12 Mountain"
    raw_items = [c.strip() for c in cards.split(";") if c.strip()]
    if not raw_items:
        _msg = "Provide at least one card in --cards (';'-separated)."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)
    purposes = [p.strip() for p in purpose.split(",") if p.strip()]

    repo = CardRepository(str(SQLITE_PATH))

    # load or create the deck
    if deck_path.exists():
        try:
            deck_obj = _Deck.load(deck_path, repo=repo)
        except Exception as e:
            print(f"[red]Failed to load deck: {e}[/red]")
            raise typer.Exit(code=1)
    else:
        if not commander:
            _msg = "First use: --commander is required to create the deck."
            if json_output:
                _emit_json_error({"error": {"type": "validation", "message": _msg}})
            else:
                print(f"[red]{_msg}[/red]")
            raise typer.Exit(code=1)
        try:
            cmds = [_Card(commander, ["WINCON"], repo=repo)]
            if partner:
                cmds.append(_Card(partner, ["WINCON"], repo=repo))
        except _CNF as e:
            if json_output:
                _emit_json_error({"error": {"type": "validation", "message": str(e)}})
            else:
                print(f"[red]{e}[/red]")
            raise typer.Exit(code=1)
        deck_obj = _Deck(cmds)

    if deck_note:
        deck_obj.agent_note = deck_note
    for kv in (set_config or []):
        if "=" in kv:
            k, v = kv.split("=", 1)
            deck_obj.config[k.strip()] = v.strip()

    # build the Card batch (fail loud per contract, whole batch rejected)
    batch, errors = [], []
    for item in raw_items:
        m = _re.match(r"^(\d+)\s+(.*)$", item)
        qty, name = (int(m.group(1)), m.group(2)) if m else (1, item)
        try:
            batch.append(_Card(name, purposes, agent_note=note, quantity=qty, repo=repo))
        except (_CNF, ValueError) as e:
            errors.append(str(e))
    if errors:
        _msg = "Batch rejected (nothing added):\n  - " + "\n  - ".join(errors)
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)

    try:
        deck_obj.add(batch)
    except _DE as e:
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": str(e)}})
        else:
            print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    deck_obj.save(deck_path)
    batch_price = round(sum((c.usd_price or 0.0) * c.quantity for c in batch), 2)
    total = deck_obj.total_price()
    result = {
        "added": [{"name": c.name, "quantity": c.quantity, "usd_price": c.usd_price} for c in batch],
        "purpose": [p.upper() for p in purposes],
        "batch_price": batch_price,
        "deck_total_price": total,
        "deck_size": deck_obj.size(),
        "max_size": deck_obj.max_size,
        "by_purpose": deck_obj.total_by_purpose(),
    }
    budget = deck_obj.config.get("budget")
    if budget:
        try:
            result["budget"] = float(budget)
            result["budget_utilization_pct"] = round(100 * total / float(budget), 1)
        except (TypeError, ValueError):
            pass
    if json_output:
        print_json(result)
    else:
        print(f"[green]Added {len(batch)} card(s) as {', '.join(result['purpose'])} "
              f"— batch ${batch_price:.2f}[/green]")
        for c in batch:
            p = f"${c.usd_price:.2f}" if c.usd_price is not None else "$?"
            print(f"  + {c.quantity}x {c.name} [dim]{p}[/dim]")
        util = f" ({result['budget_utilization_pct']}% of ${result['budget']:.0f})" \
            if "budget_utilization_pct" in result else ""
        print(f"[bold]Deck: {deck_obj.size()}/{deck_obj.max_size} cards — running total "
              f"${total:.2f}{util}[/bold]")


# Census tag -> purpose map for deck-annotate --auto (uses the EXISTING measured
# vocabulary; lands only count as RAMP via the ramp_rules single source).
_TAG_TO_PURPOSE = {
    "mana_rock": "RAMP", "mana_dork": "RAMP", "ritual": "RAMP", "land_ramp": "RAMP",
    "extra_land_drop": "RAMP", "treasure": "RAMP",
    "card_draw": "DRAW", "cantrip": "DRAW", "loot": "DRAW",
    "removal": "REMOVAL", "creature_removal": "REMOVAL", "spot_removal": "REMOVAL",
    "board_wipe": "WIPE",
    "tutor": "SEARCH",
    "protection": "PROTECTION",
}


@app.command()
def deck_annotate(
    deck_path: Path = typer.Option(..., "--deck", help="Path to the annotated deck JSON"),
    auto: bool = typer.Option(False, "--auto", help="Seed derivable purposes from the measured census (tags + commander plan coverage) — ADDs, never removes"),
    cards: Optional[str] = typer.Option(None, "--cards", help="';'-separated card names to refine"),
    purpose_add: Optional[str] = typer.Option(None, "--purpose-add", help="Comma-separated purposes to ADD to --cards"),
    note: Optional[str] = typer.Option(None, "--note", help="agent_note to set on --cards"),
    sync_notes: bool = typer.Option(False, "--sync-notes", help="Pull combo notes from the build notebook (mtg note --type combo) into the deck's combos block + mark COMBO_PIECE purposes"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """The single end-of-draft annotation pass: --auto seeds ~85% of purposes for
    free from the measured census; --cards/--purpose-add refines what only judgment
    sees (commander-granted synergy, wincons); --sync-notes persists the notebook's
    combos into the deck. Merges only — the agent's existing judgment survives."""
    require_database(SQLITE_PATH, json_output)

    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)
    if not (auto or sync_notes or (cards and purpose_add) or (cards and note)):
        _msg = "Nothing to do: use --auto, --sync-notes, or --cards with --purpose-add/--note."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)

    import json as _json
    from mtgcli.config import SEED_DATA_DIR as _SD
    from mtgcli.models import Deck as _Deck

    repo = CardRepository(str(SQLITE_PATH))
    try:
        deck_obj = _Deck.load(deck_path, repo=repo)
    except Exception as e:
        print(f"[red]Failed to load deck: {e}[/red]")
        raise typer.Exit(code=1)

    changes: Dict[str, List[str]] = {}

    if auto:
        from mtgcli.deckbuilder.card_profile import matched_tags
        from mtgcli.deckbuilder.plan_coverage import plan_coverage
        from mtgcli.deckbuilder.ramp_rules import land_matches_allowed_ramp_tags
        tag_defs = _json.load(open(_SD / "card_tags.json", encoding="utf-8"))
        covered = set()
        try:
            pc = plan_coverage(deck_obj.commanders[0]._row, [c._row | {"quantity": c.quantity}
                                                             for c in deck_obj.cards], tag_defs)
            covered = {n.lower() for n in (pc or {}).get("covered_cards", [])}
        except Exception:
            covered = set()
        for card in deck_obj.cards:
            adds = set()
            is_land = "land" in card.type_line.lower()
            for tag in matched_tags(card._row, tag_defs):
                p = _TAG_TO_PURPOSE.get(tag)
                if not p:
                    continue
                if p == "RAMP" and is_land and not land_matches_allowed_ramp_tags(card._row, tag_defs):
                    continue  # basics never count as ramp (the single-source rule)
                adds.add(p)
            if card.name.lower() in covered:
                adds.add("SYNERGY")
            new = [p for p in sorted(adds) if p not in card.purpose]
            if new:
                card.add_purposes(new)
                changes[card.name] = changes.get(card.name, []) + new

    if cards and (purpose_add or note):
        names = [n.strip() for n in cards.split(";") if n.strip()]
        targets = {n.lower() for n in names}
        found = {c.name.lower() for c in deck_obj.cards if c.name.lower() in targets}
        missing = [n for n in names if n.lower() not in found]
        if missing:
            _msg = "Not in deck (nothing annotated): " + ", ".join(missing)
            if json_output:
                _emit_json_error({"error": {"type": "validation", "message": _msg}})
            else:
                print(f"[red]{_msg}[/red]")
            raise typer.Exit(code=1)
        adds = [p.strip() for p in (purpose_add or "").split(",") if p.strip()]
        for card in deck_obj.cards:
            if card.name.lower() in targets:
                if adds:
                    new = [p.upper() for p in adds if p.upper() not in card.purpose]
                    if new:
                        card.add_purposes(new)
                        changes[card.name] = changes.get(card.name, []) + new
                if note:
                    card._agent_note = note

    synced = []
    if sync_notes:
        from mtgcli.deckbuilder.build_notes import combo_notes
        deck_names = {c.name.lower() for c in deck_obj.cards}
        existing = {frozenset(x.lower() for x in cb["cards_needed"])
                    for cls in deck_obj.combos.values() for cb in cls}
        for n in combo_notes():
            key = frozenset(c.lower() for c in n.get("cards", []))
            if key in existing:
                continue
            deck_obj.add_combo(n.get("combo_class", "non_infinite"),
                               n.get("cards", []), n.get("text", ""))
            synced.append(n.get("cards", []))
            for card in deck_obj.cards:
                if card.name.lower() in key and "COMBO_PIECE" not in card.purpose:
                    card.add_purposes(["COMBO_PIECE"])
                    changes[card.name] = changes.get(card.name, []) + ["COMBO_PIECE"]

    deck_obj.save(deck_path)
    unannotated = [c.name for c in deck_obj.cards if not c.purpose]
    result = {"changes": changes, "combos_synced": synced,
              "by_purpose": deck_obj.total_by_purpose(),
              "unannotated": unannotated}
    if json_output:
        print_json(result)
    else:
        print(f"[green]Annotated {len(changes)} card(s); {len(synced)} combo(s) synced.[/green]")
        for name, adds in list(changes.items())[:15]:
            print(f"  {name}: +{', '.join(adds)}")
        if len(changes) > 15:
            print(f"  ... +{len(changes) - 15} more")
        print(f"by purpose: {result['by_purpose']}")
        if unannotated:
            print(f"[yellow]unannotated ({len(unannotated)}): {', '.join(unannotated[:10])}"
                  + (" ..." if len(unannotated) > 10 else "") + "[/yellow]")


@app.command()
def deck_view(
    deck_path: Path = typer.Option(..., "--deck", help="Path to the annotated deck JSON"),
    card: Optional[str] = typer.Option(None, "--card", help="Show ONE card's build-facing summary (the CARD object print) instead of the deck"),
    by_purpose: bool = typer.Option(False, "--by-purpose", help="Group the list by purpose instead of Moxfield type order"),
    json_output: bool = typer.Option(False, "--json-output", help="Full deck dict + metrics as JSON"),
):
    """View the annotated DECK object: commanders, config, metrics (size, price,
    purposes, types, curve + score), combos, and the Moxfield-format list — or a
    single CARD's build summary with --card."""
    require_database(SQLITE_PATH, json_output)

    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    from mtgcli.models import Deck as _Deck

    repo = CardRepository(str(SQLITE_PATH))
    try:
        deck_obj = _Deck.load(deck_path, repo=repo)
    except Exception as e:
        print(f"[red]Failed to load deck: {e}[/red]")
        raise typer.Exit(code=1)

    if card:
        target = next((c for c in deck_obj.cards + deck_obj.commanders
                       if c.name.lower() == card.lower()), None)
        if target is None:
            _msg = f"'{card}' is not in this deck."
            if json_output:
                _emit_json_error({"error": {"type": "validation", "message": _msg}})
            else:
                print(f"[red]{_msg}[/red]")
            raise typer.Exit(code=1)
        if json_output:
            print_json({**target.to_dict(), "type_line": target.type_line,
                        "oracle_text": target.oracle_text, "mana_cost": target.mana_cost,
                        "usd_price": target.usd_price, "edhrec_rank": target.edhrec_rank,
                        "keywords": target.keywords, "produced_mana": target.produced_mana,
                        "loyalty": target.loyalty, "all_parts": target.all_parts,
                        "game_changer": target.game_changer})
        else:
            print(str(target))
        return

    metrics = {
        "size": deck_obj.size(), "max_size": deck_obj.max_size,
        "total_price": deck_obj.total_price(),
        "by_purpose": deck_obj.total_by_purpose(),
        "card_types": deck_obj.card_type_counts(),
        "mana_curve": deck_obj.mana_curve(),
        "mana_curve_score": deck_obj.mana_curve_score(),
    }
    if json_output:
        print_json({**deck_obj.to_dict(), "metrics": metrics})
        return

    cmds = " + ".join(c.name for c in deck_obj.commanders)
    print(f"[bold blue]{cmds}[/bold blue]")
    if deck_obj.agent_note:
        print(f"[dim]{deck_obj.agent_note}[/dim]")
    if deck_obj.config:
        print("config: " + ", ".join(f"{k}={v}" for k, v in deck_obj.config.items()))
    util = ""
    budget = deck_obj.config.get("budget")
    if budget:
        try:
            util = f" ({round(100 * metrics['total_price'] / float(budget), 1)}% of ${float(budget):.0f})"
        except (TypeError, ValueError):
            pass
    print(f"\n{metrics['size']}/{metrics['max_size']} cards — ${metrics['total_price']:.2f}{util}")
    print("by purpose: " + ", ".join(f"{k}={v}" for k, v in metrics["by_purpose"].items()))
    print(deck_obj.card_types())
    curve = " ".join(f"{k}:{v}" for k, v in metrics["mana_curve"].items())
    print(f"curve: {curve}  (score {metrics['mana_curve_score']})")

    combos_flat = [(cls, cb) for cls, lst in deck_obj.combos.items() for cb in lst]
    if combos_flat:
        print("\n[bold]Combos[/bold]")
        for cls, cb in combos_flat:
            how = f" — {cb['how_to']}" if cb.get("how_to") else ""
            print(f"  ({cls}) {', '.join(cb['cards_needed'])}{how}")

    print()
    if by_purpose:
        groups: Dict[str, List[str]] = {}
        for c in deck_obj.cards:
            key = c.purpose[0] if c.purpose else "UNANNOTATED"
            groups.setdefault(key, []).append(f"{c.quantity} {c.name}"
                                              + (f" [dim]({', '.join(c.purpose)})[/dim]"
                                                 if len(c.purpose) > 1 else ""))
        for key in sorted(groups):
            print(f"[bold]{key}[/bold] ({len(groups[key])})")
            for line in sorted(groups[key]):
                print(f"  {line}")
    else:
        print(str(deck_obj))
