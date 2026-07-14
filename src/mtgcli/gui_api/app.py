"""FastAPI app factory for the localhost GUI.

Run in dev with:  uvicorn --factory mtgcli.gui_api.app:create_app --reload
Run for real with:  mtg gui
"""
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from mtgcli.config import FRONTEND_DIST

_FRONTEND_HINT = {
    "message": "frontend not built — run `npm --prefix gui install && "
               "npm --prefix gui run build`, or use `npm --prefix gui run dev` "
               "against this API",
    "api": "/api/health",
}


def create_app() -> FastAPI:
    app = FastAPI(title="mtg gui", docs_url="/api/docs", openapi_url="/api/openapi.json")

    from mtgcli.gui_api.routers import (builds, cards, data, library, providers,
                                        settings, system)
    app.include_router(system.router, prefix="/api")
    app.include_router(cards.router, prefix="/api")
    app.include_router(providers.router, prefix="/api")
    app.include_router(builds.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(library.router, prefix="/api")
    app.include_router(data.router, prefix="/api")

    if FRONTEND_DIST.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"),
                  name="assets")

        # SPA fallback: any non-/api path serves index.html so client-side
        # routes (/results, /settings...) survive deep links and reloads.
        # Unknown /api/* paths stay JSON 404s — never HTML.
        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": {
                    "type": "usage", "message": f"Unknown API path: /{full_path}"}})
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def frontend_hint():
            return JSONResponse(_FRONTEND_HINT)

    return app
