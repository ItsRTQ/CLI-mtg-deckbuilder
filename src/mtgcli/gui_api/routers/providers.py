"""Provider endpoints: detection list + selection (in-memory, localhost single-user)."""
import time
from dataclasses import asdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mtgcli.core.providers import ProviderManager

router = APIRouter()

_CACHE_SECONDS = 30


class ProviderOut(BaseModel):
    name: str
    installed: bool
    version: Optional[str] = None
    detail: Optional[str] = None
    supports_build: bool = False
    selected: bool = False


class SelectIn(BaseModel):
    name: str


def get_manager(request: Request) -> ProviderManager:
    mgr = getattr(request.app.state, "provider_manager", None)
    if mgr is None:
        mgr = ProviderManager()
        request.app.state.provider_manager = mgr
    return mgr


def _detect_cached(request: Request, mgr: ProviderManager):
    cached = getattr(request.app.state, "provider_cache", None)
    if cached and time.monotonic() - cached[0] < _CACHE_SECONDS:
        return cached[1]
    infos = mgr.detect_all()
    request.app.state.provider_cache = (time.monotonic(), infos)
    return infos


def selected_provider(request: Request, mgr: ProviderManager) -> Optional[str]:
    sel = getattr(request.app.state, "selected_provider", None)
    return sel or mgr.default_build_provider()


@router.get("/providers", response_model=List[ProviderOut])
def list_providers(request: Request) -> List[ProviderOut]:
    mgr = get_manager(request)
    sel = selected_provider(request, mgr)
    return [ProviderOut(**asdict(i), selected=(i.name == sel))
            for i in _detect_cached(request, mgr)]


@router.post("/providers/select", response_model=List[ProviderOut])
def select_provider(body: SelectIn, request: Request) -> List[ProviderOut]:
    mgr = get_manager(request)
    provider = mgr.get(body.name)
    if provider is None:
        raise HTTPException(status_code=404, detail={"error": {
            "type": "validation", "message": f"Unknown provider: {body.name}"}})
    info = provider.detect()
    if not info.installed:
        raise HTTPException(status_code=409, detail={"error": {
            "type": "environment",
            "message": f"Provider '{body.name}' is not installed ({info.detail})."}})
    # Detection-only providers ARE selectable (the user owns the choice); the
    # build endpoint is the gate that refuses to BUILD with one (409 there).
    request.app.state.selected_provider = body.name
    return list_providers(request)
