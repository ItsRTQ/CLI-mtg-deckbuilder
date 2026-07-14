"""CodexProvider — headless builds via OpenAI's Codex CLI (`codex exec`).

Measured live (2026-07-11, codex-cli 0.144.1):
- `codex exec "<prompt>"` runs non-interactively; `--skip-git-repo-check` is
  required (our workspaces aren't git repos); `--ephemeral` skips session files.
- `-s workspace-write` enforces OUR sandbox contract natively: reads anywhere,
  writes only inside the working dir, shell commands allowed — no allowlist
  file needed.
- `-c shell_environment_policy.inherit="all"`: codex strips the environment for
  spawned shells by default, which hides the venv's `mtg` from PATH.
- CRITICAL: codex reads stdin to EOF and APPENDS it to the prompt when stdin is
  a pipe ("Reading additional input from stdin...") — a provider that forgets
  stdin=DEVNULL hangs forever. Measured: that was the whole failure mode.
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


class CodexProvider(AgentProvider):
    name = "codex"
    supports_build = True

    def detect(self) -> ProviderInfo:
        exe = shutil.which("codex")
        if not exe:
            return ProviderInfo(name=self.name, installed=False,
                                detail="`codex` not found on PATH",
                                supports_build=True)
        try:
            out = subprocess.run(["codex", "--version"], capture_output=True,
                                 text=True, timeout=10, stdin=subprocess.DEVNULL)
            raw = (out.stdout or out.stderr).strip()
            version = raw.splitlines()[0] if raw else None
            return ProviderInfo(name=self.name, installed=True, version=version,
                                detail=exe, supports_build=True)
        except (subprocess.TimeoutExpired, OSError) as e:
            return ProviderInfo(name=self.name, installed=False,
                                detail=f"`codex --version` failed: {e}",
                                supports_build=True)

    def build(self, workspace: Path, prompt_file: Path, *, timeout: int,
              cancel_event: Optional[threading.Event] = None,
              unsafe_skip_permissions: bool = False) -> ProviderResult:
        log_dir = workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "build.log"

        argv = ["codex", "exec", "--skip-git-repo-check", "--ephemeral",
                "-c", 'shell_environment_policy.inherit="all"']
        if unsafe_skip_permissions:
            argv.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            argv += ["-s", "workspace-write"]   # codex enforces the sandbox itself
        argv.append(prompt_file.read_text(encoding="utf-8"))

        try:
            with open(log_path, "ab") as log:
                proc = subprocess.Popen(
                    argv, cwd=workspace, stdout=log, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,   # NEVER a pipe — codex would wait for EOF
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
                                  error=f"failed to launch codex: {e}")

        code = proc.returncode
        return ProviderResult(ok=(code == 0), exit_code=code,
                              error=None if code == 0 else f"codex exited {code}",
                              log_tail=tail_log(log_path))
