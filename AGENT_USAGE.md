# Agent Usage Guide

This project is a local MTG Commander deckbuilding tool.

The agent should use the markdown files in `agents/` as behavior instructions and use the Python CLI commands as the source of truth.

## Main workflow

When the user asks:

```text
Build a deck with <commander> as commander.
```

Do this:

1. Read `agents/system.md`.
2. Read `agents/commander_analyzer.md`.
3. Look up the commander:

```bash
python -m src.mtgcli.cli card "<commander>" --json-output
```

4. Analyze the commander using the returned JSON.

5. Read `agents/theme_detector.md`.

6. Determine the deck theme and identify any user-provided constraints (e.g., land count, role priorities).

7. Adjust the deck skeleton based on constraints before searching for cards.

8. Search/suggest cards by role:

```bash
python -m src.mtgcli.cli suggest --commander "<commander>" --role ramp --json-output
python -m src.mtgcli.cli suggest --commander "<commander>" --role card_draw --json-output
python -m src.mtgcli.cli suggest --commander "<commander>" --role removal --json-output
python -m src.mtgcli.cli suggest --commander "<commander>" --role board_wipe --json-output
python -m src.mtgcli.cli suggest --commander "<commander>" --role protection --json-output
python -m src.mtgcli.cli suggest --commander "<commander>" --role synergy --json-output
```

8. Read `agents/card_ranker.md`.

9. Rank candidate cards.

10. Read `agents/deck_builder.md`.

11. Create `output/deck.json`.

12. Validate:

```bash
python -m src.mtgcli.cli validate --commander "<commander>" --deck output/deck.json --json-output
```

13. If validation fails:
    - read `agents/deck_fixer.md`
    - fix `output/deck.json`
    - validate again

14. Export:

```bash
python -m src.mtgcli.cli export output/deck.json --output output/deck.moxfield.txt
```

15. Read `agents/deck_explainer.md`.

16. Create a final explanation.

## Required rule

Never give the user a final deck until validation passes.
