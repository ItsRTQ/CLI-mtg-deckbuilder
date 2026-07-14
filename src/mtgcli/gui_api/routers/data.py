"""Data endpoints: the Download DB / Reload DB button's backend (background job)."""
import threading
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mtgcli.config import SQLITE_PATH
from mtgcli.core import data_refresh

router = APIRouter()


class DataJobOut(BaseModel):
    running: bool = False
    mode: Optional[str] = None       # "download" | "full"
    phase: Optional[str] = None
    elapsed_seconds: int = 0
    error: Optional[str] = None
    finished: bool = False


def _state(request: Request) -> Dict[str, Any]:
    st = getattr(request.app.state, "data_job", None)
    if st is None:
        st = {"running": False, "mode": None, "phase": None, "started_at": 0.0,
              "error": None, "finished": False}
        request.app.state.data_job = st
    return st


def data_refresh_running(request: Request) -> bool:
    return bool(getattr(request.app.state, "data_job", {}).get("running"))


def _out(st: Dict[str, Any]) -> DataJobOut:
    return DataJobOut(
        running=st["running"], mode=st["mode"], phase=st["phase"],
        elapsed_seconds=int(time.monotonic() - st["started_at"]) if st["running"] else 0,
        error=st["error"], finished=st["finished"],
    )


@router.get("/data/refresh", response_model=DataJobOut)
def refresh_status(request: Request) -> DataJobOut:
    return _out(_state(request))


@router.post("/data/refresh", status_code=202, response_model=DataJobOut)
def start_refresh(request: Request) -> DataJobOut:
    st = _state(request)
    if st["running"]:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "conflict", "message": "A data refresh is already running."}})

    # Never rebuild the DB under a live agent build — it reads that database.
    from mtgcli.gui_api.jobs import TERMINAL
    registry = getattr(request.app.state, "job_registry", None)
    if registry is not None and any(j.status not in TERMINAL for j in registry.list()):
        raise HTTPException(status_code=409, detail={"error": {
            "type": "conflict",
            "message": "A deck build is running — wait for it (or stop it) before "
                       "refreshing the card database."}})

    mode = "full" if SQLITE_PATH.exists() else "download"
    st.update(running=True, mode=mode, phase="starting",
              started_at=time.monotonic(), error=None, finished=False)

    def _run():
        try:
            data_refresh.refresh_data(
                full=(mode == "full"),
                on_phase=lambda msg: st.__setitem__("phase", msg))
            st.update(running=False, phase="done", finished=True)
        except Exception as e:
            st.update(running=False, error=f"{type(e).__name__}: {e}",
                      phase="failed", finished=True)

    threading.Thread(target=_run, daemon=True).start()
    return _out(st)
