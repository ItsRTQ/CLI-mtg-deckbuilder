import typer
from rich import print
from mtgcli.config import PROJECT_ROOT, RAW_CARDS_PATH
from mtgcli.data.download_cards import download_default_cards
from mtgcli.data.build_sqlite import build_sqlite_database

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
def card(name: str):
    """Lookup a card by name."""
    print(f"[yellow]card lookup not implemented yet: {name}[/yellow]")


@app.command()
def search(query: str):
    """Search for cards."""
    print(f"[yellow]search not implemented yet: {query}[/yellow]")


@app.command()
def validate():
    """Validate a deck file."""
    print("[yellow]validate command not implemented yet.[/yellow]")


@app.command()
def export():
    """Export a deck to Moxfield format."""
    print("[yellow]export command not implemented yet.[/yellow]")


if __name__ == "__main__":
    app()
