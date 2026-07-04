# ROADMAP v0.9 — Retrospective & Milestones

_Written 2026-07 after the Gargos BUILDER.md build. Source of truth for what gets
consolidated, what gets deprecated, and the order of work._

---

## 1. Retrospective: the Gargos build (how it was actually done)

Full flow executed per BUILDER.md §5-§11, audit-trailed via `--log` / `report`
(`logs/testbuild-gargos-v0.8-builder.json`, 11 commands, 1 self-documented failure).

| Phase | What happened | Verdict |
|---|---|---|
| §5 Feedback (4+4 questions) | User answered 8 questions in 2 messages; spec locked before any search | **KEEP — best part of the flow** |
| commander-analyze | analyzer read `[]` (F11, since fixed: Hydra Tribal high); legacy `build_direction_options` carried the build | Analyzer now leads; legacy carried it — Fase 2 urgency |
| category-counts | Clear targets (ramp 13 Critical, protection 7 High); BUT philosophy silently ignored + `built_in_removal: 0` for a fight commander (F10, both fixed) | Scorer must migrate to analyzer |
| Shortlists | search-tags fine; `search --max-price` didn't exist (F9 → shipped as feature); edhrec_rank made every list good | Budget-aware search is now core |
| Draft (65 spells) | Agent judgment + shortlists; `cards-batch --verify` caught 2 hallucinated names cheaply, BEFORE any deck file existed | **verify-early: KEEP as hard rule** |
| Budget Contract §11 | First real exercise: `--budget 130 --overage 10`, confidence "complete", 0 unknown prices | **Works as designed** |
| deck-write | First call WITHOUT `--structured` put the commander in the main deck; second call fixed it | Flow trap — see consolidation |
| fill → gaps → preflight → swap | gaps: 0; preflight caught a genuine color violation (message naming the card, F7 in production); swap syntax correct post-F8 | **The closing triad: KEEP** |
| report | One consolidated JSON with every command, exit code, and note | **KEEP — the review was written from it** |

**Meta-lesson recorded:** the tool audited the agent three times (2 hallucinations, 1
color violation). The value of the CLI is exactly this: a filter + validator the
agent-brain cannot skip.

---

## 2. Consolidate (it's good — make it permanent)

1. **The §5 question flow (4 core + detailed mode).** Cheap, fast, locks the spec.
2. **verify-early**: `cards-batch --verify` on the .txt draft BEFORE deck-write. Promote
   from "recommended" to a numbered mandatory step in BUILDER.md §6.
3. **The closing triad** `deck-fill-lands → deck-gaps → preflight` (+ `deck-swap` for
   repairs) with preflight as the only READY authority.
4. **Budget Contract** as exercised: `budget --budget N --overage 10` on the .txt early
   AND on the final JSON.
5. **`--log` on every command + `report` at the end.** The retrospective wrote itself.
6. **JSON error boundary + defensive parsing.** Agent-side rule for agent files: check
   `"error"` key before `"results"` on every parse.
7. **edhrec_rank ranking** in search/search-tags/complements. Extend to `suggest` and
   `similar` (M4).
8. **The golden regression net** (166 sentinels) + the batch-audit playbook (measure →
   fix root-cause → sentinel → re-run net).

## 3. Deprecate / delete (decided, scheduled)

1. **`archetype_fit` (legacy) — deprecate after the gate.** Analyzer is primary
   (BUILDER.md §7.0b already says so). M3: mark deprecated in output (`"deprecated":
   true` field), stop feeding new consumers, delete in v0.10.
