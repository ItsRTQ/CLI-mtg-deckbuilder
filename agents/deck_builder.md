# Deck Builder

Purpose: build the deck using CLI data, user preferences, category-count guidance, commander analysis, and card ranking.

Do not invent cards. Do not create helper scripts.

---

## Build Sequence

1. Read `BUILDER.md`.
2. Ask the BUILDER §5 core questions and WAIT for the user's answers — MANDATORY,
   unconditional (never "if needed"/"if in doubt": plausible defaults are not answers).
   Skip only the individual questions the user already answered in their request. One of
   them is the **target RANK** (the "norte" — power band 1–7; store `--set-config
   rank_target=<1-7|n/a>`): a GUIDE for how hard to aim, that NEVER overrides the budget.
3. Run `commander-analyze`.
4. Detect archetype, detail, constraints, and build mode.
5. Run `category-counts` with commander analysis.
6. Optionally research combos/synergies on the web yourself (BUILDER §12) — verify every card against the DB, record adoptions with `mtg note`.
7. Search/suggest candidates by role and package. **If a budget is set, draft TO it
   (target 85–100% utilization): allocate package budgets while drafting and take the
   strongest card each slot's share affords — never self-impose per-card caps far below
   what the budget allows (BUILDER.md §11). Derive `--max-price` for key-slot
   shortlists from the budget (~15–20% of it), not from habit.** Price visibility at
   pick time (full build #3 lesson): search-family results print each card's price;
   for hand-picked staples run `mtg prices-batch --name "A" --name "B"` (known-price
   total included) BEFORE adding them — NEVER sum a draft on memory prices (measured
   off by 5x). At high brackets `--max-rank <N>` surfaces format staples — popularity
   is CONSIDER-ONLY, never an include-verdict. When the budget gets tight (over, or
   a wanted upgrade doesn't fit), check WHERE the money sits with `deck-view`'s
   **cost by type** before cutting: money concentrated in a low-impact bucket
   (classic: expensive lands) can be reallocated to a better card — but ALWAYS ask
   the user first per BUILDER §11 "Budget Reallocation" (exact cuts, exact upgrade,
   both prices, consistency trade-off). Never reallocate silently — the user may
   value the mana base or see something you didn't. OWNED cards (user-bulk
   collection) cost the budget $0 — `budget`/preflight exclude them automatically
   with a visible line; prefer an owned staple over buying a weaker substitute
   (BUILDER §11 "Owned cards").
8. Rank candidates.
9. **Draft THROUGH the tool, package by package** (`mtg deck-add --cards "A;B;..."
   --purpose <role>` — the package IS the role): validates at entry (exists / color
   identity / singleton / size), and prints the batch price + RUNNING TOTAL with
   budget % — watch it land in the 85–100% window as you draft. First call MUST carry
   `--set-config budget=... budget_mode=... bracket=...` (the contract lives IN the
   deck — deck-add refuses to create it without budget + bracket, which only the
   user's step-2 answers can provide) and `--deck-note` (theme/gameplan). Basics:
   `--cards "12 Mountain"`.
   The old decklist.txt + `deck-write --structured` path still works but loses
   entry-time validation, running budget, and purposes.
10. WHILE drafting: `mtg note --type combo` the moment you SEE a combo, and
    `mtg note --type decision` for REJECTED candidates (that evaluation is what the
    Budget Upgrade Review re-pays when it isn't recorded).
11. One annotation pass at the END of the draft: `deck-annotate --auto` (census
    seeds ~85%), `--cards/--purpose-add/--note` for what only judgment sees
    (commander-granted synergy, wincons), `--sync-notes` (combos → deck).
    Inspect with `deck-view` (`--by-purpose`, `--card "Name"`).
12. Fill basics with `deck-fill-lands`.
13. Validate; run `deck-power` (consistency tier; bracket verdict if the config
    targets one — must be COMPLIANT before finalizing) AND `deck-rank` (POWER/speed
    rank, 7 bands Scrap..Mythic). They are ORTHOGONAL — RANK = how fast/strong the
    deck is, TIER = how reliably it runs its plan; report BOTH. When reporting the
    rank, flag its blind spots (fast_mana is a name-list — a new fast-mana card or
    commander-granted acceleration reads as invisible fuel; land-ramp is excluded by
    design; consider-only, calibrated:false). See BUILDER §16.
14. Fix errors.
15. Run deck-check and budget checks.
16. If under budget threshold (<~60% utilization), run Budget Upgrade Review: show under-budget upgrades and optional over-budget high-impact options, then ask the user what to apply (see BUILDER.md Section 11). The review is the FAILSAFE — if step 7 drafted to budget, it should rarely trigger.
16b. If a `rank_target` was set and the deck lands BELOW it, run the **Rank Upgrade Review**
    (BUILDER §16): `mtg deck-rank --target-band <N> --with-candidate "A;B"` computes each
    upgrade's EXACT expected rank increase; present them like the Budget Review (price + rank/tier
    delta + under/over budget) and let the user decide. The budget ALWAYS wins — never overspend
    to chase a band.
17. Apply selected upgrades, then re-run validate, deck-check, and budget-check.
18. Write `output/deck_explanation.md` — it MUST open with the at-a-glance header
    table `| Deck commander | TIER | RANK | Bracket | Total cost |` (values from
    deck-power / deck-rank / budget; see agents/deck_explainer.md). Write card names as
    PLAIN TEXT — never wrap them in Markdown links or file paths (no
    `[Card](file://…/deck.json)`); the explanation must stay clean and readable.
19. Final-build only after the Budget Upgrade Review decision is resolved and validation
    passes. `final-build` NAMES the folder itself as `<Commander>-<TIER>-<RANK>-<COST>` —
    don't hand-name it. A missing score is OMITTED (never `na`): TIER needs an annotated deck
    (purposes + combos), so annotate BEFORE final-build if you want it in the name; RANK/cost
    are always present. See BUILDER §14.

---

## Core Commands

Commander analysis:

```bash
mtg commander-analyze --commander "<commander>" --output output/commander_analysis.json --json-output
```

Category planning:

```bash
mtg category-counts \
  --commander "<commander>" \
  --archetype "<archetype>" \
  --power-level <number> \
  --philosophy "<philosophy>" \
  --analysis output/commander_analysis.json \
  --json-output
```

Write structured deck:

```bash
mtg deck-write \
  --input output/decklist.txt \
  --output output/deck.json \
  --commander "<commander>" \
  --structured \
  --force
```

Fill lands:

```bash
mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --output output/deck.json --force
```

Validate:

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

Partner decks should include `--partner` on each relevant command.

---

## Commander and Main Deck

Do not put commander-zone cards in `main_deck`.

Use structured deck output:

```json
{
  "commander": "<Commander>",
  "main_deck": []
}
```

Partner:

```json
{
  "commanders": ["<Commander A>", "<Commander B>"],
  "main_deck": []
}
```

---

## Package Planning

Use category-counts for ranges, not hard locks. Its targets are experience-grounded
GUIDANCE (hand-tuned baselines, not corpus-calibrated) — YOU are the final arbiter; if the
commander's plan or the user's answers say otherwise, follow judgment and say why. For **cEDH /
high-power combo** it's the wrong primary lens (a casual slot-template planner) — lean on
`deck-power` / `deck-rank` / `deck-gaps` + combo/tutor/fast-mana density, and use category-counts
only as a light interaction/wincon sanity check (BUILDER §10).

Prioritize:

```text
commander engine
required roles
user preferences
category-count recommended_range
validation legality
budget/salt/power limits
```

If compressed targets look misleading, use `recommended_range`, `need_score`, and deckbuilding judgment.

Build the commander engine straight from the analysis: turn each `wanted_card_patterns` entry
(and `analyzer.tags` / `engine_profile.primary_pattern`) into `suggest`/`search-tags` queries.
This is how niche hooks get covered — e.g. a `targeted_spell_payoff` commander wants cheap
self-targeting spells and buyback auras (Whip Silk) that generic archetype filling never finds.

---

## Search and Suggest

New search axes (v0.8.0) — use them before falling back to raw --oracle text matching:

```bash
mtg search --trigger <family>          # cards by trigger family (attacks, dies, enters, ...)
mtg search --pow-gte 4 --tou-lte 2     # numeric power/toughness filters
mtg search-tags <tag...>               # ranked by tag_match_count (multi-tag = strongest first)
mtg similar "<card>"                   # cards performing the SAME function (find replacements)
mtg complements "<card>"               # cards that SYNERGIZE (the other half of the interaction)
```

Before finalizing, audit the draft against the commander's plan:

```bash
mtg deck-gaps --deck output/deck.json --commander "<name>" --archetype <arch>
```

It reports thin categories with ready fill-commands, and a **Commander plan check**: for each
high/very_high analyzer band it counts the deck cards serving that plan AND LISTS THEM
(`analyzer_support[].cards` and `plan_gaps[].cards` in JSON; human output prints a
"counted: ..." line). A plan gap means the deck ignores its commander's detected plan —
fix it or consciously justify it before finalizing, using the counted list to decide with
data instead of guessing which cards were seen. Treat all output as candidates to judge,
not automatic includes.

Use role suggestions:

```bash
mtg suggest --commander "<commander>" --role ramp --json-output
mtg suggest --commander "<commander>" --role engine --synergy --analysis output/commander_analysis.json --json-output
mtg suggest --commander "<commander>" --role card_draw --type creature --json-output
```

Use search for precise effects:

```bash
mtg search --oracle "can't be blocked" --oracle target --oracle creature --json-output
mtg search --oracle "draw a card" --type creature --json-output
mtg search "type:vampire" --type creature --json-output
```

Rules:

```text
Never use --role synergy.
--synergy modifies a real role. Its matching is enriched with the analyzer's high-band plan
phrases (one vocabulary with deck-gaps), so results carry richer matched_tags.
--type narrows the card type and never bypasses role matching.
Repeated --oracle / --name / --card-type filters are AND filters.
```

---

## Decklist Writing

Write `output/decklist.txt` as a simple list of main-deck cards.

Avoid including the commander in the main deck list when using structured output.

Verify the list before writing — `cards-batch` accepts the `.txt` directly and flags any
`"found": false` name (typo or nonexistent card) cheaply, before the deck-write/fill/validate cycle:

```bash
mtg cards-batch output/decklist.txt --json-output
```

Then run `deck-write --structured`.

Do not create Python scripts to generate JSON.

---

## Lands

Build the nonland shell first. Then use `deck-fill-lands`.

Normal decks:

```text
99 main deck cards after fill
```

Partner decks:

```text
98 main deck cards after fill
```

Landfall/landsmatter usually targets 38–42 lands. Do not hard-lock exact 40 unless user asked.

---

## Combo & Synergy Research

The former `explore` / `combos` fetch commands were removed (v0.8.0). If the build
needs outside combo/synergy ideas, research the web yourself (BUILDER §12): verify
every candidate against the DB (`mtg card` / `cards-batch --verify`), record adopted
combos with `mtg note --type combo` and rejections with `--type decision`.

Do not include full combos unless user preference, power level, and salt policy allow them.

---

## Final Build

Only after validation passes:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "<commander>" \
  --theme "<theme>" \
  --bracket T3 \
  --explanation output/deck_explanation.md
```
