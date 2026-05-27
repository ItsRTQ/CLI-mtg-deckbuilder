# CLI-mtg-deckbuilder

Local Python CLI tool for building, validating, and exporting Magic: The Gathering Commander decks.

The tool downloads Scryfall card data, stores normalized card data in SQLite, exposes card lookup/search/validation commands, and gives a CLI agent enough tools to build Commander decks.

## Requirements

- Python 3.11+
- Local virtual environment
- Internet connection for first Scryfall data download

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

Editable mode means changes inside `src/mtgcli/` are picked up automatically. You usually do not need to rerun `pip install -e .` after changing normal Python source files.

Run `pip install -e .` again only if you change packaging configuration, CLI entry points, or `pyproject.toml`.

## Initialize card data

Download and build the local SQLite card database:

```bash
mtg init-data
```

This will:
1. Download Scryfall bulk card data if missing.
2. Normalize card records.
3. Build `data/processed/mtg.sqlite`.

If the raw card data already exists, the command will skip the download and rebuild SQLite.

## Common commands

Check project status:
```bash
mtg status
```

Look up a card:
```bash
mtg card "Sol Ring"
```

Look up a card as JSON:
```bash
mtg card "Sol Ring" --json-output
```

Search Commander-legal cards:
```bash
mtg search "draw a card" --colors RG --limit 20
```

Search cards by tags:
```bash
mtg search-tags ramp card_draw --colors RG --limit 30
```

Suggest cards for a commander by role:
```bash
mtg suggest --commander "Chishiro, the Shattered Blade" --role ramp --limit 20
```

Available roles depend on `data/seed/role_definitions.json`.

Validate a deck:
```bash
mtg validate --commander "Chishiro, the Shattered Blade" --deck output/deck.json
```

Validate with JSON output:
```bash
mtg validate --commander "Chishiro, the Shattered Blade" --deck output/deck.json --json-output
```

Export a deck to Moxfield format:
```bash
mtg export output/deck.json --output output/deck.moxfield.txt
```

## Agent usage

The external CLI agent should use `AGENT_USAGE.md` as its main guide.

Example prompt to the agent:
> Create a Commander deck with `Krenko, Mob Boss` as commander. Theme: Goblins. Use AGENT_USAGE.md.

The agent should:
1. Look up the commander.
2. Detect the theme.
3. Use `mtg suggest` and `mtg search` to find candidates.
4. Create `output/deck.json`.
5. Validate the deck.
6. Fix validation errors.
7. Export to `output/deck.moxfield.txt`.
8. Create `output/deck_explanation.md`.

The agent must not claim the deck is valid unless validation passes.

## Output files

Generated files are written to `output/`.

Common output files:
- `output/deck.json`
- `output/deck.moxfield.txt`
- `output/deck_explanation.md`
- `output/validation_report.json`

## Troubleshooting

### ModuleNotFoundError: No module named 'mtgcli'
Run:
```bash
pip install -e .
```
Then use:
```bash
mtg status
```

### mtg: command not found
Make sure your virtual environment is activated:
```bash
source .venv/bin/activate
```
Then reinstall editable mode:
```bash
pip install -e .
```

### mtg init-data gets killed
This usually means the SQLite builder is using too much memory. The database builder should use streaming JSON parsing with `ijson`, not `json.load()`.

Make sure `ijson` is installed:
```bash
pip install -r requirements.txt
```

### Database not found
Run:
```bash
mtg init-data
```

### Card lookup returns nothing
Make sure the SQLite database exists:
```bash
ls data/processed/mtg.sqlite
```
Then try:
```bash
mtg card "Sol Ring" --json-output
```
