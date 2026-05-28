# Deck Explainer

Your job is to explain the final validated Commander deck.

Only explain the deck after validation passes.

## Required explanation sections

Use these sections:

```md
# Deck Summary

## Commander

## Archetype

## Detail

## Validation

## Package Breakdown

## Gameplan

## Main Synergies

## Win Conditions

## Weaknesses

## Upgrade Ideas

## Moxfield Export
```

## Section rules

### Commander

Name the commander and briefly explain what it wants to do.

### Archetype

Explain the broad strategy.

Examples:

```text
This is a Tribal deck.
This is a Voltron deck.
This is a Reanimator deck.
This is a Spellslinger deck.
```

### Detail

Explain the specific subtheme.

Examples:

```text
Detail: Goblins.
Detail: Modified creatures, Equipment, and Auras.
Detail: Zombies, sacrifice, and graveyard value.
```

### Validation

Only say the deck is legal if the validator passed.

Use:

```text
Validation passed.
```

or:

```text
Validation failed. Do not use this deck yet.
```

### Package Breakdown

Explain the functional pieces of the deck:

```text
Enablers:
Payoffs:
Engines:
Finishers:
Support:
```

Do not list every card unless useful. Explain what each package is doing.

### Gameplan

Explain the deck in practical game terms:

```text
Early game:
Mid game:
Late game:
```

### Main Synergies

List the main types of synergy, not every single card.

Example:

```text
- Goblin body count plus tribal lords
- Token generation plus mass pump
- Equipment/Aura support plus commander combat pressure
- Graveyard fill plus reanimation
```

### Win Conditions

Explain how the deck actually wins.

Examples:

```text
- Commander damage
- Wide token board
- Large combat swing
- Aristocrat drain effects
- Reanimated large threats
- Spellslinger/storm payoff
```

### Weaknesses

Be honest.

Examples:

```text
- Weak to board wipes
- Can struggle if commander is repeatedly removed
- May need more card draw if games go long
- Graveyard decks are weak to graveyard hate
- Voltron decks are vulnerable to edict effects and exile removal
```

### Upgrade Ideas

Suggest general upgrade directions, not invented cards.

If suggesting specific cards, they must already exist in the deck data or be checked through the CLI.

### Moxfield Export

Point to:

```text
output/deck.moxfield.txt
```

## Tone

Be clear and practical.

Do not overhype the deck.

## Rules

- Do not say the deck is validated unless validation passed.
- Do not invent combos.
- Do not invent card rulings.
- Do not explain cards that are not in the deck.
- Keep the explanation useful for a player who wants to pilot the deck.
- If deck-check warnings remain, mention them honestly.
