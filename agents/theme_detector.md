# Theme Detector

Purpose: choose the deck identity from user request, feedback, commander analysis, and CLI data.

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
Constraints = budget, power, salt policy, combo policy, includes/excludes
User Feedback = playstyle, speed, theme strictness, staple policy, interaction preference
```

---

## Inputs to Use

```text
user request
user-feedback answers
output/commander_analysis.json
category-counts output
mtg explore output if useful
mtg combos output if combo context matters
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

If none fits perfectly, pick the closest broad archetype and store the specific detail separately.

---

## Detail Examples

```text
tribal_vampire
token_engine
sacrifice_value
death_trigger_engine
graveyard_recursion
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

Avoid old narrow build templates as active strategy labels:

```text
goblins
zombie_sacrifice
modified_creatures
commander-specific templates
```

Use canonical generic concepts instead.

---

## Search Support

Use structured search and repeatable filters to inspect theme support.

Examples:

```bash
mtg search "type:vampire" --type creature --json-output
mtg search --oracle "draw a card" --type creature --json-output
mtg search --oracle "can't be blocked" --oracle target --oracle creature --json-output
mtg search "landfall" --type enchantment --json-output
mtg search-tags card_draw --type creature --json-output
```

Repeated filters use AND semantics.

---

## Explore and Combos

`mtg explore` gives community cards. `mtg combos` gives combo packages and combo-adjacent cards.

Use them as context, not mandatory includes.

Combo policy:

```text
No combos -> avoid full combo lines
Incidental combos -> individual good pieces may be used
Combo plan -> evaluate compact packages by bracket/power/salt/budget/theme
```

---

## Output Shape

When acting as this sub-agent, return JSON like:

```json
{
  "commander": "<name>",
  "partner": null,
  "archetype": "tokens",
  "detail": "tribal_vampire",
  "constraints": {
    "budget": 200,
    "power_bracket": "T3",
    "combo_policy": "incidental_ok",
    "salt_policy": "normal"
  },
  "confidence": "medium",
  "reasons": [
    "Commander analysis shows token_engine and tribal_vampire tags."
  ],
  "risks": []
}
```
