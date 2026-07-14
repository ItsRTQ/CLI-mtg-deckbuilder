"""Build endpoints: POST /api/builds, GET /api/builds/{job_id}, POST .../cancel."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mtgcli.cards.repository import CardRepository
from mtgcli.gui_api.deps import get_repo
from mtgcli.gui_api.jobs import TERMINAL, Job, JobRegistry
from mtgcli.gui_api.routers.providers import get_manager, selected_provider

router = APIRouter()


class BuildRequest(BaseModel):
    commander: str
    partner: Optional[str] = None
    budget: Optional[str] = None       # "150" | "n/a"
    bracket: Optional[str] = None      # "1-2" | "3" | "4-5" | "n/a"
    rank_target: Optional[str] = None  # "1".."7" | "n/a"
    theme: Optional[str] = None
    notes: Optional[str] = None
    use_bulk: bool = True              # owned cards cost $0 (uncheck = full prices)
    provider: Optional[str] = None     # default: the selected/detected provider
    timeout_seconds: int = Field(900, ge=60, le=3600)


class JobStatusOut(BaseModel):
    job_id: str
    status: str
    phase: str
    elapsed_seconds: int
    provider: str
    workspace: str
    log_tail: List[str] = []
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class JobSummaryOut(BaseModel):
    job_id: str
    status: str
    phase: str
    elapsed_seconds: int
    provider: str
    commander: str


def get_registry(request: Request) -> JobRegistry:
    reg = getattr(request.app.state, "job_registry", None)
    if reg is None:
        reg = JobRegistry()
        request.app.state.job_registry = reg
    return reg


def _job_out(job: Job) -> JobStatusOut:
    return JobStatusOut(
        job_id=job.id, status=job.status, phase=job.phase,
        elapsed_seconds=job.elapsed_seconds, provider=job.provider_name,
        workspace=str(job.workspace), log_tail=job.log_tail(),
        result=job.result, error=job.error,
    )


@router.post("/builds", status_code=202)
def start_build(body: BuildRequest, request: Request,
                repo: CardRepository = Depends(get_repo)) -> Dict[str, str]:
    # No builds while the card database is being rebuilt under us.
    from mtgcli.gui_api.routers.data import data_refresh_running
    if data_refresh_running(request):
        raise HTTPException(status_code=409, detail={"error": {
            "type": "conflict",
            "message": "The card database is being refreshed — wait for it to "
                       "finish before starting a build."}})

    # ONE build at a time: a second concurrent agent build would fight the first
    # for the provider/quota. The UI locks the wizard; this is the actual gate.
    registry = get_registry(request)
    running = next((j for j in registry.list() if j.status not in TERMINAL), None)
    if running is not None:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "conflict",
            "message": f"A build is already running ({running.request.get('commander', '?')}) "
                       "— wait for it to finish or cancel it from Results.",
            "job_id": running.id,
        }})

    # Input preflight (deterministic checks only — never a fallback build).
    card = repo.get_card_by_exact_name(body.commander)
    if card is None:
        suggestions = [s.get("name") for s in repo.suggest_similar_names(body.commander, limit=5)]
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": f"Commander not found: {body.commander}",
            "suggestions": suggestions,
        }})
    if not card.get("can_be_commander"):
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation",
            "message": f"'{card['name']}' can't be your commander per the local data. "
                       "If you believe it can, verify and extend commander_overrides.json "
                       "(BUILDER §7.0).",
        }})

    mgr = get_manager(request)
    provider_name = body.provider or selected_provider(request, mgr)
    provider = mgr.get(provider_name) if provider_name else None
    if provider is None:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": "No provider selected — configure one in Settings.",
        }})
    if not provider.supports_build:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "validation",
            "message": f"'{provider_name}' is detection-only in this version and "
                       "can't build yet — switch to a build-capable provider "
                       "(claude-code) in Settings.",
        }})
    info = provider.detect()
    if not info.installed:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": f"Provider '{provider_name}' is not installed ({info.detail}).",
        }})

    payload = body.model_dump()
    payload["commander"] = card["name"]  # canonical DB name into the contract
    job = get_registry(request).create(payload, provider)
    return {"job_id": job.id, "status_url": f"/api/builds/{job.id}"}


@router.get("/builds", response_model=List[JobSummaryOut])
def list_builds(request: Request) -> List[JobSummaryOut]:
    """All build jobs, newest first. Builds run SERVER-SIDE — this is how the UI
    finds a running build again after a route change or page reload."""
    return [
        JobSummaryOut(job_id=j.id, status=j.status, phase=j.phase,
                      elapsed_seconds=j.elapsed_seconds, provider=j.provider_name,
                      commander=j.request.get("commander", "?"))
        for j in get_registry(request).list()
    ]


@router.get("/builds/{job_id}", response_model=JobStatusOut)
def job_status(job_id: str, request: Request) -> JobStatusOut:
    job = get_registry(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {
            "type": "validation", "message": f"Unknown build job: {job_id}"}})
    return _job_out(job)


@router.post("/builds/{job_id}/cancel", response_model=JobStatusOut)
def cancel_job(job_id: str, request: Request) -> JobStatusOut:
    job = get_registry(request).cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {
            "type": "validation", "message": f"Unknown build job: {job_id}"}})
    return _job_out(job)
