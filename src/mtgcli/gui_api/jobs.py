"""Build-job registry + lifecycle for POST /api/builds.

One thread per job (the provider subprocess blocks for minutes). In-memory
registry — single-user localhost; the workspace on disk survives a server restart
for post-mortem. Lifecycle: pending → running → validating → succeeded | failed |
timeout | cancelled. NO deterministic fallback building anywhere: deterministic
code only creates the workspace, validates the result, and reports errors.
"""
import json
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional  # noqa: F401 (List used in registry)

from mtgcli.core.build_workspace import (
    EXPLANATION_REL,
    FINAL_DECK_REL,
    create_build_workspace,
)
from mtgcli.core.providers.base import AgentProvider

TERMINAL = {"succeeded", "failed", "timeout", "cancelled"}
_LOG_TAIL_LINES = 30


@dataclass
class Job:
    id: str
    request: Dict[str, Any]
    provider_name: str
    workspace: Path
    kind: str = "build"            # "build" | "explain" | "advise"
    status: str = "pending"
    phase: str = "created"
    created_at: float = field(default_factory=time.monotonic)
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None

    @property
    def elapsed_seconds(self) -> int:
        return int(time.monotonic() - self.created_at)

    def log_tail(self) -> List[str]:
        log = self.workspace / "logs" / "build.log"
        try:
            return log.read_text(encoding="utf-8", errors="replace").splitlines()[-_LOG_TAIL_LINES:]
        except OSError:
            return []


def _fail(job: Job, err_type: str, message: str, *, status: str = "failed",
          **extra: Any) -> None:
    job.status = status
    job.phase = "done"
    job.error = {"type": err_type, "message": message,
                 "log_tail": job.log_tail(), **extra}


def _run_preflight(deck_path: Path, commander: str, *,
                   budget_ceiling: Optional[float] = None,
                   use_bulk: bool = True) -> Dict[str, Any]:
    """The blessed 'are we done' gate, via the pinned CLI (the preflight logic is
    inline in the command — extraction to core is the REFACTOR_MAP follow-up).

    `budget_ceiling` is the budget-mode ceiling (already includes the mode's
    allowed overage), so it is enforced strictly (--overage 0). Mode floors
    (lower's 50%) are prompt-only — preflight can only gate a ceiling."""
    mtg = shutil.which("mtg")
    if not mtg:
        return {"error": "mtg CLI not on PATH for postflight"}
    cmd = [mtg, "preflight", "--deck", str(deck_path), "--commander", commander,
           "--json-output"]
    if budget_ceiling is not None:
        cmd += ["--budget", str(budget_ceiling), "--overage", "0"]
    if not use_bulk:
        cmd.append("--no-bulk")
    proc = subprocess.run(
        cmd,
        capture_output=True, text=True, timeout=120,
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"error": "unparseable preflight output",
                  "raw": proc.stdout[-2000:]}
    report["exit_code"] = proc.returncode
    return report


def run_build_job(job: Job, provider: AgentProvider) -> None:
    """Thread target: provider build → workspace-file contract → postflight gates."""
    try:
        job.status = "running"
        job.phase = "agent building (watch the live log)"
        res = provider.build(job.workspace, job.workspace / "agent_prompt.md",
                             timeout=int(job.request.get("timeout_seconds") or 900),
                             cancel_event=job.cancel_event)

        if res.error == "cancelled" or job.cancel_event.is_set():
            _fail(job, "cancelled", "Build cancelled by the user.", status="cancelled")
            return
        if res.error and "timeout" in res.error:
            _fail(job, "timeout", f"Agent did not finish in time ({res.error}).",
                  status="timeout")
            return

        # The workspace files ARE the contract — check them even on nonzero exit
        # only to report better; a nonzero provider exit is still a failure.
        job.status = "validating"
        deck_path = job.workspace / FINAL_DECK_REL
        expl_path = job.workspace / EXPLANATION_REL
        if not res.ok:
            _fail(job, "provider", res.error or "provider failed",
                  exit_code=res.exit_code)
            return
        missing = [str(p.relative_to(job.workspace))
                   for p in (deck_path, expl_path) if not p.exists()]
        if missing:
            _fail(job, "finish_contract",
                  "Agent finished without the required output file(s): "
                  + ", ".join(missing))
            return

        # Cheap in-process shape check before the subprocess gate.
        job.phase = "validating deck"
        from mtgcli.cards.repository import CardRepository
        from mtgcli.config import SQLITE_PATH
        from mtgcli.utils.deck_io import load_deck_file
        from mtgcli.validator.deck_validator import validate_commander_deck
        try:
            loaded = load_deck_file(deck_path)
        except Exception as e:
            _fail(job, "deck_shape", f"final_deck.json is not a loadable deck: {e}")
            return
        commander = (loaded.get("commanders") or [job.request["commander"]])[0]
        repo = CardRepository(str(SQLITE_PATH))
        report = validate_commander_deck(commander, loaded["main_deck"], repo)
        if report.get("errors"):
            _fail(job, "validation", "Deck failed validation.",
                  validation=report["errors"][:10])
            return

        job.phase = "preflight gate"
        from mtgcli.deckbuilder.pricing import budget_mode_bounds, parse_budget_value
        _budget = parse_budget_value(job.request.get("budget"))
        _ceiling = None
        if _budget is not None:
            try:
                _ceiling = budget_mode_bounds(
                    _budget, job.request.get("budget_mode") or "soft",
                    job.request.get("budget_overage_pct"))["ceiling"]
            except ValueError:
                pass  # unknown mode from an old/raw request: no budget gate
        preflight = _run_preflight(deck_path, commander,
                                   budget_ceiling=_ceiling,
                                   use_bulk=job.request.get("use_bulk", True))
        if preflight.get("exit_code") != 0:
            _fail(job, "preflight", "Deck is NOT READY per mtg preflight.",
                  preflight=preflight)
            return

        job.result = {
            "commander": commander,
            "decklist": loaded["main_deck"],
            "explanation": expl_path.read_text(encoding="utf-8", errors="replace"),
            "preflight": preflight,
            "workspace": str(job.workspace),
        }

        # Auto-save to the user's build library (Settings -> builds_save_dir).
        # A save failure never fails the BUILD — the deck is intact in the
        # workspace; surface it as a warning instead.
        job.phase = "saving to library"
        try:
            from mtgcli.core.gui_settings import load_gui_settings, resolve_save_dir
            from mtgcli.core.save_build import save_build_to_library
            save_dir = resolve_save_dir(load_gui_settings().get("builds_save_dir"))
            if save_dir is not None:
                job.result.update(save_build_to_library(job.workspace, save_dir,
                                                        repo=repo))
        except Exception as e:
            job.result["save_warning"] = (f"Deck built OK but saving to the library "
                                          f"failed: {e} — it remains in the workspace.")

        job.status = "succeeded"
        job.phase = "done"
    except Exception as e:  # never leave a job spinning on an unexpected crash
        _fail(job, "internal", f"{type(e).__name__}: {e}")


