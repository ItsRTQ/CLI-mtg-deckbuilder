# Changelog

> Fresh start at v0.9.0 — the pre-0.9 history grew too heavy and was retired on
> purpose; it lives in git history and `claude-memory/CHECK-LIST.md`.

## v0.9.0 — Localhost GUI ("port the tool for deploy")

The headline: **`mtg gui`** — a localhost web app where a Magic player builds a
Commander deck WITHOUT touching the terminal. The app ships the knowledge (the
`mtg` tool + agent instruction files) and the user brings the intelligence: deck
builds run headlessly through THEIR OWN AI agent CLI. No model is bundled.

### GUI core

- **`mtg gui`** (42nd command): starts the FastAPI server (default
  `127.0.0.1:8321`) and opens the browser. `--host/--port/--no-browser`;
  API under `/api` (docs at `/api/docs`).
- **`src/mtgcli/gui_api/`** — FastAPI app factory: `/api/health`, `/api/status`,
  `/api/cards/search` + `/api/cards/{name}` (fuzzy suggestions on 404),
  `/api/providers` (+select), `/api/builds` (+status/cancel). Serves the built
  frontend with SPA deep-link fallback. Errors follow the project's JSON contract
  (`{"error": {type, message}}`).
- **`gui/`** — Vite + React frontend: Home (project status), Commander Search
  (live DB search), Build Wizard (the BUILDER §5 contract as a form), Results
  (live build log + final deck), Settings (provider detection/selection).
  Build once with `npm --prefix gui install && npm --prefix gui run build`.

### Headless agent builds

- **Provider Manager** (`src/mtgcli/core/providers/`): vendor-neutral
  `AgentProvider` interface. v0.9.0 ships TWO build-capable providers —
  **ClaudeCodeProvider** (headless `claude -p`, stream-json logs, tool
  allowlist) and **AntigravityProvider** (Google's `agy` CLI: headless
  `agy -p` + `--add-dir <workspace>` + `--print-timeout`; its print mode
  ignores the process cwd, so the shared agent prompt uses ABSOLUTE workspace
  paths — measured live). **Ollama** stays detection-only; Codex/Gemini are
  TODO stubs. Providers are switched by clicking them in Settings.
- **Sandboxed build workspaces** (`output/gui-builds/<job_id>/`): the §5 contract
  form generates `build_config.json` + `agent_prompt.md`; the agent works only
  inside the workspace. **The workspace files ARE the build contract** — required
  outputs `output/final_deck.json` + `output/explanation.md`; provider stdout is
  logs/debug only (streamed to `logs/build.log`, tailed live by the GUI).
- **Tight headless permissions**: workspace `.claude/settings.json` +
  `--allowedTools` allowlist limited to `Bash(mtg *)`, `Read`, `Write` — never
  `--dangerously-skip-permissions` (opt-in escape hatch only).
- **Postflight, not fallback**: the finished deck is gated by
  `validate_commander_deck` + the blessed `mtg preflight` (READY or the job
  fails with a structured error). There is NO deterministic fallback
  deckbuilding — the agent builds or nobody does.

### core/ services (the GUI-reuse refactor)

- New **`src/mtgcli/core/`** package — business logic shared by CLI and API
  (services return data; callers do I/O). First extraction: `core/status.py`
  behind both `mtg status` and `GET /api/status` (zero CLI behavior change).
- **`REFACTOR_MAP.md`** — the full audit of which commands still hold inline
  logic (fat/medium/thin) and the extraction order for future releases.
- Removed leftover empty dirs `src/mtgcli/explore/`, `src/mtgcli/combos/`.

### Also in this release (pre-GUI work on the 0.9 branch)

- **`mtg deck-remove`** (41st command): deck-add's inverse — atomic batch trim,
  basics decrement via `"N Mountain"`, DFC front-face names resolve, running
  total with budget %.
- **`deck-swap`** OUT side now matches DFC front-face names (the deck stores
  `Front // Back`; you type the front face).
- **RANK v1.1 — THREAT bonus**: annotated compact combos (auto_win/infinite,
  ≤3 real pieces, commander is a free piece) add a capped bonus (+1.5 max) on
  top of the FUEL-SPINE score. Annotation-optional: unannotated decks and the
  calibration corpus score exactly as before. (Kiki: 1.98 Dormant → 3.48
  Awakened — a budget compact-combo deck no longer reads as casual tribal.)
- **LEGENDARY_MATTERS negation guard**: "target **non**legendary ..." no longer
  reads as a legendary payoff (9 measured false positives dead, 142 true
  payoffs kept).
- **BUILDER §5 gate closed on the legacy path**: `deck-write` creating a NEW
  structured deck now requires the answered `--set-config budget= bracket=`
  contract, same as `deck-add` (`--force` rewrites exempt; ports =
  `deck-add --import`).
- Dependencies: + `fastapi`, `uvicorn` (runtime); + `httpx2` (dev/tests).
