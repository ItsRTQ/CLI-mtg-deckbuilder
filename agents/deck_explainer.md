# Deck Explainer

Purpose: explain the finalized deck clearly after validation passes.

Write the explanation to:

```text
output/deck_explanation.md
```

Do not claim the deck is complete unless validation passed.

---

## Inputs

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
final-build output if available
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

If available, include commander power/toughness:

```text
Power/Toughness: 4/4
```

Omit P/T when missing. Do not invent it.

---

## Commander Gameplan

Explain using `commander_analysis.json`:

```text
what the commander rewards
what the deck provides
what the commander provides
what the commander needs
primary engine pattern
main synergy tags
primary win conversion
```

---

## Package Breakdown

Describe major packages:

```text
ramp
card draw / advantage
interaction
protection
recursion
archetype core
enablers
payoffs
win conditions
lands
utility
```

Mention if package counts followed category-count ranges or were adjusted by user preference.

---

## Combo Notes

If combos are included, explain:

```text
cards involved
result of the combo
bracket/power appropriateness
why it fits user preference
```

If combo data was checked but not used, say it was treated as optional context.

---

## Budget Status

If budget exists, include:

```text
budget limit
known price total
budget status
unknown-price cards
confidence
```

Do not claim exact compliance if unknown prices remain.

---

## Validation Status

Include:

```text
validation passed/failed
main deck count
commander slots
total including commanders
remaining warnings if any
```

Do not write final success language if validation failed.

---

## Build Feedback

Include only if useful.

Good feedback:

```text
search friction
seed/tag gaps
category-count mismatch
validation issue
unknown prices
missing CLI feature
deck-check limitation
```

Do not invent feedback if the build went smoothly.
