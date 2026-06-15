# CLI-mtg-deckbuilder

Local Python CLI tool and agent workflow for building, validating, checking, explaining, and exporting **Magic: The Gathering Commander** decks.

The project is designed around one important rule:

```text
The Python `mtg` CLI provides facts, search, validation, deck checks, enrichment, and export.
The external CLI agent makes deckbuilding decisions.
```

The app should not try to fully replace deckbuilding judgment. It should act as a reliable tool layer that gives the agent accurate card data and legality checks.

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
Archetype: Tribal.
Detail: Goblins.
Use BUILDER.md.
```

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

## Common Commands

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
mtg card "Edgar Markov" --json-output
```

Card data includes creature `power` and `toughness` (stored as text, since values
can be non-numeric like `*` or `1+*`; `null` for non-creatures):

```json
{
  "name": "Edgar Markov",
  "mana_cost": "{3}{R}{W}{B}",
  "mana_value": 6.0,
  "type_line": "Legendary Creature — Vampire Knight",
  "oracle_text": "...",
  "power": "4",
  "toughness": "4",
  "colors": ["B", "R", "W"],
  "color_identity": ["B", "R", "W"],
  "commander_legal": true,
  "can_be_commander": true
}
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

Validate a deck:

```bash
mtg validate --commander "Chishiro, the Shattered Blade" --deck output/deck.json
```

Validate with JSON output:

```bash
mtg validate --commander "Chishiro, the Shattered Blade" --deck output/deck.json --json-output
```

Enrich a deck with full card data:

```bash
mtg enrich output/deck.json --output output/deck.enriched.json
```

Run deck quality checks, if available:

```bash
mtg deck-check --commander "Chishiro, the Shattered Blade" --deck output/deck.json --json-output
```

Export a deck to Moxfield format:

```bash
mtg export output/deck.json --output output/deck.moxfield.txt
```

---

## Future / Recommended Commands

These commands are recommended as the project improves:

```bash
mtg archetypes
```

```bash
mtg archetype-info voltron --json-output
```

```bash
mtg suggest-package \
  --commander "Krenko, Mob Boss" \
  --archetype tribal \
  --detail "goblins" \
  --package enablers \
  --limit 30 \
  --json-output
```

```bash
mtg deck-check \
  --commander "Krenko, Mob Boss" \
  --deck output/deck.json \
  --archetype tribal \
  --detail "goblins" \
  --json-output
```

The agent should prefer package-based commands when available because they produce more useful candidates than a generic `synergy` search.

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

When asked to build a deck, the agent should:

1. Read the user request.
2. Identify commander, archetype, detail, and constraints.
3. Use `agents/user-feedback.md` to ask useful preference questions if needed.
4. Look up the commander through the `mtg` CLI.
5. Confirm the commander exists, is Commander legal, and can be a commander.
6. Analyze the commander's engine from the returned card object.
7. Determine broad archetype and specific detail.
8. Build package goals.
9. Search/suggest candidates using the CLI.
10. Rank candidates with `agents/card_ranker.md`.
11. Build `output/deck.json`.
12. Validate with `mtg validate`.
13. Fix errors with `agents/deck_fixer.md`.
14. Run `mtg deck-check` if available.
15. Export with `mtg export`.
16. Explain the final validated deck.

The agent must not claim the deck is valid unless validation passes.

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
Archetype: Tribal
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
Create a Commander deck with Krenko, Mob Boss as commander. Archetype: Tribal. Detail: Goblins. Use exactly 33 lands.
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
output/deck.json
output/deck.enriched.json
output/deck.moxfield.txt
output/deck_explanation.md
output/validation_report.json
output/deck_check_report.json
```

### `output/deck.json`

Simple decklist used by validator/exporter:

```json
[
  {
    "quantity": 1,
    "name": "Chishiro, the Shattered Blade",
    "set_code": "nec",
    "collector_number": "77"
  },
  {
    "quantity": 1,
    "name": "Sol Ring",
    "set_code": "lcc",
    "collector_number": "299"
  }
]
```

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

Run deck-check if available:

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

Recommended future improvements:

```text
- Add archetype profile support.
- Add package-based suggestion commands.
- Add deck-check support for package balance.
- Deduplicate suggestions by oracle_id.
- Add price-aware budget filtering.
- Add power-level-aware tutor/combo filtering.
- Add engine-pattern tags during card normalization.
```

Recommended seed/config files:

```text
data/seed/card_tags.json
data/seed/role_definitions.json
data/seed/deck_skeletons.json
data/seed/constraint_rules.json
data/seed/archetype_profiles.json
data/seed/power_level_profiles.json
```

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
