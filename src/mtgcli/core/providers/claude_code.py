"""ClaudeCodeProvider — headless builds via the `claude` CLI (v0.9.0's one
build-capable provider).

Permission model (as tight as possible): the workspace generator writes
<workspace>/.claude/settings.json with an allowlist limited to `mtg` commands and
file reads/writes, and the invocation repeats it via --allowedTools —
NEVER --dangerously-skip-permissions (opt-in escape hatch lives in build_config).
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

# The tight default allowlist (no Edit unless the flow proves to need it).
ALLOWED_TOOLS = ["Bash(mtg *)", "Read", "Write"]

_POLL_SECONDS = 0.5


class ClaudeCodeProvider(AgentProvider):
    name = "claude-code"
    supports_build = True

    def detect(self) -> ProviderInfo:
        exe = shutil.which("claude")
        if not exe:
            return ProviderInfo(name=self.name, installed=False,
                                detail="`claude` not found on PATH",
                                supports_build=True)
        try:
            out = subprocess.run(["claude", "--version"], capture_output=True,
                                 text=True, timeout=10)
            version = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else None
            return ProviderInfo(name=self.name, installed=True, version=version,
                                detail=exe, supports_build=True)
        except (subprocess.TimeoutExpired, OSError) as e:
            return ProviderInfo(name=self.name, installed=False,
                                detail=f"`claude --version` failed: {e}",
                                supports_build=True)

    def build(self, workspace: Path, prompt_file: Path, *, timeout: int,
              cancel_event: Optional[threading.Event] = None,
              unsafe_skip_permissions: bool = False) -> ProviderResult:
        log_dir = workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "build.log"

        # stream-json (not plain json): plain json BUFFERS everything until the
        # agent finishes, leaving logs/build.log empty for the whole build — the
        # GUI's live log (the user's "never look frozen" requirement) needs the
        # line-by-line event stream.
        argv = ["claude", "-p", prompt_file.read_text(encoding="utf-8"),
                "--output-format", "stream-json", "--verbose"]
        if unsafe_skip_permissions:
            argv.append("--dangerously-skip-permissions")
        else:
            argv += ["--allowedTools", " ".join(ALLOWED_TOOLS)]

        try:
            with open(log_path, "ab") as log:
                proc = subprocess.Popen(
                    argv, cwd=workspace, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                deadline = time.monotonic() + timeout
                while proc.poll() is None:
                    if cancel_event is not None and cancel_event.is_set():
                        self._kill(proc)
                        return ProviderResult(ok=False, exit_code=-1,
                                              error="cancelled",
                                              log_tail=tail_log(log_path))
                    if time.monotonic() > deadline:
                        self._kill(proc)
                        return ProviderResult(ok=False, exit_code=-1,
                                              error=f"timeout after {timeout}s",
                                              log_tail=tail_log(log_path))
                    time.sleep(_POLL_SECONDS)
        except OSError as e:
            return ProviderResult(ok=False, exit_code=-1,
                                  error=f"failed to launch claude: {e}")

        code = proc.returncode
        return ProviderResult(ok=(code == 0), exit_code=code,
                              error=None if code == 0 else f"claude exited {code}",
                              log_tail=tail_log(log_path))

    # kept as an indirection so tests can assert the kill without touching the
    # shared helper (base.kill_process_group)
    _kill = staticmethod(kill_process_group)
