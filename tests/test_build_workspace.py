"""Regression: core.build_workspace (v0.9.0 Task 8) — the sandbox generator."""
import json

from mtgcli.core.build_workspace import (
    EXPLANATION_REL,
    FINAL_DECK_REL,
    create_build_workspace,
    render_agent_prompt,
)

REQ = {
    "commander": "Kiki-Jiki, Mirror Breaker",
    "partner": None,
    "budget": "150",
    "bracket": "n/a",
    "rank_target": "3",
    "theme": "copy combo",
    "notes": "salt alta ok",
    "provider": "claude-code",
    "timeout_seconds": 900,
}


def test_workspace_files_and_config_roundtrip(tmp_path):
    ws = create_build_workspace("job1", REQ, base_dir=tmp_path)
    assert ws == tmp_path / "job1"
    assert (ws / "output").is_dir() and (ws / "logs").is_dir()
    cfg = json.loads((ws / "build_config.json").read_text())
    assert cfg == REQ  # the §5 contract round-trips verbatim
    assert (ws / "agent_prompt.md").exists()


def test_prompt_carries_contract_and_absolute_finish_paths(tmp_path):
    # ABSOLUTE workspace paths on purpose: agy's print mode ignores cwd, so
    # relative ./paths would land in the provider's own scratch dir.
    ws = tmp_path / "jobX"
    prompt = render_agent_prompt(REQ, ws)
    assert "Kiki-Jiki, Mirror Breaker" in prompt
    assert "Budget: 150" in prompt and "Target power RANK: 3" in prompt
    assert f"{ws}/output/final_deck.json" in prompt
    assert f"{ws}/output/explanation.md" in prompt
    assert "mtg preflight" in prompt
    assert "./output/" not in prompt  # no cwd-relative artifact paths anywhere
    assert str(FINAL_DECK_REL) == "output/final_deck.json"
    assert str(EXPLANATION_REL) == "output/explanation.md"


def test_prompt_carries_dynamic_bulk_path(tmp_path, monkeypatch):
    # The player's collection folder is configurable — the prompt must point the
    # agent at the EFFECTIVE collection.txt, resolved at render time.
    import mtgcli.deckbuilder.user_bulk as ub
    custom = tmp_path / "my-collection"
    monkeypatch.setattr(ub, "_configured_bulk_dir", lambda: custom)
    prompt = render_agent_prompt(REQ, tmp_path / "ws")
    assert f"{custom}/collection.txt" in prompt
    assert "override" in prompt.lower()  # explicit: beats BUILDER.md's default path
    # default (no custom dir) -> the project's user-bulk file
    monkeypatch.setattr(ub, "_configured_bulk_dir", lambda: None)
    assert str(ub.USER_BULK_FILE) in render_agent_prompt(REQ, tmp_path / "ws")


def test_prompt_bulk_mode_follows_the_checkbox(tmp_path):
    # default / use_bulk=True -> owned cards are free
    assert "owned cards cost the budget $0" in render_agent_prompt(REQ, tmp_path)
    # use_bulk=False -> the agent must pass --no-bulk to budget AND preflight
    no_bulk = render_agent_prompt(dict(REQ, use_bulk=False), tmp_path)
    assert "--no-bulk" in no_bulk and "FULL prices" in no_bulk


def test_prompt_partner_line_only_when_partner(tmp_path):
    assert "Partner commander" not in render_agent_prompt(REQ, tmp_path)
    with_partner = dict(REQ, partner="Toothy, Imaginary Friend")
    assert "Partner commander: Toothy" in render_agent_prompt(with_partner, tmp_path)


def test_claude_settings_allowlist_tight(tmp_path):
    ws = create_build_workspace("job2", REQ, base_dir=tmp_path)
    settings = json.loads((ws / ".claude" / "settings.json").read_text())
    allow = settings["permissions"]["allow"]
    assert allow == ["Bash(mtg *)", "Read", "Write"]  # exact — and NO Edit
    assert "Edit" not in allow


def test_workspace_refuses_collision(tmp_path):
    create_build_workspace("dup", REQ, base_dir=tmp_path)
    import pytest
    with pytest.raises(FileExistsError):
        create_build_workspace("dup", REQ, base_dir=tmp_path)
