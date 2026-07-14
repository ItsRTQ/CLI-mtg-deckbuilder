# CLI-mtg-deckbuilder

**v0.8.0** — Local Python CLI tool and agent workflow for building, validating, checking, explaining, and exporting **Magic: The Gathering Commander** decks.

The project is designed around one important rule:

```text
The Python `mtg` CLI provides facts, search, validation, deck checks, enrichment, and export.
The external CLI agent makes deckbuilding decisions.
```

The app should not try to fully replace deckbuilding judgment. It should act as a reliable tool layer that gives the agent accurate card data (34k+ cards from Scryfall in a local SQLite database), legality checks, functional search, an evidence-first commander analyzer, an **annotated deck object with a consistency tier** (the agent drafts THROUGH the tool, package by package, with a running budget), and a hard finalization gate — while an external LLM agent (guided by `BUILDER.md`) supplies the strategy, card choices, and explanations.

## Contents

- [**Quick Start — Install & Use**](#quick-start--install--use)
- [Project Goal](#project-goal)
- [Core Architecture](#core-architecture)
- [Requirements](#requirements) · [Setup](#setup) · [Initialize Card Data](#initialize-card-data)
- [**Command Reference**](#command-reference) — all 42 commands, with a clickable [index](#index)
- [Agent Usage](#agent-usage)
- [Power Level Brackets](#power-level-brackets) · [Budget Handling](#budget-handling)
- [Deck Identity Model](#deck-identity-model) · [Engine-First Deckbuilding](#engine-first-deckbuilding) · [Broad Archetypes](#broad-archetypes)
- [Package-Based Strategy Construction](#package-based-strategy-construction) · [Generic Deckbuilding Defaults](#generic-deckbuilding-defaults)
- [Combos and Tutors](#combos-and-tutors) · [Deckbuilding Constraints](#deckbuilding-constraints)
- [Output Files](#output-files) · [Troubleshooting](#troubleshooting) · [Development Notes](#development-notes)

---

## Quick Start — Install & Use

Everything you need to go from a fresh clone to a finished, validated Commander deck.

### 1. Dependencies

What you need before cloning:

| Dependency | Version / notes |
|---|---|
| **Python** | 3.11+ (`python3 --version`), with `pip` and the `venv` module |
| **git** | any recent version, to clone the repo |
| **A shell** | bash/zsh (Linux, macOS, **WSL2** on Windows) or PowerShell (native Windows) |
| **Disk space** | ~1 GB free: Scryfall bulk download (~550 MB) + the SQLite database (~25 MB) |
| **Internet** | only for the first card-data download (everything runs local afterwards) |

Install them per platform:

```bash
# Debian/Ubuntu/WSL2
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# macOS (Homebrew)
brew install python@3.11 git

# Windows (native, PowerShell)
winget install Python.Python.3.11 Git.Git
```

An LLM CLI agent (e.g. Claude Code) is only needed for the agent-driven build in
step 4-A — the CLI itself works standalone without one.

### 2. Install

```bash
git clone <this-repo> && cd CLI-mtg-deckbuilder

# virtual environment (Linux/macOS)
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell:  python -m venv .venv ; .venv\Scripts\activate

pip install -r requirements.txt
pip install -e .            # exposes the `mtg` command (editable mode)

mtg status                  # sanity check: shows paths, DB missing is expected here
```

### 3. Build the card database (one-time, ~550MB download)

```bash
mtg init-data               # downloads Scryfall bulk data + builds data/processed/mtg.sqlite
mtg card "Sol Ring"         # verify: full card data prints
```

Details and troubleshooting: [Setup](#setup) · [Initialize Card Data](#initialize-card-data) ·
[Troubleshooting](#troubleshooting).

### 4. Use it — three ways

**GUI (new in v0.9.0 — no terminal after setup).** Build the web app once, then:

```bash
npm --prefix gui install && npm --prefix gui run build   # one-time (needs Node 18+)
mtg gui                                                   # opens http://127.0.0.1:8321
```

Pick your AI agent in **Settings** — click a provider to switch. v0.9.0 builds
through the **Claude Code** CLI or Google's **Antigravity** CLI (`agy`); Ollama is
detected but can't build yet. Find a commander
in **Search**, answer the build
contract in the **Build Wizard**, and watch your agent build the deck live in
**Results**. The build runs headlessly in a sandboxed workspace under
`output/gui-builds/` — the finished deck must pass the same `preflight` gate as a
CLI build.

**A. Agent-driven build (the primary use).** Point an LLM CLI agent (Claude Code or
similar) at the repo and give it a prompt like:

```text
Using BUILDER.md as your main context, build a "Krenko, Mob Boss" deck.
```

`BUILDER.md` is the canonical build contract. The agent will:

1. **Ask you the core questions first — mandatory, not optional** (bracket, budget,
   theme direction, detail level). The tool enforces it: `deck-add` refuses to create
   a deck without your answered budget + bracket.
2. Analyze the commander (`commander-analyze`: evidence-based archetype bands +
   oracle hooks) and plan slot targets (`category-counts`).
3. **Draft THROUGH the tool, package by package** (`deck-add`): every card is
   validated at entry (exists / color identity / singleton / size), annotated with
   its purpose, and priced — a running total shows budget utilization live.
4. Record combos and rejected candidates as it goes (`note`), annotate the finished
   draft (`deck-annotate`), and score it two orthogonal ways: `deck-power` (bracket
   compliance + a hypergeometric **consistency tier**) and `deck-rank` (a **POWER/speed
   rank**, 7 bands Scrap..Mythic).
5. Fill lands, validate, quality-check, audit against the commander's own plan
   (`deck-gaps`), and pass the one finalization gate: `preflight` → `READY`.
6. Save a versioned folder under `final-builds/` (decklist + explanation +
   `deck_list.json`, the annotated judgment) and a Moxfield-ready export.

**B. Manual use.** Every capability is a plain CLI command — useful standalone:

```bash
mtg card "Krenko, Mob Boss" --field oracle_text      # one field, no JSON wrangling
mtg search-tags sacrifice_outlet death_trigger --colors B   # search by FUNCTION, ranked
mtg similar "Sol Ring"                               # cards doing the same job
mtg complements "Viscera Seer"                       # the other half of the interaction
mtg commander-analyze --commander "Krenko, Mob Boss" # what the commander wants
mtg prices-batch --name "Rhystic Study" --name "Smothering Tithe"   # price picks BEFORE adding
mtg bulk-add --cards "Sol Ring;2 Arcane Signet"      # record cards you OWN: they cost budgets $0
mtg deck-view --deck output/deck.json                # the annotated deck: purposes, curve, cost by type
mtg budget output/deck.json --budget 150 --by-card   # where the money went
mtg preflight --deck output/deck.json --commander "Krenko, Mob Boss"   # READY / NOT READY
```

Every command supports `--json-output` (structured errors included) and `--help`.
Full details per command: [Command Reference](#command-reference).

---

## Project Goal

Build a local Commander deckbuilding assistant where an external CLI agent can:

1. Read the user request.
2. Ask useful preference questions when needed.
3. Look up the commander using local card data.
4. Analyze the commander's actual engine.
5. Search and rank candidate cards.
6. Build a legal 100-card Commander deck.
7. Validate and fix the deck.
8. Export a Moxfield-compatible decklist.
9. Explain how the deck works.

Example agent prompt:

```text
Create a Commander deck with `Krenko, Mob Boss` as commander.
Archetype: tokens (go-wide).
Detail: Goblins.
Use BUILDER.md.
```

Note: use a broad engine-first archetype (here `tokens`) and keep `Goblins` as the
*detail*. Krenko reads as a `token_engine` to the analyzer; forcing `tribal` as the
archetype produces a low fit score and a forced-archetype warning.

---

## Core Architecture

```text
External CLI Agent
    ↓
BUILDER.md
    ↓
agents/*.md
    ↓
local Python `mtg` CLI
    ↓
SQLite card database
    ↓
Scryfall bulk card data
```

### Python CLI responsibilities

The local `mtg` tool should handle reliable data work:

```text
- Download Scryfall bulk card data
- Normalize card records
- Store cards in SQLite
- Look up cards
- Search cards
- Suggest candidates by role/package
- Validate Commander legality
- Check color identity
- Check singleton legality
- Enrich deck JSON with card data
- Export Moxfield-compatible decklists
- Run deck quality/package checks
```

### CLI agent responsibilities

The external agent should handle flexible deckbuilding judgment:

```text
- Understand the user request
- Ask useful user preference questions
- Identify commander, archetype, detail, and constraints
- Analyze the commander's engine
- Decide packages
- Rank candidate cards
- Build the deck
- Fix validation/deck-check issues
- Explain the final deck
```

---

## Requirements

- Python 3.11+
- Local virtual environment
- Internet connection for the first Scryfall data download

---

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

For Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Install the CLI locally

This project uses `pyproject.toml` to expose the `mtg` command.

Install the package in editable mode:

```bash
pip install -e .
```

After this, you can run:

```bash
mtg status
```

Instead of:

```bash
python -m src.mtgcli.cli status
```

Editable mode means changes inside `src/mtgcli/` are picked up automatically. You usually do **not** need to rerun `pip install -e .` after changing normal Python source files.

Run `pip install -e .` again only if you change:

```text
- pyproject.toml
- CLI entry points
- package name/config
```

---

## Initialize Card Data

Download and build the local SQLite card database:

```bash
mtg init-data
```

This will:

1. Download Scryfall bulk card data if missing.
2. Normalize card records.
3. Build `data/processed/mtg.sqlite`.

If the raw card data already exists, the command will skip the download and rebuild SQLite.

### Large Scryfall data warning

Scryfall bulk card data can be very large. The SQLite builder should use streaming JSON parsing with `ijson`, not `json.load()`.

Recommended implementation pattern:

```python
import ijson

with RAW_CARDS_PATH.open("rb") as file:
    for raw_card in ijson.items(file, "item"):
        card = normalize_card(raw_card)
        # insert in chunks
```

Recommended chunk size:

```text
CHUNK_SIZE = 1000
```

Optional development improvement:

```bash
mtg init-data --limit 5000
```

This makes it easier to test imports without processing the entire bulk file.

---

## Command Reference

The `mtg` CLI exposes **40 commands** (v0.8.0). This index links to a detailed section for
each one. Every command supports `--json-output`, and any command accepts the global
`--log` flag (see [Global flags](#global-flags)).

### Index

**Setup & data**

| Command | What it does |
|---|---|
| [`mtg status`](#mtg-status) | Show project paths and whether the card database exists. |
| [`mtg init-data`](#mtg-init-data) | Download Scryfall bulk data (~550MB) and build the local SQLite database. |
| [`mtg update-data`](#mtg-update-data) | Delete the current raw + processed data and re-download/rebuild from scratch. |
| [`mtg temp-clean`](#mtg-temp-clean) | Clean temporary / generated files from `output/`. |

**Card lookup & prices**

| Command | What it does |
|---|---|
| [`mtg card`](#mtg-card) | Look up ONE card by exact name (full data, single field, or JSON). |
| [`mtg cards`](#mtg-cards) | Batch lookup of several card names given inline. |
| [`mtg cards-batch`](#mtg-cards-batch) | Look up every card in a decklist file; `--verify` catches bad names early. |
| [`mtg price`](#mtg-price) | Price data for one card (USD/foil/EUR/TIX). |
| [`mtg prices`](#mtg-prices) | Batch price lookup for several names given inline. |
| [`mtg prices-batch`](#mtg-prices-batch) | Prices for every card in a deck file. |
| [`mtg budget`](#mtg-budget) | Deck cost summary vs a budget: total, per-card breakdown, high-cost flags. |
| [`mtg bulk-add`](#mtg-bulk-add) | Maintain the user-bulk collection (ownership, not quantity); `--import` adds a bought deck. |

**Search & discovery**

| Command | What it does |
|---|---|
| [`mtg search`](#mtg-search) | Search commander-legal cards by text/type/name/stats/trigger/price. |
| [`mtg search-tags`](#mtg-search-tags) | Search by FUNCTION using the curated tag vocabulary, ranked by match count. |
| [`mtg suggest`](#mtg-suggest) | Role-based suggestions for a commander (ramp, card_draw, removal, …). |
| [`mtg similar`](#mtg-similar) | Cards that perform the SAME function as a given card. |
| [`mtg complements`](#mtg-complements) | Cards that complete the OTHER half of a card's interaction. |

**Commander & deck analysis**

| Command | What it does |
|---|---|
| [`mtg commander-analyze`](#mtg-commander-analyze) | Full tactical analysis of a commander → `commander_analysis.json`. |
| [`mtg analyze-card`](#mtg-analyze-card) | Evidence-first functional read of ANY card, with full provenance traces. |
| [`mtg category-counts`](#mtg-category-counts) | Recommended slot counts per category (ramp, draw, removal, …). |
| [`mtg themes`](#mtg-themes) | List the built-in deck theme profiles. |
| [`mtg theme-info`](#mtg-theme-info) | Show one theme profile and its packages. |

**Deck lifecycle**

| Command | What it does |
|---|---|
| [`mtg deck-write`](#mtg-deck-write) | Convert a plain-text decklist into structured deck JSON. |
| [`mtg deck-fill-lands`](#mtg-deck-fill-lands) | Fill a partial deck with basic lands to reach 99 (98 partner) cards. |
| [`mtg suggest-lands`](#mtg-suggest-lands) | Basic-land split suggestion for a commander's colors. |
| [`mtg deck-swap`](#mtg-deck-swap) | Swap cards in a decklist with full validation BEFORE writing. |
| [`mtg validate`](#mtg-validate) | Hard-rule validation: existence, legality, color identity, singleton, size. |
| [`mtg deck-check`](#mtg-deck-check) | Quality heuristics: land/ramp/draw/removal counts and warnings. |
| [`mtg deck-gaps`](#mtg-deck-gaps) | Audit the deck against its commander's plan; lists what's thin. |
| [`mtg preflight`](#mtg-preflight) | THE finalization gate: every must-pass check in one command → `READY`. |

**Annotated deck — drafting & scoring** (the primary flow since the Consistency Engine)

| Command | What it does |
|---|---|
| [`mtg deck-add`](#mtg-deck-add) | THE drafting primitive: add a validated PACKAGE with purpose + running budget; `--import` ports a .txt deck. |
| [`mtg deck-remove`](#mtg-deck-remove) | deck-add's inverse: atomic trim (basics decrement, nonbasics drop whole) + running total. |
| [`mtg deck-annotate`](#mtg-deck-annotate) | Seed/refine purposes on the drafted deck; sync noted combos into it. |
| [`mtg deck-view`](#mtg-deck-view) | View the annotated deck: purposes, types, curve, **cost by type**, combos. |
| [`mtg deck-power`](#mtg-deck-power) | Bracket compliance (deterministic) + consistency TIER (hypergeometric). |
| [`mtg deck-rank`](#mtg-deck-rank) | POWER/speed RANK (FUEL-SPINE): 7 bands Scrap..Mythic; ORTHOGONAL to the tier; upgrade sim. |
| [`mtg note`](#mtg-note) | Record combos/decisions/findings WHILE drafting (the carpenter's tally). |

**Export & reporting**

| Command | What it does |
|---|---|
| [`mtg enrich`](#mtg-enrich) | Embed full card data into a deck JSON. |
| [`mtg export`](#mtg-export) | Export deck JSON to Moxfield import text (with Commander section). |
| [`mtg final-build`](#mtg-final-build) | Validate and save a versioned final build under `final-builds/`. |
| [`mtg report`](#mtg-report) | Consolidate the `--log` audit trail into `logs/<name>.json`. |

**GUI (v0.9.0)**

| Command | What it does |
|---|---|
| `mtg gui` | Start the localhost web GUI + JSON API (`--host/--port/--no-browser`; API under `/api`, docs at `/api/docs`). Deck builds run through YOUR configured AI agent, never a bundled model. |

The web app lives in `gui/` (Vite + React). Build it once so `mtg gui` can serve it:
`npm --prefix gui install && npm --prefix gui run build`. For frontend development,
`npm --prefix gui run dev` serves on :5173 and proxies `/api` to a running `mtg gui --no-browser`.

### Global flags

- **`--json-output`** — every command supports it. With the flag, ALL errors (bad flags,
  unknown commands, validation aborts, crashes) are also emitted as structured JSON
  (`{"error": {"type", "message", ...}}`) instead of Rich panels, so agent parsers never
  break. Failing commands exit non-zero. Always check the `"error"` key before reading
  results.
- **`--log`** — accepted by ANY command, in any position. Appends
  `{seq, command, full_command, response, timestamp, exit_code}` to an on-going staging
  log (`output/on-going-report.json`). Consolidate it later with
  [`mtg report`](#mtg-report). Gives builds a replayable audit trail.

---

### Setup & data

#### `mtg status`

Shows the resolved project paths and whether the raw Scryfall data and the SQLite
database exist. Run it first when anything behaves oddly — most "command returns
nothing" problems are a missing database.

```bash
mtg status
mtg status --json-output   # {"project_root", "database_path", "database_exists", ...}
```

#### `mtg init-data`

Downloads the Scryfall bulk data (**~550MB**, one-time) if missing, then builds the local
SQLite database: one row per unique card identity (34k+, nonplayable layouts purged at ingest), with USD/foil/EUR/TIX prices
aggregated across all printings, `edhrec_rank` popularity, commander-legality and
`can_be_commander` flags precomputed.

```bash
mtg init-data                 # progress output
mtg init-data --json-output   # quiet; final summary JSON
```

Notes:
- Re-running refreshes the database from the (possibly re-downloaded) raw data.
- If the process is killed, see [Troubleshooting](#mtg-init-data-gets-killed).

#### `mtg update-data`

Refresh the card data **from scratch** when the Scryfall bulk is stale: deletes the current
raw bulk and SQLite DB (everything under `data/raw/` and `data/processed/` except each
`.gitkeep`), then re-downloads (~2GB) and rebuilds — a clean `init-data`.

```bash
mtg update-data            # asks for confirmation (destructive)
mtg update-data --yes      # skip the prompt (required non-interactively)
```

Destructive, so it guards: without `--yes` it prompts (interactive) or refuses; with
`--json-output` and no `--yes` it returns `{"ok": false, "error": "confirmation_required"}`.

#### `mtg temp-clean`

Cleans generated files from `output/`. Default mode removes temp files only; `--full`
removes everything except `.gitkeep` (including `deck.json` — it asks for confirmation
unless `--yes`).

```bash
mtg temp-clean --dry-run            # list what would be deleted, delete nothing
mtg temp-clean                      # remove temp files
mtg temp-clean --full --yes         # wipe output/ without prompting
```

---

### Card lookup & prices

#### `mtg card`

Exact-name lookup for ONE card — the source of truth for oracle text, mana cost, P/T,
color identity, legality, and price. Never trust memory for card data; check here.

```bash
mtg card "Sol Ring"                          # human-readable
mtg card "Krenko, Mob Boss" --json-output    # full card JSON
mtg card "Sol Ring" --field oracle_text      # ONE raw field, no JSON/rich wrapping
mtg card "Sol Ring" --field mana_cost        # pipe-friendly
```

Key behaviors:
- **Double-faced / split cards resolve by front-face name**: `mtg card "Valakut Awakening"`
  finds `Valakut Awakening // Valakut Stoneforge`.
- **Not found + `--json-output` (or `--field`)** emits
  `{"name", "found": false, "suggestions": [...]}` and **exits 1** — agent pipelines can
  branch on the exit code.
- `--field` with an unknown field name lists the real available fields and exits 1.
- `power`/`toughness` are stored as text (values like `*` or `1+*` exist); `null` for
  non-creatures.

> Looking for a card but only know part of the name? `mtg search --name "Sol Ring"`
> does partial name matching. Plain `mtg search "Sol Ring"` is a *text* search (it
> splits words and matches oracle text too — you'll get noise).

#### `mtg cards`

Batch exact-name lookup for names given inline. Each result carries `"found": true/false`.

```bash
mtg cards "Sol Ring" "Command Tower" "Arcane Signet" --json-output
```

#### `mtg cards-batch`

Looks up every card in a deck file — accepts **both** deck JSON and plain-text `.txt`
decklists (`1 Card Name` per line). Its `--verify` mode is a **mandatory step** of the
build workflow: run it on your drafted `.txt` BEFORE `deck-write` to catch misspelled or
hallucinated names cheaply.

```bash
mtg cards-batch output/decklist.txt --verify
# → "64 entries, 0 not found."            exit 0
# → "64 entries, 2 not found." + names    exit 1  (with suggestions)

mtg cards-batch output/decklist.txt --verify --json-output
# → {"total_entries", "found_count", "not_found_count", "not_found": [{name, suggestions}]}
```

Notes:
- `--verify` exits **non-zero if anything is missing** — no scripting needed to detect
  `"found": false` entries.
- Without `--verify` it returns the full card data for every entry.

#### `mtg price`

Price data for one card from the local database (aggregated across printings):
`usd_price`, `usd_foil_price`, `eur_price`, `tix_price`, plus `price_status`
(`known`/`unknown`) and `price_source`.

```bash
mtg price "Sol Ring" --json-output
```

#### `mtg prices`

Batch price lookup for names given inline.

```bash
mtg prices "Sol Ring" "Lightning Bolt" --json-output
```

#### `mtg prices-batch`

Prices for every card in a deck file (deck JSON or `.txt` decklist) — **or for
hand-picked names via `--name` (repeatable), BEFORE they join any list**. Both modes
end with a known-price TOTAL.

```bash
mtg prices-batch output/decklist.txt --json-output
mtg prices-batch --name "Rhystic Study" --name "Smothering Tithe" --name "Dockside Extortionist"
```

Notes:
- **Never sum a draft on memory prices** — measured off by 5x in a real build
  (Flawless Maneuver remembered ~$4, actual $20.30). Cost hand-picked staples with
  `--name` before adding them.
- `--name` mode JSON returns `{results, known_total, unknown_count, not_found_count}`;
  not-found names get fuzzy did-you-mean suggestions.

#### `mtg budget`

Deck cost summary against a budget. Accepts deck JSON **or** the raw `.txt` decklist, so
you can budget-check a draft before any deck file exists.

```bash
mtg budget output/decklist.txt --budget 130
mtg budget output/deck.json --budget 130 --overage 10 --json-output
mtg budget output/decklist.txt --budget 130 --by-card         # most expensive first
mtg budget output/deck.json --budget 130 --by-card --top 25
```

Options:
- `--budget <USD>` — the ceiling. **A budget is a spending plan as well as a cap**:
  draft TO it (target 85–100% utilization); landing far under budget is a drafting
  failure, and below ~60% the Budget Upgrade Review is required (BUILDER §11).
- `--overage <pct>` — allowed percent above the limit (default 10).
- `--by-card` — per-card `line_total = usd_price × quantity` breakdown, most expensive
  first (`--top N`, 0 = all).
- `--high-cost-pct` — flags single cards eating ≥ this fraction of the budget
  (default 0.20); they surface in `high_cost_cards` with `pct_of_budget`.
- `--strict` — fail if any card has unknown price.
- `--no-bulk` — ignore the user-bulk collection (owned cards count full price).

Notes:
- Output includes `budget_status` (`under_budget` / `over_budget` / …) and
  `budget_confidence` (`complete` when every card has a known price).
- **Unknown price means unknown — not free and not forbidden.**
- **Owned cards cost $0**: cards in the [user-bulk collection](#mtg-bulk-add) are
  excluded from the bill ENTIRELY (ownership, not quantity — all copies free), always on
  a visible `Owned (user-bulk)` line; the same applies inside `preflight`'s budget gate.
  The 5 basics + Sol Ring + Arcane Signet are owned by default (`--no-bulk` disables).

#### `mtg bulk-add`

Maintains the **user-bulk collection** — the cards you already OWN. It tracks
**ownership, not quantity**: an owned card is priced at $0 for ALL its copies (Commander
is singleton, basics unlimited). Even with an empty collection you're assumed to own the
**5 basic lands + Sol Ring + Arcane Signet**. Saved in two synced forms:
`user-bulk/collection.txt` (hand-editable) and `user-bulk/collection.json` (agent-friendly).

```bash
mtg bulk-add --cards "Sol Ring;Arcane Signet;Rhystic Study"   # add (validated, atomic)
mtg bulk-add --remove "Rhystic Study"                          # remove
mtg bulk-add --import bought-deck.txt                          # BOUGHT a deck? import it whole (.txt or deck .json)
mtg bulk-add --list                                            # view with prices + known value
```

Notes:
- `--cards`/`--remove` validate against the DB with fuzzy did-you-mean on typos; any bad
  name rejects the whole batch (atomic).
- `--import` ports an entire bought deck card-by-card — a `.txt` decklist OR a deck `.json`
  (its `main_deck` AND commander(s) become owned); names not found are warned and skipped
  (the rest still import).
- The file is a plain name-per-line list (`#` comments; a leading `N ` is tolerated but
  ignored) — hand-editable; run `mtg cards-batch user-bulk/collection.txt --verify`
  afterwards. See `user-bulk/README.md`.

---

### Search & discovery

#### `mtg search`

The general card search over commander-legal cards. Three ways to express a query, all
AND-combined:

**1. Query string with structured tokens** (`oracle:`, `type:`, `name:`, `mv:`):

```bash
mtg search 'type:vampire oracle:draw' --json-output
mtg search 'mv<=3 oracle:draw oracle:card' --json-output
```

**2. Repeatable filter options** (cleaner when text has quotes/apostrophes):

```bash
mtg search --oracle "can't be blocked" --oracle target --json-output
mtg search --oracle "draw a card" --type creature --json-output
mtg search --card-type vampire --type creature --json-output
```

**3. Numeric / structural filters:**

```bash
# efficient beaters: power >= 5 at MV <= 4 in green
mtg search --colors G --type creature --pow-gte 5 --mv-lte 4 --json-output

# cards that trigger on an EVENT family
mtg search --trigger permanent_dies --colors B --json-output
mtg search --list-triggers    # permanent_dies, permanent_enters, you_cast_spell,
                              # attacks_or_combat, sacrifice, targeted_by_spell,
                              # draw_or_discard, life_change, recurring_tick

# budget builds
mtg search --oracle "extra turn" --max-price 5 --json-output
```

Full filter list: `--colors` (color identity), `--type` (broad card type), `--oracle/--text`
(repeatable), `--name` (repeatable), `--card-type/--subtype` (repeatable), `--mv`,
`--mv-lte`, `--mv-gte`, `--pow-lte/gte`, `--tou-lte/gte`, `--trigger`, `--max-price`,
`--limit` (default 20).

Notes:
- **Repeated filters and tokens use AND semantics** — a result must match everything.
- **Plain free text is split into words**, each matched as a substring of
  name OR type OR oracle text. `mtg search "Sol Ring"` therefore matches Soldiers
  ("**Sol**dier") and "du**ring**" — for a specific card use
  [`mtg card`](#mtg-card) (exact) or `--name` (partial name, phrase kept whole).
- `*` / variable power never matches a numeric bound (a `*/*` creature is not a
  guaranteed 5-power beater).
- An unknown `--type` value errors out listing the supported types and suggesting
  `--subtype` for creature types (e.g. `Rogue`).
- Results are ranked with real EDHREC popularity as tiebreak (staples first), and
  **every result row prints a price chip** (`$1.23`, `$?` when unknown) — allocation
  happens with prices visible, never from memory.
- `--max-rank <N>` caps candidates by EDHREC rank (unknown ranks are kept) — useful
  to surface format staples at high brackets. Popularity is CONSIDER-ONLY, never an
  include-verdict. Also available on `search-tags`.

#### `mtg search-tags`

Search by **card function** using the curated tag vocabulary (140 functional tags —
`ramp`, `card_draw`, `evasion`, `sacrifice_outlet`, `reanimation`, `protection`, …).
Passing several tags unions their phrases, and results are **ranked by
`tag_match_count`** — how many of the requested tags' phrases each card hits — so the
most on-function cards come first.

```bash
mtg search-tags evasion --colors G --type creature --json-output
mtg search-tags sacrifice_outlet death_trigger --colors B --json-output
mtg search-tags ramp --max-price 3 --mv-lte 3 --json-output
mtg search-tags --list-tags        # the full vocabulary
```

This is how to search deeper than the obvious: decompose the plan into functions
(commander damage = `evasion` + `damage_multiplier` + `protection`; aristocrats =
`sacrifice_outlet` + `death_trigger` + `token_maker`), pull a ranked shortlist per
function, then judge fit yourself.

Notes:
- Tags are curated and substring-based — treat results as **candidates to evaluate**,
  not a verdict.
- A `ramp` search will NOT leak basic lands: lands only count as ramp when they
  actually ramp (Myriad Landscape yes, Mountain no).
- Filters: `--colors`, `--type`, `--max-price`, `--mv-lte`, `--limit`.

#### `mtg suggest`

Role-based suggestions for a commander. `role` is the functional job of the card
(`ramp`, `card_draw`, `removal`, `engine`, …); `--synergy` additionally narrows to cards
that connect with the commander's strategy — **applied after** the role match, never
replacing it.

```bash
mtg suggest --commander "Krenko, Mob Boss" --role ramp --json-output
mtg suggest --commander "Krenko, Mob Boss" --role engine --synergy \
    --analysis output/commander_analysis.json --json-output
mtg suggest --commander "Krenko, Mob Boss" --role card_draw --type creature --json-output
```

Rules that keep suggestions honest:
- **`synergy` is not a role.** Never `--role synergy`; use `--synergy` as a modifier on a
  real role.
- Role results carry non-empty `matched_tags` — that's the evidence for WHY a card
  qualified. Ramp must be real acceleration (rocks, dorks, rituals, Treasure makers,
  land search, extra land drops, cost reducers) — normal lands are not ramp.
- `--analysis` (defaults to `output/commander_analysis.json`) makes `--synergy` smarter.
- `--type` narrows after the role match; `--exclude <deck.json>` skips cards already in
  the deck; `--max-price` for budget builds.
- Ties are sorted by real EDHREC popularity.

#### `mtg similar`

Cards that perform the **same function** as a given card: profiles the card's functional
tags and finds other cards sharing them, ranked by how many they share. Defaults to the
source card's own color identity.

```bash
mtg similar "Sol Ring" --json-output
mtg similar "Cultivate" --colors G --max-price 2 --json-output
```

Use it to find replacements: budget stand-ins, redundancy copies for a key effect, or
alternatives when a card is banned/excluded.

#### `mtg complements`

The **other half of the interaction**: profiles the card and maps its functions to their
payoffs/enablers via a curated complement map. A sacrifice outlet finds death-triggers,
recursion and token makers; a +1/+1-counter placer finds proliferate and counter payoffs.

```bash
mtg complements "Ashnod's Altar" --json-output
mtg complements "Krenko, Mob Boss" --json-output
```

Use it after locking a key engine piece to build the package around it.

> **Removed in v0.8.0:** the former `mtg explore` / `mtg combos` commands fetched
> community data from external sites without permission — a liability for the tool.
> Combo and high-synergy research is the agent's job now (own web search when
> needed), always verified against the local DB and recorded with
> [`mtg note`](#mtg-note) (`--type combo` entries feed `deck-power` directly).

---

### Commander & deck analysis

#### `mtg commander-analyze`

The first command of every build: full tactical analysis of a commander, written to
`output/commander_analysis.json` (a reusable artifact other commands consume).

```bash
mtg commander-analyze --commander "Krenko, Mob Boss" \
    --output output/commander_analysis.json --json-output

# partner decks
mtg commander-analyze --commander "Tymna the Weaver" --partner "Thrasios, Triton Hero" \
    --output output/commander_analysis.json --json-output
```

What the artifact contains (all top-level keys):
- `color_identity` / `combined_color_identity` — the deck's legal colors.
- **`analyzer` — the ONLY archetype read** (evidence-first): `archetype_support` as ordinal
  bands (`very_high/high/medium/low`) each backed by detected signals, plus `signals`
  (compact IDs), `tags` (the functional tag names it matched), `dominant_symmetry`, and
  `warnings`. Full traces via [`mtg analyze-card`](#mtg-analyze-card). (The legacy
  `archetype_fit` weighted-score list was REMOVED in v0.8.0 — build from
  `analyzer.archetype_support`.)
- `best_archetype` — the top analyzer band, aliased to snake_case for convenience.
- `engine_profile` — the commander's primary pattern and engine action.
- `oracle_hooks` — generic, commander-agnostic structural reads of the oracle text:
  `named_counters` (a custom counter like `slime`/`experience` means proliferate +
  any-counter payoffs, NOT +1/+1-specific ones), `asymmetric_punisher` (build
  attrition/protection, not go-wide), `trigger_events`, `token_types`,
  `cost_reduction_type`, and derived `build_signals`.
- `analyzer.tags` (the functional tags the commander matched — replaces the removed
  `commander_tags` / `synergy_tags` lists), `wanted_card_patterns` / `avoid_card_patterns`,
  `role_pressures`, commander scores, `build_direction_options`.
- Power/toughness when available — real data for combat/Voltron/fragility judgment.

Notes:
- Check commander legality FIRST: `mtg card "<name>" --field can_be_commander`. Legal
  non-creature face commanders missing from detection can be added to the curated
  allowlist `data/seed/commander_overrides.json` (verify before adding).
- Analysis JSONs are stamped with `tool_version`; consumers warn when an artifact
  predates the installed version (stale-cache trap) — re-run after upgrading the tool.
- If `archetype_support` comes back empty/all-low on a commander that clearly has a
  plan, that's an analyzer coverage gap: note it and reason from the oracle text.

#### `mtg analyze-card`

Deck-independent, evidence-first functional analysis of **any** card — the transparency
tool behind the analyzer. Every conclusion is a signal with a trace: which rule fired,
on what text. No scores, no include/cut verdict — judgment stays with the agent.

```bash
mtg analyze-card "Krenko, Mob Boss"          # compact: bands + signals
mtg analyze-card "Grave Pact" --json-output  # full provenance traces
```

Use it when a card's function is non-obvious, when you disagree with a band, or to
audit WHY the analyzer read something (calibration work relies on it).

#### `mtg category-counts`

Recommended slot counts per functional category (ramp, card draw, removal, wipes,
lands, synergy packages…) for a commander + archetype + power level, adjusted by the
commander's own provisions (a commander that IS removal lowers the removal need).

```bash
mtg category-counts --commander "Krenko, Mob Boss" --archetype "tokens" \
    --power-level 7 --analysis output/commander_analysis.json --json-output

mtg category-counts --commander "Krenko, Mob Boss" --archetype "tokens" --table
```

How to read it — **this contract matters**:
- **`recommended_range` and `need_score` are the source of truth**, NOT the visually
  prominent `compressed_target_count`. Compression can shrink a Critical-need category
  to a misleading near-zero target. If `need_score` is High/Critical, stay near the TOP
  of `recommended_range` regardless of the compressed number.
- `--table` prints a flat one-row-per-category table (need_score, range, compressed,
  priority) sorted by need — grep/awk-friendly, exactly the fields the contract needs.
- Pass `--analysis` for richer commander scoring; re-generate the analysis after tool
  upgrades (cached scores go stale).
- Counts are guidance, not hard locks. An invalid `--philosophy` string warns and falls
  back to `balanced` (`philosophy_warning` names the 14 valid options).

#### `mtg themes`

Lists the built-in theme profiles (token_engine, sacrifice_value, creature_type_tribal, …).

```bash
mtg themes --json-output
```

#### `mtg theme-info`

Shows one theme profile: description and its packages with min/ideal counts.

```bash
mtg theme-info token_engine --json-output
```

---

### Deck lifecycle

#### `mtg deck-write`

Converts a plain-text decklist (`1 Card Name` per line) into deck JSON.

```bash
mtg deck-write --input output/decklist.txt --output output/deck.json \
    --commander "Krenko, Mob Boss" --structured --force

# partner decks
mtg deck-write --input output/decklist.txt --output output/deck.json \
    --commander "Tymna the Weaver" --partner "Thrasios, Triton Hero" --structured --force
```

Notes:
- **`--commander` implies `--structured`** — the structured shape
  (`{"commander": ..., "main_deck": [...]}`) keeps the commander in the command zone as
  metadata, NOT as a main-deck card. The old unstructured default silently produced an
  illegal deck shape when a commander was given; that trap is closed.
- `--force` overwrites an existing output file.
- Workflow rule: run [`mtg cards-batch --verify`](#mtg-cards-batch) on the `.txt` BEFORE
  this step.

#### `mtg deck-fill-lands`

Fills a partial deck with basic lands (split by the commander's color identity) up to
the target main-deck size (99, or 98 for partners).

```bash
mtg deck-fill-lands --deck output/deck.json --commander "Krenko, Mob Boss" \
    --output output/deck.json
mtg deck-fill-lands --deck output/deck.json --commander "..." --dry-run
```

Notes:
- **In-place fill (output == deck) just works** — `--force` is only needed to overwrite
  a *different* existing file.
- If a flat list contains the commander, it is treated as command-zone metadata and
  removed from the main-deck count.
- `--target-main` overrides the default size.

#### `mtg suggest-lands`

Suggests a basic-land split for a commander's color identity (default 37 lands).
Useful as a starting point before manual mana-base work.

```bash
mtg suggest-lands --commander "Lathril, Blade of the Elves" --count 38 --json-output
```

#### `mtg deck-swap`

**The blessed way to change cards in a list** (budget trims, cutting a salt card, fixing
a violation). Each `--swap "Old=New"` is validated BEFORE anything is written: the
incoming card must exist, be Commander-legal, fit the commander's color identity, and
not create a singleton violation. If ANY swap is invalid, the whole operation aborts
atomically — nothing is written, and the message names the offending card.

```bash
mtg deck-swap --deck output/decklist.txt --commander "Krenko, Mob Boss" \
    --swap "Lightning Bolt=Goblin Bombardment"

mtg deck-swap --deck output/deck.json --commander "..." \
    --swap "Old One=New One" --swap "Old Two=New Two" --dry-run
```

Notes:
- Works on `.txt` decklists AND deck JSON; `--output` writes elsewhere instead of
  in-place; `--dry-run` validates and reports without writing.
- **Never hand-edit the list with `sed`/`python` replaces** — that skips every check
  this command enforces.

#### `mtg validate`

Hard-rule validation of a deck: all cards exist (no hallucinated/misspelled names), all
Commander-legal, all inside the color identity, singleton respected, correct main-deck
and total size, commander present as metadata.

```bash
mtg validate --commander "Krenko, Mob Boss" --deck output/deck.json --json-output
```

Error types you may see:

| Error | Meaning | Action |
|---|---|---|
| `card_not_found` | hallucinated/misspelled card | replace with a real card |
| `not_commander_legal` | illegal in Commander | replace |
| `color_identity_violation` | outside commander identity (message names the card) | replace |
| `invalid_deck_size` | wrong main-deck count | add/cut cards |
| `singleton_violation` | duplicate non-basic | remove duplicates |
| `commander_missing` | no commander metadata/flag | pass `--commander` or use structured JSON |

A deck is not complete until validation passes — but prefer
[`mtg preflight`](#mtg-preflight) as the single finalization gate.

#### `mtg deck-check`

Quality heuristics (not legality): land count, ramp, card draw, removal, board wipes,
protection, synergy counts, with warnings for low counts. Optional `--theme` validates
thematic package minimums.

```bash
mtg deck-check --commander "Krenko, Mob Boss" --deck output/deck.json --json-output
```

Notes:
- Lands only count as ramp when they actually ramp (Myriad Landscape yes, basics no).
- Fight/bite spells count as removal; so do burn-to-target (Lightning Bolt) and
  tuck effects (Chaos Warp).
- Counts are heuristic tag matches — treat warnings as prompts for judgment, not
  hard failures.
- Also reports **`staple_density`** (median EDHREC rank + % top-2000 over nonland
  cards) as a purely INFORMATIONAL line — never a warning, never gates preflight.
  Popularity ≠ power; synergy-dense decks read low by design.

#### `mtg deck-gaps`

Audits the built deck against **its own plan**: cross-references the category-count
targets and the commander's oracle hooks against what the deck actually contains, then
lists what's thin — ranked by need, each gap with a ready-to-run
[`search-tags`](#mtg-search-tags) command to fill it. Also reports hook-specific gaps
(e.g. a custom-counter commander with no proliferate).

```bash
mtg deck-gaps --deck output/deck.json --commander "Krenko, Mob Boss" \
    --archetype tokens --power-level 7 --json-output
```

Run it before finalizing — it closes the analyze → build → audit loop and catches the
deck's blind spots against its own strategy.

#### `mtg preflight`

**The single finalization gate.** Runs every must-pass check in one command, reusing the
same validator/deck-check/budget logic: commander legal & in the command zone, deck
size, all cards exist, all Commander-legal, singleton, color identity, and budget (when
`--budget` is given). Prints a ✓/✗ checklist ending in **`READY`** or **`NOT READY`**
(exit code 0/1). Quality notes (low ramp, etc.) are shown as non-blocking.

```bash
mtg preflight --deck output/deck.json --commander "Krenko, Mob Boss" --budget 130
```

**Do not declare a deck done — and do not run `final-build` — until preflight prints
`READY`.** This one command replaces remembering ten separate rules.

---

### Annotated deck — drafting & scoring

Since the Consistency Engine, the draft is built THROUGH the tool instead of in agent
memory: every card enters with a **purpose** (RAMP / DRAW / REMOVAL / WINCON /
SYNERGY / COMBO_PIECE / …), the build contract (budget, bracket) travels IN the deck
JSON, and the finished deck can be scored for consistency.

#### `mtg deck-add`

**THE drafting primitive.** Adds a PACKAGE of cards, batch and ATOMIC — any invalid
card rejects the whole batch. Every card is validated at entry (exists, color
identity, singleton, deck size), annotated with the batch's purpose, and priced: the
output shows the batch price and the **running deck total with budget %** (the
draft-to-budget mechanism).

```bash
# FIRST call creates the deck and MUST carry the user's answered build contract:
mtg deck-add --deck output/deck.json --commander "Krenko, Mob Boss" \
    --cards "Sol Ring;Arcane Signet;Fellwar Stone" --purpose ramp \
    --set-config budget=150 --set-config budget_mode=soft --set-config bracket=n/a \
    --deck-note "goblin swarm: token engine + damage payoffs"

# subsequent packages (~8-12 per build); basics use "N Name":
mtg deck-add --deck output/deck.json --cards "Skullclamp;..." --purpose draw
mtg deck-add --deck output/deck.json --cards "30 Mountain" --purpose flex
```

Notes:
- **The first call is gated**: without `budget` AND `bracket` in `--set-config` it
  refuses to create the deck — those values come from the user's answers to the
  BUILDER §5 core questions, so a draft cannot start before asking (`n/a` is a valid
  explicit answer; missing is not).
- `--purpose` accepts several, comma-separated (`--purpose ramp,synergy`);
  `--note` applies an agent note to the whole batch.
- The contract lives in the deck's `config` — it survives context loss and travels
  with the file.
- `--import <list.txt>` ports an EXISTING/bought deck into the JSON card-by-card instead
  of the atomic package add: cards not found or incompatible (color identity / singleton /
  size) are WARNED and SKIPPED (the rest still import), the commander line is treated as
  command-zone, and it's exempt from the contract gate (a port, not drafting). Score the
  result with [`deck-rank`](#mtg-deck-rank).

#### `mtg deck-remove`

deck-add's inverse: remove cards from the annotated deck THROUGH the tool. ATOMIC —
any name not in the deck rejects the whole batch. Basics decrement by quantity
(`"2 Mountain"`, entry drops at 0); nonbasics drop whole. DFC front-face names
resolve against the stored `Front // Back` canonical names. Prints the running
deck total, so a trim stays on the draft-to-budget radar.

```bash
mtg deck-remove --deck output/deck.json --cards "Purphoros, God of the Forge;2 Mountain"
```

For a 1-for-1 replacement prefer [`deck-swap`](#mtg-deck-swap) (validates the
incoming card and inherits the slot's purpose).

#### `mtg deck-annotate`

One annotation pass at the END of the draft (never per-card-per-add):

```bash
mtg deck-annotate --deck output/deck.json --auto          # seed ~85% from the measured census
mtg deck-annotate --deck output/deck.json --cards "A;B" --purpose-add synergy --note "..."
mtg deck-annotate --deck output/deck.json --sync-notes    # pull noted combos into the deck
```

Notes:
- `--auto` is merge-only (never removes a purpose you set) and counts lands as RAMP
  only when they actually ramp.
- `--sync-notes` deduplicates combos recorded with [`mtg note`](#mtg-note) and marks
  their pieces COMBO_PIECE.

#### `mtg deck-view`

Shows the annotated deck: commanders, config, budget utilization, metrics
(cards by purpose, primary-type counts, **cost by type**, mana curve + score),
combos, and the Moxfield-format list.

```bash
mtg deck-view --deck output/deck.json
mtg deck-view --deck output/deck.json --by-purpose        # group the list by purpose
mtg deck-view --deck output/deck.json --card "Sol Ring"   # one card's build-facing summary
mtg deck-view --deck output/deck.json --json-output       # full dict + metrics
```

The **cost by type** line (`creature=$45.64, sorcery=$34.71, … land=$6.12`) answers
"where does the MONEY sit" — the lens behind the Budget Reallocation check: money
concentrated in a low-impact bucket (classic: expensive nonbasic lands) can fund a
better card, and the agent must ASK before reallocating (BUILDER §11).

#### `mtg deck-power`

The two categorizers in one command:

1. **Bracket compliance (deterministic)** — Game Changers count (WotC's official
   flag), mass land denial, extra-turn cards, complete 2-card combos, tutors
   (informational) → computed minimum bracket + a COMPLIANT verdict against the
   deck's configured bracket target (skipped when the target is `n/a`).
2. **Consistency TIER (0.0–10.0, +S ≥ 9.5 … F < 5.0, consider-only)** — exact
   hypergeometrics over the annotated deck: win-route access weighted by combo class
   (auto-win > infinite > value), tutors count as wildcards, function bundle at turn
   targets (ramp@T2, draw/removal@T3), curve score. Reports broken routes as a
   "one card away" list and includes per-category draw odds.

```bash
mtg deck-power --deck output/deck.json --commander "Krenko, Mob Boss" --json-output
```

Notes:
- The tier needs the annotated deck (purposes + combos); an unannotated deck falls
  back to a text-census tier with a notice.
- The tier is CONSIDER-ONLY — report it, never gate on it.

#### `mtg deck-rank`

The deterministic **POWER/speed** meter (FUEL-SPINE v1), **ORTHOGONAL to the tier**: the tier
asks "how reliably does the deck run its OWN plan"; RANK asks "how fast/strong is it vs the
metagame". 0–10 → **7 bands: 1 Scrap · 2 Dormant · 3 Awakened · 4 Charged · 5 Ascendant ·
6 Forbidden · 7 Mythic (= cEDH)**, from `fast_mana` (rocks/rituals — the spine) + tutors + game
changers + curve. **Draw is excluded by design** (a grind signal, measured higher in casual than
cEDH). Needs NO annotation — it reads DB facts, so it runs on any deck JSON. Consider-only,
`calibrated:false` (mid bands interpolated).

```bash
mtg deck-rank --deck output/deck.json
mtg deck-rank --deck output/deck.json --target-band 5 \
  --with-candidate "Mana Crypt;Jeweled Lotus;Demonic Tutor"   # Rank Upgrade Review
```

- `--target-band <1-7>` reports the gap to the user's target rank (the agent's "norte").
- `--with-candidate "A;B"` SIMULATES upgrades: each card's EXACT rank before→after delta, whether
  it crosses a band, and whether it's off the commander's color identity — the deck is never
  modified. This is the deterministic "expected increase" for the Rank Upgrade Review.
- Blind spots to flag when reporting: `fast_mana` is a name-list (a brand-new fast-mana card or
  commander-granted acceleration reads as invisible fuel); land-ramp/dorks are excluded by design.

#### `mtg note`

The carpenter's tally: record combos, decisions, and findings the moment you see them
while drafting — never hold them in memory.

```bash
mtg note "Kiki + Zealous Conscripts = infinite hasty tokens" \
    --type combo --cards "Kiki-Jiki, Mirror Breaker;Zealous Conscripts" \
    --combo-class auto_win
mtg note "Rejected Purphoros: $27 vs remembered ~$5" --type decision
```

Notes:
- Combo notes are first-class `deck-power` sources (deduped against the external
  fetch; the noted classification wins). `;` separates card names because names
  contain commas.
- `--cards` validates names against the DB and warns on ghosts.
- Notes live in `output/build-notes.json`; `deck-annotate --sync-notes` pulls the
  combos into the deck itself.

---

### Export & reporting

#### `mtg enrich`

Embeds full card data (oracle text, types, prices, …) from the database into a deck
JSON — producing `deck.enriched.json` for downstream consumers that need card details
without further lookups. Accepts `.txt` decklists too.

```bash
mtg enrich output/deck.json --output output/deck.enriched.json --json-output
```

#### `mtg export`

Exports deck JSON to Moxfield-compatible import text. The export includes a
**`Commander` section** so the commander lands in Moxfield's command zone, plus the
`Deck` section with the 99.

```bash
mtg export output/deck.json --output output/deck.moxfield.txt --json-output
```

#### `mtg final-build`

Validates the deck and saves a versioned final build folder. The folder name is built from
the deck's own scores — `<Commander>-<TIER>-<RANK>-<COST>` — computed by the command:

```text
final-builds/<Commander>-<TIER>-<RANK>-<COST>/      e.g. Dihada-Binder-of-Wills-+S-Mythic-4776usd
├── <build-name>.txt                # Moxfield-compatible decklist
├── <build-name>.explanation.md     # the deck explanation
└── deck_list.json                  # the ANNOTATED deck: purposes, notes, config, combos
```

A MISSING segment is OMITTED (never `na`): an unannotated deck has no TIER, so its folder is
`<Commander>-<RANK>-<COST>`. Exact-name collisions get a rising number right after the
commander name (`<Commander>1-…`, `<Commander>2-…`). `--theme` / `--bracket` feed the
explanation, not the folder. `deck_list.json` means the build's judgment travels with it —
reload it any time with [`mtg deck-view`](#mtg-deck-view).

```bash
mtg final-build --deck output/deck.json --commander "Krenko, Mob Boss" \
    --theme "goblin-swarm" --bracket T3 --explanation output/deck_explanation.md
```

Never final-build a deck that hasn't passed [`mtg preflight`](#mtg-preflight).

#### `mtg report`

Consolidates the on-going `--log` audit trail into `logs/<name>.json` and clears the
staging file (`--keep` retains it). `--note` adds annotations (repeatable); `--summary`
derives calibration metrics (per-command call counts, every card passed to
`analyze-card`, and any non-zero-exit commands).

```bash
mtg search-tags ramp --colors R --log           # ... any commands, all with --log
mtg report --name krenko-build-v1 --note "budget build, $130 cap" --summary
```

The log is self-verifying: any logged command can be re-run later and compared. Use it
whenever a build should be auditable/reproducible.

---

## Agent Usage

The external CLI agent should use `BUILDER.md` as its main guide.

Recommended agent file order:

```text
BUILDER.md
agents/system.md
agents/user-feedback.md
agents/commander_analyzer.md
agents/theme_detector.md
agents/card_ranker.md
agents/deck_builder.md
agents/deck_fixer.md
agents/deck_explainer.md
```

### Agent workflow

When asked to build a deck, the agent should (the annotated-deck flow, BUILDER §6.0):

1. Read the user request.
2. Identify commander, archetype, detail, and constraints.
3. **Ask the BUILDER §5 core questions (bracket, budget, theme, detail level) and
   WAIT for the answers — mandatory and unconditional**, never "only if in doubt"
   (`agents/user-feedback.md` has the exact wording). `deck-add` enforces it: the
   first call refuses to create a deck without the answered budget + bracket.
4. Confirm the commander exists and is legal: `mtg card "<name>" --field can_be_commander`.
5. Analyze the commander: `mtg commander-analyze` (prefer the `analyzer` bands; read `oracle_hooks`).
6. Plan slot targets with `mtg category-counts` (trust `recommended_range`/`need_score`).
7. Build package goals; shortlist candidates with `search`, `search-tags`, `suggest`,
   `similar`, `complements` (results print prices; cost hand-picks with
   `prices-batch --name` BEFORE adding — never sum a draft on memory prices).
8. Rank candidates with `agents/card_ranker.md`.
9. **Draft THROUGH the tool, package by package: `mtg deck-add --purpose <role>`** —
   validated at entry, running budget total with utilization %. First call sets the
   contract (`--set-config budget=... bracket=...`) and theme (`--deck-note`).
10. WHILE drafting: `mtg note --type combo` the moment a combo is seen; `--type
    decision` for rejected candidates. If the budget gets tight, check `deck-view`'s
    **cost by type** and ASK the user before reallocating (BUILDER §11).
11. One annotation pass at the end: `mtg deck-annotate --auto` + refine + `--sync-notes`.
12. Fill lands: `mtg deck-fill-lands`. Inspect: `mtg deck-view`.
13. Score: `mtg deck-power` (bracket compliance if targeted; consistency TIER is
    consider-only). Audit against the plan: `mtg deck-gaps`. Validate: `mtg validate`;
    quality: `mtg deck-check`; budget: `mtg budget`.
14. Fix errors with `mtg deck-swap` (guided by `agents/deck_fixer.md`).
15. **Gate: `mtg preflight` must print `READY`.**
16. Export with `mtg export`; save with `mtg final-build` (ships `deck_list.json`).
17. Explain the final validated deck.

The agent must not claim the deck is done unless `mtg preflight` prints `READY`.
The legacy path (draft `output/decklist.txt` → `cards-batch --verify` →
`deck-write --structured`) still works, but loses entry-time validation, the running
budget, and purposes — prefer `deck-add`.

---

## New Agent File: `user-feedback.md`

`agents/user-feedback.md` helps the agent ask the user useful deckbuilding questions before building.

The agent should not leave questions open-ended when clear options are possible. It should ask using options like:

```text
Power level?
a) Casual
b) Optimized Casual
c) High Power
d) cEDH
e) Agent choice
```

The last option should usually be **Agent choice**, meaning the agent picks one of the listed options if the user does not care.

### Recommended user questions

The agent may ask about:

```text
- Power level
- Budget
- Commander build direction
- Specific card/effect includes
- Cards/effects to avoid
- Infinite combo preference
- Tutor preference
- Mana base quality
- Meta answers
```

The agent should ask only what is useful. Avoid asking too many questions before building.

Recommended maximum:

```text
up to 4 core questions before deckbuilding
```

---

## Power Level Brackets

Use these practical brackets.

### Casual

```text
Precon / precon-level
No infinite combos
No tutors unless user asks
Tapped lands are acceptable
Theme and fun matter more than optimization
```

### Optimized Casual

```text
Precon upgraded / optimized casual
1-2 tutors if they make sense
Mid synergy or better
No infinite combos by default
Avoid tapped lands unless they fit theme, commander, or budget
```

### High Power

```text
High synergy
Tutors allowed
1-2 incidental infinite combos allowed
The deck should not be built only around finding the combo unless requested
Avoid tapped lands unless they fit theme, commander, or budget
```

### cEDH

```text
No budget by default
Perfect or near-perfect synergy
Infinite combos allowed without limitation
Tutors and fast mana allowed
Prioritize speed, efficiency, and consistency
```

---

## Budget Handling

If the user does not mention budget, the agent should ask when budget is likely to affect card choices.

Suggested options:

```text
a) $100
b) $150
c) $200
d) No budget
e) Custom
f) Agent choice
```

Default if no budget is provided:

```text
No strict budget
```

If a custom budget is very low, the agent should still build the best possible deck near that budget. It should not stop deckbuilding.

Helpful budget behavior:

```text
- Treat basic lands as $0.
- Use cheaper alternatives when possible.
- Do not avoid expensive staples unless budget requires it.
- After the deck is created, optionally suggest upgrades if the user wants them.
```

---

## Deck Identity Model

The agent should separate:

```text
Commander = the card leading the deck
Archetype = broad Commander strategy
Detail = specific tribe/mechanic/subtheme/flavor
Constraints = user-specific requirements
```

Examples:

```text
Commander: Krenko, Mob Boss
Archetype: tokens (go-wide)
Detail: Goblins
```

```text
Commander: Chishiro, the Shattered Blade
Archetype: Voltron
Detail: Modified creatures, Equipment, Auras, +1/+1 counters
```

```text
Commander: Wilhelt, the Rotcleaver
Archetype: Tribal / Reanimator
Detail: Zombies, sacrifice, graveyard value
```

---

## Engine-First Deckbuilding

Do **not** build from rigid commander templates.

The agent should analyze the commander's engine:

```text
What starts the engine?
What resource does it use?
What resource does it generate?
What card types does it prefer?
What card patterns does it reward?
What does it naturally avoid?
What protects the engine?
What converts the engine into a win?
```

A good card should usually do one or more of these:

```text
- Feed the engine
- Multiply the engine
- Protect the engine
- Convert the engine into a win
- Cover an important deck role efficiently
```

This prevents shallow keyword matching.

Bad reasoning:

```text
This card says "token", so it fits the token deck.
```

Better reasoning:

```text
This card repeatedly creates tokens, the commander buffs those tokens, and the deck uses token count as a win condition.
```

---

## Broad Archetypes

Use broad archetypes, not overly narrow templates:

```text
battlecruiser
stax
spellslinger
control
pillowfort
voltron
group_hug
group_slug
reanimator
mill
theft
tribal
tokens
infect
```

The agent may combine archetypes when the commander naturally supports a hybrid deck.

Examples:

```text
tribal + tokens
spellslinger + voltron
blink + stax/control
graveyard value + reanimator
attack triggers + extra combats
```

---

## Package-Based Strategy Construction

Do not fill the deck with generic “synergy” cards.

Break strategy cards into:

```text
enablers
payoffs
engines
finishers
support
```

### Enablers

Cards that make the deck function.

Examples:

```text
token makers
sacrifice outlets
self-mill
cheap spells
equipment/auras
attack trigger creatures
ETB creatures
```

### Payoffs

Cards that reward the strategy.

Examples:

```text
lords
aristocrat drain
spell payoff creatures
token anthems
graveyard payoffs
attack trigger rewards
```

### Engines

Repeatable value cards.

Examples:

```text
repeatable draw
repeatable token generation
recursive permanents
blink loops
sacrifice loops
graveyard recursion
```

### Finishers

Cards that close the game.

Examples:

```text
mass pump
extra combat
commander damage
combo line
big threats
mill/drain/burn loops
control lock
```

### Support

Cards that protect or stabilize the plan.

Examples:

```text
protection
removal
recursion
tutors/search
mana fixing
meta answers
```

---

## Generic Deckbuilding Defaults

These are defaults. User requests and commander needs override them.

### Lands

Start with:

```text
32 base lands
+1 land per commander color, max +3
```

Then adjust for average mana value after the nonland package is built:

```text
0.0 - 2.6 avg mana value = +0 lands
2.7 - 3.3 avg mana value = +1 land
3.4+ avg mana value = +2 lands
```

For landfall or landsmatter decks:

```text
38 lands minimum
42 lands maximum
```

Recommended workflow:

```text
1. Build commander + 67 nonland cards.
2. Calculate land count.
3. Add lands.
4. Cut or adjust nonlands until the final deck is 99 main deck cards + commander.
```

### Ramp

Default minimum:

```text
9 ramp cards
```

Common baseline:

```text
5 mana rocks including Sol Ring and Arcane Signet when legal/appropriate
```

Increase ramp when:

```text
- commander is expensive
- commander is essential
- average mana value is high
- deck has expensive key spells
- deck wants to cast multiple spells per turn
```

### Card Draw / Card Advantage

Tutors are **search**, not draw.

Increase card advantage when:

```text
- deck has a low curve
- deck casts many spells
- deck empties its hand quickly
- deck specifically rewards draw/discard/loot
- deck needs to assemble specific engine pieces
```

### Removal

Default range:

```text
5-15 total removal pieces
```

Typical split:

```text
spot removal: 2-4
board wipes: 1 default, 3 max unless the deck wants more
artifact/enchantment removal: 0-2
graveyard hate: 0-1
counterspells: depends on deck/colors/power level
```

Removal attached to a permanent is better when the deck reuses permanents, blinks permanents, sacrifices permanents, or recurs permanents.

### Protection

Default range:

```text
0-5 protection pieces
```

Increase protection when:

```text
- commander is central to the deck
- commander is part of the main combo
- deck does not function without commander
- commander must attack/connect
- commander attracts heavy removal
```

### Win Conditions

Default:

```text
1-5 win conditions
```

The agent should clearly explain each win path.

Possible win paths:

```text
massive combat
commander damage
aristocrat drain
mill
combo
control lock
value overwhelm
big creatures
alternate win condition
```

---

## Combos and Tutors

### Infinite combos

Default policy depends on power level.

```text
Casual: avoid infinite combos
Optimized Casual: avoid infinite combos by default
High Power: allow 1-2 incidental combos
cEDH: allow combos freely
```

Important distinction:

```text
Incidental combo = allowed in higher power casual if pieces are already good in the deck.
Dedicated combo deck = only build if user asks.
```

### Tutors

Tutors are allowed depending on power level and user preference.

```text
Casual: avoid or limit tutors
Optimized Casual: 1-2 tutors if they make sense
High Power: tutors allowed
cEDH: tutors expected
```

Tutors should usually find:

```text
- key engine pieces
- important win conditions
- protection
- toolbox answers
```

---

## Deckbuilding Constraints

The agent can follow user constraints when building decks.

Examples:

```text
Create a Commander deck with Krenko, Mob Boss as commander. Archetype: tokens (go-wide). Detail: Goblins. Use exactly 33 lands.
Create a Chishiro deck with more Equipment and fewer board wipes.
Create a Wilhelt Zombie sacrifice deck with 35 lands and no infinite combos.
```

Supported constraint types:

```text
exact counts: 33 lands, 12 ramp, 2 board wipes
minimum counts: at least 30 creatures
maximum counts: no more than 3 board wipes
preferences: more ramp, less removal, more equipment
avoids: no infinite combos, avoid tutors
budget: $100, $150, $200, no budget, custom
power: casual, optimized casual, high power, cEDH
```

Always preserve:

```text
exactly 100 cards total
commander legality
color identity legality
singleton rule
no banned cards
```

---

## Output Files

Generated files are written to `output/`.

Common output files:

```text
output/deck.json                # the ANNOTATED deck (purposes, config, combos) — see deck-add
output/deck.enriched.json
output/deck.moxfield.txt
output/deck_explanation.md
output/validation_report.json
output/deck_check_report.json
output/commander_analysis.json
output/build-notes.json         # combos/decisions recorded with `mtg note`
```

### `output/deck.json`

The annotated deck (created by [`mtg deck-add`](#mtg-deck-add)) — judgment only;
card facts re-hydrate from the database on load:

```json
{
  "commander": "Chishiro, the Shattered Blade",
  "agent_note": "modified-creatures engine: counters + auras, wide payoff",
  "config": { "budget": "150", "budget_mode": "soft", "bracket": "n/a" },
  "combos": { "infinite": [], "non_infinite": [], "utility": [], "auto_win": [] },
  "main_deck": [
    { "name": "Sol Ring", "quantity": 1, "purpose": ["RAMP"] },
    { "name": "Rishkar's Expertise", "quantity": 1, "purpose": ["DRAW", "SYNERGY"],
      "agent_note": "draw scales with the biggest modified body" }
  ]
}
```

Legacy shapes (a flat card array, or `{commander, main_deck}` without purposes) are
still accepted by every consumer — they just carry no judgment.

### `output/deck.enriched.json`

Hydrated deck with full card data from SQLite.

The validator should hydrate internally and should not require the enriched file to validate.

### `output/deck.moxfield.txt`

Moxfield-compatible export:

```text
1 Chishiro, the Shattered Blade (NEC) 77
1 Akki Battle Squad (NEC) 18
1 Arcane Signet (LCC) 299
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'mtgcli'`

Run:

```bash
pip install -e .
```

Then use:

```bash
mtg status
```

---

### `mtg: command not found`

Make sure your virtual environment is activated:

```bash
source .venv/bin/activate
```

Then reinstall editable mode:

```bash
pip install -e .
```

---

### `mtg init-data` gets killed

This usually means the SQLite builder is using too much memory.

Make sure the database builder uses streaming JSON parsing with `ijson`, not `json.load()`.

Make sure `ijson` is installed:

```bash
pip install -r requirements.txt
```

---

### Database not found

Run:

```bash
mtg init-data
```

---

### Card lookup returns nothing

Make sure the SQLite database exists:

```bash
ls data/processed/mtg.sqlite
```

Then try:

```bash
mtg card "Sol Ring" --json-output
```

---

### Agent is producing generic decks

Check that the agent is using the files in this order:

```text
BUILDER.md
agents/system.md
agents/user-feedback.md
agents/commander_analyzer.md
agents/theme_detector.md
agents/card_ranker.md
agents/deck_builder.md
agents/deck_fixer.md
agents/deck_explainer.md
```

Also check that the agent is ranking by engine value, not just keyword matches.

Bad:

```text
Card mentions Goblin, so include it.
```

Good:

```text
Card creates Goblins repeatedly, feeds the deck's body count, and enables mass pump finishers.
```

---

### Deck validates but feels incoherent

Run deck-check and deck-gaps:

```bash
mtg deck-check --commander "<commander name>" --deck output/deck.json --json-output
```

Then use `agents/deck_fixer.md` to fix package balance issues.

Common causes:

```text
too few enablers
too many payoffs
not enough draw
not enough ramp
no clear win condition
too much generic goodstuff
too many cards that only keyword-match the theme
```

---

## Development Notes

Project layout (v0.8.0):

```text
src/mtgcli/
├── cli/               # the Typer CLI package (38 commands in commands/{data,search,cards,deck,analysis,misc}.py)
├── analyzer/          # evidence-first card analyzer: signals with provenance traces, ordinal bands
├── models/            # CARD and DECK build-context objects + the consistency-tier math
├── cards/             # SQLite repository, search engine, query parser
├── category_counts/   # slot planning (calculator, scoring, output)
├── deckbuilder/       # commander analyzer, oracle hooks, pricing, land filler, deck check,
│                      #   ramp rules, deck power, build notes, plan coverage
├── data/              # Scryfall download / normalize / SQLite build
├── combos/, explore/  # external combo & EDHREC data
├── export/            # Moxfield + final-builds
├── utils/, validator/ # deck IO, JSON IO, phrase matching, deck validation
└── config.py, logging_util.py
```

Key data files:

```text
data/seed/card_tags.json              # 140 functional tags — curated, DB-measured phrases
data/seed/tier_weights.json           # every consistency-tier constant, declared with provenance
data/seed/commander_overrides.json    # allowlist for non-creature face commanders
data/golden/golden_cards.json         # 376 hand-verified analyzer reads (the regression net)
data/processed/mtg.sqlite             # the card database (built by init-data)
```

Testing:

```bash
pip install -e .
python3 -m pytest -q     # 1300+ tests; the golden set catches analyzer regressions in seconds
```

Run the full suite after ANY code change, and add a regression test for any bug fixed.
Agent-facing workflow docs live in `BUILDER.md` (the canonical build contract) and
`agents/*.md` (per-role guides); `CHANGELOG.md` documents what each version fixed.

---

## Most Important Principle

```text
Do not make the Python app pretend to be the deckbuilder.
Make the Python app a reliable tool.
Make the CLI agent the flexible deckbuilder.
```

The best deckbuilding flow is:

```text
Commander text
→ engine analysis
→ user preferences
→ package plan
→ candidate search
→ card ranking
→ deck construction
→ validation
→ deck-check
→ export
→ explanation
```
