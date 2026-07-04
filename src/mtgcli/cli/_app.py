"""The single central Typer application.

Command modules import ``app`` from here and attach their ``@app.command()``
handlers. Keeping the app in its own tiny module (with no heavy imports) lets
every command module and ``_shared`` reference the same instance without a
circular import.
"""
import typer

app = typer.Typer(help="Local MTG Commander deckbuilding CLI.")
