"""Regression: report --summary separates STATUS exits from real failures (v0.8.0
polishing, BAJA item from the full-build-#3 retro).

Several commands exit non-zero to signal a documented workflow STATE (a not-found
card lookup, cards-batch --verify with missing names). Counting those beside real
errors buried the audit signal. Rule: a JSON response WITHOUT an "error" key is a
status exit (the JSON error contract guarantees real errors carry {"error": ...});
everything else non-zero stays a failure.

Also: the category-counts --table demotes the compressed target to a trailing
"comp*" column with a contract footnote (Need/Range are the source of truth).
"""
from mtgcli.logging_util import summarize_log


def _entry(seq, command, response, exit_code):
    return {"seq": seq, "command": command, "full_command": f"mtg {command} ...",
            "response": response, "exit_code": exit_code}


def test_json_without_error_key_is_status_exit():
    entries = [_entry(1, "card", {"name": "Krenkooo", "found": False, "suggestions": []}, 1)]
    s = summarize_log(entries)
    assert s["failure_count"] == 0
    assert s["status_exit_count"] == 1
    assert s["status_exits"][0]["command"] == "card"


def test_json_with_error_key_is_failure():
    entries = [_entry(1, "search-tags", {"error": {"type": "validation", "message": "x"}}, 1)]
    s = summarize_log(entries)
    assert s["failure_count"] == 1
    assert s["status_exit_count"] == 0


def test_budget_human_summary_is_status_exit():
    entries = [_entry(1, "budget", "Budget Summary\n  Total (known USD): $200\n...", 1)]
    s = summarize_log(entries)
    assert s["failure_count"] == 0
    assert s["status_exit_count"] == 1


def test_plain_text_nonzero_stays_failure():
    # SIGPIPE-truncated / rich-panel output: a real anomaly, must remain a failure
    entries = [_entry(1, "search", "20 cards for tags ...", 1)]
    s = summarize_log(entries)
    assert s["failure_count"] == 1
    assert s["status_exit_count"] == 0


def test_zero_exits_land_nowhere():
    entries = [_entry(1, "card", {"name": "Sol Ring", "found": True}, 0)]
    s = summarize_log(entries)
    assert s["failure_count"] == 0
    assert s["status_exit_count"] == 0


def test_table_comp_demoted_last_with_footnote():
    from mtgcli.category_counts.output import format_table
    fake = {
        "land_count": 35, "nonland_slots": 64, "projected_avg_mv": 3.2,
        "archetype_fit_score": 4.0,
        "category_recommendations": [
            {"display_name": "Removal", "category": "removal", "need_score": 7.1,
             "recommended_range": "4-8", "compressed_target_count": 2, "priority": "High"},
        ],
    }
    table = format_table(fake)
    header = table.splitlines()[0]
    # comp* is the LAST column and carries the contract footnote
    assert header.rstrip().endswith("comp*")
    assert header.index("Need") < header.index("Priority") < header.index("comp*")
    assert "guidance only" in table and "Need/Range" in table
