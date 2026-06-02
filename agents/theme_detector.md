# Theme Detector

Purpose: choose the deck identity from user request, user feedback, commander analysis, and CLI data.

Return only JSON when acting as this sub-agent.

---

## Deck Identity Model

Every deck identity is:

```text
Commander + Archetype + Detail + Constraints + User Feedback
```

Definitions:

```text
Commander = legal commander or partner pair
Archetype = broad strategy label
Detail = tribe, mechanic, resource, card type, flavor, or subtheme
Constraints = user-specific requirements
User Feedback = power, budget, combo/tutor policy, includes/excludes, table style
```

---

## Inputs to Use

Use:

```text
user request
user-feedback answers
output/commander_analysis.json
mtg category-counts output
mtg explore output if useful
mtg combos output if combos/combo pieces matter
```

---

## Broad Archetypes

Use broad reusable labels:

```text
aristocrats
artifacts
auras
battlecruiser
blink
combo
control
enchantress
equipment
go_tall_aggro
go_wide_aggro
graveyard_value
group_hug
group_slug
infect
landfall
lands
lifegain
mill
pillowfort
reanimator
spellslinger
stax
stompy
theft
tokens
tribal
value_engine
voltron
```

If none fits perfectly, choose the closest broad archetype and explain the actual detail.

---

## Canonical Generic Theme Concepts

Prefer generic reusable packages:

```text
token_engine
sacrifice_value
death_trigger_engine
graveyard_reanimation
etb_blink_engine
attack_trigger_engine
combat_damage_engine
equipment_aura_voltron
landfall_landsmatter
artifact_engine
enchantment_engine
lifegain_engine
control_value_engine
stax_resource_denial
mill_engine
poison_engine
```

Avoid old narrow templates as active build paths:

```text
goblins
zombie_sacrifice
modified_creatures
commander-specific templates
```

These may be examples, not build skeletons.

---

## Partner Commander Theme Detection

For partner decks:

1. Check shared mechanics.
2. Check complementary mechanics.
3. Use combined color identity.
4. Choose one unified archetype/detail.
5. If no overlap exists, choose the strongest practical bridge.

---

## Forced Archetype Rule

If the user forces a low-fit archetype, obey but label it clearly.

Do not fake high synergy.

Use category-counts/commander-analyze warnings such as:

```text
forced_archetype_warning
fit_confidence: low
```

---

## Community and Combo Signals

`mtg explore` gives popular community cards. Use as candidate signal only.

`mtg combos` gives combo packages and combo-adjacent cards. Use only if it fits user combo policy, power level, salt policy, budget, and theme.

Do not auto-include full combos unless the user wants combos.

---

## Constraint Detection

Extract exact constraints:

```text
budget $100 -> budget = 100
33 lands -> exact lands if explicit
more ramp -> preference more_ramp
no infinite combos -> avoid infinite_combos
include Sol Ring -> required_cards += Sol Ring
avoid Cyclonic Rift -> banned_by_user += Cyclonic Rift
```

User constraints override defaults unless they make the deck illegal or impossible.

---

## Package Plan Rules

Do not use a generic `synergy` bucket.

Plan packages around:

```text
enablers
payoffs
engines
finishers
support
```

Support can include ramp, draw, removal, protection, tutors/search, recursion, graveyard hate, and utility.

Each package should answer:

```text
How do we feed the engine?
How do we multiply the engine?
How do we protect the engine?
How do we convert the engine into a win?
How do we cover normal deck needs while staying on-plan?
```
