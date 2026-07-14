"""Build-workspace generator — the sandbox a headless agent build runs in.

The workspace IS the contract: the agent works only inside it, and the build's
source of truth are its files (output/final_deck.json + output/explanation.md);
provider stdout is logs/debug only.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from mtgcli.config import OUTPUT_DIR, PROJECT_ROOT

GUI_BUILDS_DIR = OUTPUT_DIR / "gui-builds"
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "agent_prompt_template.md"
_EXPLAIN_TEMPLATE_PATH = (Path(__file__).parent / "templates"
                          / "explain_prompt_template.md")

# Tight headless permission allowlist (mirrors providers.claude_code.ALLOWED_TOOLS —
# no Edit unless the flow proves to need it; see REFACTOR_MAP/plan risk #1).
_CLAUDE_SETTINGS = {
    "permissions": {
        "allow": ["Bash(mtg *)", "Read", "Write"],
    }
}

FINAL_DECK_REL = Path("output") / "final_deck.json"
EXPLANATION_REL = Path("output") / "explanation.md"


def render_agent_prompt(request: Dict[str, Any], workspace: Path) -> str:
    """Absolute workspace paths ON PURPOSE: some providers' headless modes do not
    honor the process cwd (measured: agy print mode writes relative paths to its
    own scratch dir), so the prompt never relies on relative paths."""
    from mtgcli.deckbuilder.user_bulk import default_bulk_file

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    partner = request.get("partner")
    return template.format(
        project_root=PROJECT_ROOT,
        ws=workspace,
        # resolved at RENDER time: honors Settings -> Card collection folder,
        # so every build's prompt points the agent at the player's real bulk
        bulk_file=default_bulk_file(),
        commander=request["commander"],
        partner_line=f"\n- Partner commander: {partner}" if partner else "",
        budget=request.get("budget") or "n/a",
        bracket=request.get("bracket") or "n/a",
        rank_target=request.get("rank_target") or "n/a",
        theme=request.get("theme") or "agent choice — follow the commander's plan",
        notes=request.get("notes") or "none",
        bulk_mode=(
            "USE it — owned cards cost the budget $0 (the default; budget/preflight "
            "apply it automatically)"
            if request.get("use_bulk", True) else
            "DO NOT use it — the player wants FULL prices: pass --no-bulk to every "
            "`mtg budget` and `mtg preflight` call"
        ),
    )


def create_explain_workspace(job_id: str, request: Dict[str, Any],
                             deck_data: Dict[str, Any], *,
                             base_dir: Optional[Path] = None) -> Path:
    """Workspace for an annotate-and-explain job on an EXISTING deck: the deck
    JSON is copied in; the prompt carries the owner's form answers (their context
    makes the agent VERIFY instead of guess)."""
    import json

    workspace = (base_dir or GUI_BUILDS_DIR) / job_id
    (workspace / "output").mkdir(parents=True, exist_ok=False)
    (workspace / "logs").mkdir()
    (workspace / ".claude").mkdir()

    (workspace / "output" / "deck.json").write_text(
        json.dumps(deck_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (workspace / "build_config.json").write_text(
        json.dumps(request, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    template = _EXPLAIN_TEMPLATE_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        project_root=PROJECT_ROOT,
        ws=workspace,
        commander=request["commander"],
        theme=request.get("theme") or "n/a — figure it out from the cards",
        combos=request.get("combos") or "none declared — hunt for them yourself",
        bracket=request.get("bracket") or "n/a",
        notes=request.get("notes") or "none",
    )
    (workspace / "agent_prompt.md").write_text(prompt, encoding="utf-8")
    (workspace / ".claude" / "settings.json").write_text(
        json.dumps(_CLAUDE_SETTINGS, indent=2) + "\n", encoding="utf-8")
    return workspace


def create_build_workspace(job_id: str, request: Dict[str, Any], *,
                           base_dir: Optional[Path] = None) -> Path:
    """Create output/gui-builds/<job_id>/ with build_config.json, agent_prompt.md,
    the tight .claude/settings.json allowlist, and the logs/ + output/ dirs."""
    workspace = (base_dir or GUI_BUILDS_DIR) / job_id
    (workspace / "output").mkdir(parents=True, exist_ok=False)
    (workspace / "logs").mkdir()
    (workspace / ".claude").mkdir()

    (workspace / "build_config.json").write_text(
        json.dumps(request, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (workspace / "agent_prompt.md").write_text(
        render_agent_prompt(request, workspace), encoding="utf-8")
    (workspace / ".claude" / "settings.json").write_text(
        json.dumps(_CLAUDE_SETTINGS, indent=2) + "\n", encoding="utf-8")
    return workspace
