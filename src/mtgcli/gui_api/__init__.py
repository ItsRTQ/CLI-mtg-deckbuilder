"""gui_api — the localhost FastAPI app behind `mtg gui` (v0.9.0).

Serves the JSON API under /api/* (reusing `mtgcli.core` services — never Typer)
and the built Vite frontend from FRONTEND_DIST at / when it exists.
"""
