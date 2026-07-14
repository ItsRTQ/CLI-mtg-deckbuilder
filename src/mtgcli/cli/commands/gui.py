"""GUI command: start the localhost FastAPI server and open the browser (v0.9.0)."""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _emit_json_error  # noqa: F401 -- underscore not re-exported by *


@app.command()
def gui(
    host: str = typer.Option("127.0.0.1", "--host", help="Interface to bind (localhost by default)"),
    port: int = typer.Option(8321, "--port", help="Port for the GUI server"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open the web browser automatically"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit the server config as JSON on startup (the server still runs until Ctrl+C)"),
):
    """Start the local GUI: serves the web app + JSON API on http://HOST:PORT and
    opens your browser. The GUI is a prep-and-launch surface — deck builds are run
    by YOUR OWN AI agent (configured in Settings), never by a model shipped here.

    Blocks until stopped with Ctrl+C. For API-only use (or headless), pass
    --no-browser; the API lives under /api (docs at /api/docs)."""
    import threading
    import webbrowser

    import uvicorn

    from mtgcli.gui_api.app import create_app

    url = f"http://{host}:{port}/"
    if not no_browser:
        # Arm before the blocking server run; 1.5s is enough for uvicorn to bind.
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    if json_output:
        print_json({"serving": url, "host": host, "port": port, "api_docs": f"{url}api/docs"})
    else:
        print(f"[bold blue]mtg gui[/bold blue] — serving on [green]{url}[/green] (Ctrl+C to stop)")
    try:
        uvicorn.run(create_app(), host=host, port=port,
                    log_level="warning" if json_output else "info")
    except OSError as e:
        msg = (f"Could not bind {host}:{port} — {e}. "
               f"Is another `mtg gui` running? Try --port <other>.")
        if json_output:
            _emit_json_error({"error": {"type": "environment", "message": msg}})
        else:
            print(f"[red]{msg}[/red]")
        raise typer.Exit(code=1)
