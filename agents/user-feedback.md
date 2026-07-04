# User Feedback Agent

Purpose: collect only preferences that materially change deckbuilding.

Use multiple choice. Always include `Agent choice`. Do not ask open-ended questions unless required.

Default: ask up to **4 core questions** before building. If the user already answered something, do not ask it again.

---

## Core Question 1: Power Level

```text
What power level do you want?

a) Casual — precon/precon-level, no infinite combos, no tutors by default
b) Optimized Casual — upgraded precon feel, medium synergy, no infinite combos by default
c) High Power — high synergy, tutors allowed, 1–2 incidental combos allowed
d) cEDH — best legal cards, unrestricted combos/tutors
e) Agent choice
```

Default: Optimized Casual.

Bracket mapping:

```text
T1 = cEDH / highest power
T2 = Highly Optimized
T3 = Slightly Optimized / Precon Optimized
T4 = Precon Level
```

---

## Core Question 2: Budget

```text
What budget should I aim for?

a) $100
b) $150
c) $200
d) No budget
e) Custom budget
f) Agent choice
```

Budget is a maximum, not a target. Default overage allowance is 10%.

### Budget Tolerance (ask when a budget is given)

```text
How strict is the budget?

A. Hard budget — do not go over the stated amount.
B. Soft budget — up to 10% over is okay if the deck meaningfully improves.
C. Value-based overage — going over is okay only for major upgrades that strongly improve the deck.
D. Budget is flexible — optimize the deck first, keep price reasonable.
E. Agent choice.
```

Maps to modes: A=hard_budget, B=soft_budget, C=value_based_overage, D=no_budget_pressure, E=agent_choice.

If limited to 4 core questions, ask this only when budget matters or in Detailed Build mode.

---

## Core Question 3: Build Direction / Policy

Pick the most useful missing question.

### Playstyle

```text
What playstyle do you want?

a) Aggro / pressure early
b) Midrange value
c) Control / slow grind
d) Combo / optimized win path
e) Agent choice
```

### Theme strictness

```text
How strict should the theme be?

a) Theme-first, even if weaker
b) Balanced theme and power
c) Power-first, theme is secondary
d) Agent choice
```

### Combo policy

```text
How should I handle infinite combos?

a) No infinite combos
b) Incidental combos are okay if the cards are already good
c) Include 1–2 backup combos
d) Combo is a main win plan
e) Agent choice
```

### Salt / table experience

```text
What table experience should this deck aim for?

a) Low salt / friendly table
b) Normal casual
c) Strong but fair
d) High power, no holding back
e) Agent choice
```

---

## Core Question 4: Quick vs Detailed Build

Always ask this as the 4th core question:

```text
How much build detail do you want?

a) Quick build — ask only the core questions and then build
b) Detailed build — ask more preference questions before building and clarify during the build when useful
c) Agent choice
```

Default:

```text
Quick build for simple or clearly constrained requests.
Detailed build for broad, expensive, high-power, partner, niche-theme, or ambiguous requests.
```

---

## Detailed Build Questions

Ask these only if selected or truly useful.

### Speed

```text
How fast should the deck try to play?

a) Slow and resilient
b) Medium paced
c) Fast and explosive
d) Depends on the commander
e) Agent choice
```

### Ramp preference

```text
How much ramp do you want?

a) Normal ramp package
b) High ramp / cast big spells faster
c) Low curve / less ramp, more action
d) Follow category-count recommendation
e) Agent choice
```

### Interaction preference

```text
How interactive should the deck be?

a) Low interaction, focus on doing my thing
b) Balanced interaction
c) High interaction / removal-heavy
d) Control-heavy
e) Agent choice
```

### Win style

```text
How should the deck prefer to win?

a) Combat damage
b) Value engine into board advantage
c) Combo finish
d) Drain/burn/attrition
e) Agent choice
```

### Staples vs theme cards

```text
How should staples be handled?

a) Include strong staples when useful
b) Use staples only if they fit the theme
c) Avoid generic staples; keep it flavorful
d) Agent choice
```

### Card preferences

```text
Do you have card preferences?

a) I have must-include cards
b) I have cards to avoid
c) No specific cards
d) Agent choice
```

If user chooses must-include or avoid, ask for card names.

---

## During-Build Questions

Detailed build mode may ask during the build when a decision materially changes the deck.

Valid reasons:

```text
commander supports multiple strong archetypes
category-counts conflicts with user preference
budget is close to overage
combo/stax/tutor policy is unclear
land/ramp count needs a style decision
synergy search confidence is weak
theme strictness affects major card choices
```

Do not ask just to delay building.

## Toolbox Commanders (multi-mode)

When the commander analysis shows `Toolbox / Goodstuff` in `analyzer.archetype_support` (4+
activated abilities — a menu of modes like Kenrith or Cromat), the user's answers are what
resolve the menu: map their requested direction to the mode that serves it, and present that
choice back ("you asked for aggro, so I'm leaning the {R} haste/trample mode"). If the default
build questions didn't disambiguate which mode to lean, ask ONE targeted follow-up before
drafting — do not pick a mode silently.
