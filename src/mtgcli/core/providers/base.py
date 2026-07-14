"""Provider interface — generic, never agent-vendor-specific."""
import os
import signal
import subprocess
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

LOG_TAIL_LINES = 30


def tail_log(log_path: Path, n: int = LOG_TAIL_LINES) -> List[str]:
    try:
        return log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def kill_process_group(proc: "subprocess.Popen") -> None:
    """Kill the agent AND its subprocesses (it spawns mtg commands); killpg is
    POSIX-only — guarded for Windows-someday."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:  # pragma: no cover - Windows path
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


class ProviderBuildUnsupported(RuntimeError):
    """Raised by providers that can detect but not build (Ollama in v0.9.0)."""


@dataclass
class ProviderInfo:
    name: str
    installed: bool
    version: Optional[str] = None
    detail: Optional[str] = None
    supports_build: bool = False


@dataclass
class ProviderResult:
    """Outcome of a headless build INVOCATION. The provider's stdout/stderr are
    logs/debug ONLY — build success is judged by the workspace's output files
    (output/final_deck.json + output/explanation.md), never by this object alone."""
    ok: bool                    # process ran to completion with exit code 0
    exit_code: int
    error: Optional[str] = None            # timeout / cancelled / spawn failure
    log_tail: List[str] = field(default_factory=list)  # last lines of logs/build.log


class AgentProvider(ABC):
    name: str = "abstract"
    supports_build: bool = False

    @abstractmethod
    def detect(self) -> ProviderInfo:
        """Is the provider's CLI installed? Version/status if so. Never raises."""

    @abstractmethod
    def build(self, workspace: Path, prompt_file: Path, *, timeout: int,
              cancel_event: Optional[threading.Event] = None) -> ProviderResult:
        """Run the agent headlessly with cwd=workspace until it exits, the timeout
        elapses, or cancel_event is set. Streams output to workspace/logs/build.log."""
