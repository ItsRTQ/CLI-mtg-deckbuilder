"""Card / price lookup commands: card, price, cards, cards-batch, prices,
prices-batch, budget.

Bodies split verbatim from the former monolithic ``cli.py``.
"""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _apply_max_price, _emit_json_error  # noqa: F401 -- underscore not re-exported by *

@app.command()
def card(
    name: str,
    json_output: bool = typer.Option(False, "--json-output", help="Output card data as JSON"),
    field: str = typer.Option(
        None, "--field",
        help="Print only this field's raw value (e.g. oracle_text, mana_cost, power). "
             "Skips JSON/rich formatting entirely; exits 1 with an error to stderr if the "
             "field doesn't exist on the card. Avoids piping through json.tool + grep.",
    ),
):
    """Lookup a card by exact name."""
    require_database(SQLITE_PATH, json_output)

    repo = CardRepository(str(SQLITE_PATH))
    card_data = repo.get_card_by_exact_name(name)

    if card_data:
        if field:
            if field not in card_data:
                print(f"[red]Unknown field '{field}'. Available: {', '.join(sorted(card_data))}[/red]")
                raise typer.Exit(code=1)
            value = card_data[field]
            # Raw value to stdout, no JSON quoting/escaping, no rich styling — pipe-friendly.
            print(value if value is not None else "")
            return
        if json_output:
            print_json(card_data)
        else:
            print(f"[bold blue]{card_data['name']}[/bold blue] {card_data['mana_cost']}")
            print(f"[italic]{card_data['type_line']}[/italic]")
            if has_power_toughness(card_data):
                p = card_data.get("power") or "?"
                t = card_data.get("toughness") or "?"
                print(f"Power/Toughness: {p}/{t}")
            print("-" * 20)
            print(card_data["oracle_text"])
            if card_data["usd_price"]:
                print(f"[green]Price: ${card_data['usd_price']}[/green]")
    else:
        suggestions = repo.suggest_similar_names(name, limit=5)
        if field or json_output:
            print_json({
                "name": name,
                "found": False,
                "suggestions": [s["name"] for s in suggestions],
            })
            raise typer.Exit(code=1)
        print(f"[red]No exact match found for '{name}'.[/red]")
        if suggestions:
            print("[yellow]Did you mean:[/yellow]")
            for s in suggestions:
                print(f" - {s['name']}")



@app.command()
def price(
    name: str,
    json_output: bool = typer.Option(False, "--json-output", help="Output price data as JSON"),
):
    """Look up local Scryfall price data for a card."""
    require_database(SQLITE_PATH, json_output)

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
        print_json(result)
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
    require_database(SQLITE_PATH, json_output)

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
        print_json(results)
    else:
        for r in results:
            if r.get("found"):
                print(f"[bold blue]{r['name']}[/bold blue] {r.get('mana_cost', '')} | {r.get('type_line', '')}")
            else:
                print(f"[red]Not found: {r['name']}[/red]")



