# User Feedback Agent

Purpose: collect only preferences that materially change deckbuilding.

Use multiple choice. Always include `Agent choice`. Do not ask open-ended questions unless required.

**MANDATORY: ask the 4 core questions and WAIT for the answers before building** — every
build, unconditionally. This never depends on the agent "having doubts": an agent with
plausible defaults has no doubts, and its defaults are not answers. If the user already
answered something in their request, do not ask it again — the remaining core questions
still get asked. Enforcement: `deck-add`'s first call refuses to create a deck without
the answered contract (budget + bracket via `--set-config`).

---

## Core Question 1: Bracket

```text
What official Commander Bracket should the deck target?

a) Bracket 1-2 — casual/precon table: no Game Changers, no MLD, no 2-card combos
b) Bracket 3 — upgraded: up to 3 Game Changers, no MLD, no cheap 2-card combos
c) Bracket 4-5 — optimized/cEDH: no restrictions
d) n/a — I don't care about brackets; just build it well
e) Agent choice
```

Default: n/a (brackets are a social contract, not a requirement — many users don't
play them; the option exists for the tables that do).

Wire the answer to the tooling:
- a/b/c → run `mtg deck-power --bracket <N>` before finalizing; the compliance
  verdict (deterministic: GC count, MLD, extra turns, 2-card combos) must be
  COMPLIANT for the target. Combos policy follows the bracket (1-2: none;
  3: no cheap 2-card infinites).
- n/a → skip the compliance verdict entirely; still show `deck-power`'s TIER
  (consider-only) in the build summary.

Internal power mapping for slot planning (category-counts `--power-level`):

```text
Bracket 1-2 -> power 4-5      Bracket 3 -> power 6-7
Bracket 4-5 -> power 8-10     n/a       -> agent judgment from the other answers
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

Wire the answer to the tooling: (a) → use `--max-rank` on shortlists to surface format
staples (popularity is CONSIDER-ONLY, never an include-verdict); (c) → skip `--max-rank`
and expect `deck-check`'s staple_density to read low — that is the requested outcome,
not a problem to fix.

### Card preferences

```text
Do you have card preferences?

a) I have must-include cards
b) I have cards to avoid
c) No specific cards
d) Agent choice
```

If user chooses must-include or avoid, ask for card names.

### Owned cards (user-bulk)

```text
Do you already own cards you'd want this deck to use?

a) Yes — I'll list them now (they'll be recorded with `mtg bulk-add`)
b) Yes — my user-bulk collection is already up to date
c) No / buy everything
d) Agent choice
```

Owned cards are excluded from the budget bill (BUILDER §11 "Owned cards"). Ask this
once in Detailed Build mode or whenever the user mentions owning cards; on (a),
record the names via `mtg bulk-add --cards "..."` before budgeting.

---

## During-Build Questions

Detailed build mode may ask during the build when a decision materially changes the deck.

Valid reasons:

```text
commander supports multiple strong archetypes
category-counts conflicts with user preference
budget is close to overage
budget reallocation across type buckets (see below)
combo/stax/tutor policy is unclear
land/ramp count needs a style decision
synergy search confidence is weak
theme strictness affects major card choices
```

### Budget reallocation question (cost-by-type lens, BUILDER §11)

When `deck-view`'s cost by type shows money concentrated in a low-impact bucket
(classic: expensive lands) while a better card was passed on for price, ALWAYS ask —
never reallocate silently. The user owns this trade: they may value the mana base,
already own those cards, or see something the agent didn't (this is what makes the
build personal). The proposal must name exact cuts, the exact upgrade, both prices,
the freed amount, and the consistency trade-off:

```text
Cost by type shows $31 on lands. Swapping <Land A, Land B, Land C> for basics
frees ~$18, enough for <Upgrade X> ($15). Trade-off: slightly less consistent
mana (2-color deck — low risk).

a) Keep the mana base as is — find the money elsewhere (or skip the upgrade)
b) Swap the listed lands for basics and apply the upgrade
c) Partial — swap only the lands I name, then re-check
d) Agent choice
```

Do not ask just to delay building.

## Toolbox Commanders (multi-mode)

When the commander analysis shows `Toolbox / Goodstuff` in `analyzer.archetype_support` (4+
activated abilities — a menu of modes like Kenrith or Cromat), the user's answers are what
resolve the menu: map their requested direction to the mode that serves it, and present that
choice back ("you asked for aggro, so I'm leaning the {R} haste/trample mode"). If the default
build questions didn't disambiguate which mode to lean, ask ONE targeted follow-up before
drafting — do not pick a mode silently.
