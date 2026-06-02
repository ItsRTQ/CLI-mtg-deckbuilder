# Deck Explainer

Purpose: explain the finalized deck clearly after validation passes.

Write the explanation to:

```text
output/deck_explanation.md
```

Do not claim the deck is complete unless validation passed.

---

## Required Inputs

Use:

```text
output/deck.json
output/deck.enriched.json if available
output/commander_analysis.json
output/commander_combos.json if used
category-counts output if available
validation report
deck-check report
budget report if budget exists
user feedback preferences
```

---

## Explanation Structure

Use this order:

```text
# Deck Explanation: <Commander> - <Theme>

## Summary
## Build Preferences
## Commander Gameplan
## Package Breakdown
## Ramp / Mana Plan
## Card Advantage Plan
## Interaction and Protection
## Win Conditions
## Combo Notes, if relevant
## Budget Status, if relevant
## Validation Status
## Weaknesses
## Upgrade / Downgrade Ideas, optional
## Build Feedback, optional
```

---

## Summary

Include:

```text
commander / partner
archetype
detail/theme
power bracket
budget assumption
validation status
final build path if available
```

---

## Package Breakdown

Explain package choices using category-counts and commander analysis.

Mention where the deck follows or intentionally deviates from `recommended_range`.

Do not pretend compressed category-count targets are hard rules.

---

## Win Conditions

List realistic win paths.

Examples:

```text
combat damage
token swarm
commander damage
aristocrats drain
combo finish
value engine into attrition
big mana finisher
```

If combos are included, explain:

```text
combo cards
what the combo produces
bracket/power relevance
why it fits user combo policy
```

If combos are not included but combo data was checked, say combo data was treated as context only.

---

## Budget Status

If budget applies, include:

```text
budget limit
known price total
budget status
unknown-price cards
budget confidence
```

Do not claim exact budget compliance if unknown-price cards remain.

Budget is a maximum, not a target.

---

## Validation Status

State whether validation passed.

Mention:

```text
main deck count
commander-zone count
total cards including commanders
color identity
Commander legality
singleton rule
```

Do not say final if validation failed.

---

## Weaknesses

Be honest. Examples:

```text
commander dependency
weak to board wipes
weak to graveyard hate
slow mana base
limited card draw
combo vulnerability
budget substitutions
unknown prices
```

---

## Build Feedback

Optional. Include only if useful.

Good feedback is specific and actionable:

```text
Build Feedback:
- Search friction: `suggest --role ramp` returned lands, so ramp needed manual filtering.
- Category-count friction: forced low-fit archetype compressed removal below practical floor.
- Validation friction: structured command-zone handling needed review.
```

Skip this section if the build went smoothly.