@app.command()
def cards_batch(
    input_path: Path = typer.Argument(..., help="Path to deck JSON or .txt decklist"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
    verify: bool = typer.Option(False, "--verify", help="Only report names that weren't found (with suggestions) and exit non-zero if any are missing. No inline scripting needed to validate a drafted list."),
):
    """Look up all cards in a deck JSON or .txt decklist."""
    require_database(SQLITE_PATH, json_output)

    if not input_path.exists():
        print(f"[red]File not found: {input_path}[/red]")
        raise typer.Exit(code=1)

    try:
        deck_entries = load_deck_file(input_path)["main_deck"]
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

    if verify:
        missing = [r for r in results if not r.get("found")]
        if json_output:
            print_json({
                "total_entries": len(results),
                "found_count": len(results) - len(missing),
                "not_found_count": len(missing),
                "not_found": [
                    {"name": r["name"], "suggestions": [s["name"] for s in repo.suggest_similar_names(r["name"], limit=3)]}
                    for r in missing
                ],
            })
        else:
            print(f"{len(results)} entries, {len(missing)} not found.")
            for r in missing:
                sugg = [s["name"] for s in repo.suggest_similar_names(r["name"], limit=3)]
                hint = f"  (did you mean: {', '.join(sugg)}?)" if sugg else ""
                print(f"  [red]NOT FOUND:[/red] {r['name']}{hint}")
        if missing:
            raise typer.Exit(code=1)
        return

    if json_output:
        print_json(results)
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
    require_database(SQLITE_PATH, json_output)

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
        print_json(results)
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
    input_path: Optional[Path] = typer.Argument(None, help="Path to deck JSON or .txt decklist"),
    names: Optional[List[str]] = typer.Option(None, "--name", help="Card name to price; repeatable — cost hand-picked candidates BEFORE they join a list (no file needed)"),
    json_output: bool = typer.Option(False, "--json-output", help="Output as JSON"),
):
    """Look up prices for cards in a deck file, and/or for ad-hoc names via --name.

    The --name mode exists so package allocation can be costed AT PICK TIME
    (full build #3 friction: hand-picked staples were summed on memory prices).
    Human output ends with a known-price TOTAL in both modes. JSON stays a plain
    list in file mode (backward compatible); with --name it returns
    {"results": [...], "known_total": X, "unknown_count": N, "not_found_count": N}.
    """
    require_database(SQLITE_PATH, json_output)

    if input_path is None and not names:
        _msg = "Provide a deck file or at least one --name."
        if json_output:
            _emit_json_error({"error": {"type": "validation", "message": _msg}})
        else:
            print(f"[red]{_msg}[/red]")
        raise typer.Exit(code=1)

    deck_entries = []
    if input_path is not None:
        if not input_path.exists():
            print(f"[red]File not found: {input_path}[/red]")
            raise typer.Exit(code=1)
        try:
            deck_entries = list(load_deck_file(input_path)["main_deck"])
        except Exception as e:
            print(f"[red]Failed to read deck file: {e}[/red]")
            raise typer.Exit(code=1)
    deck_entries += [{"name": n, "quantity": 1} for n in (names or [])]

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
            not_found = {
                "name": name,
                "found": False,
                "quantity": entry.get("quantity", 1) if isinstance(entry, dict) else 1,
                "usd_price": None,
                "price_status": "not_found",
            }
            # Ad-hoc names are typed by hand — offer the same fuzzy suggestions as `card`.
            # suggest_similar_names returns dicts; only "name" is guaranteed.
            if names and name in names:
                not_found["suggestions"] = [s["name"] for s in repo.suggest_similar_names(name)]
            results.append(not_found)

    known_total = 0.0
    unknown_count = 0
    not_found_count = 0
    for r in results:
        if not r.get("found"):
            not_found_count += 1
        elif r["usd_price"] is None:
            unknown_count += 1
        else:
            try:
                known_total += float(r["usd_price"]) * r.get("quantity", 1)
            except (TypeError, ValueError):
                unknown_count += 1
    known_total = round(known_total, 2)

    if json_output:
        if names:
            print_json({"results": results, "known_total": known_total,
                        "unknown_count": unknown_count, "not_found_count": not_found_count})
        else:
            print_json(results)
    else:
        for r in results:
            qty = r.get("quantity", 1)
            if not r.get("found"):
                sug = f"  [yellow]did you mean: {', '.join(r['suggestions'])}?[/yellow]" if r.get("suggestions") else ""
                print(f"[red]{qty}x {r['name']}: not found[/red]{sug}")
            elif r["usd_price"] is not None:
                print(f"{qty}x {r['name']}: [green]${r['usd_price']}[/green]")
            else:
                print(f"{qty}x {r['name']}: [yellow]unknown price[/yellow]")
        tail = []
        if unknown_count:
            tail.append(f"{unknown_count} unknown")
        if not_found_count:
            tail.append(f"{not_found_count} not found")
        extra = f" ({', '.join(tail)})" if tail else ""
        print(f"[bold]Known-price total: ${known_total:.2f}[/bold]{extra}")



@app.command()
def budget(
    deck_path: Path = typer.Argument(..., help="Path to deck JSON or .txt decklist"),
    budget_limit: Optional[float] = typer.Option(None, "--budget", help="Budget maximum in USD (e.g. 500)"),
    overage: float = typer.Option(10.0, "--overage", help="Allowed overage percent above budget limit (default 10)"),
    by_card: bool = typer.Option(False, "--by-card", help="Show per-card price breakdown, most expensive first (no inline scripting needed)"),
    top: int = typer.Option(15, "--top", help="With --by-card, how many of the most expensive cards to show (0 = all)"),
    high_cost_pct: float = typer.Option(0.20, "--high-cost-pct", help="Flag single cards whose cost exceeds this fraction of the budget (default 0.20 = 20%)"),
    json_output: bool = typer.Option(False, "--json-output", help="Output budget summary as JSON"),
    strict: bool = typer.Option(False, "--strict", help="Fail if any card has unknown price"),
):
    """Summarize deck budget using local Scryfall price data."""
    require_database(SQLITE_PATH, json_output)

    if not deck_path.exists():
        print(f"[red]Deck file not found: {deck_path}[/red]")
        raise typer.Exit(code=1)

    repo = CardRepository(str(SQLITE_PATH))
    deck_entries = load_deck_file(deck_path)["main_deck"]

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

    summary = build_budget_summary(
        hydrated, budget_limit=budget_limit, overage_percent=overage, high_cost_pct=high_cost_pct
    )

    if strict and summary["unknown_price_cards_count"] > 0:
        summary["strict_mode_failed"] = True
        summary["strict_mode_reason"] = (
            f"{summary['unknown_price_cards_count']} card(s) have unknown price."
        )

    if json_output:
        print_json(summary)
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
        # AF-4: flag single cards eating a big chunk of the budget.
        high = summary.get("high_cost_cards") or []
        if high:
            print(f"[yellow]High-cost cards (>= {int(high_cost_pct*100)}% of budget):[/yellow]")
            for c in high:
                print(f"  - {c['name']}  ${c['line_total']} ({c['pct_of_budget']}% of budget)")
        if by_card:
            rows = summary["breakdown"]
            shown = rows if top <= 0 else rows[:top]
            print(f"[bold]Most expensive cards{'' if top<=0 else f' (top {len(shown)})'}:[/bold]")
            for c in shown:
                qty = f"{c['quantity']}x " if c["quantity"] != 1 else ""
                print(f"  ${c['line_total']:>7.2f}  {qty}{c['name']}")
        if budget_limit is not None and summary.get("note"):
            print(f"[dim]{summary['note']}[/dim]")
        if strict and summary.get("strict_mode_failed"):
            print(f"[red]Strict mode: {summary['strict_mode_reason']}[/red]")
            raise typer.Exit(code=1)


