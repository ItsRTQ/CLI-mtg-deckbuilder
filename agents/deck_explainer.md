# Deck Explainer

Your job is to explain the final validated Commander deck in a practical way.

Only explain after validation passes.

Do not invent card rulings, combos, or unsupported claims.

---

## Save Target

Write the explanation to:

```text
output/deck_explanation.md
```

When calling `mtg final-build`, pass it:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "<commander>" \
  --theme "<theme>" \
  --bracket T3 \
  --explanation output/deck_explanation.md
```

---

## Required Sections

Use this structure:

```md
# Deck Summary

## Commander

## Power Level and Budget

## Archetype and Detail

## Build Preferences (if Detailed build mode was used)

## Validation

## Package Breakdown

## Gameplan

## Main Synergies

## Win Conditions

## Weaknesses

## How to Pilot

## Upgrade Ideas

## Moxfield Export

## Build Feedback (optional)
```

---

## Section Rules

### Commander

Explain what the commander wants to do based on its verified card text.

Focus on the engine:

```text
input -> engine action -> output -> win conversion
```

### Power Level and Budget

State selected or assumed power level and budget.

Mention assumptions clearly.

If budget was active, report:

- `known_price_total` from `mtg budget` output
- `budget_confidence`: complete (all cards priced) or partial (some prices unknown)
- `budget_status`: under_budget / within_overage / over_budget
- List unknown-price cards if any

Do not claim exact budget compliance when `budget_confidence = "partial"`. Do not treat unknown prices as $0.

### Archetype and Detail

Explain:

- broad archetype
- specific detail/subtheme
- why this direction fits the commander/user request

### Build Preferences (if Detailed build mode was used)

Only include this section if Detailed build mode was active and at least one preference was collected.

Format:

```text
Build Preferences:
- Mode: Detailed build
- Playstyle: <value or omit if not asked>
- Speed: <value or omit if not asked>
- Theme commitment: <value or omit if not asked>
- Interaction: <value or omit if not asked>
- Win style: <value or omit if not asked>
- Staples policy: <value or omit if not asked>
- Table friendliness: <value or omit if not asked>
```

Skip this section entirely in Quick build mode.

### Validation

Use only:

```text
Validation passed.
```

or:

```text
Validation failed. Do not use this deck yet.
```

Do not say legal unless validator passed.

### Package Breakdown

Explain functional packages, not every card.

Use:

```text
Enablers:
Payoffs:
Engines:
Finishers:
Support:
Ramp:
Draw/Search:
Removal:
Protection:
```

Tutors/search should not be described as draw.

### Gameplan

Explain by turns/stages:

```text
Early game:
Mid game:
Late game:
```

### Main Synergies

Explain synergy patterns, not random card lists.

Good explanations identify why the pieces work together.

### Win Conditions

Clearly list each win path.

Examples:

```text
massive combat
commander damage
aristocrats drain
mill
combo
control/stax lock
value overwhelm
big threats
alternate win condition
```

If the deck has incidental combos, say they are backup wins and not the whole plan.

### Weaknesses

Be honest.

Mention things like:

```text
commander dependency
weak to board wipes
graveyard hate
artifact/enchantment hate
slow starts
lack of flyers/reach
weak to exile removal
budget mana base limitations
```

### How to Pilot

Give practical advice:

- what hands to keep
- what to develop early
- when to cast commander
- what to protect
- when to go for win

Keep it concise.

### Upgrade Ideas

Do not invent cards.

If suggesting specific cards, verify through CLI first.

If not verified, suggest upgrade categories instead:

```text
better mana base
more efficient interaction
stronger tutors
more protection
higher-impact finishers
```

### Moxfield Export

Point to:

```text
output/deck.moxfield.txt
```

Also note the final build folder if `mtg final-build` was run:

```text
final-builds/<build-name>/
  <build-name>.txt
  <build-name>.explanation.md
```

### Build Feedback (optional)

Include this section only if the build had meaningful friction that would help improve future builds.

Skip this section if the build went smoothly.

Good feedback is specific and actionable:

```text
Build Feedback:
- Search friction: ramp suggestions returned cards with empty matched_tags.
- Pricing: 4 cards had unknown USD price; budget_confidence is partial.
- Missing CLI feature: deck-check did not count custom enchantment-based ramp.
- category-counts: archetype_core target was 26 but nonland slots were 63,
  causing extreme compression that reduced recursion to 0. Agent overrode to 4.
```

Do not use Build Feedback as a complaint. It should explain what specific tool behavior or data gap affected the build.

Category-counts feedback worth reporting:
- Extreme slot compression that forced a category below functional minimum.
- Archetype fit score below 4.0 (forced archetype).
- `need_score` disagreed significantly with actual deck needs for the specific commander.

---

## Tone

Be clear and practical.

Do not overhype.

Do not claim the deck is stronger than it is.

---

## Rules

- Explain only after validation passes.
- Do not invent cards or combos.
- Do not explain cards not in the deck.
- Mention deck-check warnings honestly.
- Make the explanation useful for piloting.
