"""Regression: core/status service (the Task-2 extraction template — v0.9.0).

`project_status` is the first `core/` service: pure function, paths as parameters
with config defaults, returns data (the CLI/API do the I/O).
"""
import json
from pathlib import Path

from typer.testing import CliRunner

from mtgcli.core.status import project_status

runner = CliRunner()


def test_project_status_reports_existence_flags(tmp_path):
    db = tmp_path / "mtg.sqlite"
    raw = tmp_path / "scryfall_cards.json"
    info = project_status(project_root=tmp_path, sqlite_path=db, raw_cards_path=raw)
    assert set(info) == {"project_root", "database_path", "database_exists",
                         "raw_cards_path", "raw_cards_exists"}
    assert info["database_exists"] is False and info["raw_cards_exists"] is False
    db.write_text("x")
    raw.write_text("x")
    info = project_status(project_root=tmp_path, sqlite_path=db, raw_cards_path=raw)
    assert info["database_exists"] is True and info["raw_cards_exists"] is True
    assert info["database_path"] == str(db)


def test_status_command_delegates_to_service(tmp_path, monkeypatch):
    # Patching the COMMAND module's globals must still steer the output —
    # the D1 pass-through contract.
    import mtgcli.cli.commands.data as data_mod
    from mtgcli.cli import app
    fake_db = tmp_path / "fake.sqlite"
    monkeypatch.setattr(data_mod, "SQLITE_PATH", fake_db)
    r = runner.invoke(app, ["status", "--json-output"])
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert out["database_path"] == str(fake_db)
    assert out["database_exists"] is False
