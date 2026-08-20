"""GUI command: start the localhost FastAPI server and open the browser (v0.9.0)."""
from mtgcli.cli._shared import *  # noqa: F401,F403 -- shared imports, helpers, app
from mtgcli.cli._shared import _emit_json_error  # noqa: F401 -- underscore not re-exported by *


@app.command()
def gui(
    host: str = typer.Option("127.0.0.1", "--host", help="Interface to bind (localhost by default)"),
    port: int = typer.Option(8321, "--port", help="Port for the GUI server"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open the web browser automatically"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Rebuild the frontend bundle (npm run build) before serving — needed after frontend code changes"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit the server config as JSON on startup (the server still runs until Ctrl+C)"),
):
    """Start the local GUI: serves the web app + JSON API on http://HOST:PORT and
    opens your browser. The GUI is a prep-and-launch surface — deck builds are run
    by YOUR OWN AI agent (configured in Settings), never by a model shipped here.

    Blocks until stopped with Ctrl+C. For API-only use (or headless), pass
    --no-browser; the API lives under /api (docs at /api/docs).

    The web app is served from the PRE-BUILT bundle (gui/dist) — restarting the
    server does NOT pick up frontend source changes; pass --rebuild for that."""
    import threading
    import webbrowser

    import uvicorn

    from mtgcli.gui_api.app import create_app

    if rebuild:
        import shutil
        import subprocess

        from mtgcli.config import FRONTEND_DIST

        gui_dir = FRONTEND_DIST.parent
        npm = shutil.which("npm")
        if npm is None or not (gui_dir / "package.json").exists():
            msg = ("Cannot rebuild the frontend: "
                   + ("npm not found on PATH" if npm is None
                      else f"no package.json in {gui_dir}") + ".")
            if json_output:
                _emit_json_error({"error": {"type": "environment", "message": msg}})
            else:
                print(f"[red]{msg}[/red]")
            raise typer.Exit(code=1)
        if not json_output:
            print(f"[bold blue]mtg gui[/bold blue] — rebuilding frontend ({gui_dir})…")
        built = subprocess.run([npm, "run", "build"], cwd=gui_dir)
        if built.returncode != 0:
            msg = "Frontend build failed — see npm output above."
            if json_output:
                _emit_json_error({"error": {"type": "environment", "message": msg}})
            else:
                print(f"[red]{msg}[/red]")
            raise typer.Exit(code=1)
        if not json_output:
            print("[green]Frontend rebuilt.[/green]")

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
