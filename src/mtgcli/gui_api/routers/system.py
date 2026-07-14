"""System endpoints: /api/health (liveness) and /api/status (project status)."""
from importlib import metadata

from fastapi import APIRouter

from mtgcli.core.status import project_status
from mtgcli.gui_api.schemas import HealthOut, ProjectStatusOut

router = APIRouter()


def _version() -> str:
    try:
        return metadata.version("cli-mtg-deckbuilder")
    except metadata.PackageNotFoundError:
        return "unknown"


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=_version())


@router.get("/status", response_model=ProjectStatusOut)
def status() -> ProjectStatusOut:
    return ProjectStatusOut(**project_status())
