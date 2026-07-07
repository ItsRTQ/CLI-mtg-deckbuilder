"""The ``mtg`` CLI, split from a former single ``cli.py`` module into a package.

Importing this package builds the Typer ``app`` and registers every command (by
importing the command modules), then exposes the console entry point ``main`` /
``_run_app`` plus the small public surface the test suite imports (``app``,
``has_power_toughness``, ``print_json``) and the symbols historically patched
(``SQLITE_PATH``, ``CardRepository`` — now owned by the command modules that
use them).

The entry point ``mtg = mtgcli.cli:main`` and ``python -m mtgcli.cli`` (via
``__main__.py``) both resolve to :func:`main` below.
"""
from mtgcli.cli._app import app
from mtgcli.cli._shared import (
    print_json,
    has_power_toughness,
    _apply_max_price,
    _emit_json_error,
    SQLITE_PATH,
    CardRepository,
)

# Importing each command module runs its @app.command() decorators, registering
# the commands on the shared app. Order does not affect behavior (Click lists
# commands alphabetically in --help).
from mtgcli.cli.commands import (  # noqa: E402,F401 -- imported for registration side effect
    data,
    search,
    cards,
    deck,
    analysis,
    misc,
)

# Typer lists commands in registration order, which the functional split above
# changes (commands now register grouped by module). Restore the exact order the
# former single-file cli.py produced so ``mtg --help`` output is unchanged.
_COMMAND_ORDER = [
    "status", "init_data", "card", "search", "search_tags", "suggest",
    "commander_analyze", "validate", "deck_write", "deck_fill_lands", "enrich",
    "export", "suggest_lands", "deck_check", "themes", "theme_info",
    "temp_clean", "final_build", "price", "cards", "cards_batch", "prices",
    "prices_batch", "budget", "category_counts", "deck_swap",
    "preflight", "similar", "complements", "deck_gaps", "analyze_card", "report",
]
_ORDER_INDEX = {name: i for i, name in enumerate(_COMMAND_ORDER)}
app.registered_commands.sort(
    key=lambda c: _ORDER_INDEX.get(c.callback.__name__, len(_COMMAND_ORDER))
)


# ── entry point + JSON error boundary (moved verbatim from the former cli.py) ─
# (_emit_json_error now lives in _shared.py: command modules call it too — the
# search family's --type validation error — so it must be importable by them.)

def _run_app() -> None:
    """Run the Typer app. When ``--json-output`` is on the command line, EVERY error —
    usage errors (bad flag/command, with Click's did-you-mean suggestions), our own
    validation aborts, and unexpected crashes — is emitted as structured JSON on stdout
    so an agent's parser never breaks on a Rich panel. Without the flag, behavior is
    unchanged (human-friendly panels)."""
    import sys as _sys
    if "--json-output" not in _sys.argv:
        app()
        return
    import json as _json
    import click as _click
    try:
        rv = app(standalone_mode=False)
        # click SWALLOWS typer.Exit/click.Exit when standalone_mode=False and
        # RETURNS the exit code instead of raising (click.core.Command.main:
        # `except Exit: ... return e.exit_code`). Without propagating it, every
        # `raise typer.Exit(1)` under --json-output exited 0 — breaking the
        # documented contract (card not-found exits 1, cards-batch --verify
        # exits non-zero). The `except Exit` below stays as a defensive guard.
        if isinstance(rv, int) and rv != 0:
            raise SystemExit(rv)
    except _click.exceptions.Abort:
        raise SystemExit(1)
    except _click.exceptions.Exit as e:
        raise SystemExit(e.exit_code)
    except _click.UsageError as e:
        _emit_json_error({"error": {"type": "usage", "message": e.format_message()}})
        raise SystemExit(e.exit_code if hasattr(e, "exit_code") else 2)
    except _click.ClickException as e:
        _emit_json_error({"error": {"type": "cli", "message": e.format_message()}})
        raise SystemExit(e.exit_code)
    except SystemExit:
        raise
    except Exception as e:  # crash boundary: never a raw traceback in JSON mode
        _cls = type(e).__name__
        _kind = "usage" if ("UsageError" in _cls or "NoSuch" in _cls or "Missing" in _cls
                            or "BadParameter" in _cls) else "internal"
        _msg = e.format_message() if hasattr(e, "format_message") else str(e)
        _emit_json_error({"error": {"type": _kind, "exception": _cls, "message": _msg}})
        raise SystemExit(1)


def main() -> None:
    """Console entry point. Transparently handles a global ``--log`` flag (usable on ANY command,
    e.g. ``mtg search --colors G --log``) by capturing the command's output into the on-going
    audit log, then delegating to the Typer app. Strips ``--log`` before Typer sees it so no
    individual command needs to declare it."""
    import sys as _sys
    from io import StringIO

    if "--log" not in _sys.argv:
        _run_app()
        return

    from mtgcli.logging_util import append_log, _Tee

    original_args = list(_sys.argv[1:])
    full_command = "mtg " + " ".join(original_args)
    # the command name is the first non-option token
    command = next((a for a in original_args if not a.startswith("-")), "")
    # remove --log so Typer (whose commands don't declare it) doesn't error
    _sys.argv = [a for a in _sys.argv if a != "--log"]

    real_stdout = _sys.stdout
    buffer = StringIO()
    _sys.stdout = _Tee(real_stdout, buffer)
    exit_code = 0
    try:
        _run_app()
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (0 if e.code in (None, "") else 1)
        raise
    finally:
        _sys.stdout = real_stdout
        # don't log the `report` command into the very log it is consolidating
        if command != "report":
            append_log(command, full_command, buffer.getvalue(), exit_code)
