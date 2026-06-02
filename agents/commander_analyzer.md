# Commander Analyzer

Purpose: convert commander data into a tactical map for deckbuilding.

Use the CLI. Do not rely on model memory for card text.

---

## Required Commands

Single commander:

```bash
mtg commander-analyze --commander "<commander>" --output output/commander_analysis.json --json-output
```

Partner commanders:

```bash
mtg commander-analyze --commander "<commander A>" --partner "<commander B>" --output output/commander_analysis.json --json-output
```

With context:

```bash
mtg commander-analyze \
  --commander "<commander>" \
  --archetype "<archetype>" \
  --theme "<theme>" \
  --power-level <number> \
  --philosophy "<philosophy>" \
  --meta "<meta>" \
  --output output/commander_analysis.json \
  --json-output
```

---

## What to Read From the Analysis

Use `output/commander_analysis.json` for:

```text
color identity
commander slots / library slots
card types / subtypes / supertypes
power/toughness
text signals
commander tags
commander type tags
synergy tags
anti-synergy tags
engine profile
archetype fit
role pressures
commander scores
provides / requires / rewards
wanted card patterns
avoid card patterns
build direction options
```

Do not invent missing fields. If power/toughness is null, treat it as unknown.

---

## Commander Interpretation

Analyze the commander through these questions:

```text
What does the commander reward?
What does it require from the deck?
What does it provide by itself?
How dependent is the deck on the commander?
How likely is the commander to be removed on sight?
Does it need ramp, protection, evasion, redundancy, or recursion?
Is it combat-oriented, engine-oriented, combo-oriented, or support-oriented?
```

---

## Type and Creature Stats

Use type and subtype carefully.

Examples:

```text
Vampire / Dinosaur / Zombie / Dragon -> possible tribal signal
Artifact / Enchantment / Planeswalker -> card-type strategy signal
Equipment / Aura text -> Voltron/equipment/aura signal
```

Do not assume every subtype means tribal.

Use power/toughness for:

```text
Voltron viability
aggro pressure
go_tall/go_wide combat evaluation
commander fragility
blocker quality
combat-damage trigger support
creature finisher evaluation
```

Do not let P/T dominate non-combat roles.

---

## Archetype Fit

Use `archetype_fit` to identify natural paths.

If the user forces a low-fit archetype, respect it but flag the risk.

```text
Low fit does not mean impossible.
It means the build needs more support and should not blindly follow compressed category targets.
```

---

## Output to Other Agents

The analysis should guide:

```text
theme selection
category-counts arguments
suggest --synergy
card ranking
role pressure fixes
deck explanation
Build Feedback
```
