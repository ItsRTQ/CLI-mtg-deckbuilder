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
import sys
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


def summarize_log(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive calibration metrics from the raw log (does not change capture).

    Returns command call-counts, the cards passed to `analyze-card` (direct candidates for
    miss review), and any commands that exited non-zero (real friction)."""
    command_counts: Dict[str, int] = {}
    analyze_cards: List[str] = []
    failures: List[Dict[str, Any]] = []

    for e in entries:
        cmd = e.get("command", "")
        command_counts[cmd] = command_counts.get(cmd, 0) + 1

        if cmd == "analyze-card":
            # the card is the first non-option token after the command in full_command
            toks = e.get("full_command", "").split()
            # drop 'mtg', the command, and options; take the quoted/first bare arg
            after = e.get("full_command", "").split("analyze-card", 1)[-1].strip()
            card = _first_arg(after)
            if card:
                analyze_cards.append(card)

        if e.get("exit_code", 0) not in (0, None):
            failures.append({
                "seq": e.get("seq"),
                "command": cmd,
                "full_command": e.get("full_command"),
                "exit_code": e.get("exit_code"),
            })

    return {
        "total_commands": len(entries),
        "command_counts": dict(sorted(command_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "analyze_card_calls": analyze_cards,
        "analyze_card_count": len(analyze_cards),
        "failures": failures,
        "failure_count": len(failures),
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
