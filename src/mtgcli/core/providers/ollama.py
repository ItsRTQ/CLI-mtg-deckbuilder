"""OllamaProvider — DETECTION-ONLY in v0.9.0 (an Ollama model has no tool-calling
harness to drive the mtg CLI; building through it is a later milestone)."""
import shutil
import threading
from pathlib import Path
from typing import Optional

import requests

from mtgcli.core.providers.base import (
    AgentProvider,
    ProviderBuildUnsupported,
    ProviderInfo,
    ProviderResult,
)

_TAGS_URL = "http://127.0.0.1:11434/api/tags"


class OllamaProvider(AgentProvider):
    name = "ollama"
    supports_build = False

    def detect(self) -> ProviderInfo:
        exe = shutil.which("ollama")
        if not exe:
            return ProviderInfo(name=self.name, installed=False,
                                detail="`ollama` not found on PATH")
        detail = "installed; server not running"
        try:
            r = requests.get(_TAGS_URL, timeout=2)
            models = [m.get("name") for m in r.json().get("models", [])]
            detail = f"server up — models: {', '.join(models) or 'none pulled'}"
        except Exception:
            pass
        return ProviderInfo(name=self.name, installed=True,
                            detail=f"{detail} (detection-only in v0.9.0)")

    def build(self, workspace: Path, prompt_file: Path, *, timeout: int,
              cancel_event: Optional[threading.Event] = None) -> ProviderResult:
        raise ProviderBuildUnsupported(
            "Ollama is detection-only in v0.9.0 — select a build-capable provider "
            "(claude-code).")
