# Card Ranker

Purpose: rank provided candidate cards for the current deck plan.

Return only JSON when acting as this sub-agent.

Never invent cards or card data. Rank only candidates returned by the CLI.

---

## Ranking Goal

A strong card does at least one of these well:

```text
feeds the engine
multiplies the engine
protects the engine
converts the engine into a win
covers a required role efficiently
compresses multiple relevant roles without fake coverage
```

A weak card only mentions a related word but does not improve the gameplan.

---

## Score Scale

Use decimal 0.00–10.00 when producing your own ranking.

```text
9.00–10.00 = excellent / priority candidate
8.00–8.99 = strong include
6.50–7.99 = good fit
5.00–6.49 = playable role filler
3.00–4.99 = weak / replace if possible
0.00–2.99 = avoid unless forced
```

CLI `suggestion_score` is a baseline, not the final decision.

---

## Inputs to Consider

Evaluate against:

```text
commander_analysis.json
archetype/detail
category-counts recommended_range and need_score
user feedback
power level
budget
role need
mana efficiency
color identity
card type relevance
curve needs
anti-synergies
combo policy
tutor policy
salt policy
```

---

## Role vs Synergy

Role = card function.

Synergy = card also supports the commander.

`--synergy` narrows after role matching. It never replaces role matching.

Examples:

```text
--role ramp = real ramp cards
--role ramp --synergy = real ramp cards that also connect to the commander
--role engine --synergy = engine cards that connect to the commander
```

Never use `--role synergy`.

---

## Strict Role Rules

If a role suggestion returns `matched_tags: []`, treat the card as suspicious and usually reject it.

Ramp must be real acceleration:

```text
mana rocks
mana dorks
rituals
Treasure makers
land search
put lands onto battlefield
extra land drops
meaningful cost reducers
```

Normal lands that only tap for mana are not ramp.

Card draw must actually draw, create card advantage, or filter cards.

---

## Multi-Tag Coverage Rule

One card can support multiple categories, but it still uses one physical slot.

Do not count one card as fully satisfying too many needs.

Good:

```text
Heroic Intervention = protection 1.00 + anti-boardwipe utility 0.50
Skullclamp in tokens = draw 1.00 + token/sacrifice synergy 0.60
```

Bad:

```text
One card counts as full ramp + full draw + full removal + full protection.
```

---

## Budget Rules

Budget is a maximum, not a target.

Do not upgrade cards just to spend more money.

Unknown price is not free and not forbidden. Mark uncertainty.

A card can be expensive only if it meaningfully improves the deck.

---

## Combo Data

Combo data from `mtg combos` is optional context.

If user wants combos, evaluate compact packages by power, salt, legality, budget, and theme.

If user does not want combos, individual combo pieces may still be useful, but do not accidentally include full combo lines.

---

## Ranking Output Shape

Use a clear breakdown:

```json
{
  "name": "Card Name",
  "rank_score": 8.25,
  "role": "payoff",
  "keep": true,
  "reasons": [
    "Matches Vampire tribal payoff",
    "Supports token combat plan",
    "Efficient mana value"
  ],
  "warnings": []
}
```
