# Commander Analyzer

Purpose: turn commander data into a tactical map for the build.

Use the CLI. Do not rely on model memory for card text.

---

## Required Command

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

## What to Extract

Use `output/commander_analysis.json` to understand:

```text
color_identity
commander_slots / library_slots
card types and subtypes
text signals
commander tags
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

---

## Analysis Questions

Answer these before building:

```text
What does the commander provide?
What does the commander require?
What does the commander reward?
Is the commander the engine, payoff, wincon, or support piece?
How commander-dependent is the deck?
How likely is the commander to be removed on sight?
Does the commander need ramp, protection, evasion, recursion, or redundancy?
What card types, subtypes, zones, events, and resources matter?
What archetypes naturally fit?
What archetypes are forced/low-fit?
```

---

## Type and Subtype Rules

Type tags are signals, not automatic archetypes.

Example:

```text
Vampire subtype -> possible tribal_vampire signal
Artifact commander -> possible artifact_engine signal
Planeswalker commander -> planeswalker_commander signal
```

Do not force tribal just because a commander has a creature subtype.

---

## Provides / Requires / Rewards

Keep these separate:

```text
provides = commander directly supplies the effect
requires = commander needs support to function
rewards = commander makes more of that effect/card type better
```

Examples:

```text
Commander draws cards -> provides card_draw
Commander must attack/connect -> requires protection/evasion
Commander creates tokens -> provides tokens and may reward token payoffs
Commander rewards creatures dying -> rewards sacrifice/death_trigger packages
Commander costs 6+ -> requires ramp and protection
```

---

## Partner Commanders

For partner decks:

```text
combine color identity
analyze each commander separately
then analyze overlap and complementarity
build one unified plan
main deck size is 98
```

---

## How Other Agents Use It

`commander_analysis.json` should guide:

```text
category-counts
suggest --synergy
card ranking
package planning
deck fixing
deck explanation
```

If the analysis looks wrong or weak, do not blindly follow it. Note the issue in Build Feedback.