def run_explain_job(job: Job, provider: AgentProvider) -> None:
    """Thread target: annotate-and-explain an EXISTING library deck. The card
    list must not change; the deliverables (explanation.md + annotated deck.json)
    are copied back into the deck's library folder on success."""
    try:
        job.status = "running"
        job.phase = "agent studying the deck (watch the live log)"
        res = provider.build(job.workspace, job.workspace / "agent_prompt.md",
                             timeout=int(job.request.get("timeout_seconds") or 600),
                             cancel_event=job.cancel_event)
        if res.error == "cancelled" or job.cancel_event.is_set():
            _fail(job, "cancelled", "Explain job cancelled by the user.",
                  status="cancelled")
            return
        if res.error and "timeout" in res.error:
            _fail(job, "timeout", f"Agent did not finish in time ({res.error}).",
                  status="timeout")
            return
        if not res.ok:
            _fail(job, "provider", res.error or "provider failed",
                  exit_code=res.exit_code)
            return

        job.status = "validating"
        job.phase = "checking deliverables"
        expl = job.workspace / "output" / "explanation.md"
        deck = job.workspace / "output" / "deck.json"
        missing = [p.name for p in (expl, deck) if not p.exists()]
        if missing:
            _fail(job, "finish_contract",
                  "Agent finished without: " + ", ".join(missing))
            return
        text = expl.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            _fail(job, "finish_contract", "explanation.md is empty.")
            return

        # Copy back into the deck's library folder.
        job.phase = "saving into the library"
        target = Path(job.request["_target_dir"])
        build_name = target.name
        (target / f"{build_name}.explanation.md").write_text(text, encoding="utf-8")
        # The agent regenerates the deck JSON without the user's print prefs —
        # capture them before the copy and re-inject after (taste always wins).
        from mtgcli.core.print_prefs import load_deck_print_prefs
        old_prefs = load_deck_print_prefs(target / "deck_list.json")
        shutil.copy2(deck, target / "deck_list.json")
        if old_prefs:
            dl = target / "deck_list.json"
            try:
                data = json.loads(dl.read_text(encoding="utf-8"))
                data["print_prefs"] = old_prefs
                dl.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
            except (OSError, ValueError):
                pass  # unreadable agent output — leave the copy as-is

        # The deck just EARNED annotations — its tier/rank may now compute, and
        # the library folder name is where the banner reads them from. Rename to
        # the up-to-date `<Commander>-<TIER>-<RANK>-<COST>` (best-effort).
        from mtgcli.core.save_build import rename_to_current_tokens
        target, build_name = rename_to_current_tokens(target, job.request["commander"])

        job.result = {
            "deck_name": build_name,
            "explanation": text,
            "saved_to": str(target),
            "workspace": str(job.workspace),
        }
        job.status = "succeeded"
        job.phase = "done"
    except Exception as e:
        _fail(job, "internal", f"{type(e).__name__}: {e}")


