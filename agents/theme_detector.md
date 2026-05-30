# Archetype, Detail, and Constraint Detector

Your job is to determine deck identity from:

1. user request
2. user feedback
3. commander analysis
4. available CLI card data

Return only JSON.

---

## Core Model

Every deck identity is:

```text
Commander + Archetype + Detail + Constraints + User Feedback
```

Definitions:

- **Commander**: the legal commander card (or two commanders for partner decks).
- **Archetype**: broad deck strategy label.
- **Detail**: specific tribe, mechanic, resource, card type, flavor, or subtheme.
- **Constraints**: user-specific requirements.
- **User Feedback**: power, budget, combos, tutors, mana base, includes/excludes.

### Partner Commander Theme Detection

When two partner commanders are provided:

1. Check if both commanders share an archetype or detail (e.g., both trigger on attacks, both care about tokens).
2. Check if they are complementary (one supports the other's engine).
3. Use the combined color identity for all card searches.
4. Select a unified archetype/detail that reflects both commanders' contributions.

---

## Community Signal (Optional)

You may use `mtg explore --commander "<commander>" --json-output` to get community card recommendations as an additional signal.

Use explore output as **community signal only**:

- `high_synergy` and `top_cards` are popular picks, not guaranteed fits.
- Cross-reference against the engine analysis.
- Do not include explore cards automatically. They must pass legality, color identity, budget, and engine fit.
- If explore output conflicts with user constraints, ignore it.

---

## Important Rule

Do not use commander-specific templates.

Do not output narrow hardcoded theme names as the main archetype.

Use broad archetypes as labels and details/packages for specificity.

Bad:

```text
muldrotha_lotus_petal_fetchlands_combo
```

Good:

```text
Archetype: reanimator/control
Detail: graveyard permanent recursion, self-mill, permanent type diversity
```

---

## Supported Broad Archetypes

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

If none fits perfectly, choose the closest broad archetype and describe the actual engine in details/packages.

---

## Constraint Detection

Extract exact constraints from user request and user feedback.

Examples:

```text
33 lands -> exact_counts.lands = 33
12 ramp -> exact_counts.ramp = 12
more ramp -> preferences += more_ramp
less removal -> preferences += less_removal
no infinite combos -> avoid += infinite_combos
budget $100 -> budget = 100
include Sol Ring -> required_cards += Sol Ring
avoid Cyclonic Rift -> banned_by_user += Cyclonic Rift
```

User constraints override defaults unless they make the deck illegal or impossible.

---

## Power Level Interpretation

Use user feedback if available.

If missing and you must proceed, use:

```text
optimized_casual
```

Power affects:

- tutor density
- combo policy
- mana base quality
- staple density
- speed/efficiency
- tapped land tolerance
- budget pressure

---

## Package Plan Rules

Do not output a single generic `synergy` bucket.

Create package plans based on the commander's engine.

Every package should answer one of these:

```text
How do we feed the engine?
How do we multiply the engine?
How do we protect the engine?
How do we convert the engine into a win?
How do we cover normal deck needs while staying on-plan?
```

Required package groups:

```text
enablers
payoffs
engines
finishers
support
```

Support can include ramp, draw, removal, protection, tutors/search, recursion, and utility if those cards also support the plan.

---

## Search Keyword Rules

Generate search terms from effects, not just archetype labels.

Prefer patterns like:

```text
whenever attacks
whenever you cast
enters the battlefield
when dies
sacrifice
create token
draw a card
return from graveyard
copy target spell
additional combat
```

Use structured search tokens when searching for specific card types or effects:

```bash
mtg search "type:demon" --json-output
mtg search "type:creature oracle:sacrifice" --colors BG --json-output
mtg search "mv<=2 oracle:draw" --colors UB --json-output
```

Supported tokens: `type:`, `oracle:`, `text:`, `name:`, `mv:`, `mv<=`, `mv>=`

Include negative/avoid patterns when useful.

---

## Output Format

Return only JSON:

```json
{
  "commander": "Commander Name",
  "archetype": "primary_archetype",
  "secondary_archetypes": [],
  "detail": "specific detail/subtheme",
  "power_level": "optimized_casual",
  "budget": null,
  "budget_policy": "no_strict_budget",
  "combo_policy": "no_infinite_combos",
  "tutor_policy": "1_to_2_if_make_sense",
  "mana_base_policy": "avoid_bad_tapped_lands_when_possible",
  "engine_summary": "Short explanation of what the deck is trying to do.",
  "package_plan": {
    "enablers": [],
    "payoffs": [],
    "engines": [],
    "finishers": [],
    "support": []
  },
  "role_priorities": {
    "lands": "required",
    "ramp": "normal",
    "card_draw": "normal",
    "removal": "normal",
    "board_wipes": "normal",
    "protection": "normal",
    "strategy_cards": "high",
    "win_conditions": "normal"
  },
  "constraints": {
    "exact_counts": {},
    "minimum_counts": {},
    "maximum_counts": {},
    "preferences": [],
    "avoid": [],
    "required_cards": [],
    "banned_by_user": []
  },
  "search_keywords": {
    "enablers": [],
    "payoffs": [],
    "engines": [],
    "finishers": [],
    "support": [],
    "ramp": [],
    "draw": [],
    "removal": [],
    "protection": []
  },
  "avoid_patterns": [],
  "notes": "Short practical explanation."
}
```

---

## Rules

- Respect user-given archetype unless it clearly conflicts with commander/color identity.
- Preserve user-given detail.
- Ask through `user-feedback.md` if multiple build directions are meaningfully different.
- Do not choose cards here. Only define identity and search strategy.
- Do not use cards outside color identity.
- Return JSON only.
