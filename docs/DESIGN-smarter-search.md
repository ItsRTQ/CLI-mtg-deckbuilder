# Design: Smarter search for the deckbuilding agent

Goal (from the user): the agent shouldn't copy how a human builds. A human can't know all 38k
cards or all interactions. The agent should use the tool to **prune to a functional shortlist and
reason over it**, discovering on-function cards and lines a normal player wouldn't see — always
inside the intent of the deck the user wants. This doc designs four additions toward that, ordered
by value/effort. All four build on existing pieces (no greenfield):

- `oracle_hooks.extract_hooks(text)` — already extracts named counters, token types, 9 trigger
  families, scaling, asymmetry, cost reduction from ANY card's text.
- `search_by_tags(..., rank=True)` — 97-tag functional vocabulary, OR-union, ranked by match count.
- `query_parser` — already has the `mv<=`/`mv>=` comparator pattern to copy.
- `commander_analyze` output — already the "plan" (oracle_hooks, wanted_card_patterns, role_pressures,
  archetype_fit, synergy_tags).
- `deck_check._get_category_phrases` — already maps a category → phrases via roles/tags.

Cross-cutting principles (the same ones that have guided this project):
- **One vocabulary.** Everything functional routes through `card_tags.json` + `oracle_hooks`; no new
  parallel dictionaries.
- **Tool proposes, agent judges.** Every feature returns a *ranked shortlist of candidates*, never a
  verdict. Substring/heuristic matching is imperfect by design.
- **Respect intent.** Every search composes with `--colors`, `--type`, price, and the commander's plan.
- **No scripts.** Each capability is a CLI verb/flag so the agent never shells out.

---

## #3 — Numeric / stat queries (lowest effort, pure SQL on existing columns)

### Problem (as the agent)
I reason about creature quality in numbers — "efficient beaters" (high power for low mv), "evasive
attackers" (power > toughness), "X/1 fragile dorks to avoid as blockers", "fits under a Stax mana
cap". The DB already has `power`, `toughness`, `mana_value` as columns, but I can only filter `mv`.
So I guess, or pull a tag list and eyeball stats.

### Design
Extend the query parser + `search` with numeric comparators on `power` and `toughness`, mirroring the
existing `mv<=`/`mv>=` plumbing exactly:
- Query tokens: `pow>=4`, `pow<=2`, `tou>=5`, `pow=tou`, plus derived `pow>tou` (attacker) / `pow<tou`
  (defender).
- CLI flags: `--pow-gte/--pow-lte`, `--tou-gte/--tou-lte`, and a convenience `--beater` (pow≥4 & mv≤4)
  and `--evasive-body` style presets later.
- Gotcha: `power`/`toughness` are stored as text and can be `*`, `1+*`, null (non-creatures). Coerce
  with a safe `CAST(... AS REAL)` guarded by a regex/`GLOB '[0-9]*'` so `*`/null rows don't crash or
  match. This is the one real implementation risk; everything else is column comparisons.

### Reuses / new
Reuses the parser's comparator pattern and `build_search_conditions`. New: power/toughness fields in
`empty_parsed`, parse rules, SQL clauses, CLI flags. ~Small.

### Why it makes the agent smarter
Turns "card quality" from eyeballing into a filter: "give me green creatures with power ≥ 5 at mv ≤ 4"
is a one-shot query. Directly serves aggro/stompy/Voltron evaluation.

---

## #1 — `similar` / `complements` (highest value; reuses oracle_hooks + tags)

### Problem (as the agent)
I find one good card (Whip Silk) and think "what else does this, and what wants to be next to it?"
Today I can't ask the tool that — I re-derive search terms by hand.

### Design
Two verbs, both built on `extract_hooks(card.oracle_text)` + `search_by_tags(rank=True)`:

`mtg similar "<Card>"` — cards that do the *same kind of thing*:
1. Extract the source card's hooks (trigger families, named counters, token types, tags it matches).
2. Map those to tags (reuse the tag phrases; a card "matches" a tag if its text hits the phrases).
3. `search_by_tags(those_tags, colors=<source identity or --colors>, rank=True)`, excluding the
   source. Rank = shared-facet count (already what `tag_match_count` does).

`mtg complements "<Card>"` — cards that *synergize* (the other half of the interaction). This needs a
small **complement map**: function → the function that pays it off / enables it. Examples:
- `sacrifice_outlet` ↔ `death_trigger`, `recursion`, `token_maker`
- `+1/+1 counter` placer ↔ `proliferate`, `counter_payoff`
- `self_mill` ↔ `reanimation`, `graveyard_recursion`
- `etb_value` ↔ `blink`, `flicker`
- `attacks_trigger` ↔ `evasion`, `extra_combat`, `go_wide_payoff`
The map is curated (a dozen+ pairs), lives next to `card_tags.json`, and is the only new data. Then
`complements X` = detect X's functions → look up their complements → `search_by_tags(rank=True)`.