def run_advise_job(job: Job, provider: AgentProvider) -> None:
    """Thread target: read-only ADVISORY pass on an in-progress draft. The
    deliverable is output/recommendations.json; every suggested card is verified
    against the DB here (existence + color identity) — the agent's judgment
    ships, its hallucinations don't."""
    try:
        job.status = "running"
        job.phase = "agent analyzing the draft (watch the live log)"
        res = provider.build(job.workspace, job.workspace / "agent_prompt.md",
                             timeout=int(job.request.get("timeout_seconds") or 600),
                             cancel_event=job.cancel_event)
        if res.error == "cancelled" or job.cancel_event.is_set():
            _fail(job, "cancelled", "Advise job cancelled by the user.",
                  status="cancelled")
            return
        if res.error and "timeout" in res.error:
            _fail(job, "timeout", f"Agent did not finish in time ({res.error}).",
                  status="timeout")
            return
        if not res.ok:
            _fail(job, "provider", res.error or "provider failed",
                  exit_code=res.exit_code)
            return

        job.status = "validating"
        job.phase = "checking recommendations"
        from mtgcli.core.build_workspace import RECOMMENDATIONS_REL
        rec_path = job.workspace / RECOMMENDATIONS_REL
        if not rec_path.exists():
            _fail(job, "finish_contract",
                  "Agent finished without output/recommendations.json")
            return
        try:
            data = json.loads(rec_path.read_text(encoding="utf-8",
                                                 errors="replace"))
        except ValueError as e:
            _fail(job, "finish_contract", f"recommendations.json is not valid JSON: {e}")
            return
        recs = data.get("recommendations")
        if not isinstance(recs, list) or not recs:
            _fail(job, "finish_contract",
                  "recommendations.json has no recommendations list.")
            return

        # Deterministic gate on the agent's card names: exists + color identity.
        from mtgcli.cards.repository import CardRepository
        from mtgcli.config import SQLITE_PATH
        repo = CardRepository(str(SQLITE_PATH))
        cmd = repo.get_card_by_exact_name(job.request["commander"]) or {}
        identity = set(cmd.get("color_identity") or [])
        for rec in recs:
            for card in (rec.get("cards") or []):
                found = repo.get_card_by_exact_name(str(card.get("name", "")))
                if not found:
                    card["valid"] = False
                    card["issue"] = "not found in the card DB"
                    continue
                card["name"] = found["name"]  # canonical casing/DFC name
                if set(found.get("color_identity") or []) - identity:
                    card["valid"] = False
                    card["issue"] = "outside the commander's color identity"
                    continue
                card["valid"] = True
                if card.get("price_usd") is None:
                    card["price_usd"] = found.get("usd_price")
                card["image_url"] = found.get("image_url")

        job.result = {
            "deck_name": job.request.get("_deck_name"),
            "summary": data.get("summary") or "",
            "recommendations": recs,
            "workspace": str(job.workspace),
        }
        job.status = "succeeded"
        job.phase = "done"
    except Exception as e:
        _fail(job, "internal", f"{type(e).__name__}: {e}")


class JobRegistry:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, request: Dict[str, Any], provider: AgentProvider,
               *, base_dir: Optional[Path] = None) -> Job:
        job_id = uuid.uuid4().hex[:12]
        workspace = create_build_workspace(job_id, request, base_dir=base_dir)
        job = Job(id=job_id, request=request, provider_name=provider.name,
                  workspace=workspace)
        job.thread = threading.Thread(target=run_build_job, args=(job, provider),
                                      daemon=True)
        with self._lock:
            self._jobs[job_id] = job
        job.thread.start()
        return job

    def create_explain(self, request: Dict[str, Any], deck_data: Dict[str, Any],
                       provider: AgentProvider, *,
                       base_dir: Optional[Path] = None) -> Job:
        from mtgcli.core.build_workspace import create_explain_workspace
        job_id = uuid.uuid4().hex[:12]
        workspace = create_explain_workspace(job_id, request, deck_data,
                                             base_dir=base_dir)
        job = Job(id=job_id, request=request, provider_name=provider.name,
                  workspace=workspace, kind="explain")
        job.thread = threading.Thread(target=run_explain_job, args=(job, provider),
                                      daemon=True)
        with self._lock:
            self._jobs[job_id] = job
        job.thread.start()
        return job

    def create_advise(self, request: Dict[str, Any], deck_data: Dict[str, Any],
                      provider: AgentProvider, *,
                      base_dir: Optional[Path] = None) -> Job:
        from mtgcli.core.build_workspace import create_advise_workspace
        job_id = uuid.uuid4().hex[:12]
        workspace = create_advise_workspace(job_id, request, deck_data,
                                            base_dir=base_dir)
        job = Job(id=job_id, request=request, provider_name=provider.name,
                  workspace=workspace, kind="advise")
        job.thread = threading.Thread(target=run_advise_job, args=(job, provider),
                                      daemon=True)
        with self._lock:
            self._jobs[job_id] = job
        job.thread.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self) -> List[Job]:
        """All jobs, newest first — lets the UI recover a running build after a
        route change or reload (the build lives server-side, not in the page)."""
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: -j.created_at)

    def cancel(self, job_id: str) -> Optional[Job]:
        job = self.get(job_id)
        if job and job.status not in TERMINAL:
            job.cancel_event.set()
        return job
