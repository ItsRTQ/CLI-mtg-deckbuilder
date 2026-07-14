"""AntigravityProvider — headless builds via Google's Antigravity CLI (`agy`).

Promoted to build-capable (2026-07-10) after measuring its headless model live:
- `agy -p "<prompt>"` runs non-interactively and EXECUTES terminal commands and
  file writes WITHOUT `--dangerously-skip-permissions` (measured: bash echo,
  file write, and a real `mtg card` lookup all ran headless, exit 0).
- CRITICAL quirk: print mode does NOT honor the process cwd — relative paths land
  in agy's own scratch (~/.gemini/antigravity-cli/scratch). The fix, also
  measured: pass the job workspace via `--add-dir <workspace>` AND use ABSOLUTE
  workspace paths in the prompt (the shared template does since v0.9.1).
- `--print-timeout` defaults to 5m — far too short for a deck build; set from the
  job's timeout.
"""
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from mtgcli.core.providers.base import (
    AgentProvider,
    ProviderInfo,
    ProviderResult,
    kill_process_group,
    tail_log,
)

_POLL_SECONDS = 0.5


class AntigravityProvider(AgentProvider):
    name = "antigravity"
    supports_build = True

    def detect(self) -> ProviderInfo:
        exe = shutil.which("agy")
        if not exe:
            return ProviderInfo(name=self.name, installed=False,
                                detail="`agy` (Antigravity CLI) not found on PATH",
                                supports_build=True)
        version = None
        try:
            out = subprocess.run(["agy", "--version"], capture_output=True,
                                 text=True, timeout=10)
            raw = (out.stdout or out.stderr).strip()
            version = raw.splitlines()[0] if raw else None
        except (subprocess.TimeoutExpired, OSError):
            pass  # installed is still true — version is best-effort
        return ProviderInfo(name=self.name, installed=True, version=version,
                            detail=exe, supports_build=True)

    def build(self, workspace: Path, prompt_file: Path, *, timeout: int,
              cancel_event: Optional[threading.Event] = None,
              unsafe_skip_permissions: bool = False) -> ProviderResult:
        log_dir = workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "build.log"

        # --add-dir is REQUIRED: agy print mode ignores cwd, so the workspace must
        # be granted explicitly (and the prompt uses absolute paths inside it).
        # --print-timeout must cover the whole build (default 5m is too short).
        argv = ["agy", "--add-dir", str(workspace),
                "-p", prompt_file.read_text(encoding="utf-8"),
                "--print-timeout", f"{timeout}s"]
        if unsafe_skip_permissions:
            argv.append("--dangerously-skip-permissions")

        try:
            with open(log_path, "ab") as log:
                proc = subprocess.Popen(
                    argv, cwd=workspace, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                deadline = time.monotonic() + timeout
                while proc.poll() is None:
                    if cancel_event is not None and cancel_event.is_set():
                        kill_process_group(proc)
                        return ProviderResult(ok=False, exit_code=-1,
                                              error="cancelled",
                                              log_tail=tail_log(log_path))
                    if time.monotonic() > deadline:
                        kill_process_group(proc)
                        return ProviderResult(ok=False, exit_code=-1,
                                              error=f"timeout after {timeout}s",
                                              log_tail=tail_log(log_path))
                    time.sleep(_POLL_SECONDS)
        except OSError as e:
            return ProviderResult(ok=False, exit_code=-1,
                                  error=f"failed to launch agy: {e}")

        code = proc.returncode
        return ProviderResult(ok=(code == 0), exit_code=code,
                              error=None if code == 0 else f"agy exited {code}",
                              log_tail=tail_log(log_path))