### Reuses / new
Reuses extract_hooks, the tag vocabulary, ranked tag search. New: a card→tags reverse matcher
(detect which tags a given card satisfies) and the curated complement map. ~Medium.

### Why it makes the agent smarter
This is the "see a hammer, find what else hammers / what the hammer needs" tool. It turns a single
known-good card into a ranked shortlist of similar and synergistic cards — discovery, not recall.

---

## #2 — Search by trigger family (new query axis; reuses the 9 families)

### Problem (as the agent)
I reason in *events*: "I need payoffs for when a creature attacks", "for when I cast a noncreature
spell", "for when I gain life". `search-tags` matches phrases; it doesn't let me ask by the
structural event the way `oracle_hooks` already classifies it for commanders.

### Design
`oracle_hooks` already has `_TRIGGER_FAMILIES` (targeted_by_spell, permanent_dies, permanent_enters,
you_cast_spell, attacks_or_combat, sacrifice, draw_or_discard, life_change, recurring_tick). Promote
that to a searchable axis:
- `mtg search --trigger attacks_or_combat --colors R` → cards whose oracle, run through
  `extract_trigger_events`, contains that family.
- Implementation: this is a post-filter, not pure SQL (classification needs the function), so do a
  broad SQL prefilter on trigger words ("whenever", "when", "at the beginning") then run
  `extract_trigger_events` per row and keep matches. Bounded and fast enough; cache later if needed.
- Could also expose `--trigger-list`.

### Reuses / new
Reuses `_TRIGGER_FAMILIES` and `extract_trigger_events` verbatim. New: the SQL prefilter + per-row
classify + a CLI flag. ~Small-medium. Note: precision depends on the classifier (already imperfect,
e.g. the GF-1 punisher nuance) — same tool-proposes/agent-judges caveat.

### Why it makes the agent smarter
Adds an orthogonal search axis (by event), complementing tags (by function) and stats (#3). "All
attack-triggers in my colors" becomes one query instead of guessing phrasings.

---

## #5 — Deck gap analysis vs the commander's plan (most "intelligent"-feeling)

### Problem (as the agent)
I analyze the commander, build a list, validate it — but nothing tells me where the deck is *thin
against its own plan*: "commander damage deck with 0 protection", "8 sac enablers but 1 payoff",
"custom-counter commander with no proliferate". I close the loop only by eyeballing.

### Design
`mtg deck-gaps --deck <file> --commander <name> [--analysis ...]`:
1. Load the commander's plan: `oracle_hooks.build_signals` + `wanted_card_patterns` + `role_pressures`
   + `category-counts` recommended ranges (all already produced).
2. Tag the actual deck: for each card, detect which tags/functions it satisfies (the same card→tags
   matcher #1 needs — shared dependency).
3. Compare have-vs-want per function/category: report `under` (need ≥ range floor, have < it),
   `over`, and `missing plan signals` (e.g. commander wants proliferate, deck has 0).
4. Output a ranked TODO: "add ~3 attacker-protection (have 1, want 4); add proliferate (have 0)",
   each with a ready `search-tags` command to fill it.

### Reuses / new
Reuses commander_analyze output, category-counts ranges, deck_check category phrases, and the card→tags
matcher from #1. New: the have-vs-want diff + actionable output. ~Medium. **Depends on #1's
card→tags matcher**, so #1 should come first (or that matcher is built as a shared helper used by both).

### Why it makes the agent smarter
Closes the analyze → build → **audit** loop. It's the feature that most makes the agent look like it
*understands* the deck, because it catches its own blind spots and tells the user (and itself) exactly
what to search for next — which feeds right back into #1/#2/#3.

---

## Shared dependency & suggested order

A **card → functions matcher** ("which tags/trigger-families/hooks does THIS card satisfy?") is needed
by #1, #2, and #5. Build it once as a shared helper (`card_function_profile(card) -> {tags, triggers,
counters, ...}`) reusing `extract_hooks` + the tag phrases. Then:

1. **#3 numeric queries** — independent, smallest, immediate win. Good warm-up.
2. **Shared `card_function_profile` helper** — the keystone the rest reuse.
3. **#1 similar/complements** — first payoff of the keystone; highest standalone value.
4. **#2 trigger-family search** — small add once the helper exists.
5. **#5 deck-gaps** — capstone; ties analysis, the helper, and search together into the audit loop.

Risks to keep honest: text→function extraction is imperfect (substring + heuristic); `power`/`toughness`
text coercion needs guarding; trigger classification inherits the analyzer's edge cases. Every output
stays a ranked candidate list for the agent to judge, never an automated include.
