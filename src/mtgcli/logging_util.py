"""Command audit logging: capture each CLI invocation (command, full args, response, timing)
into an on-going JSON staging file, which `report` later consolidates into the output directory.

Design notes:
- Each `mtg` invocation is a separate process, so the log must persist on disk between commands.
  Entries accumulate in OUTPUT_DIR/on-going-report.json; `report` serializes + clears it.
- `seq` is a global running counter (chronological order of the whole build), derived from the
  current length of the on-going log.
- The captured response is the parsed JSON when the command emitted JSON (e.g. --json-output),
  otherwise the raw text — so machine-readable output stays machine-readable in the log.
"""
import json
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List

from mtgcli.config import OUTPUT_DIR

ONGOING_PATH = OUTPUT_DIR / "on-going-report.json"


def _load_ongoing() -> List[Dict[str, Any]]:
    if not ONGOING_PATH.exists():
        return []
    try:
        with open(ONGOING_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _coerce_response(raw: str) -> Any:
    """Parsed JSON if the output was JSON, else the raw text (stripped of trailing newline)."""
    text = raw.rstrip("\n")
    stripped = text.strip()
    if stripped and stripped[0] in "[{":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return text


def append_log(command: str, full_command: str, raw_response: str, exit_code: int) -> int:
    """Append one command entry to the on-going log. Returns the assigned seq."""
    log = _load_ongoing()
    seq = len(log) + 1
    log.append({
        "seq": seq,
        "command": command,
        "full_command": full_command,
        "response": _coerce_response(raw_response),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
    })
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ONGOING_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    return seq


def _is_status_exit(entry: Dict[str, Any]) -> bool:
    """A non-zero exit that is a DOCUMENTED WORKFLOW STATE, not an error.

    Several commands exit 1 to signal a state the agent is expected to act on:
    `budget` when over budget, `cards-batch --verify` when names are missing,
    `card` on a not-found lookup. Counting those beside real errors buried the
    signal in full-build audits (Ragost: 8 "failures", only 6 real). Rule:
      - JSON response WITHOUT an "error" key = status (the JSON error contract
        guarantees every real error carries {"error": {...}}).
      - Human-mode `budget` whose output is the normal summary = status.
    Everything else non-zero (usage/validation/crash/SIGPIPE-truncated) stays a failure.
    """
    resp = entry.get("response")
    if isinstance(resp, dict):
        return "error" not in resp
    if isinstance(resp, list):
        return True  # well-formed JSON list output (e.g. batch results) — not an error shape
    if entry.get("command") == "budget" and isinstance(resp, str) and "Budget Summary" in resp:
        return True
    return False


def summarize_log(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive calibration metrics from the raw log (does not change capture).

    Returns command call-counts, the cards passed to `analyze-card` (direct candidates
    for miss review), commands that exited non-zero with a REAL error (failures), and
    non-zero DOCUMENTED-STATE exits (status_exits: budget over, verify-missing,
    not-found) — kept apart so audits read signal, not noise."""
    command_counts: Dict[str, int] = {}
    analyze_cards: List[str] = []
    failures: List[Dict[str, Any]] = []
    status_exits: List[Dict[str, Any]] = []

    for e in entries:
        cmd = e.get("command", "")
        command_counts[cmd] = command_counts.get(cmd, 0) + 1

        if cmd == "analyze-card":
            # the card is the first non-option token after the command in full_command
            after = e.get("full_command", "").split("analyze-card", 1)[-1].strip()
            card = _first_arg(after)
            if card:
                analyze_cards.append(card)

        if e.get("exit_code", 0) not in (0, None):
            item = {
                "seq": e.get("seq"),
                "command": cmd,
                "full_command": e.get("full_command"),
                "exit_code": e.get("exit_code"),
            }
            (status_exits if _is_status_exit(e) else failures).append(item)

    return {
        "total_commands": len(entries),
        "command_counts": dict(sorted(command_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "analyze_card_calls": analyze_cards,
        "analyze_card_count": len(analyze_cards),
        "failures": failures,
        "failure_count": len(failures),
        "status_exits": status_exits,
        "status_exit_count": len(status_exits),
    }


def _first_arg(text: str) -> str:
    """Extract the first positional argument from a command tail, respecting simple quotes."""
    text = text.strip()
    if not text:
        return ""
    if text[0] in "\"'":
        quote = text[0]
        end = text.find(quote, 1)
        if end != -1:
            return text[1:end]
    # otherwise take tokens until the first option flag
    out = []
    for tok in text.split():
        if tok.startswith("-"):
            break
        out.append(tok)
    return " ".join(out)


class _Tee:
    """Write-through stream: forwards to the real stream while buffering a copy for the log."""
    def __init__(self, real, buffer: StringIO):
        self._real = real
        self._buffer = buffer

    def write(self, s):
        self._real.write(s)
        self._buffer.write(s)
        return len(s)

    def flush(self):
        self._real.flush()

    def __getattr__(self, name):
        return getattr(self._real, name)
