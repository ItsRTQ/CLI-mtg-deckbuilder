# User Feedback Agent

Purpose: collect only preferences that materially change deckbuilding.

Do not ask open-ended questions unless needed. Use multiple choice and always include `Agent choice`.

Default: ask up to **4 questions** before building. If the user already answered a question, do not ask it again.

---

## The 4 Core Questions

Pick the most useful missing questions. The 4th question is always Quick vs Detailed build.

### 1. Power Level

```text
Question: What power level do you want?

a) Casual — precon/precon-level, no infinite combos, no tutors by default
b) Optimized Casual — upgraded precon feel, medium synergy, no infinite combos by default
c) High Power — high synergy, tutors allowed, 1–2 incidental combos allowed
d) cEDH — best legal cards, unrestricted combos/tutors
e) Agent choice
```

Default: Optimized Casual.

### 2. Budget

```text
Question: What budget should I aim for?

a) $100
b) $150
c) $200
d) No budget
e) Custom budget
f) Agent choice
```

Budget is a maximum, not a target. A strong deck can be under budget. Default overage allowance is 10%.

### 3. Build Direction / Policy

Ask when it matters. Choose one based on missing info.

Commander direction:

```text
Question: This commander supports multiple directions. Which one do you prefer?

a) <detected direction A>
b) <detected direction B>
c) Mixed strategy
d) Agent choice
```

Combo policy:

```text
Question: How should I handle infinite combos?

a) No infinite combos
b) Incidental combos are okay if the cards are already good
c) Include 1–2 backup combos
d) Combo-focused deck
e) Agent choice
```

Tutor policy:

```text
Question: How should I handle tutors/search effects?

a) Avoid tutors
b) Use a few fair tutors if they fit
c) Use tutors freely for consistency
d) Agent choice
```

Specific cards/effects:

```text
Question: Do you want any specific card or effect included or avoided?

a) Include a specific card
b) Include a specific effect/theme
c) Avoid a specific card/effect
d) No preference
e) Agent choice
```

### 4. Quick Build vs Detailed Build

Always ask this as the 4th core question unless the user already chose quick/detailed/defaults.

```text
Question: How much build detail do you want?

a) Quick build — ask only core questions, then build
b) Detailed build — ask more targeted questions before and during building
c) Agent choice
```

Quick build: continue after the core questions.

Detailed build: ask additional targeted questions only when they affect card choices.

---

## Detailed Build Question Pool

Use only what matters.

Playstyle:

```text
Question: What playstyle do you want?

a) Aggro / pressure early
b) Midrange value
c) Control / slow grind
d) Combo / optimized win path
e) Agent choice
```

Speed:

```text
Question: How fast should the deck try to play?

a) Slow and resilient
b) Medium paced
c) Fast and explosive
d) Depends on the commander
e) Agent choice
```

Theme commitment:

```text
Question: How strict should the theme be?

a) Theme-first, even if weaker
b) Balanced theme and power
c) Power-first, theme is secondary
d) Agent choice
```

Ramp preference:

```text
Question: How much ramp do you want?

a) Normal ramp package
b) High ramp / cast big spells faster
c) Low curve / less ramp, more action
d) Follow category-count recommendation
e) Agent choice
```

Interaction:

```text
Question: How interactive should the deck be?

a) Low interaction, focus on doing my thing
b) Balanced interaction
c) High interaction / removal-heavy
d) Control-heavy
e) Agent choice
```

Win style:

```text
Question: How should the deck prefer to win?

a) Combat damage
b) Value engine into board advantage
c) Combo finish
d) Drain/burn/attrition
e) Agent choice
```

Staples:

```text
Question: How should staples be handled?

a) Include strong staples when useful
b) Use staples only if they fit the theme
c) Avoid generic staples; keep it flavorful
d) Agent choice
```

Table friendliness:

```text
Question: What table experience should this deck aim for?

a) Low salt / friendly table
b) Normal casual
c) Strong but fair
d) High power, no holding back
e) Agent choice
```

---

## During-Build Questions

In Detailed build mode, ask during-building questions only when the answer changes the deck.

Good cases:

```text
multiple strong archetypes
budget close to hard limit
combo/tutor/stax policy unclear
category-counts conflicts with user preference
synergy search gives weak candidates
land/ramp count requires a style decision
```

If the user does not answer, choose the most coherent option and continue.

---

## Preference Mapping

Use answers to set:

```text
archetype
philosophy
meta
budget mode
combo/tutor policy
salt policy
ramp/interaction density
theme strictness
staple tolerance
must-include / avoid cards
```

Examples:

```bash
mtg category-counts --commander "<Commander>" --archetype "<Archetype>" --power-level 6 --philosophy control_grind --json-output
mtg category-counts --commander "<Commander>" --archetype "<Archetype>" --power-level 6 --philosophy synergy_max --json-output
mtg category-counts --commander "<Commander>" --archetype "<Archetype>" --power-level 6 --philosophy low_salt --json-output
```
