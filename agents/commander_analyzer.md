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

**Exact top-level paths** (don't guess nested locations — these live at the ROOT of the JSON):
`color_identity` (e.g. `["B","U"]`), `combined_color_identity` (with partner),
`is_valid_commander`, `analyzer` (the preferred archetype read; its `tags` list replaces the
deprecated tag lists), `archetype_fit` (legacy, deprecated), `legacy_deprecations` (what is
deprecated and what replaces it), `engine_profile`, `synergy_tags` (deprecated),
`wanted_card_patterns`, `oracle_hooks`, `build_direction_options`. The `commander` key holds the raw card object (name, oracle,
type_line, mana_cost) — identity fields are NOT nested inside it.

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

## Archetype: `analyzer` (preferred) then `archetype_fit` (legacy hint)

The analysis carries TWO archetype reads. Read them in this order:

**1. `analyzer` (preferred, evidence-first).** Contains `archetype_support` (ordinal bands
`very_high/high/medium/low`, each backed by detected evidence), `signals` (feature IDs the
analyzer detected in the oracle text), `tags` (the functional tag names it matched — the
single-source replacement for the deprecated `commander_tags`/`synergy_tags`),
`dominant_symmetry`, and `warnings`. For partners it also carries
`partner_archetype_support` / `partner_signals`. If you need the full evidence traces
(which rule fired on which text), run `mtg analyze-card "<Commander>"`.

**2. `archetype_fit` (legacy, DEPRECATED — removal planned v0.10).** Weighted text scores
(0-10), ordered best-first, with `low_confidence` flags. The analysis JSON carries a
machine-readable `legacy_deprecations` block naming it and its replacement; its numeric
scores can be confidently wrong. **When the two reads disagree, trust
`analyzer.archetype_support`** and treat `archetype_fit` as a secondary hint (BUILDER.md §7.0b).

If `archetype_support` is empty or all-low while the commander clearly has a plan, that is an
analyzer coverage gap: note it (it is calibration signal), reason from the oracle text yourself,
and proceed with your own judgment.

A `Toolbox / Goodstuff` band (multi-mode commander, 4+ activated abilities) means the per-mode
bands are options, not the theme — hand the mode choice to the user-feedback flow.

If the user forces a low-fit archetype, respect it but flag the risk.

```text
Low fit does not mean impossible.
It means the build needs more support and should not blindly follow compressed category targets.
```

A big creature commander now scores as a beatdown fit on its power/toughness alone, so an
8/7 with little oracle text still reads as `stompy`/`go_tall` rather than defaulting to value.

---

## Engine Package — build to the mechanical hook

`engine_profile.primary_pattern`, `synergy_tags`, and `wanted_card_patterns` name *how the
commander actually wins or generates value*. Translate them into the deck's synergy package
directly — do not flatten the commander into a generic archetype and fill with goodstuff.

Read `wanted_card_patterns` as a shopping list and turn each entry into `suggest`/`search-tags`.
Entries suffixed "(analyzer high/very_high)" come from the evidence-first analyzer and already
carry a ready-to-run command (e.g. `Go Wide (analyzer high): mtg search-tags go_wide_payoff
token_maker anthem`) — run those first; they are the commander's detected plan. Turn the rest into `suggest`/`search-tags`
queries. Examples of hooks the analyzer surfaces:

```text
etb_blink_engine        -> ETB creatures, blink/flicker, cheap value bodies
death_trigger_engine    -> sac outlets, death payoffs, token fodder
token_engine            -> repeatable token makers, doublers, anthems
targeted_spell_payoff   -> CHEAP spells that target YOUR OWN creatures, and
                           recurring/buyback auras (e.g. Whip Silk) to retrigger
```

The `targeted_spell_payoff` class is easy to miss: the commander fires whenever a creature you
control becomes the target of a spell (yours included), so low-cost self-targeting spells and
buyback auras turn it into a repeatable engine — these belong in the build even though generic
archetype filling would never surface them.

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
