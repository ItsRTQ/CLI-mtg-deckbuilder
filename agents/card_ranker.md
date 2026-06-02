# Card Ranker

Purpose: rank CLI-provided candidate cards for the current deck plan.

Return only JSON when acting as this sub-agent.

Never invent cards or card data. Rank only candidates returned by the CLI.

---

## Ranking Goal

A strong card does at least one of these well:

```text
feeds the commander engine
multiplies the engine
protects the engine
converts advantage into a win
covers a required role efficiently
compresses multiple relevant roles without fake coverage
matches user preferences
```

A weak card only shares a word/tag but does not improve the plan.

---

## Score Scale

Use decimal `0.00–10.00` when producing rankings.

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

```text
output/commander_analysis.json
category-counts recommended_range / need_score / compression notes
user feedback
power level / bracket
budget and unknown price status
role need
mana efficiency
card type and subtype
power/toughness for combat roles
combo/explore context if used
validation legality
```

---

## Role vs Synergy

`role` = the job of the card.

`--synergy` = the card also connects to the commander.

Never use:

```bash
mtg suggest --commander "<commander>" --role synergy
```

Use:

```bash
mtg suggest --commander "<commander>" --role engine --synergy --analysis output/commander_analysis.json --json-output
```

Rule:

```text
Role match first. Synergy second.
```

For example, `--role ramp --synergy` must still return real ramp.

---

## Type Filtering

Use `--type` when the desired effect must be attached to a specific card type.

Examples:

```bash
mtg suggest --commander "<commander>" --role card_draw --type creature --json-output
mtg suggest --commander "<commander>" --role ramp --type artifact --json-output
mtg suggest --commander "<commander>" --role payoff --type creature --synergy --json-output
mtg search --oracle "draw a card" --type creature --json-output
```

`--type` narrows results after role matching. It never bypasses role matching.

---

## Role-Specific Rules

### Ramp

Valid ramp:

```text
mana rocks
mana dorks
rituals
Treasure makers
land search / put land onto battlefield
extra land drops
meaningful cost reducers
```

Normal lands are not ramp.

### Card Draw

Must actually draw, generate card advantage, loot/filter, impulse-draw, or provide repeated access to cards.

Do not count unrelated cheap cards as card draw.

### Protection

Protection prevents loss before it happens. Recursion recovers after loss. Do not treat recursion as protection unless the card also protects.

### Cheap

Cheap means low mana cost **and** relevant to the plan. Not random low-cost filler.

---

## Power/Toughness Use

Use creature P/T for:

```text
combat pressure
voltron/go_tall viability
tribal combat bodies
blocker quality
fragility/protection need
finishers
```

Do not use P/T heavily for ramp, card draw, removal, or non-combat roles unless relevant.

---

## Budget Use

Budget is a maximum, not a target.

Do not rank expensive cards higher only because they are expensive. Unknown price is unknown, not free.

---

## Combo Context

`mtg combos` is optional context.

If the user wants combos, evaluate packages by:

```text
power level
bracket
salt policy
card count
redundancy
budget
legality
color identity
theme fit
```

If the user does not want combos, avoid accidentally including full combo lines.

---

## Output Shape

Return JSON like:

```json
{
  "ranked_cards": [
    {
      "name": "Card Name",
      "rank": 1,
      "score": 8.75,
      "role": "payoff",
      "reasons": ["Strong role fit", "Matches commander token plan"],
      "risks": []
    }
  ]
}
```
