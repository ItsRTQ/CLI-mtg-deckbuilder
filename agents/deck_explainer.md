# Deck Explainer

Purpose: explain the finalized deck clearly after validation passes.

Write the explanation to:

```text
output/deck_explanation.md
```

Do not claim the deck is complete unless validation passed.

## Formatting rule — plain card names, NO links (mandatory)

Write every card name as **plain text** (bold is fine for emphasis). **NEVER** wrap a card
name in a Markdown link, and NEVER attach a file path or URL to it. Do not do this:

```text
[Phyrexian Altar](file:///…/output/deck.json)      ← WRONG: path is noise, unreadable
```

Do this:

```text
Phyrexian Altar          or          **Phyrexian Altar**
```

The explanation is a clean human-readable document — no `file://` paths, no `output/deck.json`
links, no clickable card names anywhere in it (headings, tables, prose, or lists).

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

<AT-A-GLANCE HEADER TABLE — always first, see below>

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

## At-a-glance header table (ALWAYS first, right under the title)

Before any prose, emit a one-row Markdown table so the deck's key numbers are visible
instantly:

```text
| Deck commander | TIER | RANK | Bracket | Total cost |
|---|---|---|---|---|
| <Commander[/ Partner]> | <+S (9.78)> | <Mythic 7 (9.55)> | <3 · COMPLIANT> | <$146.63> |
```

Where each value comes from (run the tools; never fill from memory):
- **Deck commander** — the commander name (both, if partner/background).
- **TIER** — the consistency tier from `mtg deck-power` (letter + score, e.g. `+S (9.78)`).
  Needs the annotated deck; if the deck isn't annotated, write `n/a`.
- **RANK** — the power band from `mtg deck-rank` (band name + number + score, e.g.
  `Mythic 7 (9.55)`). Needs no annotation.
- **Bracket** — the bracket from `deck-power`: the target from the deck config plus the
  compliance verdict if one was targeted (`3 · COMPLIANT`); `n/a` if the user chose no bracket.
- **Total cost** — the known-price total from `mtg budget` / `deck-view` (e.g. `$146.63`;
  add ` (+unknowns)` if unpriced cards remain).

TIER and RANK are ORTHOGONAL (power vs reliability — see the section below); showing both in
the header is the point. Consider-only: never present either as a verdict.

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

### Budget Upgrade Review (include if it happened)

```text
## Budget Upgrade Review

Initial valid deck cost: ~$<x>
Budget: $<y>
Budget tolerance: <mode>
Budget utilization: <pct>%
Unused budget: ~$<z>

User decision:
- <what was applied>

Considered but not applied:
- <Card> would push the deck to ~$<total>, over budget by ~$<delta>.
  Reason: <value>, but user chose <mode>.

Final estimated cost: ~$<final>
```

If the user accepted an over-budget card, record the swap, new total, amount over
budget, and the reason accepted (major improvement to engine / win condition).

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

## Explaining the two scores (RANK vs TIER)

When you report `deck-rank` and `deck-power`, make the distinction explicit — they are
ORTHOGONAL and users conflate them:

- **RANK** (`deck-rank`, 7 bands 1 Scrap … 7 Mythic=cEDH): how **fast/strong** the deck is
  vs the metagame, from fast_mana + tutors + game changers + curve (draw excluded — grind,
  not speed). Reads DB facts; no annotation. Answers "is this cEDH-fast?"
- **TIER** (`deck-power`, +S … F): how **reliably it runs its own declared plan**
  (purposes + combos). Answers "does it do its thing well?"
- They diverge: a reliable budget combo can be **TIER +S but RANK band 2** (executes its plan
  impeccably, but no fast-mana hardware). A cEDH deck is high on both. Say which is which.
- Flag the rank's blind spots when relevant: fast_mana is a name-list (a new fast-mana card or
  commander-granted acceleration reads as invisible fuel); land-ramp is excluded by design;
  both scores are consider-only (rank is calibrated:false). BUILDER §16.


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