2. **`_score_provides` oracle heuristics — replace with analyzer signals** (M2,
   consumer #1). Keep as fallback only when analyzer is absent.
3. **`deck-write` unstructured default with `--commander` present.** If `--commander`
   is given, `--structured` should be implied (the current default silently builds an
   illegal deck shape). Small fix, M4.
4. **Legacy `commander_tags` / `synergy_tags` duplication** in commander-analyze output
   vs analyzer signals: keep both until M3, then single source.
5. **Stale `output/` artifacts** between builds (old analysis JSONs cache stale
   scores — the F10 cache trap). M4: `mtg clean-output` helper or timestamp warning
   when an analysis file predates the installed version.

---

## 3b. Code audit of `src/mtgcli/` (static, 2026-07 — post-Gargos)

**Structure (10,113 LOC):** `cli.py` is a 2,420-LOC god-module (24% of the codebase, every
command in one file). Second largest: `deckbuilder/commander_analyzer.py` (875) — THE
integrator and the single choke point between legacy and analyzer worlds.

**The legacy dependency chain is exactly four files** — this IS the M2/M3 work list:
`category_counts/{calculator,scoring,output}.py` + `deckbuilder/commander_analyzer.py`.
No downstream consumer reads the analyzer yet (only cli.py display + the embedding);
Fase 2 is literally "point category_counts at the analyzer".

**Duplication confirmed (two brains, same phrases):** `scoring.py::_score_provides`
re-implements "destroy target"/"draw a card" that `analyzer/content.py` already detects
with scope/negation awareness, PLUS its own tutors/ramp heuristics ("search your
library", "add {") that the analyzer doesn't cover yet — migration must port those two
as analyzer detectors first, or keep them as documented fallback.

**Dead code:** near-zero. One real candidate (`utils/json_io.py::safe_float`, unused).
The Typer command functions are decorator-registered, not dead.

**Tests (907):** well-distributed; the three most-tested areas (analyzer scope/model,
category_counts, v7_fixes+golden net) match where the risk lives. `cli.py` itself has
no direct unit tests — it's covered indirectly via subprocess tests only; the M4 split
should add per-command smoke tests.

**Added to M4 scope:** split `cli.py` into `cli/commands/*.py` (mechanical, low-risk,
enables per-command tests); delete `safe_float`.

---

## 4. Milestones

### M1 — Close the certification gate (next session)
- Send batch #13 (prompt ready; sanity line **167 passed**) to the strict judge.
- PASS bar: right+partial ≥6/10 AND confidently_wrong = 0.
- Done when: gate criterion (c) confirmed → Fase 2 unlocked. If FAIL: audit, fix the
  class, one more confirmation batch.

### M2 — Fase 2 kickoff: first consumers migrate to the analyzer
- Consumer #1: `category_counts/scoring.py::_score_provides` reads analyzer signals
  (SCOPE_TARGET_OPPOSING_CREATURE, removal/draw/ramp detectors); oracle heuristics
  demoted to fallback.
- Consumer #2: `deck-gaps` archetype context; consumer #3: `suggest` /
  `wanted_card_patterns`.
- Done when: consumers produce same-or-better outputs on a 10-commander spot-check +
  full suite green; certero re-measured (target: hold ≥75%).

### M3 — Legacy deprecation
- `archetype_fit` marked deprecated in JSON output; agent files updated to stop
  mentioning it except as historical.
- Remove `commander_tags`/`synergy_tags` duplication (single source: analyzer).
- Done when: no consumer reads legacy fields; deprecation notes in CHANGELOG.

### M4 — Build-flow polish (the consolidation list)
- `deck-write`: `--commander` implies `--structured`.
- BUILDER.md §6: verify-early as mandatory numbered step; §11 example uses the real
  flags (`--budget/--overage`).
- edhrec_rank ranking extended to `suggest` and `similar`.
- Stale-analysis warning (or `clean-output`).
- Done when: a fresh BUILDER.md build runs with zero flag/flow traps.

### M5 — Validation of the new world
- One full BUILDER.md test build on a virgin commander (post-migration).
- Re-run the 110-commander certero measurement on the migrated pipeline.
- Done when: build READY with ≤2 new frictions and certero ≥75% sustained.

### M6 — v0.9.0 release
- CHANGELOG consolidated, version bump, final zip.
- Stretch: `edhrec_rank` exposed as a search filter (`--max-rank`), power-level
  heuristics reading it.

---

_Order rationale: M1 gates everything (no consumer migration on an uncertified
analyzer); M2-M3 are the payoff the whole campaign was for; M4 is cheap and
independent (can interleave); M5 proves it; M6 ships it._
