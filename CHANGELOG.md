# Changelog

## 0.8.0

### Changed
- **README brought up to date with everything shipped since 2026-07-04, plus a
  Quick Start.** New "Quick Start — Install & Use" section at the top (fresh
  clone → venv → `pip install -e .` → `init-data` → the two ways to use it:
  agent-driven build with the annotated flow spelled out step by step, and
  manual one-liners). Command Reference 34 → **39 commands**: new "Annotated
  deck — drafting & scoring" group with full sections for `deck-add` (incl.
  the §5 contract gate), `deck-annotate`, `deck-view` (cost by type + the
  reallocation lens), `deck-power` (bracket compliance + consistency TIER)
  and `note`. Updated in place: `prices-batch --name` mode, budget contract
  language (spending plan, 85–100% target), search price chips + `--max-rank`,
  deck-check `staple_density` + Bolt/tuck vocab, final-build ships
  `deck_list.json`, Agent Usage rewritten to the §6.0 annotated flow (questions
  MANDATORY at step 3), Output Files shows the annotated `deck.json` shape +
  `build-notes.json`, Development Notes (models/, tier_weights.json, 140 tags,
  376 golden sentinels, 1300+ tests). Stale counts swept (34k identities).
  Docs-only. (`README.md`)

### Added
- **Budget Reallocation — the cost-by-type lens wired into the agent contract
  (user design: make the build more personal).** `budget --by-card` answers
  "which CARD is expensive"; `deck-view`'s cost by type answers "where does the
  MONEY sit" — and money in a low-impact bucket (classic: expensive nonbasic
  lands) is budget a passed-on staple/wincon could use. New BUILDER §11
  subsection "Budget Reallocation": when over budget or an upgrade doesn't fit,
  read `metrics.price_by_type`, and if reallocation would fund a better card,
  **ASK the user — never reallocate silently** (proposal template: exact cuts,
  exact upgrade, both prices, freed amount, consistency trade-off; basics-for-
  duals is cheap in mono/2-color, risky in 3+). Rationale in the contract
  itself: the user owns this trade — they may value the mana base, own the
  cards, or see something the agent didn't. Synced with intentional redundancy:
  user-feedback.md (new during-build question + valid reason), deck_builder.md
  step 7, deck_fixer.md Budget Fixes (reallocation before card-by-card cuts),
  CLAUDE.md step 7. Docs-only; suite 1305 green. (`BUILDER.md`, `CLAUDE.md`,
  `agents/{user-feedback,deck_builder,deck_fixer}.md`)
- **`Deck.total_price_by_type()` — "the deck has $X on lands" (user request).**
  Known-price USD total per Moxfield PRIMARY type (the existing `primary_type`
  single-bucket rule: Artifact Creature = creature, Dryad Arbor = land),
  quantity-aware, sorted most-expensive first, same unknown-price convention as
  `total_price` (None sums $0 — unknown ≠ free, documented in the docstring).
  Wired into `deck-view`: human "cost by type:" line + `metrics.price_by_type`
  in JSON. Live on Kiki: creature $45.64 > sorcery $34.71 > ... > land $6.12
  (a combo deck's money is in its engine, not its mana — visible at a glance).
  2 regression tests (model + CLI pin); suite 1305 green. (`models/deck.py`,
  `cli/commands/deck.py`, `tests/{test_deck_model,test_fase4_commands}.py`)
- **The §5 core questions get a mechanical gate (user finding: agents skip the
  default questions).** Root cause was two-sided: user prompts phrase the questions
  as conditional ("ask for any doubts" — an agent with plausible defaults never has
  doubts), and BUILDER §5 used soft language ("Default: ask up to 4 core questions").
  Fixed with the project's proven pattern (preflight / verify-early / deck-add
  guardians: docs-only rules get skipped, gates don't): (1) **`deck-add`'s FIRST
  call now refuses to create a deck without the answered build contract** —
  `--set-config budget=<USD|n/a>` AND `--set-config bracket=<1-5|n/a>` — with an
  error that points the agent at the §5 questions ("Do not draft on assumed
  defaults"); explicit `n/a` is a valid answer, missing is not. A draft mechanically
  cannot start before the questions were asked. (2) Docs hardened preserving the
  intentional redundancy: BUILDER §2 gains rule 14 (questions are UNCONDITIONAL;
  "ask if in doubt" is not the contract) and §5 rewritten MANDATORY-wait-for-answers;
  agents/system.md rule 12; agents/user-feedback.md header; agents/deck_builder.md
  step 2 ("if needed" was the same bug) + step 9; CLAUDE.md step 2. Legacy
  `deck-write` path is NOT gated (docs-only there) — noted as a known hole. 2
  regression tests (gate blocks / partial contract blocks / n-a passes / not
  required after first use); suite 1304 green. (`cli/commands/deck.py`,
  `BUILDER.md`, `CLAUDE.md`, `agents/{system,user-feedback,deck_builder}.md`,
  `tests/test_fase4_commands.py`)
- **Full build #4 = the Consistency Engine's ACCEPTANCE TEST: Kiki-Jiki, Mirror
  Breaker (virgin, mono-R combo-first, salt alta, tutors-first, $150 soft,
  bracket n/a — the new §5 bracket question's production debut) — READY at
  $149.04 (99.4% utilization, a PERFECT draft-TO-budget landing) and TIER +S
  (9.78/10), earned:** 9 auto-win routes (6 with the commander always
  available), Q_wincon 0.998 with 5 tutor wildcards, functions 0.83–0.94, curve
  8.19. **Ragost F (4.61, no combos/tutors) vs Kiki +S — the tier discriminates
  exactly along the user's axis.** The new flow validated itself: deck-add's
  guardian caught TWO color violations AT ENTRY (Hyrax Tower Scout is G,
  Village Bell-Ringer is W — the class of error that reached `validate` in
  build #2); the running total exposed a budget explosion INSTANTLY
  ($197/131% when Purphoros turned out to be $27 vs a ~$5 memory) and the trim
  landed 99.4%; pre-draft `prices-batch --name` discarded Deflecting Swat (44%
  of budget) and Jeska's Will (26%) before they were touched; 6 combos noted
  the moment they were seen and synced into the deck; validate 0 errors and
  preflight READY first try; the build folder ships deck_list.json. Live
  calibration catch: **Kiki reads `Legendary Matters: high` from "target
  NONlegendary creature" — a negation with no guard in LEGENDARY_MATTERS**
  (queued). Acceptance frictions (backlog): no `deck-remove` CLI command (the
  Deck object has it), and deck-swap's OUT side doesn't match DFC front-face
  names — both noted with `mtg note` DURING the build, as designed.
  (`final-builds/Kiki-Jiki-Mirror-Breaker-Twin-Lines-Combo-T1-v1/`,
  `logs/testbuild-kiki-fullbuild-4.json`)

### Changed
- **Consistency-engine Fase 5 (A+B): cleanup + the big agents-sync.** Cleanup:
  pyflakes sweep, three real items removed (an unused Optional import, dead
  `toks`/`sys` in logging_util) — the _shared/models re-export warnings are the
  deliberate star-import surface, untouched. Agents-sync (intentional redundancy
  preserved): **BUILDER gains §6.0 — the annotated-deck flow as the PRIMARY
  workflow** (deck-add per package with the contract in `--set-config` → note
  combos AND rejected candidates as spotted → one deck-annotate pass →
  deck-view → deck-power → the classic close; the legacy decklist.txt path stays
  documented with what it loses); CLAUDE.md steps 5-6 rewritten to match;
  agents/system.md rule 8 + the full build mindset (final-build ships
  deck_list.json); agents/deck_builder.md steps 9-13 (draft THROUGH the tool,
  the rejected-candidates note rule, annotate at the end, deck-power before
  finalizing). Docs + 3 code lines; suite 1302 green. Remaining: test build #4
  as the plan's acceptance. (`BUILDER.md`, `CLAUDE.md`,
  `agents/{system,deck_builder}.md`, `models/consistency.py`, `logging_util.py`,
  `logs/fase5-cleanup-agents-sync.json`)

### Added
- **Consistency-engine Fase 4: the tooling — `mtg deck-add`, `mtg deck-annotate`,
  and deck-power wired to the consistency tier.** (1) **Survival fix
  (prerequisite):** `deck-swap` rebuilt `{commander, main_deck}` from scratch and
  silently DROPPED every other top-level key (combos, agent_note, config) — the
  exact silent-death bug the Fase-2 design feared, caught by the survival test
  (fill-lands preserved everything); it now carries the original JSON whole, and
  the swapped-in card inherits the slot's purpose. (2) **`deck-add`** — THE
  drafting primitive (drafting was 100% agent memory): batch per PACKAGE, ATOMIC
  through the Deck object's guardians (exists / color identity / singleton /
  size), `"12 Mountain"` syntax for basics, `--purpose` at entry (the package IS
  the role), `--set-config` (the build CONTRACT — budget/mode/bracket — travels
  IN the deck via Deck.config, killing the mid-build compaction risk and
  replacing the planned sidecar file), and **batch price + running total with
  budget %** — draft-TO-budget made mechanical (live: 1.8%→12.4%→43.7%→60.5%
  package by package). (3) **`deck-annotate`** — `--auto` seeds derivable
  purposes from the measured census (merge-only; lands count as RAMP only via
  the ramp_rules single source), `--cards/--purpose-add/--note` batch
  refinement, `--sync-notes` pulls the notebook's combos into the deck (dedup)
  and marks COMBO_PIECE. (4) **deck-power** prints the CONSISTENCY tier (routes,
  broken routes, per-turn functions, curve) when the deck is annotated, falls
  back to the legacy census tier with a notice otherwise, and reads the bracket
  target from Deck.config. Smoke pin 36→38. The new CLI tests immediately caught
  a NameError of the historical split class (deck.py missing `_emit_json_error`)
  — fixed. Plus **`mtg deck-view`** (user-spotted gap: scores existed but nothing
  SHOWED the annotated deck): commanders + config + budget utilization, metrics
  (by_purpose, primary-type counts, curve + score), combos, Moxfield-format list
  or `--by-purpose` grouping, and `--card "Name"` printing the CARD object's
  build-facing summary (with its agent_note); JSON mode returns the full dict +
  metrics. Smoke pin 34→39 across the phase. And **`final-build` now ships
  `deck_list.json`** in the build folder (user request): the ANNOTATED deck JSON
  — purposes, agent notes, config and combos travel with the finished build
  beside the .txt list and the explanation guide. 10 CLI tests; suite 1302
  green. (`cli/commands/{deck,misc}.py`, `models/{card,deck}.py`,
  `tests/{test_fase4_commands,test_cli_smoke}.py`, `logs/fase4-tooling.json`,
  `logs/fase4-deck-view.json`, `logs/fase4-final-build-ships-json.json`)

### Added
- **Consistency-engine Fase 3: the tier math (`models/consistency.py` +
  `data/seed/tier_weights.json`).** TIER = deck consistency, exact hypergeometrics
  over the agent's annotation: **CORE is a weighted GEOMETRIC mean** (consistency
  is conjunctive — `10 × Q_wincon^0.45 × P_bundle^0.30 × curve^0.25`; a deck with
  no wincon access is F by structure, the user's GC-pile thesis test-pinned) plus
  a small capped ADDITIVE bonus (arsenal routes, raw GCs — low per user).
  Q_wincon weights each win route by CLASS quality (auto-win infinite 1.0 >
  infinite 0.85 > value wincon 0.6 > non-infinite 0.55 — reaching Toxrill ≠
  reaching an auto-win); assembly probability is the exact multi-piece joint with
  **tutors (SEARCH) as wildcards** (two-group sum, not a heuristic); DRAW velocity
  multiplies through n_seen(T) instead of scoring separately; function bundle at
  Magic-argumentable turn targets (RAMP@T2 — the user's table definition incl.
  Cultivate-class land search —, DRAW/REMOVAL@T3, SYNERGY@T4, wincon@T7). Every
  constant is DECLARED in the seed file with provenance. Reliability guards: zero
  declared routes → tier None with a reason (never a fake F); **broken routes
  (pieces not in the deck) are reported as the "one card away" signal and never
  scored — a real bug caught on the first live run** (Heliod+Ballista scored
  0.296 with Ballista absent; the honest tier dropped 8.95→8.15). `Deck.tier()`
  exposes the full report (components, weights, notes). 11 hand-pinned tests;
  suite 1290 green. (`models/{consistency,deck}.py`,
  `data/seed/tier_weights.json`, `tests/test_consistency.py`)

### Added
- **Consistency-engine Fase 2: the CARD and DECK build-context objects
  (`src/mtgcli/models/`, user design).** **CARD**: agent judgment (purpose — one
  or MANY from a controlled vocabulary; optional agent_note) + DB-hydrated facts
  (oracle, P/T, loyalty, keywords, produced_mana, edhrec_rank, all_parts GROUPED
  by component and self-filtered, image_src, mana cost/value, color identity,
  price, game_changer — GC auto-adds itself as a purpose from the flag). Names
  arrive PRE-VERIFIED; a miss fails loud Krenkooo-style (fuzzy did-you-mean + fix
  instructions). `__str__` is the build-facing summary (type from type_line,
  stats, oracle, note-wins-over-purpose). **DECK**: composition (deliberately NOT
  a List subclass); 1-2 commanders (partner/background; max_size 99/98); mutation
  only through batch-friendly ATOMIC `add()`/`remove()` guarding size
  (quantity-aware, commanders excluded), singleton (basics MERGE quantities) and
  color identity; deck-level combos grouped by class ({infinite, non_infinite,
  utility, auto_win} of {cards_needed, how_to}); metrics per spec —
  total_by_purpose, total_price, card_types (Moxfield-style PRIMARY type),
  mana_curve and the user's TVD-based `mana_curve_score` (10 = ideal shape;
  IDEAL_CURVE is the one declared judgment constant; None on an empty deck, never
  a fake 10); print = card count + Moxfield-format list. Both objects are
  EPHEMERAL: serialization persists judgment only (facts re-hydrate from the DB
  on load — the user keeps the DB fresh). 26 regression tests; suite 1279 green.
  (`models/{__init__,card,deck}.py`, `tests/{test_card_model,test_deck_model}.py`)

### Added
- **Consistency-engine Fase 1: five new ingest fields wired through the whole
  pipeline (DB rebuild left to the user's manual reset).** `keywords` (Scryfall's
  parsed keyword list — the analyzer currently regexes oracle text for keywords
  that arrive structured here), `loyalty` (face-aware, the get_power_toughness
  pattern), `produced_mana` (None when absent), `all_parts` (slimmed to
  component/name/type_line/id — PARKED for v0.9.0) and `image_url` (front-face
  normal with DFC face-fallback — PARKED for v0.9.0). The printings merge is
  hardened: first-printing-wins left gaps for per-printing fields (image_url) when
  the first printing lacked them — now fills from any later printing. The existing
  migration guard ALTERs the new columns into an old DB on rebuild; a fresh build
  creates them directly. Schema sync 31==31==31; 6 unit tests on fakes (zero DB
  dependency); suite 1253 green. (`data/{normalize_cards,build_sqlite}.py`,
  `tests/test_fase1_ingest_fields.py`, `logs/fase1-ingest-wiring.json`)

### Added
- **Draw-odds panel in `deck-power` (user framing: probabilities are interpretable
  where raw density is not).** Exact hypergeometric — per-draw %, P(≥1 in the
  opening 7), expected count — for plan/synergy cards, combo pieces and game
  changers. Counts are quantity-weighted over the WHOLE deck (draws include lands,
  more honest than density-over-nonland) and the commander is excluded from k
  (command zone, not drawable). Ragost live: plan cards 18/99 → 18.2% per draw,
  76.6% opening-hand chance, 1.27 expected. Honest framing kept in the output: a
  representation change, not new information — k is still the text-visible census.
  2 regression tests (math pinned against `math.comb`); suite 1247 green.
  (`deckbuilder/deck_power.py`, `cli/commands/deck.py`, `tests/test_deck_power.py`,
  `logs/feature-draw-odds.json`)

### Added
- **The two categorizers (user design): `mtg deck-power` (bracket compliance +
  tier) and `mtg note` (building notes) — plus the `game_changer` ingest.**
  (1) **Bracket compliance** — deterministic official-criteria checks: Game
  Changers (WotC's flag, newly ingested — 53 cards; new column + a MIGRATION GUARD
  in build_sqlite that ALTERs missing columns into an existing DB on rebuild), mass
  land denial, extra-turn cards, complete 2-card infinite/auto-win combos, tutors
  (informational) → computed minimum bracket (1-2 / 3 / 4-5) and a COMPLIANT
  verdict against `--bracket <target>`. BUILDER's core question 1 now asks for the
  BRACKET with an `n/a — I don't care` default (brackets are a social contract, not
  a requirement); user-feedback.md carries the bracket→power-level mapping.
  (2) **Tier** — 0.0–10.0 in 0.5 bands per user spec (+S ≥9.5 … D 5.0, F below):
  synergy density + classed combos (auto_win > infinite > non_infinite > utility)
  + game changers, CONSIDER-ONLY by contract. The formula encodes the user's power
  philosophy: a GC pile without synergy stays F (test-pinned) and no-combo decks
  cap ≈+C. Calibration honesty: density measured 0.25–0.43 on the 4 real builds;
  commander-granted synergy (Ragost's rocks-are-Foods) is text-invisible and
  underreads — documented in the output itself. (3) **`mtg note`** — the
  carpenter's tally: record combos/decisions/findings DURING the build
  (`--type combo --cards "A;B" --combo-class ...`); combo notes are first-class
  deck-power sources deduped against the external fetch (noted classification
  wins), with graceful offline degrade and a "one card away" near-miss list (live
  on Ragost: missing Walking Ballista for the Heliod auto-win). Ghost-name guard:
  `--cards` validates names against the DB and warns (caught live on first use —
  a bad separator created ghost cards silently). deck-gaps' plan check refactored
  onto the new single-source `deckbuilder/plan_coverage.py` (verified identical),
  which deck-power's synergy density shares — no drift possible. Smoke pin
  34→36 commands (deliberate). 22 regression tests; suite 1245 green.
  (`data/{normalize_cards,build_sqlite}.py`, `deckbuilder/{deck_power,build_notes,
  plan_coverage}.py`, `cli/commands/{deck,misc}.py`, `BUILDER.md`,
  `agents/{system,user-feedback}.md`, `tests/{test_deck_power,test_cli_smoke}.py`,
  `logs/feature-deck-power-categorizers.json`)

### Changed
- **Agent files synced to today's tooling (audit-driven, redundancy preserved).**
  The audit found the role files unaware of every feature shipped 2026-07-06; fixed
  surgically: (1) `agents/deck_builder.md` step 7 gains the price-at-pick-time rule
  (search rows print prices; `prices-batch --name` before summing; `--max-rank`
  consider-only) and its deck-gaps section documents the counted-cards lists for
  fix-or-justify; (2) `agents/system.md` rule 8 adds `prices-batch --name` to the
  no-scripting helpers, and the JSON error contract gains the INVERSE rule: non-zero
  exit + JSON without `"error"` = documented workflow state (`status_exits` in
  report summaries), not a failure; (3) `agents/card_ranker.md` inputs gain
  edhrec_rank labeled consider-only; (4) `agents/deck_fixer.md` re-audit notes the
  counted-cards list verifies a fix registered; (5) `BUFF.md` judges plan_gap leads
  against the counted list, not the number; (6) `agents/user-feedback.md` wires the
  staple-policy answer to the tooling (answer (a) → `--max-rank`; answer (c) → a low
  staple_density is the REQUESTED outcome, not a problem). Docs-only; suite 1232
  green. (`agents/{deck_builder,system,card_ranker,deck_fixer,user-feedback}.md`,
  `BUFF.md`)

### Added
- **EDHREC-rank popularity signals (the two v0.8.0 tentativo items), scoped
  CONSIDER-ONLY by user direction.** (1) `deck-check` gains **`staple_density`**:
  median edhrec_rank + % top-2000 over nonland cards, with a qualitative read —
  printed as a dim informational line and JSON block, deliberately NEVER a warning
  and NEVER gating preflight ("popularity ≠ power; synergy-dense decks read low by
  design" is in the output itself). Thresholds calibrated against the four real
  agent builds (Felothar T3 43.3%, Galadriel T3 65.6%, Mendicant T2 71.4%, Ragost T1
  72.6% — the signal orders the brackets correctly; ≥65 staple-dense / 40–65 mixed /
  <40 outlier flag, coarse on purpose at n=4). Honest note: the initial thresholds
  from intuition were useless (everything read staple-heavy) — real decks are full
  of staples BY COUNT; calibration beat prediction. (2) **`--max-rank`** on
  `search`/`search-tags` (unknown ranks kept — 17% of the DB is unranked). Bug
  caught in live verification: the post-filter STARVED the result list (a rank cap
  on a limit-5 fetch returned nothing); fixed with conditional oversampling in all
  three search branches — plain `search`'s `--max-price` had the same pre-existing
  starvation and gets the fix for free. BUILDER.md search axes updated. 8 regression
  tests incl. the never-a-warning contract; suite 1232 green.
  (`deckbuilder/deck_check.py`, `cli/_shared.py`, `cli/commands/{search,deck}.py`,
  `BUILDER.md`, `tests/test_staple_density.py`, `logs/polish-edhrec-signals.json`)

### Fixed
- **Trigger-doubler CAST context (the last Fase-0.2 known-gap) — the doubler's four
  contexts are now complete: attack / death / enter / cast.** New
  DOUBLES_CAST_TRIGGERS branch in `detect_trigger_doubler` (per-line "cast" check,
  the same structural pattern as the other contexts) → Spellslinger SUPPORTING (a
  defining promotion would overband type-scoped doublers). Veyran fires the signal —
  his Spellslinger high is now signal-backed beside magecraft; Echoes of Eternity
  correctly excluded (its doubler line reads "colorless spell you CONTROL"; the
  'cast' sits on its separate copy line), Gandalf the White turned out to be an ETB
  doubler in his real text (a memory misread the per-line check classified correctly
  on its own), Harmonic Prodigy's reminder-cast excluded. Controls green: Isshin,
  Panharmonicon, Teysa Karlov. Veyran pin upgraded with expected_signals; suite 1224
  green. (`analyzer/content.py`, `analyzer/mapping.py`,
  `data/golden/golden_cards.json`, `logs/polish-doubler-cast-context.json`)

### Fixed
- **Audit signal/noise + compression prominence (v0.8.0 polishing, the two BAJA
  items — the full-build-#3 retro backlog is now CLOSED).** (1) `report --summary`
  separates **status exits** from real failures: a non-zero exit whose JSON response
  has NO `"error"` key is a documented workflow state (card not-found, `cards-batch
  --verify` with missing names) — the JSON error contract itself is the classifier;
  plain-text non-zero output (SIGPIPE-truncated, rich panels) stays a failure. The
  human summary prints status exits as a separate dim line. Honest correction
  recorded: `budget` never exits non-zero (verified both modes) — the two
  "over-budget exits" in the Ragost audit were also pipe-to-`head` SIGPIPEs; all 8
  were pilot noise, zero tool anomalies (the budget-text branch stays as a forward
  guard). (2) `category-counts --table` demotes the compressed target to a trailing
  lowercase **`comp*`** column with a self-documenting footnote ("guidance only —
  build to Need/Range; a High/Critical category can compress to a misleading tiny
  target") — the third confirmation of the misleading-compression issue, now encoded
  in the output itself instead of only in the contract docs. 6 regression tests;
  suite 1224 green. (`logging_util.py`, `cli/commands/misc.py`,
  `category_counts/output.py`, `tests/test_report_summary_split.py`,
  `logs/polish-baja-items.json`)

### Fixed
- **The qualifier-interruption GENERAL mechanism (v0.8.0 polishing, the structural
  MEDIA item — 5 sightings incl. 1 in production) + deck-gaps now shows WHICH cards
  it counted.** New single-source module `utils/phrase_match.py`: a tag phrase may
  carry the `" * "` wildcard — literal parts in order with a BOUNDED same-clause gap
  (40 chars, never crossing `.`/`;`/newline; unbounded would recreate the
  naked-substring FP class). ALL SIX phrase consumers ported (cards/search SQL via
  `phrase_to_like` + rank re-check, deck_check ×2, card_profile — the analyzer's
  matched_tags —, suggestion_scorer, ramp_rules, deck-gaps) so the multi-consumer
  drift class is structurally closed for phrase matching; plain phrases behave
  byte-for-byte as before. First wildcard phrases, both measured: reanimation
  "creature card * from your graveyard to/onto the battlefield" (273+2 genuine —
  **Mirko, the founding #21 member, reads Reanimator very_high**; Alesha improves
  free; Otrimi's to-HAND control stays excluded) and lifegain_payoff "you gained *
  life this turn" (57/57 — **Angelic Accord, the production sighting, reads Lifegain
  Matters high**). Same round: deck-gaps' plan check returns and prints the counted
  cards (`analyzer_support[].have/cards`, `plan_gaps[].cards`, human "counted:"
  line) — verified live on Ragost (Lifegain 4→6, gap resolved by data not guesswork).
  Mirko pin updated + Angelic Accord/Alesha sentinels → 376, sanity "377 passed";
  9 mechanism tests; suite 1218 green. (`utils/phrase_match.py`, `cards/search.py`,
  `deckbuilder/{deck_check,card_profile,suggestion_scorer,ramp_rules}.py`,
  `cli/commands/deck.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`, `tests/test_phrase_match.py`,
  `logs/polish-media-items.json`)

### Added
- **Price visibility at pick time (v0.8.0 polishing — the two ALTA items from the
  full-build-#3 retro).** (1) Every search-family result row now prints a **price
  chip** (`$1.23` / `$?` when unknown) via a shared `fmt_price` helper — `search`,
  `search --trigger`, `search-tags`, `similar`, `complements`. The shortlists
  already FILTERED by `--max-price` but never showed the price, so hand allocation
  ran on memory prices (measured off by 5x: Flawless Maneuver remembered ~$4,
  actual $20.30). (2) **`prices-batch --name` (repeatable; the file argument is now
  optional and both combine)** — cost hand-picked candidates BEFORE they join a
  list; human output ends with a known-price TOTAL in both modes; JSON stays a
  plain list in file mode (backward compatible) and returns `{results, known_total,
  unknown_count, not_found_count}` in `--name` mode; ad-hoc not-found names get the
  fuzzy did-you-mean suggestions. No new command — the 34-command smoke pin is
  intact. Live check reproduced the build friction in one shot: three `--name`
  lookups → $60.20, the exact surprise money from the Ragost draft. One bug caught
  during verification (suggest_similar_names returns dicts — join crashed; fixed).
  BUILDER §6/§11 and CLAUDE.md updated: never sum a draft on memory prices.
  8 regression tests; suite 1207 green. (`cli/_shared.py`,
  `cli/commands/search.py`, `cli/commands/cards.py`, `BUILDER.md`, `CLAUDE.md`,
  `tests/test_price_visibility.py`, `logs/polish-price-visibility.json`)

### Added
- **Full build #3 (post-30-batch milestone): Ragost, Deft Gastronaut (virgin, RW
  artifacts-as-Foods group slug, user-picked) — READY at $146.63/$150 soft (97.8%
  utilization), T1, ZERO tool errors, preflight first try — and the draft-TO-budget
  Budget Contract PASSED its acceptance test.** The Upgrade Review never triggered;
  package allocation happened while drafting (key slots Solphim $25.59 / Heliod
  $20.66 / Aetherflux $19.68 inside the 15–20% guidance; Smothering Tithe at 33% of
  budget correctly skipped). Honest asterisk: the first COSTED sum hit $219 because
  hand-picked staples carried memory price guesses (Flawless Maneuver $20.30 vs ~$4
  remembered) — the `--by-card` flag caught it and 7 deck-swaps landed 97.6% before
  deck-write, inside the same drafting pass. **Friction lesson: allocation needs
  price visibility at pick time — run `prices-batch` over hand-picked staples before
  summing.** The analyzer ran the build end-to-end in production: the triple read
  (Artifacts + Group Slug + **Lifegain Matters — an archetype created HOURS earlier
  in the post-30 fix round**) drove every package, and the M2 plan check raised a
  real plan_gap (4 lifegain payoffs < 5) that improved the deck (Second Breakfast →
  Exemplar of Light). Calibration sighting: **Angelic Accord's "gained 4 OR MORE
  life" is the qualifier-interruption family's 5th member and FIRST production
  sighting** — the deck-gaps counter undercounts a genuinely-covered category.
  Two pilot memory-of-effects errors caught by the spot-check discipline before
  building (Throne of the God-Pharaoh counts tapped CREATURES; Currency Converter is
  discard-based); 6 SIGPIPE audit artifacts from piping through `head` (the Felothar
  lesson, repeated). verify-early 76/76.
  (`final-builds/Ragost-Deft-Gastronaut-Food-Cannon-T1-v1/`,
  `logs/testbuild-ragost-fullbuild-3.json`)

### Fixed
- **Post-30 fix round: the mature two-member gap queue closed — 2 NEW archetypes,
  6 measured tag extensions, 1 structural tribal fix, 2 measured rejects.** NEW:
  **Devotion** ("devotion to" 67/67 — Nylea's #21 honest empty closed; Klothys and
  Athreos read their god clauses; Gray Merchant pinned as payoff control) and
  **Coin Flips** (payoff forms only, 8 — Yusri/Okaun/Zndrsplt; naked "flip a coin"
  81 rejected like the d20-roller class). Extensions: spell_payoff += "instant and
  sorcery spells you cast cost" (22/22 all less-direction — **the Electromancer
  gap closed: Vadrik and Baral read Spellslinger high**); clone_copy += "becomes a
  copy of" (73 — **Volrath and Brudiclad read Clones high**, Krark guard
  untouched); group_hug += "attacking player draws" (Breena's Goad + Politics +
  Counters triple); death_trigger += "another creature you own dies" (Athreos →
  Aristocrats high); land_payoff += "land you control is put into a graveyard"
  (Titania → Lands + Go Wide, her full truth); investigate += "you sacrifice a
  clue" (14/14). STRUCTURAL: the tribal capture's lazy `+?`/`s?` ate the trailing
  s of s-ending types ("Fungus"→"fungu") and -ves plurals ("elve"/"wolve") — word
  resolution now tries raw/s-stripped/s-restored/ves→f candidates (Thelon reads
  Fungus Tribal high) plus a whitelist-filtered global-anthem pattern "(all|each)
  <Type> get" (Slivers/Saprolings/Nightmares class). REJECTED measured-dirty:
  "target opponent draws" (4/8 are drawback riders — Thought-Knot Seer pinned as
  guard) and naked "flip a coin". Deferred: the general qualifier-interruption
  mechanism (every member so far closed via cheap measured variants). Twelve pins
  updated + 2 new guards → 374 sentinels, sanity "375 passed"; suite 1199 green.
  (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`, `logs/post-30-fixround.json`)

### Added
- **Calibration batch #30 (blind-first): FAIL (CW 1) — fixed at BOTH layers, and
  THE 30-BATCH PLAN IS COMPLETE (7 PASS / 7 FAIL-fixed post-gate, zero unfixed
  lies).** Rights: Kotori (**Vehicles validating fresh**), Klothys (symmetric-pinger
  slug + punisher warning), Kumena (mode 3's clean "each Merfolk you control" fired
  tribal, beating the blind's qualifier-interruption prediction), Eloise
  (Aristocrats + clue value engine), Edgar, Charmed Groom (Vampire Tribal + Go Wide
  — and the DFC control: the Coffin's bloodline counter read SELF, per-face
  card_name plumbing works). The CW: **Grimgrin read `Stax: high` from his OWN
  "enters tapped and doesn't untap during your untap step" at BOTH layers** —
  UNTAP_RESTRICTION was missing from the SELF_RESTRICTION guard's signal list (the
  #18 audit-the-alternation lesson on a guard's SIGNAL list) and the stax tag
  carried a naked "doesn't untap" (the scope-check-only-in-signal-layer annotation
  finally producing a real lie). Fixed both: guard extended (self subject before +
  "during your untap step" after — Winter Orb/Frost Titan keep true Stax;
  _self_subjects gains this artifact/land/enchantment for the Mana Vault class) and
  the tag split directionally (its-controller 179 / their-controllers 35 stay;
  your-untap-step 54 out). Controls all green; Grimgrin reads Aristocrats medium.
  New known-gaps: coin-flip (Yusri), generic incoming-damage 3rd form (Michiko),
  land-GY 3rd form (Titania), global symmetric anthem (Thelon), devotion 2nd member
  (Klothys). Twelve sentinels (10 batch + Winter Orb/Mana Vault controls) → 372,
  sanity "373 passed"; suite 1197 green. (`analyzer/semantics.py`,
  `data/seed/card_tags.json`, `data/golden/golden_cards.json`,
  `logs/calibration-batch-30.json`, `logs/calibration-batch-30-fixround.json`)

### Added
- **Calibration batch #29 (blind-first): FAIL (CW 3, two predicted) — the attack
  DIRECTION family completed with its 4th direction, and the batch-11 name class
  fixed at a second site.** Rights: Beckett Brass (Pirate + Theft + Attack triple
  true), Wort (conspire copy-slinger), Cadira (deployment side of #19). The CWs, all
  ONE direction-scope family: (1) **Medomai** read `Stax: high` from his OWN "can't
  attack during extra turns" — the SELF_RESTRICTION guard's split(",")[0] subject
  never matches no-comma legends referenced by first name (the batch-11 class in
  semantics.detect_negation); fixed with a first-name fallback, Gadrak/Peacekeeper
  controls green. (2) **Breena** (predicted) read `Attack: high` from "whenever a
  player attacks one of your opponents" — the THIRD-PARTY direction; new
  THIRD_PARTY_ATTACK_INCENTIVE signal → Goad / Forced Combat defining (measured 14,
  all incentive class) — the attack family now covers all four directions
  (self/board/incoming/third-party); Breena reads Goad + Counters, Marisi/Cadira
  intact. (3) **Teysa EoG** (predicted) read `Attack + Go Wide: high` from "a
  creature deals combat damage to YOU... create a Spirit" — the saboteur-INVERSE
  incoming form escaped the #22 guard and her compensation Spirits fed the token
  conjunction; incoming regex extended (7/7 defensive measured) + a new
  incoming-compensation token guard (2/2: Teysa, Search the Premises); she reads
  Pillowfort high, Isperia intact. Partials seeded the queue: Baral = **2nd
  Electromancer member** (typed spell cost-reduction, now firmly measurable),
  Brudiclad = 2nd "becomes a copy" member, Atraxa PV = the proliferate-only class,
  Go-Shintai = Shrine identity (enchantment-type tribal). Ten sentinels with 3
  signal-asserting CW pins → 360, sanity "361 passed"; suite 1185 green.
  (`analyzer/semantics.py`, `analyzer/content.py`, `analyzer/mapping.py`,
  `data/golden/golden_cards.json`, `logs/calibration-batch-29.json`,
  `logs/calibration-batch-29-fixround.json`)

### Added
- **Calibration batch #28 (blind-first): PASS — right 5, partial 3, empty 2, CW 0 —
  seventh post-gate PASS; both #27 archetypes and MODAL_TOOLBOX validated fresh, and
  the #19 attack boundary held on BOTH sides in one batch.** Rights: Vadmir (**Crimes
  Matter validating fresh**; his crime counters go on himself — correctly SELF),
  Trelasarra (**Lifegain Matters validating fresh**), Fain, the Broker
  (**MODAL_TOOLBOX validating fresh** on a virgin member of the measured 4-commander
  class — menu warning fired, per-mode bands are options per §7.0b), Neheb the Worthy
  (Minotaur Tribal; his saboteur "deals combat damage → each player discards" is
  VALUE, no Attack band), Runo//Krothuss (DFC split; copies entering tapped and
  attacking = creature DEPLOYMENT feeding combat — Attack high TRUE — plus Clones).
  Partials/empties all honest with mechanisms identified: Light-Paws (aura-cast-enters
  payoff form), Marina Vendrell (rooms/doors class + enchantment-dig-to-hand form),
  Ms. Bumbleflower (gift-draw hug form "target opponent DRAWS" — group_hug only has
  "may draw"; her Spellslinger high is the Birgi no-rider precedent), Ulamog CH
  (defending-player exile-mill + eldrazi-titan class), Athreos ("another creature YOU
  OWN dies" — **qualifier-interruption 4th member**, the general regex-tag mechanism
  gains pressure). Zero changes per PASS protocol; ten sentinels → 350, sanity "351
  passed"; suite 1175 green. (`data/golden/golden_cards.json`,
  `docs/MIGRATION-archetypes.md`, `logs/calibration-batch-28.json`)

### Added
- **Calibration batch #27 (blind-first): FAIL (CW 1) — the counter-DIRECTION family
  reaches the counter-sense layer; fixed structurally, plus two new archetypes.**
  Rights 6: Anthousa (**Targeted Spell Payoff / Heroic validating fresh**), Satsuki
  (**Sagas Matter validating fresh**; her Counters high is lore-counter MANIPULATION —
  the Vorel class, proliferate genuinely accelerates Sagas), Higure (**Ninjutsu
  validating fresh** + Ninja Tribal via the #19 tutor pattern; his saboteur
  self-trigger correctly did NOT band Attack), Henzie (Creature Spells + Aristocrats
  both true — tags-see-reminder landing defensible: blitzed creatures die every turn),
  Phylath (Landfall via the M5 ability-word strip), Inalla (Wizard Tribal + Clones +
  Life Loss triple; the EPHEMERAL guard kept her end-step copies out of Go Wide).
  Aragorn KoG validated MONARCH fresh (partial: his can't-block-as-offense half is a
  measurable gap). The CW: **Jhoira of the Ghitu read `Counters Matter: high` from
  "put four time counters on" — but suspend time counters COUNT DOWN (fewer = casts
  sooner); proliferate is actively anti-plan.** Fixed with a new **COUNTER_CLOCK**
  sense: put-time-counters + suspend-countdown context on the same reminder-stripped
  line (alternation audited per the #18 lesson — it catches Alaundo's textual grant
  "last time counter is removed" and Curse of the Cabal's "is suspended") never feeds
  Counters Matter. Measured 39 put-forms: 12/12 countdown-grants excluded, 27
  accumulators kept (Rose Tyler, Kate Stewart, As Foretold — more counters IS their
  plan). Coverage: NEW archetypes **Crimes Matter** (`crime_payoff` — "you commit a
  crime" 19 + "you've committed a crime" 7, opponent form excluded; the class hit its
  2nd commander-member per the conditional-rider precedent — Marchesa DoD empty→high,
  Magda reads Crimes + Treasures) and **Lifegain Matters** (pure mapping fix, Fynn
  precedent — `lifegain_payoff` existed unmapped; Amalia reads her truth, Vito gains
  Lifegain high beside his true drain). Process: "Marchesa, Resolute Monarch" turned
  out to be a battle back-face — the not-found path caught it (verify-early), replaced
  with Aragorn. Twelve sentinels (10 batch + Kate Stewart/Alaundo clock-split
  controls) → 340, sanity "341 passed"; suite 1165 green.
  (`analyzer/semantics.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`, `logs/calibration-batch-27.json`,
  `logs/calibration-batch-27-fixround.json`)

### Added
- **Calibration batch #26 (blind-first): PASS — right 6, partial 4, empty 0, CW 0 —
  sixth post-gate PASS, fourth consecutive; three post-#25 archetypes validated on
  virgin commanders in one batch.** Rights: Beluna Grandsquall (**Adventures Matter
  validating fresh**; his imperative "Mill seven cards" self-fill never read opponent
  Mill), Farideh (**Dice Rolling validating fresh**; the ability-word prefix stripped by
  the M5 fix), Yeva (**Flash / Instant Speed validating fresh** on the enabler form that
  motivated the archetype), Daxos the Returned (Enchantments + Go Wide double-high;
  experience counters via SCALES_WITH, no false Counters band), Rakdos, Lord of Riots
  (Creature Spells + Life Loss double-high — LOST_LIFE_PAYOFF caught the cast condition,
  beating the blind prediction), Volrath (Minus Counters high). Partials all honest with
  the mechanism identified: Ishkanah (delirium class — the one-shot token guard held),
  Kathril (keyword-counter class + GY dependency; his final +1/+1 correctly read SELF),
  Yasharn (predicted blind: "players can't pay life or sacrifice" not in the stax
  vocab), Vadrik (typed instant/sorcery cost-reduction does not band Spellslinger — the
  Goblin Electromancer family, the ripest gap of the batch). Zero changes per PASS
  protocol; five measurable known-gaps queued. Ten sentinels → 328, sanity "329 passed";
  suite 1153 green. (`data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/calibration-batch-26.json`)

### Changed
- **Budget Contract rewritten from "safety-first" to "draft-TO-budget" (user finding:
  the builder was forcing itself to save money).** Evidence across all three full
  builds: Galadriel 59.5%, Felothar 69%, Mendicant first draft 48% — the agent
  systematically anchored cheap because the FIRST thing the contract said was "Budget
  is a maximum constraint, not a spending target", gave explicit permission to land low
  ("Under budget is valid", "Do not add expensive cards only to spend budget"), and
  offered no per-card price guidance (so the agent invented tiny caps: $1–3/card on a
  $75 budget). The 60% floor + Upgrade Review was a two-pass patch that walked money
  back AFTER drafting cheap. New model (BUILDER §2 rule 12 + §11, CLAUDE.md step 7,
  agents/deck_builder.md steps 7/16, redundancy intentional): a budget is a SPENDING
  PLAN as well as a ceiling — target 85–100% utilization in the FIRST draft, allocate
  package budgets while drafting (mana base ~20-30%, core plan ~30%...), take the
  strongest card each slot's share affords, derive `--max-price` from the budget
  (~15–20% for key slots) instead of habit, and treat the >20% high-cost flag as
  visibility, not prohibition. Unchanged: the ceiling is absolute (hard budgets never
  exceeded), the quality bar stays (an expensive card that doesn't improve the deck is
  not an upgrade), and the 60% floor + Upgrade Review remains as the FAILSAFE — it
  should rarely trigger if drafting follows the contract. Docs-only; suite 1143 green.
  (`BUILDER.md`, `CLAUDE.md`, `agents/deck_builder.md`)

### Added
- **Full build #2 (post-batch-#25 milestone): Mendicant Core, Guidelight (virgin, WU
  artifacts + speed, user-picked) — READY at $68.62/$75 HARD (91.5% utilization), and
  the Budget Contract exercised END-TO-END exactly as designed.** The arc: draft
  $81.21 (the high-cost flag caught Sea Gate Restoration eating 51.6% of budget) →
  trim → $36.03 (48%, BELOW the 60% floor) → **the M5 utilization-floor rule fired in
  production for the first time: Budget Upgrade Review REQUIRED** → 9-upgrade package
  presented with prices/labels per §11, user chose B+Inventors' Fair → $68.62 READY.
  validate caught 2 draft color violations (Hexplate R, Armix B — fixed via deck-swap);
  verify-early 64/64; deck-gaps plan check + preflight green.
  (`final-builds/Mendicant-Core-Guidelight-Artifacts-Speed-T2-v1/`,
  `logs/testbuild-mendicant-fullbuild-2.json`)

### Fixed
- **deck-swap on a multi-copy basic-land entry renamed the WHOLE stack (full build #2
  friction #1).** "Island=Buried Ruin" turned 17 Islands into 17 Buried Ruins — a
  singleton violation validate caught only after the write, because deck-swap's
  singleton guard checked duplicate ENTRIES but not quantity > 1 within one entry.
  Fixed both halves: swapping out of a multi-copy entry now takes ONE copy (decrement
  + add the incoming card as its own entry; renames stay whole-entry for
  basic-to-basic), and the guard now also rejects any non-basic entry with quantity
  > 1. 3 regression tests; suite 1143 green. Friction #2 (calibration, annotated): the
  speed mechanic ("Start your engines!") has no class — Mendicant's `Life Loss: high`
  comes from the REMINDER text and happens to be strategically right (speed wants
  opponents losing life), but it produced a spurious deck-gaps plan_gap that had to be
  consciously justified. (`cli/commands/deck.py`, `tests/test_deck_swap_quantity.py`)

### Fixed
- **Post-#25 fix round: the entire #23–#25 measurable-gap queue closed — 7 NEW
  archetypes, 6 extensions, 2 structural fixes.** NEW: **Targeted Spell Payoff /
  Heroic** (the Gargos/Anax/Ivy family — Gargos, the project's original calibration
  class, finally reads his own plan), **Dice Rolling**, **Flash / Instant Speed**,
  **Storm** (keyword form "storm ("; naked substring rejected — 19 Windstorm-class
  self-reference FPs), **Ninjutsu / Sneak**, **Adventures Matter**, **Cycling**.
  Extensions: exploit/escape_gy/investigate as supporting tokens, singular land-GY form
  (Slogurk Lands high), "greatest power among" (PS Zegana Stompy high), directional
  permanent-card reanimation, punctuated imperative mill forms. Structural: modal-BULLET
  lines merge into their header ability (Caesar Go Wide high — recurring layout cause
  #2 closed for the token conjunction) and "you control attack" joins the trigger
  family at the oracle_hooks single source (Neyali Attack high). The golden net earned
  its keep twice: Bruvac's historical pin caught the naked "mill a card" matching his
  REMINDER text (punctuated forms shipped instead — strictly safer than the original
  unpunctuated vocabulary), and all 318 pins verified every change. Sixteen pins
  tightened; suite 1140 green. Still open: Mothman's Mill band, the general
  qualifier-interruption mechanism, tags-see-reminder (deliberate).
  (`analyzer/content.py`, `analyzer/mapping.py`, `deckbuilder/oracle_hooks.py`,
  `data/seed/card_tags.json`, `data/golden/golden_cards.json`,
  `logs/post-25-fixround.json`)

### Added
- **Calibration batch #25 (blind-first): PASS — right 5, partial 4, empty 1, CW 0 —
  fifth post-gate PASS, third consecutive.** Rights: Zevlor, Balmor, Eriette (the #22
  Pillowfort archetype validating fresh — Pillowfort + Life Loss + Stax triple, all
  true), Bright-Palm (the Vorel counter-doubling class), Mr. House (dice robots are a
  real army). Partials honest: Lonis (clue-steal reads genuine THEFT_CONTROL;
  investigate class = gap), Mothman (passive "cards are milled" form), Old Rutstein
  (imperative "mill a card" — the family now has 3 members), Ivy (the
  **targeted-spell-payoff/heroic family** — Gargos/Anax/Ivy, 3+ members, ripest
  archetype candidate; spell_copy correctly narrow, no Spellslinger lie). Gorion honest
  empty (adventure class). Process: an invented commander name ("Zimone, Wisdom
  Faucet") was caught by the not-found path before use. Zero changes per PASS
  protocol; ten sentinels → 318, sanity "319 passed"; suite 1140 green.
  (`data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/calibration-batch-25.json`)

### Added
- **Calibration batch #24 (blind-first): PASS — right 4, partial 4, empty 2, CW 0 —
  fourth post-gate PASS, second consecutive.** Rights: Gavi (cycling commander read via
  the session-2 draw_trigger_payoff + token engine), Kamiz (sneak-attack: Attack high +
  Voltron medium, both true), Tazri (the #18 Party archetype validating fresh), Gyrus
  (Attack + Clones + GY Value triple-high — and the blind-flagged ephemeral-variant
  risk did NOT materialize; pinned must_not Go Wide as guard). Partials/empties all
  honest with mechanisms identified: ninjutsu (Satoru), heroic ability-word (Anax),
  exploit (Sidisi UV), escape + land-put-from-hand (Uro — whose value "enters or
  attacks" the Zur rule correctly suppressed, pinned as control), "greatest power
  among" (PS Zegana), one-shot ETB (Malfegor). Zero changes per PASS protocol; ten
  sentinels → 308, sanity "309 passed"; suite 1130 green.
  (`data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/calibration-batch-24.json`)

### Added
- **Calibration batch #23 (blind-first): PASS — right 4, partial 5, empty 1, CW 0 —
  the third post-gate PASS.** Rights: Caesar (sac-on-attack; his tokens sit at low
  because modal BULLETS break the same-line conjunction — the recurring layout cause,
  now queued measurable), Otharri ("tapped and attacking" = combat-feed + token engine),
  Baeloth (the #19 Goad + Treasures archetypes validating on a fresh commander), Shanid
  (Legendary Matters validating). Partials all honest with the exact miss mechanism
  identified: Neyali (token-attack form — "one or more TOKENS you control attack"),
  Slogurk (singular "a land card IS put" vs the plural Gitrog phrase), Aeve (storm
  keyword; his Ooze Tribal read is right), Tayam (PERMANENT-card reanimation variant),
  Wyll (dice class). Errant and Giada honest empty — the flash-enabler class now has 2
  members and becomes measurable. Theft direction guards held on both self-impulse
  commanders. Zero changes per PASS protocol; 7 measurable known-gaps queued. Ten
  sentinels → 298, sanity "299 passed"; suite 1120 green.
  (`data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/calibration-batch-23.json`)

### Added
- **Calibration batch #22 (blind-first): FAIL (CW 2, one predicted) — the
  conditional-rider class fixed structurally, closing the batch-20 standing gap.**
  CW 1 (Isperia, predicted): "whenever a creature attacks YOU" banded Attack Triggers —
  direction inversion; fixed with the INCOMING_ATTACK_TRIGGER guard (19/19 pillowfort)
  + NEW archetype **Pillowfort / Defense**. CW 2 (Hallar): the SECOND conditional-rider
  commander, revoking the "1-card class" ruling — measured 23 "cast a spell, if
  <rider>" cards; fixed with the CONDITIONAL_CAST_RIDER detector + a mapper exclusion
  (wide-vs-tall precedent): non-spell-type riders demote spell_payoff to supporting.
  **Raggadragga's standing known-gap is closed** (Spellslinger high→low); controls
  Birgi (no rider) and Alania (instant rider) keep genuine highs. Coverage: NEW
  archetype **Sagas Matter** ("lore counter" rejected — would band all 239 printed
  Sagas) — Tom Bombadil empty→high; plural pair-anthem tribal patterns (29 pairs) —
  Gisa reads Zombie+Skeleton Tribal; graveyard_recast += "from among cards in your
  graveyard" — Kagha medium→high. Millicent the lone right: quadruple-high, all true.
  New known-gap family documented: tags see reminder text (Raff — deliberate: several
  tags rely on it; a per-tag strip list only if it ever produces a real lie). Eleven
  sentinels + 2 updates → 288, sanity "289 passed"; suite 1110 green.
  (`analyzer/content.py`, `analyzer/analyze.py`, `analyzer/mapping.py`,
  `data/seed/card_tags.json`, `data/golden/golden_cards.json`,
  `logs/calibration-batch-22.json`)

### Added
- **Calibration batch #21 (blind-first): PASS — right 6, partial 3, empty 1, CW 0 —
  the second post-gate PASS.** Rights: Moraug (landfall extra-combat — the M5
  ability-word strip + extra_combat), Osgir (GRAVEYARD_CLONE caught the PLURAL "create
  two tokens that are copies" the singular tag would miss), Karlach, Dina (very_high
  drain), Birgi (ritual storm — the comma-form spell_payoff is TRUE here, confirming
  the Raggadragga gap is the rider, not the phrase), Myrkul (Aristocrats + Clones).
  Partials honest: Mirko (NEW general known-gap: **qualifier-interruption** — "creature
  card WITH POWER LESS THAN MIRKO'S from your graveyard" breaks the contiguous
  reanimation phrase; the batch-16 nontoken-skip family), Ranar (foretell class
  unread), Strefan (tribal cheat-from-hand form + LOST_LIFE relative clause). Nylea
  honest empty (devotion class — future candidate). Zero analyzer changes per PASS
  protocol; ten improvement-friendly sentinels → 277, sanity "278 passed"; suite 1099
  green. (`data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/calibration-batch-21.json`)

### Added
- **Full build #1 (post-batch-#20 milestone): Felothar the Steadfast (virgin, WBG
  toughness/defenders, user-picked) — READY at $103.78/$150 (69% utilization), ZERO
  tool errors, exactly 1 friction (meets the ≤2 bar) — fixed root-cause same-session.**
  Full BUILDER.md flow: analyze → category-counts → function shortlists → verify-early
  (65/65, zero invented names) → deck-write/fill/validate → deck-check (no issues) →
  budget --by-card (no card >20%) → deck-gaps (zero gaps on a deliberately on-plan
  deck) → preflight READY first try → final-build
  (`final-builds/Felothar-the-Steadfast-Toughness-Defenders-T3-v1/`). The friction:
  the analyzer read only `Aristocrats: medium` — Felothar's PRIMARY (assigns-combat-
  damage-by-toughness) was invisible; `toughness_matters` covered only the batch-11
  Arcades forms ("with defender" + toughness-lifegain). FIXED: + "damage equal to its
  toughness" (24 measured — Arcades/Doran/Felothar/Bedrock Tortoise class) and the
  didn't-have-defender forms (49+5); "attack as though" rejected (Instill Energy haste
  FP). Felothar now reads Toughness/Defenders high + Aristocrats medium — his exact
  deck. Two pilot errors owned, not tool bugs: 4 logged "failures" were SIGPIPE from
  piping CLI output through `head` (exit 0 without the pipe), and the budget JSON parse
  guessed wrong keys (the real shape is `known_price_total`/`budget_status`, properly
  documented in the output itself). 2 sentinels → 267, sanity "268 passed"; suite 1089
  green. Audits: `logs/testbuild-felothar-fullbuild-1.json`,
  `logs/felothar-friction-fixround.json`. (`data/seed/card_tags.json`,
  `data/golden/golden_cards.json`)

### Fixed
- **Pre-build fix round: the batch #17–#20 leftovers swept — every open gap fixed or
  measured-rejected.** Fixed: (1) the stax tag's dead "costs more" phrase removed (0 DB
  matches) and "can't cast more than" split directionally ("each player..." 8 stays —
  Rule of Law control; "you can't..." 4 excluded — the session-2 Colfenor's Plans false
  Stax is dead); (2) new **EXILE_MILL** detector — targeted top-of-library exile with
  no play permission (4/4 measured: Ashiok, Circu, Scrib Nibblers, Mindreaver) → Mill
  defining; Circu reads his true Mill + Stax co-primary, the each-player forms rejected
  as theft/hug-dirty (Pako, Share the Spoils), Gonti/Etali unaffected; (3) broad-phrase
  audit: the enchantress "draw a card" landmine is inert (no archetype consumes it).
  Measured-rejected: Yennett free-cast (526, direction-less), Bruna attach (1-card
  forms), dorks-matter, Imodane's pinger phrase (mixed), untap-tempo, day-night.
  265 sentinels, sanity "266 passed"; suite 1087 green.
  (`analyzer/content.py`, `analyzer/analyze.py`, `analyzer/mapping.py`,
  `data/seed/card_tags.json`, `data/golden/golden_cards.json`,
  `logs/pre-build-fixround.json`)

### Added
- **Calibration batch #20 (blind-first): FAIL (CW 2, one predicted) — direction traps
  in my own week-old boundary, plus the tribal whitelist gap.** Rights: Elsha, Kalemne
  (Creature Spells Matter validating on the experience class), Imodane (Group Slug +
  Spellslinger both true). CW 1, PREDICTED blind: Otrimi's "return target creature card
  to your HAND" hit the batch-19 "creature card" combat exemption — now a compound
  (battlefield required; Gishath control green); the same card exposed the reanimation
  tag's NAKED "return target creature card" (284, ~139 non-battlefield) → replaced with
  battlefield-directional forms, killing his false Reanimator high (Sefris intact).
  CW 2, deferred honestly: Raggadragga's Spellslinger high comes from a 7-mana rider on
  "whenever you cast a spell," — the rider subclass measures EXACTLY 1 card, so per the
  Jetmir precedent it's pinned as the **conditional-rider awareness** known-gap, not
  patched. Coverage: whitelist +47 real creature types (Gallia's Satyrs and Reaper
  King's Scarecrows were invisible), 2 new tribal patterns ("other X creatures",
  "another X you control"), "for each aura attached" → aura_equipment_payoff (Uril
  Voltron high — the Bruna-class sibling), `attacks_alone` (exalted family, 95) as
  Voltron SUPPORTING with Noble Hierarch pinned as the no-lie guard, NEW archetype
  **Mutate** (39). Eleven sentinels → 263, sanity "264 passed"; suite 1085 green.
  (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`, `logs/calibration-batch-20.json`)

### Added
- **Calibration batch #19 (blind-first, niche-mechanics spectrum): FAIL (CW 3, one
  class) — the saboteur self-trigger family fixed, plus 5 niche archetypes.** Tally:
  right 3 (Sefris, Marisi, Grolnok), partial 2, empty 2 (both honest — Yennett proved
  the Zur rule works; Lynde's curses are a 2-card class, rejected), CW 3: Jorn, Keene
  and Yidris all read `Attack Triggers: high` from SELF-combat triggers with VALUE
  effects. Two sub-bugs in one class: the self-scope check missed the saboteur form
  ("<name> deals combat damage to a player" — Keene/Yidris), and the untap combat-feed
  exemption was directionless ("untap each snow permanent" is mana, not attackers —
  measured 101 creature-untaps vs 94 other). The golden net then caught Lathril/Gishath
  in seconds and drew the exact boundary: creature DEPLOYMENT in the effect feeds
  combat (Kaalia/Lathril/Gishath keep high); noncreature value is an engine event.
  Ragavan improved: true Theft+Treasures instead of a false attack band. Same round:
  NEW archetypes **Snow Matters** ("snow permanent" 24; snow-land/snow-creature forms
  rejected with measured FPs), **Gates Matter**, **Dungeons / Venture**, **Cascade**,
  **Goad / Forced Combat**; NEW tribal patterns for or-conjunction pairs ("a Wolf or
  Werewolf you control" — Tovolar) and tutor forms ("search your library for a Sliver
  card" — Sliver Overlord). Twelve sentinels incl. Godo (directional-untap control) and
  Ragavan (improvement pin) → 252 sentinels, sanity "253 passed"; suite 1074 green.
  (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`, `logs/calibration-batch-19.json`)

### Added
- **Coverage fix round post-#18: the #17/#18 known-gap backlog closed in one measured
  pass — 4 NEW archetypes, 2 defining extensions, 1 detector form.** NEW: *Enchantments
  Matter* (the missing parallel of Artifacts Matter — 6 measured phrases + recursion
  supporting; "enchantment spell" rejected with 8 counterspell FPs, Annul pinned as
  guard; the legacy `enchantress` tag avoided — it carries a naked "draw a card"
  landmine, annotated), *Energy* ("{e}" 146), *Forced Discard* (opponent-discard class,
  15+68+1 — distinct from self-discard/Wheels), *Clones / Copies* ("token that's a copy"
  352 + "as a copy of" 75; "copy target" rejected — Fork/Twincast is Spellslinger; Krark
  pinned as must_not guard for the excluded "copy that spell" form, so Volo stays
  honest-empty). Extensions: *THEFT_TOPDECK* detector form (same-line top-of-their-
  library + you-may-play/cast, 37 measured — Xanathar finally reads Theft beside his
  true Stax) and *Vehicles defining += vehicle_payoff* (Greasefang reads Vehicles high).
  Batch commanders now read their full plans: Anikthea Enchantments+Clones+GY triple,
  Satya Energy+Clones+Attack triple, Tinybones Forced Discard high. Controls: Sythis
  Enchantments high, all 238 prior pins green. Measurement bug caught live: regex
  `libraries?` never matches singular "library" (s-optional trap) — a 0-hit measure was
  debugged before anything shipped. 5 pins updated + 2 guard sentinels → 240 sentinels,
  sanity "241 passed"; suite 1062 green. Still open: exile-mill detector, Bruna
  aura-attach, untap-tempo, desert, Volo's copy-that-spell form.
  (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`, `logs/coverage-fixround-post-18.json`)

### Added
- **Calibration batch #18 (blind-first self-run): FAIL (CW 1) — the guard-alternation
  class discovered, plus two new archetypes.** Tally: right 4 (Guff, Lathliss, Satya,
  Karametra — the day-old Creature Spells Matter archetype validated on a virgin
  commander), partial 5, CW 1: **Phelddagrif read `Go Wide: high` from Hippos he GIFTS
  opponents** — "target opponent creates" was missing from `_OPPONENT_TOKEN_RE` (a new
  failure family: a scope guard existed but its alternation was incomplete; audit
  alternations when adding guard classes). Fix round, all measured: the guard gains
  "target opponent creates" (23, all gifts; "target player creates" rejected — Dark
  Salvation-class self-target), `group_hug` gains "target opponent may draw" (4/4 —
  Phelddagrif now reads Group Hug high), NEW archetype **Poison / Infect** (the poison
  tag — 182 "poison counter" cards — existed but was never mapped; Fynn empty→high, a
  pure mapping fix), NEW archetype **Party** ("in your party", 31 — Burakos Party +
  Treasures co-primary), `lifedrain` gains "defending player loses" (31, afflict class).
  Rejected measured-dirty: "target opponent gains" (24 gains-control FPs), exile-mill
  phrases (impulse-theft dominated — Tibalt would read Mill; needs a detector with
  play-permission exclusion, known-gap), desert-landfall (1-card class). Generalization
  positives: nontoken tribal→Lathliss, ephemeral guard→Satya, Zur rule→Burakos. Controls
  held: Krenko Go Wide high, Hunted Horror low. Process note: the blind-phase audit log
  was lost — pytest cleared `output/on-going-report.json`; run `mtg report` BEFORE the
  test suite. Eleven sentinels (238-card set, sanity "239 passed"); suite 1060 green.
  (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/calibration-batch-18.json`)

### Added
- **Calibration batch #17 (post-gate, blind-first self-run): PASS — right 4, partial 5,
  empty 1, CW 0.** First batch of the extended-testing plan (17 of 30). Rights: Syr Gwyn
  (Voltron via aura_equipment_payoff + board attack trigger), Zaffai (Spellslinger; Go
  Wide high accepted — the 4/4s are a plan-aligned win route, not a deterrent token),
  Vorel (Counters Matter via COUNTER_MARKER reading the DOUBLING manipulation — beat the
  blind prediction of empty), Chainer NA (Graveyard Value via graveyard_recast +
  Reanimator medium). Partials all honest: Xanathar (Stax high true, Theft unread —
  "play the top card of their library" has no phrase), Greasefang (Vehicle reanimation
  invisible: "return target VEHICLE card from your graveyard" matches neither
  reanimation's creature-phrasings nor VEHICLE), Derevi (Attack Triggers high defensible
  per the Toski board-scope precedent; untap-tempo engine has no archetype), Anikthea
  (GRAVEYARD_CLONE generalized from batch #16; Enchantments Matter archetype missing),
  Preston (directional lows; SAC_OUTLET genuine). Tinybones honest empty (opponent-
  discard payoff class unread; "each opponent WITH NO CARDS IN HAND loses" breaks the
  lifedrain substring). Per PASS protocol zero analyzer changes; 5 new known-gaps
  recorded in MIGRATION. Ten sentinels pinned improvement-friendly — one pin lesson:
  `expected_archetypes` must hold only bands the card reads TODAY (a gap goes in the
  note, not in expected; the Xanathar Theft pin failed the net and was corrected).
  227 sentinels, sanity "228 passed"; suite 1049 green.
  (`data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/calibration-batch-17.json`)

### Fixed
- **The Deglamer tuck class — deck-check learns the substring-undecidable removal form
  via a same-line conjunction.** "shuffles it into their library" is worded identically
  for targeted removal ("Choose target artifact or enchantment. Its owner shuffles it
  into their library" — Deglamer/Unravel the Aether/Blink/Riftsweeper) and for a card's
  own drawback ("At the beginning of the end step, its owner shuffles it into their
  library" — Lightning Shrieker); no substring can split them. New
  `_is_targeted_tuck_removal` conjunction in deck_check: "target" + "shuffles it into"
  on the SAME oracle line → removal (measured: 13/13 genuine removal with, 8/8
  self-shuffle without). Design decision recorded (CHECK-LIST): the general "uncertain
  bucket" pattern — (1) if a rule can decide, write the rule; (2) if it can't, flag the
  match uncertain (low Confidence + machine-readable list in deck-check) for the agent
  to verify manually, gated on decision-relevance so it costs ~zero tokens; (3) never
  count doubt as certainty — is agreed but deliberately NOT built until the first truly
  undecidable class appears. 7 regression tests; suite 1039 green.
  (`deckbuilder/deck_check.py`, `tests/test_deck_check_removal.py`)

### Fixed
- **Known-gaps session 2: the ENTIRE remaining batch backlog closed — 12 gap classes
  fixed, 5 new archetypes, all measured-first.** (1) *morph_facedown FP:* the naked
  "face down" tag (517 matches: 305 morphish, 145 exile-face-down, 67 hidden-info)
  rebuilt with directional forms (turn-face-up + keyword-cost forms + "face-down
  creature"; union 189, only 4 clone-name FPs excluded) — Gonti/Kotose no longer read
  Morph, Kadena/Ixidor keep high. (2) *theft "exiled with" (191 dirty) removed;*
  THEFT_EXILE v2 adds the card-level multi-line conjunction (opponent-zone exile line +
  "exiled with" play line; 12 measured, all genuine) — Nightveil/Jeleva/Kheru keep Theft,
  Colfenor's Plans false-high dead. (3) *Creature Spells Matter* (new archetype,
  `creature_cast_payoff`: 72+28+4 measured) — Animar/Chulane empty→high, Thalia taxers
  excluded. (4) *X Spells Matter* (new archetype, `x_spell_payoff`: cast/cost anchors
  exclude Gaddock Teeg-class hate) — Zaxara/Rosheen high. (5) *Counter-body guard:* a 0/0
  token receiving +1/+1 counters in the same clause is a real body (30 measured, Fractal
  cycle), not UTILITY_TOKEN_MAKER fodder — Zaxara's false Aristocrats dead, Atla's Eggs
  (184 true fodder) intact. (6) *`discard_payoff`* ("whenever you discard", 48) defining
  Wheels — closes Rielle (batch #15) AND Anje madness (batch #16) with one phrase.
  (7) *Amass / Army* (new archetype, "amass" 60 + "army you control" 52) — Sauron.
  (8) *Pingers / Damage Matters* (new archetype, `pinger_payoff` union 19; deliberately
  NOT the broad `damage_payoff` tag whose combat phrase is saboteur territory) —
  Ghyrson/Taii Wakeen empty→high. (9) *`draw_trigger_payoff`* (48+51) defining Wheels —
  Locust God co-primary, Sheoldred high. (10) *dethrone* (keyword, 10) Counters
  SUPPORTING — Marchesa BR low→medium, honestly not defining. (11) *"creature token
  dies"* (2, zero FP) in death_trigger — Grismold Aristocrats+Go Wide co-primary.
  (12) *deck-check Bolt/Chaos Warp vocab:* `removal`/`creature_removal` gain "damage to
  any target" (733) / "damage to target creature" (530) / "owner of target" (22 tuck) —
  Bolt and Chaos Warp finally count as removal, Healing Salve still doesn't. Process
  catch: a duplicate `damage_payoff` JSON key (would have silently shadowed the original
  tag — last-key-wins) caught by an Edit-tool uniqueness error and renamed
  `pinger_payoff`. NEW annotated (not fixed): the stax tag matches SELF-restrictions
  ("You can't cast more than one spell" — Colfenor's Plans reads a false Stax high; the
  batch-3 scope check exists only in the signal layer), and the Deglamer tuck class is
  substring-undecidable (self-shuffle vs targeted shuffle share identical wording).
  Golden: 9 pins tightened + 7 new sentinels → 217 sentinels, sanity "218 passed";
  suite 1032 green. Remaining detection gap from the batch backlog: ONLY the clone/copy
  value archetype (Volo honest empty). (`analyzer/content.py`, `analyzer/mapping.py`,
  `data/seed/card_tags.json`, `data/golden/golden_cards.json`,
  `docs/MIGRATION-archetypes.md`)

### Fixed
- **Known-gaps session: the annotated backlog worked — one CW regression killed, three
  detector classes added, two stale annotations reconciled, one data-drift regression
  caught.** Live verification first: the batch-11 known-gaps (Tymna/Xenagos/Kozilek/
  Jhoira/Ikra) and Galea were ALREADY closed by later fix rounds — annotations were stale.
  The real work: (1) *Volo CW regression (batch-16 fallout):* GRAVEYARD_CLONE matched
  Volo's reminder text ("(A copy of a creature spell becomes a token.)") beside a NEGATIVE
  graveyard condition → false `Graveyard Value: high`. Reminder text now stripped (the
  batch-14 lesson at a second site) with two measured compensations: embalm/eternalize
  keywords + the directional "from ... graveyard ... copy it" recast form (112 cards, 7
  reminder FPs out, 20 genuine recasters in — Kaervek/Nashi/Shiko/Mizzix's Mastery class).
  (2) *Sygg class:* new LOST_LIFE_PAYOFF detector — threshold "lost (N or more) life this
  turn" payoffs are a variable-number class the vocabulary cannot enumerate (40 measured:
  spectacle cycle, Bloodchief Ascension; self-loss excluded) → defining Life Loss. Sygg
  empty→high; Vito low→medium via lifedrain +"target opponent loses" (104 measured).
  (3) *Old Stickfingers class:* new GRAVEYARD_SCALING detector ("equal to the number of
  ... in your graveyard", 46 measured — the Lhurgoyf class) + self_mill reveal-forms
  ("rest into your graveyard", 76 measured). Empty→medium. (4) *Elder Brain class:* new
  THEFT_EXILE conjunction — same-line exile + opponent-zone + "you may play/cast",
  order-free, reminder-stripped, "you own"-excluded (97 measured, all you-play-theirs).
  Also caught a DATA-DRIFT regression: fresh Scryfall wording had silently cost Gonti,
  Lord of Luxury his Theft read (the measured "don't own" phrase no longer exists on the
  card) — THEFT_EXILE restores it. (5) Surrak documented honest-empty (Jetmir precedent).
  NEW findings annotated (not fixed): morph_facedown FPs on exile-face-down (Gonti reads
  a false Morph high), theft's "exiled with" phrase measured dirty (191 cards, needs a
  directional rebuild that preserves the multi-line Nightveil class). Golden set: +6
  sentinels and 5 historical duplicate-name entries consolidated → 210 unique sentinels,
  sanity "211 passed"; suite 1025 green. (`analyzer/content.py`, `analyzer/analyze.py`,
  `analyzer/mapping.py`, `data/seed/card_tags.json`, `data/golden/golden_cards.json`,
  `docs/MIGRATION-archetypes.md`)

### Fixed
- **Both M5 frictions fixed root-cause, plus the Budget Contract gains a utilization
  floor.** (1) *Ability-word trigger class (968 cards measured):* `extract_trigger_events`
  required the clause to START with a trigger word, so "Alliance — Whenever ..." /
  "Landfall — Whenever ..." / every ability-word-prefixed trigger (Magecraft, Coven, Raid,
  Constellation...) was invisible to trigger families. A lookahead-guarded prefix strip
  (only fires when a real trigger condition follows the em dash) fixes the whole class at
  the single source both consumers share — Galadriel now reads `permanent_enters` + ETB
  Value/Blink bands; Izoni and Professor Onyx controls read their events; Galadriel pinned
  as sentinel (209-card set). (2) *Token-shadow class (data):* Scryfall token printings
  lived in the DB as cards — 4,020 nonplayable rows (token, double_faced_token, emblem,
  art_series, vanguard, scheme, planar), 88 of them SHADOWING a real card's name in
  exact-name lookups; the eternalize token of Timeless Witness answered for the real card
  with `commander_legal=False`. New `NONPLAYABLE_LAYOUTS` filter at ingest
  (build_sqlite skips them) + existing DB repaired via DELETE (38,304 → 34,284 rows);
  Timeless Witness now resolves uniquely and legal. (3) *Budget Contract:* the budget is
  also a POWER signal — new utilization floor (~60%): landing more than 40% under budget
  makes the Budget Upgrade Review REQUIRED before finalizing (BUILDER §11, both the
  principles block and the review trigger). 5 regression tests; suite 1024 green.
  (`deckbuilder/oracle_hooks.py`, `data/normalize_cards.py`, `data/build_sqlite.py`,
  `BUILDER.md`, `data/golden/golden_cards.json`, `tests/test_m5_fixes.py`)

### Added
- **M5 validation build: Galadriel, Light of Valinor (virgin commander, post-migration
  pipeline) — READY at $77.33/$130, zero gaps, exactly 2 new frictions (meets the ≤2
  bar).** Full BUILDER.md flow: analyze → category-counts → function shortlists →
  verify-early (63/63) → budget trim via deck-swap (Bristly Bill flagged at 31.5% of
  budget by `--by-card`) → deck-write/fill/validate → deck-check → deck-gaps → preflight
  READY → final-build. The M2 plan check earned its keep in production: `plan_gaps: []`
  on a deliberately on-plan deck. validate caught a real draft error (Timeless Witness,
  black) — and exposed friction #2: **`commander_legal=False` in the DB for Timeless
  Witness, which IS Commander-legal (data bug)**. Friction #1 (detection class): the
  Alliance layout "Whenever another creature you control enters, choose one — •…" fires
  NO `permanent_enters` trigger family (oracle_hooks.trigger_events empty, no ETB Value
  band) — the modal-trigger layout is invisible to trigger families; the analyzer still
  read Counters Matter high from mode 2. deck-swap resolved a DFC by front face (Bala Ged
  Recovery) mid-fix. Audit: `logs/testbuild-galadriel-m5.json` (26 commands, 0 failures).
  (`final-builds/Galadriel-Light-of-Valinor-Alliance-Counters-T3-v1/`)

### Changed
- **Agent files synced to the current tool (pre-M5 pass).** Audit of BUILDER.md, BUFF.md
  and agents/*.md against everything shipped this cycle found the M2/M3 features
  undocumented for agents; fixed surgically, preserving intentional redundancy:
  (1) deck-gaps' **Commander plan check** (`analyzer_support`/`plan_gaps` + fill commands)
  documented in BUILDER §8, agents/deck_builder.md ("fix it or consciously justify it"),
  agents/deck_fixer.md (re-audit closes plan gaps too) and BUFF.md (plan_gaps = the
  strongest lead); (2) the "(analyzer high)" entries in `wanted_card_patterns` documented
  in agents/commander_analyzer.md — run those ready commands FIRST, they are the detected
  plan; (3) `suggest --synergy` enrichment noted in agents/deck_builder.md; (4) NEW
  **JSON error contract** section in agents/system.md — the five error types
  (usage/cli/validation/environment/internal), check-"error"-before-"results", non-zero
  exits, and fuzzy not-found suggestions ("Krenkooo" → Krenko) — the defensive-parsing
  lesson made durable for every future agent; (5) commander_analyzer.md's top-level path
  list now marks the deprecated fields and adds `legacy_deprecations` + `analyzer.tags`.
  Suite 1018 green (docs-only). (`BUILDER.md`, `BUFF.md`, `agents/system.md`,
  `agents/deck_builder.md`, `agents/deck_fixer.md`, `agents/commander_analyzer.md`)

### Changed
- **M3: legacy archetype fields formally deprecated (delete lands in v0.10).**
  `commander_analysis.json` gains a machine-readable `legacy_deprecations` block naming
  `archetype_fit`, `commander_tags` and `synergy_tags` as deprecated with their
  replacements (`analyzer.archetype_support`, `analyzer.tags` + `analyzer.signals`) and
  the planned removal (v0.10); the fields themselves REMAIN so no consumer breaks before
  then. The analyzer embed now exposes `tags` (tag names only; traces via
  `mtg analyze-card`) — the single-source replacement for the two legacy tag lists. All
  four agent files updated in place (BUILDER.md §7.0b, agents/commander_analyzer.md,
  agents/system.md rule 11, CLAUDE.md hard rules), preserving their intentional
  redundancy. 2 regression tests (block present + fields still present + embed tags);
  suite 1018 green. (`deckbuilder/commander_analyzer.py`, `BUILDER.md`,
  `agents/commander_analyzer.md`, `agents/system.md`, `CLAUDE.md`,
  `tests/test_m3_deprecation.py`)

### Changed
- **M2 consumer #3 migrated: `suggest --synergy` and `wanted_card_patterns` consume the
  analyzer — Fase 2 consumer migration COMPLETE.** (a) `wanted_card_patterns` now appends
  one pattern per high/very_high analyzer band with a ready search command ("Go Wide
  (analyzer high): mtg search-tags go_wide_payoff token_maker anthem"), reusing the
  profile already computed for scoring (M2 #1) — no extra analyzer run. (b)
  `extract_commander_synergy_signals` enriches its signal set with the measured
  card_tags phrases of each high band's rule tokens via a new `_analyzer_synergy_phrases`
  helper — in BOTH paths (analysis-file and the no-analysis heuristic fallback, where the
  analyzer runs directly on the card; pure logic, no DB). All three consumers now share
  ONE plan vocabulary (`mapping._ARCHETYPE_RULES` ∩ card_tags) — the multi-consumer-drift
  root cause is structurally closed for archetype context. Additive and guarded
  throughout: analyzer failure leaves legacy behavior intact. Certero note: M2 did not
  touch `archetype_support` itself; the 208-sentinel golden net (green) carries the
  regression evidence, and an exact certero re-measure needs the 110-commander judgment
  dataset, which is not in the repo. 5 regression tests; suite 1016 green.
  (`deckbuilder/commander_analyzer.py`, `deckbuilder/suggestion_scorer.py`,
  `tests/test_m2_synergy_analyzer.py`)

### Changed
- **M2 consumer #2 migrated: `deck-gaps` audits the deck against the analyzer's read of
  the commander.** New "Commander plan check" section: for every high/very_high band in
  `analyzer.archetype_support`, deck-gaps counts the deck cards that serve that plan and
  reports a `plan_gap` (with a ready `search-tags` fill command) when fewer than 5 do.
  The plan→function map is the analyzer's OWN vocabulary — `mapping._ARCHETYPE_RULES`
  defining+supporting tokens that are card_tags names — so it can never drift out of sync
  with the archetype system (the recurring multi-consumer root cause this project keeps
  fixing); tribal bands count by creature type in the type line. JSON output gains
  `analyzer_support` and `plan_gaps`; guarded so an analyzer failure only drops the new
  section. Verified live: an off-plan Krenko deck reports `Go Wide: high but only 0 deck
  cards serve it` with `fill: mtg search-tags go_wide_payoff token_maker anthem --colors
  R`. 2 DB-backed regression tests (off-plan reports, on-plan stays quiet); suite 1011
  green. (`cli/commands/deck.py`, `tests/test_m2_deck_gaps_analyzer.py`)

### Changed
- **M2 consumer #1 migrated: `_score_provides` now consumes analyzer signals, oracle
  heuristics as per-branch fallback (Fase 2, gate opened by batch #15).**
  `score_commander` gains an optional `signals` param; `analyze_commander` computes the
  universal analyzer profile BEFORE scoring (guarded — analyzer failure leaves signals
  None and behavior exactly legacy) and reuses it for the `analyzer` embed, so the
  analyzer runs once per card; category-counts' no-analysis fallback path passes signals
  via a guarded helper. Semantics: a present signal REPLACES its oracle twin (same score,
  no double counting — TUTOR_UNCONDITIONAL 3.0 / TUTOR_CONDITIONAL 1.5 / MANA_ABILITY
  2.5); an absent signal falls back to the oracle substring, preserving coverage the
  narrow regexes lack ("search your library for TWO basic lands" still scores). Measured
  improvement shipped: the Esika class — "{T}: Add one mana of any color" matches neither
  "add {" nor "add mana", so legacy scored 0 ramp; MANA_ABILITY sees it (Esika and Zaxara
  now report `built_in_ramp: 2.5`). Spot-check over 10 diverse commanders: 8 identical,
  2 strictly better, 0 worse. Removal/protection/wipes/draw branches stay pure oracle
  heuristics until the analyzer covers them. 7 regression tests; suite 1009 green.
  (`category_counts/scoring.py`, `category_counts/calculator.py`,
  `deckbuilder/commander_analyzer.py`, `tests/test_m2_provides_migration.py`)

### Added
- **Calibration batch #16 (post-gate; Chishiro by user request): one CW — the first
  promotion-regression — and four class fixes.** Chishiro read right in batch #2, but the
  later `aura_equipment_payoff`→defining-Voltron promotion (measured on the Sram/Galea class,
  whose payoffs are personal) made him read `Voltron: very_high` — his payoff scopes "EACH
  modified creature you control": the deck goes wide, not tall. Fix: **wide-vs-tall
  exclusion** in the mapper — when evidence carries both REPEATABLE_TOKEN_MAKER and broad
  COUNTER_MARKER, aura_equipment_payoff demotes to Voltron supporting (measured over all 24
  commanders with the tag: only the Chishiro class has both; Sram/Galea/Wyleth/Kemba/Stangg
  keep their reads). Coverage: `attacks_or_combat` gains the player-scope "you attack" form
  (156 cards — Raffine now Attack Triggers high); tribal patterns skip an optional
  "nontoken" qualifier (Miirym reads Dragon Tribal high; the "non-" negation guard is
  unaffected because the qualifier is skipped, not captured); and a new **GRAVEYARD_CLONE
  conjunction detector** (same-line graveyard + copy — a class substring vocab cannot
  express safely; 90 cards measured, all genuine: Lazav family, Scarab God, Feldon, the
  embalm/eternalize cycle) defines Graveyard Value — closing the batch-14 Mimeoplasm
  known-gap. Positives from the batch: Food correctly reads value-engine (Gyome), the
  ephemeral-token guard held on Feldon's sac-at-end-step copies, Ojer Axonil's replacement
  effect wasn't misread as a trigger. Ten sentinels (208-card set, sanity "209 passed");
  suite 1002 green. (`analyzer/mapping.py`, `analyzer/content.py`, `analyzer/analyze.py`,
  `deckbuilder/oracle_hooks.py`, `data/golden/golden_cards.json`,
  `docs/MIGRATION-archetypes.md`, `logs/calibration-batch-16.json`,
  `logs/calibration-batch-16-fixround.json`)

### Added
- **Gate-validation batch #15 (confirmation batch, blind-first self-run): PASS — the Fase 2
  gate is OPEN.** Tally: right 5 (Yawgmoth, Kwain, Syr Konrad — whose Mill + Group Slug +
  Aristocrats triple-high is all true, Emiel, Multani), partial 4 (Zaxara, Grismold, Rielle,
  Vito — honest underbands, zero lies), empty 1 (Animar, honest), wrong 0, **CW 0**:
  right+partial 9/10 ≥ 6 AND CW=0. The batch also confirmed the #13/#14 fix classes
  generalize on fresh commanders (Emiel's activated flicker reads Blink high via the batch-13
  vocab; Animar's self-counters correctly never band Counters Matter). Per the PASS protocol
  no analyzer changes were made: findings recorded as known-gaps (cast-creature engine class,
  X-spell payoff class, 0/0-with-counters tokens read as fodder, wheel/lifedrain vocab
  phrasings). Ten sentinels pinned with improvement-friendly band lists (198-card set, sanity
  "199 passed"); suite 992 green. Gate criteria: (1) golden set ✓ (2) product bar ✓
  (3) coverage ✓ (4) goodstuff case ✓ (c) fresh confirmation batch ✓ — **M1 closed, M2
  (consumer migration, starting with `_score_provides`) is unblocked.**
  (`data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/gate-validation-batch-15.json`)

### Added
- **Gate-validation batch #14 (confirmation batch, blind-first self-run): FAIL (right 5,
  partial 1, empty 3, CW 1) — three class fixes.** The CW: Queen Marchesa read `Go Wide:
  high` from her conditional upkeep Assassin — a token whose creation is CONDITIONED on an
  opponent state ("if an opponent is the monarch") is a deterrent/catch-up effect, not an
  army (measured: 15 cards, all parity effects — Beza, Linvala, Sunset Revelry class). New
  guard in `REPEATABLE_TOKEN_MAKER`; Brimaz (attacking Cats) unaffected. Her missing truth:
  new `MONARCH` detector ("becomes? the monarch", ~60 cards / 13 commanders measured, all
  monarch-politics builds) → defining `Group Hug / Politics` — Queen Marchesa and Palace
  Jailer now read Politics high. Reminder-text class: Ghyrson's ward reminder ("counter it
  unless that player pays {2}") fed COUNTERSPELL_INTERACTION → a false Spellslinger band;
  the counterspell branch now matches rules text only (parens stripped THERE only — the
  counter-marker branch keeps reminder text, dethrone's counters read is real; Talrand
  control intact). Positive generalization from batch #13 confirmed on fresh commanders:
  Tivit (Treasures ≠ Go Wide), Brimaz (real token army IS Go Wide), Gisela (replacement not
  read as trigger). Known-gaps annotated: Chulane cast-creature engine, Mimeoplasm
  graveyard-clone, Ghyrson exactly-N-damage pingers, Marchesa BR counters underband. Nine
  sentinels (188-card set, sanity "189 passed"); suite 982 green. Batch consumed →
  confirmation batch #15 required. (`analyzer/content.py`, `analyzer/semantics.py`,
  `analyzer/mapping.py`, `data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`,
  `logs/gate-validation-batch-14.json`, `logs/gate-batch-14-fixround.json`)

### Added
- **Gate-validation batch #13 (confirmation batch, blind-first self-run): FAIL (right 6,
  partial 2, empty 1, CW 1) — four class fixes + one honest rejection.** The CW: Lord
  Windgrace read `Go Wide: high` because `REPEATABLE_TOKEN_MAKER`'s activated-ability regex
  accepted ANY loyalty line — his −11 ultimate's six Cats read as an engine. The loyalty
  split: only +N:/0: activations are repeat markers (fire every turn); a minus ability
  consumes loyalty, so its token creation is a finisher (measured: 53 plus/0 engines keep
  firing — Archangel Elspeth control; 81 minus ultimates stop). Coverage: `land_recursion`
  gains the "land card(s) from your graveyard to the battlefield" forms (Windgrace finally
  reads Lands; "to your hand"/"discard a land card" forms measured dirty, rejected) and
  `blink` gains the activated delayed-flicker phrasing (22/22 pure — Roon/Flickerwisp/
  Mistmeadow class; the "return it..." death-recursion and "return the exiled card" O-Ring
  forms measured dirty, rejected). Mapping: the tax detector now splits per line —
  TAX_COST_INCREASE (general tax, PROMOTED to defining Stax: GAAIV and Thalia read
  `Stax: high`) vs new TARGETED_TAX (targeting-conditional tax = protection, never Stax —
  kills the would-be Erebos-class CWs on Kopala/Charix/Esior/Hinata; measured 5 general vs
  6 targeting taxers). Direction: `sacrifice_outlet` rebuilt with directional forms
  (colon-cost / you-may / additional-cost, all measured clean) — the naked "sacrifice a
  creature" caught opponent edicts ("unless THEY sacrifice" — Mogis read a false
  Aristocrats). Honest rejection: Jetmir's threshold anthems measure 3 cards and every
  generalization is dirty (anthem→defining would flip 92 commanders, Mikaeus CW again) —
  documented as known-gap, no archetype forced. Positive generalization confirmed: Wyleth
  (`Voltron: very_high` via aura_equipment_payoff) and Esika (DFC split + Legendary Matters)
  read right untouched. Thirteen sentinels (179-card set, sanity "180 passed"); suite 973
  green. Batch consumed → confirmation batch #14 required. (`analyzer/content.py`,
  `analyzer/mapping.py`, `data/seed/card_tags.json`, `data/golden/golden_cards.json`,
  `docs/MIGRATION-archetypes.md`, `logs/gate-validation-batch-13.json`,
  `logs/gate-batch-13-fixround.json`)

### Fixed
- **The global "Database not found" pre-check now respects `--json-output` (last F2-class
  hole).** Every command's DB pre-check printed rich plain text under `--json-output`,
  breaking agent parsers — annotated as a ~30-site global class in the search-family fix, and
  measured at exactly 20 broken sites (deck 6, search 5, cards 7, analysis 2; `status` in
  data.py was already JSON-aware). All 20 now call a shared `require_database(SQLITE_PATH,
  json_output)` helper (`cli/_shared.py`) that emits `{"error": {"type": "environment",
  "message": ...}}` and exits 1; human-mode output unchanged. The helper takes the caller's
  `SQLITE_PATH` as an argument so the suite's per-module monkeypatching keeps working. New
  error type `environment` joins `validation`/`usage`/`cli`/`internal` (a missing DB is not
  an input error). 6 regression tests (one command per module + human mode). Suite: 960 green.
  (`cli/_shared.py`, `cli/commands/{deck,search,cards,analysis}.py`,
  `tests/test_db_missing_json.py`)

Quality, agent-ergonomics, and analysis-generality pass driven by full end-to-end builds (Krenko, Mob Boss; Gargos, Vicious Watcher) and friction notes from agent runs.

### Fixed
- **`card` not-found suggestions are now fuzzy.** The suggester was pure substring LIKE, so an
  in-word typo suggested NOTHING (`mtg card "Krenkooo"` → empty suggestions). New
  `CardRepository.suggest_similar_names()`: substring first (cheap, unchanged behavior), then a
  difflib fallback over all card names (cutoff 0.6, measured against the real DB: "Krenkooo" →
  Krenko, Mob Boss; "Sol Rign" → Sol Ring; "Lightning Blot" → Lightning Bolt; ~0.15s, error-path
  only). All 7 not-found suggestion sites switched (card, cards-batch --verify, similar,
  complements, deck-swap, analyze-card). (`cards/repository.py`, `cli/commands/*.py`)
- **The search family's LOCAL validation errors now respect `--json-output`.** Three validation
  paths (search with no query/filters, search-tags with no tags, `suggest --role synergy`)
  printed plain rich text under `--json-output`, breaking agent parsers — the same F2b class the
  boundary fixed for usage errors, but these never reached the boundary. They now emit
  `{"error": {"type": "validation", ...}}` like the `--type` error path. Note: the
  "Database not found" pre-check shares this class across ALL commands — annotated for a future
  pass, not fixed here. (`cli/commands/search.py`, `tests/test_type_filter.py`)
- **Functional test sweep of all 34 commands (post-split) found and fixed two exit-path bugs.**
  (1) *Split regression:* the search family's `--type` validation error calls `_emit_json_error`
  inside the command; after the split the helper stayed in `cli/__init__.py` so the call raised
  `NameError` — masked as a `{"type": "internal"}` JSON by the crash boundary, which is why the
  generic boundary test (only checks for an `"error"` key) kept passing. The helper now lives in
  `cli/_shared.py` (imported by both the package and `commands/search.py`), and three regression
  tests pin the REAL contract: `{"type": "validation"}` with the `--subtype` suggestion, never a
  NameError. (2) *Pre-existing:* with `--json-output`, EVERY `raise typer.Exit(1)` exited 0 —
  click with `standalone_mode=False` swallows `Exit` and RETURNS the exit code
  (`click.core.Command.main`), and `_run_app` ignored the return value, breaking the documented
  non-zero-exit contract (card not-found, `cards-batch --verify`). `_run_app` now propagates a
  non-zero returned code; regression test runs the real `mtg` binary via subprocess. Also added
  `Any`/`Dict` to the shared typing imports (used in local-variable annotations in the deck
  commands — never evaluated at runtime, so the monolith never crashed, but they were undefined
  names). Suite: 950 green. (`cli/_shared.py`, `cli/__init__.py`, `cli/commands/search.py`,
  `tests/test_type_filter.py`, `tests/test_v7_fixes.py`)

### Changed
- **`cli.py` (the 2,420-LOC god-module) split into a `mtgcli/cli/` package — zero behavior
  change.** The former single module is now a package: `cli/_app.py` holds the one central
  `typer.Typer` app; `cli/_shared.py` carries the exact former module-level import surface plus
  the `print_json` / `has_power_toughness` / `_apply_max_price` helpers; the 34 commands moved
  verbatim into six functional modules under `cli/commands/` (`data`, `search`, `cards`, `deck`,
  `analysis`, `misc`); and `cli/__init__.py` re-exports the public surface (`app`, `main`,
  `has_power_toughness`, `print_json`), imports the command modules to register them, and keeps
  the `main` / `_run_app` / `_emit_json_error` entry point + `--json-output` JSON error boundary
  byte-for-byte. A new `cli/__main__.py` preserves `python -m mtgcli.cli`. Command **bodies were
  extracted by exact line range** (verified to tile the source with no gap or overlap, so every
  line is preserved once), so no command, flag, help text, or output changed. Because Typer lists
  commands in registration order, `__init__` re-sorts `app.registered_commands` to the original
  sequence so `mtg --help` is identical. The four test files that patched moved symbols
  (`SQLITE_PATH` / `CardRepository` / `build_explore_url` / `fetch_commander_page`) were retargeted
  from `mtgcli.cli.*` to the owning command module. New `tests/test_cli_smoke.py` gives the CLI its
  first direct tests: every command answers `--help` with exit 0, the exact 34-command set and its
  order are pinned, and `python -m mtgcli.cli --help` works. (`src/mtgcli/cli/`,
  `tests/test_cli_smoke.py`, `tests/test_card_lookup.py`, `tests/test_v7_fixes.py`,
  `tests/test_search_multi.py`, `tests/test_explore.py`)

### Fixed
- **Punisher detection no longer fires on targeted fight/removal (general).** `oracle_hooks`
  flagged any commander whose text contained "you don't control" as an `asymmetric_punisher`,
  which mislabeled fight/removal commanders (e.g. Gargos — "fights up to one target creature you
  don't control") and steered them toward attrition instead of their real plan. Detection now
  requires a *mass or opponent-scoped* effect ("each opponent", "creatures you don't control",
  "each creature you don't control"), so a single targeted fight/removal is correctly NOT a
  punisher, while a mass board effect (Toxrill) still is. Works for any commander. (`deckbuilder/oracle_hooks.py`)
- **`deck-fill-lands` no longer demands `--force` for an in-place fill.** Filling basics into the
  same deck file you passed is the intended operation, but the command refused with "Output already
  exists" unless `--force` was given. It now only guards against overwriting a *different* existing
  file; an in-place fill just works. (`cli.py`)

- **`deck-check` ramp count was massively inflated.** Lands fell through into core-category
  matching, so basic lands matched the mana_rock phrase `"{T}: Add"` and were counted as ramp
  (a real deck reported `ramp: 44`). A land now counts as ramp only when it matches a
  land-specific ramp tag (`land_ramp` / `extra_land_drop` / `land_recursion`) — true ramp-lands
  like Myriad Landscape still count, basics no longer do. This mirrors the existing guard in
  `suggestion_scorer`, fixing an inconsistency where the two consumers of the same tags treated
  lands differently. The broad `"{T}: Add"` phrase is intentionally kept (it catches Sol Ring,
  signets, Mind Stone, etc.); the type-awareness lives at the consumption site, not the tag.
  (`deckbuilder/deck_check.py`)
- **Double-faced / split cards were unfindable by their front name.** `get_card_by_exact_name`
  now falls back to a front-face match (`"Front // Back"`), so `mtg card "Valakut Awakening"`
  resolves `"Valakut Awakening // Valakut Stoneforge"`. (`cards/repository.py`)
- **`mtg card --json-output` broke agent pipes on a not-found card** by printing rich text
  instead of JSON. It now emits `{"name", "found": false, "suggestions": [...]}` and exits 1
  while keeping the human-readable output unchanged when `--json-output` is not set. (`cli.py`)
- **`search-tags ramp` leaked lands (incl. all five basics) into the candidate pool.**
  `search_by_tags` matched mana-production phrases in raw SQL with no land guard, so a
  ramp/mana_rock tag search returned ~half lands. It now drops lands that only matched via
  mana-production tags, while leaving land-oriented searches (`land_ramp`, `landfall`)
  untouched. Real ramp-lands (Fabled Passage, Myriad Landscape, …) still pass.
  (`cards/search.py`)
- **`deck-check` could not see green fight/bite removal.** The `removal` role only matched
  destroy/exile-target wording, so fight spells ("…fights target creature") and bite spells
  ("…deals damage equal to its power to target creature") counted as zero. A fight-heavy green
  deck reported `removal: 3` with a false "low removal" warning when it actually ran ~10. Added
  `fights` and `deals damage equal to its power to target` to the `creature_removal` tag.
  (`data/seed/card_tags.json`)
- **`deck-check` false-positive board wipes.** The `board_wipe` tag matched the bare phrases
  `each creature` and `all creatures`, flagging beneficial effects ("draw a card for each
  creature you control", "all creatures able to block … do so") as wraths. Tightened to real
  mass-removal wording (`destroy all`, `exile all`, `all creatures get -`, `damage to each
  creature`, `each creature gets -`, `all nonland permanents`). (`data/seed/card_tags.json`)
- **Moxfield export dropped the commander.** `export` wrote only the 99 mainboard cards even
  though the deck JSON carried the commander, so the import had no command zone. It now emits a
  `Commander` section (plus a `Deck` section) that Moxfield recognizes; no-commander exports are
  unchanged. (`export/moxfield.py`, `cli.py`)
- **Archetype fit ignored creature size, mis-scoring beatdown commanders.** Fit was pure oracle
  keyword matching, so a big creature commander (e.g. an 8/7 Hydra) scored 2.5/10 for `stompy`
  and triggered a false "low fit / forced-archetype" warning. `score_archetype_fit` now takes
  optional power/toughness and gives beatdown archetypes (`stompy`, `go_tall_aggro`, `voltron`,
  `battlecruiser`) a size bump; both callers pass P/T. Omitting P/T is unchanged, so the keyword
  cases and their tests are stable. (`category_counts/scoring.py`, `category_counts/calculator.py`,
  `deckbuilder/commander_analyzer.py`)
- **`commander-analyze` returned empty `archetype_fit` / `build_direction_options`.** When no
  archetype cleared the confidence threshold the fields came back empty (no directions for a
  "detailed" build). `_compute_archetype_fit` now falls back to the top-scoring archetypes flagged
  `low_confidence` so the agent always gets directional options. (`deckbuilder/commander_analyzer.py`)

### Changed
- **Single source of truth for land/ramp rules (`deckbuilder/ramp_rules.py`).** The rule
  "a land counts as ramp only when it actually ramps" was duplicated/diverging across three
  consumers — `suggestion_scorer` had it, `deck_check` lacked it (the `ramp: 44` bug), and
  `search_by_tags` lacked it (the land-leak above). All three now import the same
  `RAMP_LAND_ALLOWED_TAGS` / `MANA_RAMP_TAGS` / `land_matches_allowed_ramp_tags` definitions,
  so they can no longer drift apart.

### Added
- **Roadmap M4 executed + M2-prep detectors.** M4a: `deck-write --commander` now implies
  `--structured` (the unstructured default silently produced an illegal deck shape — the Gargos
  trap). M4b: BUILDER.md marks cards-batch verify-early as a MANDATORY step. M4c: `suggest` sorts
  ties by real EDHREC popularity (edhrec_rank added to its output fields; Birds of Paradise #33
  tops Gargos ramp suggestions). M4d: analysis JSONs are stamped with `tool_version` and the
  category-counts loader warns when the file predates the installed version (the F10 stale-cache
  trap). M4e: dead `safe_float` removed. M2-prep: new `detect_provides` analyzer detectors emit
  TUTOR_UNCONDITIONAL / TUTOR_CONDITIONAL / MANA_ABILITY — the signals `_score_provides` will
  consume when it migrates (the golden net caught a bad enum value in the first draft within
  seconds: four tutor commanders crashed, fixed to Confidence.LIKELY). (`cli.py`, `BUILDER.md`,
  `analyzer/content.py`, `analyzer/analyze.py`, `deckbuilder/commander_analyzer.py`,
  `category_counts/calculator.py`, `utils/json_io.py`)

### Added
- **Static code audit of `src/mtgcli/` appended to the roadmap (§3b).** Findings: cli.py is a
  2,420-LOC god-module (24% of codebase, no direct unit tests — M4: split into cli/commands/* with
  smoke tests); the legacy chain is exactly four files (category_counts/{calculator,scoring,
  output} + commander_analyzer) and NO downstream consumer reads the analyzer yet — Fase 2 has a
  precise file-level work list; scoring.py duplicates analyzer phrase detection AND owns
  tutors/ramp heuristics the analyzer lacks (port-first requirement for M2); dead code near-zero
  (one candidate: json_io.safe_float). (`docs/ROADMAP-v0.9.md`)

### Added
- **`docs/ROADMAP-v0.9.md`: retrospective of the Gargos BUILDER build + consolidation decisions +
  six milestones (M1 gate close -> M2/M3 Fase 2 migration & legacy deprecation -> M4 flow polish
  -> M5 validation -> M6 v0.9.0).** Consolidated: the §5 question flow, verify-early as mandatory,
  the closing triad, the Budget Contract, --log/report, defensive JSON parsing, edhrec ranking,
  and the golden-net playbook. Scheduled for deprecation: legacy archetype_fit (post-gate),
  _score_provides oracle heuristics (analyzer fallback only), deck-write unstructured default
  with --commander, tag duplication, and stale output/ analysis caches. (`docs/ROADMAP-v0.9.md`)

### Added
- **F11: the X-SPELLS tribal pattern — Gargos finally reads `Hydra Tribal: high`.** "Hydra spells
  you cast cost {4} less" matched no tribal pattern (they covered creatures/you-control/cards/one-
  or-more forms, never SPELLS). New whitelist-guarded pattern covers tribal cost-reduction and
  cast payoffs: Goblin Warchief and Dragonspeaker Shaman read their tribes; generic phrasings
  ("instant spells you cast" — Archmage of Runes) filtered by the creature-type whitelist. Four
  sentinels (166-card set). (`analyzer/content.py`)

### Fixed
- **F10 (both halves): the category-counts scorer learns FIGHT, and philosophy fallback is loud.**
  (1) Gargos's "fights up to one target creature" scored `built_in_removal: 0.0` — the legacy
  removal heuristic only knew destroy/exile/damage/-X/-X; fight phrasings now score 2.0
  (repeatable removal), and the downstream targeted_removal target reflects the commander
  providing it. Note: `--analysis` files cache scores — re-run commander-analyze after tool
  upgrades. (2) Custom `--philosophy` strings silently fell back to 'balanced'; the output now
  carries a `philosophy_warning` naming the 14 valid options (None when valid). Full migration of
  `_score_provides` to analyzer signals annotated as the priority Fase-2 consumer. Two regression
  tests. (`category_counts/scoring.py`, `category_counts/calculator.py`)

### Added
- **Full BUILDER.md-guided build (Gargos fight-engine, power 7, $130): READY at $94.45, and the
  Budget Contract exercised for the first time.** New feature from friction F9: `search` gains
  `--max-price` (a budget build cannot shortlist without it; shared `_apply_max_price` across all
  branches). Frictions annotated: category-counts ignores custom `--philosophy` strings and
  scores `built_in_removal: 0` for Gargos whose fight trigger IS removal (the legacy scorer
  doesn't read the analyzer — Fase 2 motivation); the analyzer reads [] for Gargos ("Hydra spells
  cost less" — no X-SPELLS tribal pattern, known gap). Agent lesson recorded: defensive parsing —
  check the "error" key before "results" (a well-emitted boundary error was swallowed by a lazy
  parse). The tool caught two hallucinated names (cards-batch) and a genuine color violation
  (preflight, F7 message naming the card in production). (`cli.py`,
  `logs/testbuild-gargos-v0.8-builder.json`)

### Changed
- **F3 definitive: ranking tiebreak switched from price proxy to real EDHREC popularity.** The
  user's fresh network `init-data` populated `edhrec_rank` for 31,740/38,304 cards (83%; the rest
  are digital-only) with a canonical top (Sol Ring #1, Command Tower #2, Arcane Signet #3), and
  the 182-commander ingest fix survived its first production run (0 broken). `search_by_tags`
  ranked ties now sort by edhrec_rank ASC (NULLs sink). Anowon's complements evolution: v1
  alphabetical chaff -> v2 price-inflated reserved list -> v3 what players actually play (Animate
  Dead #224, Curiosity #592, Aqueous Form back on MERIT at #732). The full 162-sentinel net
  passed untouched against the fresh Scryfall oracle texts — the detectors generalize over new
  data. (`cards/search.py`)

### Fixed
- **`mtg init-data` crashed with "24 values for 25 columns" — the edhrec_rank wiring was
  incomplete (our miss).** The previous change added the column to the schema and to the INSERT
  column list but not to `_to_row()` nor the VALUES placeholders, so a fresh network ingest died
  at the first chunk. Both synced (the rank survives printing aggregation since it is
  per-oracle). A no-network sync test now asserts schema columns == placeholders == row length,
  so this class cannot ship again. (`data/build_sqlite.py`, `tests/test_v7_fixes.py`)

### Fixed
- **F1 resolved — and it was pilot error turned into documentation.** `color_identity` DOES live
  at the top level of `commander_analysis.json`; the test-build agent (Claude) guessed a nested
  `commander.color_identity` path. Root cause: the JSON structure was never documented, so agents
  guess paths. `agents/commander_analyzer.md` now lists the exact top-level paths for every field
  agents read (color_identity, analyzer, archetype_fit, engine_profile, wanted_card_patterns...)
  and clarifies the `commander` key holds only the raw card object. All 8 test-build frictions
  now closed. (`agents/commander_analyzer.md`)

### Fixed
- **F3: complements/search-tags ranking no longer floods with cheap chaff.** The rank tiebreak was
  cheapest-CMC-first, so hundreds of $0.05 one-mana auras tied at 1 tag-match and buried staples
  alphabetically. Ties now break by usd_price DESC (an imperfect but real staple proxy — Anowon's
  complements went from "Aboshan's Desire, Air Bladder..." to multi-match Treachery/Necromancy/
  Pemmin's Aura). The DEFINITIVE fix is wired and dormant: the ingest now extracts Scryfall's
  `edhrec_rank` (normalize + schema + insert) — it will populate on the next `mtg init-data` with
  network access, and the ranking can then prefer it. (`cards/search.py`,
  `data/normalize_cards.py`, `data/build_sqlite.py`)

### Fixed
- **JSON error boundary (the F2b/F4 class): with `--json-output`, EVERY error is structured JSON.**
  A single boundary at the entry point runs Typer in non-standalone mode when the flag is present
  and converts usage errors (bad flag/command, Click did-you-mean preserved), validation aborts,
  and unexpected crashes into `{"error": {type, message, exception?}}` — an agent's parser can
  never break on a Rich panel again. Human mode untouched. The `--type` validation error now also
  suggests `--subtype` for creature types (F2c). Regression test covers the three error classes.
  (`cli.py`)

### Fixed
- **Live test build (Anowon, mill+rogues) surfaced 8 frictions; 3 fixed root-cause, 5 annotated.**
  FIXED: (F5, critical) deck JSONs with plain-string entries crashed fill-lands/deck-gaps/
  preflight with a raw AttributeError — `_normalize_entries` in the single load point
  (`utils/deck_io.py`) now accepts strings or dicts; (F7) color-identity violations now NAME the
  offending card in the message; (F8) `agents/deck_fixer.md` documented nonexistent
  `--remove/--add` flags — corrected to the real `--swap "Old=New"`. ANNOTATED for a future pass:
  validation errors that ignore `--json-output` (F2b/F4 — Rich panels break agent parsing; the
  `deck-fill-lands` did-you-mean error is the UX standard to replicate), `--type` not suggesting
  `--subtype` (F2c), `complements` ranking chaff over staples (F3). Positives: perfect analyzer
  read on a virgin commander (Mill+Rogue high), cards-batch caught an invented card, preflight
  caught a color violation, deck-gaps reported a real gap, build reached READY.
  (`utils/deck_io.py`, `validator/deck_validator.py`, `agents/deck_fixer.md`)

### Changed
- **Certero rate raised 67% -> 71% via the cheap layer: five measured band promotions, zero new
  lies.** The 12 "directional" commanders (right signal stuck at low/medium) grouped into
  promotable classes: `DOUBLES_ETB_TRIGGERS` -> defining ETB Value (Yarok), `DONATION` -> defining
  Group Hug (Zedruu), `spell_copy` -> defining Spellslinger (Kalamax), `attack_trigger_payoff` ->
  defining Attack Triggers (Tymna), and a new measured `aura_equipment_payoff` tag defining
  Voltron (Sram/Galea/Estrid class). `counter_enabler` deliberately NOT promoted (generic "+1/+1
  counter" phrase — honesty over coverage). All 156 sentinels green through every promotion;
  re-measured over the 110 judged commanders: 71% certero, 0% off-highs. Five sentinels
  (161-card set). (`analyzer/mapping.py`, `data/seed/card_tags.json`)

### Changed
- **Gate criterion #2 re-specified to the product bar and measured: 67% certero, 0% lies.** The
  product goal is a filter the agent can trust (>=60% accurate, zero confident lies), not
  perfection over the infinite niche tail. Re-running the CURRENT tool over all 110
  strictly-judged commanders from 12 validation batches: 67% correct-high, 11% directional
  low/medium, 22% honest empty, 0% suspicious highs (fuzzy keyword auto-judging vs the judges'
  written correct_archetype; training-set bias acknowledged — fresh-batch confirmation pending as
  criterion (c)). Batch #13 becomes the confirmation batch under the new bar: right+partial
  >=6/10, CW=0. (`docs/MIGRATION-archetypes.md`)

### Added
- **Gate-validation batch #12: FAIL (CW 2); two token/counter direction classes fixed.** (1)
  Grenzo read `Counters Matter: high` from "counters on" matching his self-entering counters —
  the `counter_payoff` tag is now directional (counters on each / on creatures you control) plus
  MANIPULATION phrasings (remove a/X +1/+1 counters — Ghave and Marath, real counter decks,
  restored by the net after the sweep); (2) Estrid's Aura "Mask" tokens read `Go Wide: high`
  because the token classifier's ELSE branch assumed creature — the default is now conservative
  (only explicit creature tokens or P/T-statted tokens feed Go Wide; Kemba's Cats intact).
  Honest empties: Ghalta, Balthor, Vial Smasher, Sedris-underbanding annotated. Six sentinels
  (156-card set). (`analyzer/content.py`, `data/seed/card_tags.json`)

### Added
- **The five batch-11 coverage gaps closed.** New archetypes `Battlecruiser / Big Mana`
  (annihilator, 18 measured — Kozilek high) and `Toughness / Defenders` ("with defender" +
  toughness-lifegain payoff — Arcades and Ikra high; toughness-REMOVAL like Devour Flesh reads
  nothing); the power-matters regex covers power-DOUBLING ("X is that creature's power" — Xenagos
  reads Stompy high); `artifact_payoff`/`historic` gain "historic spell" (Jhoira reads Artifacts
  high); and a new `attack_trigger_payoff` supporting tag covers combat-damage-draw phrasings
  including Tymna's "opponents that were dealt combat damage this turn". Seven sentinels
  (150-card set). (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`)

### Added
- **Gate-validation batch #11: FAIL (right 4, CW 1); the self-attack class refined with two new
  dimensions.** Zur read `Attack Triggers: high` because (a) no-comma legend names are referenced
  by FIRST name in oracle text ("Whenever Zur attacks" — the split-on-comma short name missed it;
  articles skipped), and (b) the judge's Kaalia-vs-Zur contrast revealed the real rule: a
  self-attack trigger whose EFFECT feeds combat (puts creatures attacking/untaps/extra combat)
  is an attack THEME (Kaalia stays high), while a non-combat effect (tutoring) is an engine event
  (Zur now honest empty; Korvold/Saskia intact). Five honest gaps annotated for a future session
  (Tymna, Xenagos, Kozilek, Jhoira, Ikra). Six sentinels (143-card set). (`analyzer/content.py`,
  `data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`)

### Added
- **Gate-validation batch #10: FAIL (CW 4) exposed SLEEPER generic phrases; proactive full-vocab
  audit executed.** All four CWs traced to naked phrases in tags that had never fired a CW before:
  `death_trigger` had "dies" (any death, anyone's — Kelsien/Toshiro read Aristocrats from
  OPPONENTS' creatures dying), `group_slug` had "whenever an opponent" (Kraum's draw trigger read
  slug), `land_payoff` had "lands you control" (Zacama's untap-ramp read Lands). Rather than
  whack-a-mole, a proactive audit swept ALL tags for short/high-match phrases; only four generic
  tags feed archetype buckets and all were rebuilt with DIRECTIONAL phrasings (you control dies /
  another creature dies / undying / counter-on-it dies / damage to that player / that player-
  target player-opponent loses...). The golden net caught 9 regressions from the sweep and every
  one was restored via a measured directional phrase — net behavior: 4 CWs dead, zero legitimate
  reads lost, 866 tests green. Seven sentinels (137-card set). Streak restarts again.
  (`data/seed/card_tags.json`, `data/golden/golden_cards.json`)

### Added
- **Gate-validation batch #9 (streak decider): FAIL — streak reset; two new CW classes fixed.**
  (1) NEGATION in tribal: Mikaeus's "Other non-Human creatures" read `Human Tribal: high` — the
  tribal patterns now check for a "non-" prefix before the captured type (Winota's real Human
  tribal intact); (2) the `stax` tag's generic "opponents can't"/"players can't"/"skip"/"only one"
  phrases caught anti-lifegain hate (Erebos read `Stax: high`) — replaced with specific
  restriction phrasings (can't cast/untap/attack/draw, skip their, only one spell; Peacekeeper
  intact, Erebos now honest empty). Plus two coverage fixes: `artifact_payoff` gains "sacrifice
  two artifacts" (Breya: Artifacts high) and `extra_combat` promoted to DEFINING of Attack
  Triggers (44 measured, all combat decks — Aurelia medium -> high). Eight sentinels (130-card
  set). Streak restarts: next clean batch is the new 1-of-2. (`analyzer/content.py`,
  `analyzer/mapping.py`, `data/seed/card_tags.json`)

### Added
- **Gate-validation batch #8: PASS — right 8/10, zero confidently-wrong, zero wrong/partial. The
  certification streak starts (1 of 2 consecutive clean batches).** Audit: triangle-verified,
  strict judge, all eight rights confirmed (Thassa's Blink high is the batch-1 fix generalizing
  seven batches later on a commander that was invisible before the 182-commander ingest repair).
  Two honest empties (Sygg, Surrak) annotated as known-gaps — per the sequential gate rule, NO
  analyzer changes until the streak resolves; eight PASS sentinels pinned (122-card set, behavior
  untouched). Two prompt-authoring errors owned: the expected sanity count was off by one (114
  cards -> 115 passed was correct) and the report-name literal said batch-7; the agent proceeded
  correctly on both. (`data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`)

### Added
- **Gate-validation batch #7: FAIL (right 2/10, CW 1) — audit confirmed honest coverage territory,
  not judge over-strictness. Four fixes:** (1) the CW — Atla Palani's 0/1 Eggs read `Go Wide:
  high`; utility bodies (0/X) now emit `UTILITY_TOKEN_MAKER` feeding Aristocrats as SUPPORTING
  (fodder, not army — Atla now reads `Aristocrats: very_high`, her truth); (2-3) two tribal
  phrasings invisible to the patterns: "Dinosaur creature cards" (Gishath) and "one or more
  Zombies" (Varina), both whitelist-guarded — both commanders now read their tribes high; (4)
  `landfall` gains "play an additional land" (Oracle of Mul Daya class) and "land cards are put
  into your graveyard" (Gitrog: low -> high). Kruphix/Neheb big-mana annotated as an honest
  known-gap (candidate phrases measured dirty; no archetype forced). Six sentinels (115-card
  set). (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`)

### Fixed
- **182 legal commanders were invisible to the tool (ingest bug, or-conjunction class).**
  `normalize_cards.py` flagged commanders with the contiguous substring "Legendary Creature",
  missing every multi-supertype commander: Theros Gods ("Legendary Enchantment Creature"),
  legendary artifact creatures (Karn, Legacy Reforged), etc. Found while validating gate batch #7
  candidates (Kruphix/Heliod read no-commander). Fixed to require both "Legendary" and "Creature"
  in the type line; existing DB repaired via UPDATE (182 rows); regression test added. Note: any
  DB restored from an old backup needs `mtg init-data` re-run or the same repair.
  (`data/normalize_cards.py`, `tests/test_v7_fixes.py`)

### Added
- **Gate-validation batch #6 (strict judge): FAIL 6/10 right but ZERO confidently-wrong — the
  first over-confidence-free batch in six attempts; failure mode has shifted entirely to coverage.
  Four coverage gaps fixed:** new `Graveyard Value / Recursion` archetype via the precise
  `graveyard_recast` tag (recast-engine phrasings, deliberately NOT the broad "from your
  graveyard" — Muldrotha high, Kess gains it correctly, Eternal Witness stays low); the
  power-matters regex now covers COMPARATIVE phrasing ("power is greater than" — Selvala reads
  Stompy high; Fell the Mighty guard-protected); `artifact_recursion` gains "artifact or
  enchantment card" (the Alela or-conjunction class in a third location — Tameshi); and a new
  `Morph / Face-down` archetype ("face down"/"face-down", 436 measured — Kadena from wrong to
  right). Blind calibration: predicted right ~7 (actual 6), all three predicted risks landed
  exactly, CW predicted 0-1 — actual 0. Seven sentinels added (108-card set).
  (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`)

### Added
- **Gate-validation batch #5 (strict judge, blocking sanity evidence): legitimate FAIL; two
  self/list classes fixed.** Tally right 5/10, CW 2 — both secondary-high falses beside a correct
  primary, both variants of known families: (1) Korvold read `Attack Triggers / Aggro: high` from
  his OWN "enters or attacks" engine trigger — the attack trigger family now scope-checks self vs
  board (new `SELF_ATTACK_TRIGGER` signal; Toski/Isshin/Yuriko board themes intact; Goreclaw now
  reads pure Stompy, its best read yet); (2) Shalai read `Superfriends: high` because
  "planeswalkers you control" matched her protection LIST (the Braids type-list class in another
  tag) — replaced with measured payoff phrases (loyalty abilities / loyalty ability / planeswalker
  spells; Carth and Oath of Teferi intact). Blind-prediction calibration: predicted right 6-7
  (actual 5), the three predicted risks (Volo/Galea/Old Stickfingers) landed exactly as predicted
  as honest non-gate-breaking gaps (annotated in MIGRATION), CW 0-1 predicted as unseen secondary
  falses — actual 2, both that pattern. Seven sentinels added (101-card set).
  (`analyzer/content.py`, `analyzer/analyze.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`, `docs/MIGRATION-archetypes.md`)

### Added
- **Gate-validation batch #4 (self-run) : one CW and five coverage gaps fixed.** Claude ran the
  batch itself with a blind-first protocol (expert reads written from oracles BEFORE running the
  analyzer; verdicts logged in logs/gate-validation-batch-4-claude.json for external audit).
  Tally: right 4/10, partial 4, empty 1, CW 1 -> FAIL. The CW: Braids read `Artifacts Matter:
  high` because "sacrifice an artifact" matched a TYPE LIST ("artifact, creature, enchantment,
  land, or planeswalker") — replaced with list-safe phrasings (sacrifices an artifact / whenever
  you sacrifice an artifact / the ":"-cost form; Krark-Clan Ironworks unaffected). Coverage gaps
  closed with exact culprit strings: Tergrid theft-by-acquisition (new detector conjunction:
  opponent event + "under your control" in one line), Liesa ("spell, they lose" -> group_slug),
  Yuriko (singular tribal pattern "a Ninja you control", whitelist-guarded), Alela ("artifact or
  enchantment spell"), and a new `Stompy / Big Power` archetype (POWER_MATTERS detector with a
  positive-context guard so anti-big removal like Smite the Monstrous reads nothing). Nine
  sentinels added (94-card set). (`analyzer/content.py`, `analyzer/analyze.py`,
  `analyzer/mapping.py`, `data/seed/card_tags.json`, `data/golden/golden_cards.json`)

### Added
- **Gate-validation batch #3: legitimate FAIL; four polarity/direction/permanence classes fixed.**
  Both judges agreed on FAIL; audit confirmed all four confidently-wrong reads as real classes of
  one family: (1) SELF-RESTRICTION — "Gadrak can't attack unless..." is the card's own drawback,
  not stax (new scope check in the negation layer; Gadrak now leads with `Treasures / Value
  Engine: high`, proving the batch-2 fix generalized; Peacekeeper's real stax intact); (2) the
  aristocrats tag's "each opponent loses" phrase caught pure drain (Lathril now reads Attack
  Triggers + Life Loss, its truth); (3) EPHEMERAL tokens — encore-style copies sacrificed at the
  next end step are a strike force, not an army (Araumi no longer Go Wide high); (4) CONTROL-CHANGE
  DIRECTION — a new detector reads WHO gains control: `THEFT_CONTROL` (you take theirs) vs
  `DONATION` (Zedruu gives his away, feeding Group Hug), replacing the directionless "gain control"
  tag phrases (Blatant Thievery/Sower of Temptation unaffected). Golden judging also corrected one
  of our own pins (Pontiff extort = Life Loss, not Aristocrats) and added Mirkwood Bats' real
  phrasing ("create or sacrifice a token"). Six sentinels added (86-card set). Note: the strict
  CLI judge skipped the golden sanity gate (protocol breach, flagged); the package judge ran it
  (80 passed). A fourth fresh batch is required. (`analyzer/semantics.py`, `analyzer/content.py`,
  `analyzer/mapping.py`, `analyzer/analyze.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`)

### Added
- **Gate-validation batch #2: judge disagreement resolved to a legitimate FAIL; value-token class
  fixed.** Two independent judges measured the same 10 fresh commanders with identical tool
  outputs but split verdicts (PASS vs FAIL) — audit sided with the strict judge: Prosper and Magda
  reading `Go Wide: high` from repeatable TREASURE production were confidently-wrong (value tokens
  are resources, not an army). The token detector now classifies WHAT is created: noncreature
  value tokens (Treasure/Clue/Food/Blood/Gold/Powerstone/Map/Junk/Incubator) emit
  `REPEATABLE_VALUE_TOKENS` feeding a new `Treasures / Value Engine` archetype, while creature
  tokens keep feeding Go Wide (Krenko/Adeline unaffected; Smothering Tithe now reads Treasures
  high). Positive generalization confirmed by both judges: Aminatou (blink fix), Wilhelt
  (aristocrats fix), Emry, Chishiro, Giada, Gisa all read right untouched. Six sentinels added
  (79-card set). A third fresh batch is required for the gate. (`analyzer/content.py`,
  `analyzer/mapping.py`, `data/golden/golden_cards.json`)

### Added
- **Gate-validation batch #1: legitimate FAIL, three defining-phrase false positives fixed.** The
  criterion-#2 exam (10 fresh commanders, cross-verified authentic) scored right 8/10 but breached
  the zero-confidently-wrong bar with three secondary high bands: Meren read Blink (the `blink` tag
  matched graveyard "return it to the battlefield" — real blink now requires exile-context
  phrasings, with Brago/Oath/Felidar batch-and-delayed variants measured in), Sram read Spellslinger
  ("whenever you cast" matched ANY cast trigger — replaced with instant/sorcery/noncreature-specific
  phrases; Talrand unaffected), and Tatyova read Aristocrats ("you gain" matched all lifegain —
  removed; "creature you control dies" added, Zulaport-style intact). The golden set caught two
  blink regressions during the fix (Oath of Teferi, Teleportation Circle) — its first real
  engagement, working as designed. Five sentinels added (73-card set). The gate requires a NEW
  fresh batch: these 10 commanders were consumed by this calibration. (`data/seed/card_tags.json`,
  `data/golden/golden_cards.json`)

### Added
- **Backlog of five verified misses from golden-set judging: fixed.** (1) The trigger doubler now
  extracts a DEATH context (`DOUBLES_DEATH_TRIGGERS`, defining for Aristocrats — Teysa Karlov reads
  `high`, was `low` noise); (2) `artifact_payoff` gained the "artifact spell" phrasing (119
  measured matches — Sai and Etherium Sculptor now read Artifacts Matter); (3) `mill_opponents`
  gained "that player mills" / "each player mills" / "enchanted player mills" / "controller mills"
  (Mesmeric Orb and Fraying Sanity now read Mill high); (4) `group_slug` gained symmetric-pinger
  phrasings ("damage to each player/opponent" — Spear Spewer reads Life Loss high); (5) a new
  regex-based `SAC_OUTLET` detector catches sacrifice-as-cost with VARIABLE types ("Sacrifice a
  Goblin:") that vocabulary cannot enumerate, supporting Aristocrats (Skirk Prospector, Viscera
  Seer). Eight sentinels added to the golden set (68 cards, all green). One process lesson
  recorded: python str.replace fails silently — a mapper edit missed because the target string had
  drifted; caught by controls, fixed via the checked str_replace tool. (`analyzer/content.py`,
  `analyzer/mapping.py`, `analyzer/analyze.py`, `data/seed/card_tags.json`,
  `data/golden/golden_cards.json`)

### Added
- **Golden set materialized: 60 hand-verified pinned reads (Fase 2 gate criterion #1 — DONE).**
  `data/golden/golden_cards.json` + parametric suite `tests/test_golden_set.py`. Candidates were
  harvested from every calibration source (2 live builds, 10-commander batch, Fase 0/0.2, both
  recon batches — 123 golden notes), then each read was JUDGED before pinning (anti-freeze-bugs
  rule: a golden set that pins wrong reads is worse than none — the rule worked in both
  directions, catching one wrong pin of ours: Toxrill's slime counters are named counters, not
  literal -1/-1). Bands pin as acceptable LISTS so legitimate improvements don't break the net;
  entries carry must_not_have bands, expected/forbidden signals, source and note. Judging also
  surfaced a fresh verified miss backlog (Teysa death-doubler context, "artifact spell" phrasing,
  "that player mills", symmetric pingers, tribal sac outlets) documented in
  docs/MIGRATION-archetypes.md. (`data/golden/golden_cards.json`, `tests/test_golden_set.py`,
  `CALIMAX.md`, `docs/MIGRATION-archetypes.md`)

### Added
- **Modal-toolbox detection resolves the over-confident goodstuff case (Fase 2 gate criterion
  #4).** Kenrith read `Counters Matter: high` because one of his five activated abilities places a
  broad counter — a single menu item dominating the read. Rather than suppressing evidence (magic-
  number demotion) the analyzer now ADDS the missing structural signal: `MODAL_TOOLBOX` fires on 4+
  separate activated-ability lines (measured scope: exactly 4 commanders — Kenrith, Cromat,
  Super-Skrull, Fain), maps to a `Toolbox / Goodstuff` archetype, and emits a warning instructing
  the agent that per-mode bands are OPTIONS to be resolved against the user's answers from the
  build questions (user wants aggro -> lean the aggro-adjacent mode; if unknown, ask). BUILDER.md
  §7.0b, agents/user-feedback.md and agents/commander_analyzer.md wire the rule into the feedback
  flow. The tool proposes, the user's direction disposes. (`analyzer/content.py`,
  `analyzer/mapping.py`, `analyzer/analyze.py`, `BUILDER.md`, `agents/*.md`)

### Added
- **Five new archetypes from the uncovered-territory recon + vocab precision fixes.** Two
  independent LLM recon batches (cross-verified identical against the deterministic tool) mapped
  six uncovered territories; fixes: new archetypes `Mill` (new measured `mill_opponents` tag incl.
  the "would mill" replacement-doubler phrasing — Bruvac now `Mill: high`, was a false `Reanimator:
  low`), `Wheels / Forced Draw` (new `wheel` tag + the already-firing draw-trigger family — Windfall
  `high`, Nekusar surfaces the engine), `Artifacts Matter` (existing `artifact_payoff` + singular
  "artifact you control" phrase — Urza now `high`), `Group Hug / Politics` (existing `group_hug` tag
  — Kynaios now `high`, was a near-opposite `Punisher: low`), and `Superfriends / Planeswalkers`
  (new measured `superfriends` tag + proliferate — Carth the Lion `high`). Three vocab false
  positives root-caused and fixed: `self_mill`'s naked "mill" phrase (caught opponent-mill),
  `token_doubler`'s "twice that many" (caught mill doublers), and `repeatable_token_maker`'s naked
  scheduled-trigger phrases (tag is now create-anchored; the conjunction SIGNAL remains the
  archetype truth). The punisher warning now checks polarity: a one-sided commander that GIVES
  resources gets a group-hug build note instead of attrition advice. (`analyzer/mapping.py`,
  `analyzer/analyze.py`, `data/seed/card_tags.json`)

### Changed
- **Agent files synced to v0.8.0 (audit-driven).** A feature-coverage audit of the agent
  instruction files against the actual CLI found BUILDER.md/CLAUDE.md ~90% current but the role
  files (`agents/*.md`) missing everything from v0.8.0, and the `--log`/`report` audit trail
  documented nowhere. Fixed per role (intentional redundancy preserved): `agents/system.md` adds
  the analysis tools, the archetype-preference rule (#11) and deck-gaps in the build mindset;
  `agents/commander_analyzer.md` rewrites its archetype section around the Fase 1 `analyzer`
  object (preferred) with `archetype_fit` demoted to legacy hint, plus the coverage-gap protocol;
  `agents/deck_builder.md` adds the new search axes (`--trigger`, pow/tou filters, ranked
  search-tags, similar/complements) and the pre-final deck-gaps audit; `agents/card_ranker.md`
  adds analyze-card as an evidence check for non-obvious cards; `agents/deck_fixer.md` adds the
  deck-swap/similar/deck-gaps fix loop ending at preflight READY; `BUFF.md` starts its weakness
  pass with deck-gaps; and BUILDER.md §7.9 + CLAUDE.md document `--log`/`report`.

### Added
- **Fase 1 of the archetype migration: the evidence-first analyzer is now embedded in
  `commander_analysis.json`.** `analyze_commander` adds an `analyzer` object (archetype_support
  ordinal bands, compact signal IDs, dominant_symmetry, warnings — partner supported) ALONGSIDE the
  untouched legacy `archetype_fit`, guarded so the parallel analyzer can never break the legacy
  analysis. BUILDER.md §7.0b and CLAUDE.md now instruct agents to prefer `analyzer.archetype_support`
  when the two reads disagree, treating the legacy score as a hint. Signals are compacted to IDs
  (~5% of the payload; full traces via `mtg analyze-card`), so agents get the better read in ONE
  command instead of two. The Fase 2 gate criteria (golden set green, fresh-spectrum ≥8/10 with zero
  confidently-wrong, common-archetype coverage, goodstuff case resolved) are written down in
  `docs/MIGRATION-archetypes.md`. (`deckbuilder/commander_analyzer.py`, `BUILDER.md`, `CLAUDE.md`,
  `docs/MIGRATION-archetypes.md`)
- **Lands / Landfall archetype + Spellslinger de-noising + theft phrasing (Fase 0.2 fixes).**
  Phase-0.2 generalization measurement confirmed the calibration fixes were rules, not per-card
  patches (Wulfgar and Adeline read correctly untouched), and surfaced three cheap gaps now closed:
  (1) a `Lands / Landfall` archetype (defining: landfall/land_payoff; supporting: extra_land_drop/
  land_recursion — deliberately excluding generic `land_ramp`, which belongs in every green deck),
  fixing Aesi's confidently-wrong `Spellslinger` read; (2) generic `cheap_spell`/`card_draw` removed
  from Spellslinger's buckets (third occurrence of this noise — Valgavoth, Earthshaker, Aesi), with
  real spellslingers unaffected via their defining magecraft/spell_payoff; (3) the `theft` tag gained
  the exact phrase "cast spells from that player's hand" (measured: 0 false positives), so Sen
  Triplets now reads `Stax high + Theft high`. Known-gaps annotated without action: doubler
  cast-context (covered by tag redundancy — Veyran reads right via magecraft), Elder Brain theft
  phrasing, Atraxa ETB band. (`analyzer/mapping.py`, `data/seed/card_tags.json`)
- **Trigger-doubler detection with context + generic-token de-noising (Fase 0 coverage gaps).**
  Isshin gave an empty analysis because his meta-trigger ("If a creature attacking causes a
  triggered ability ... to trigger, that ability triggers an additional time") matches no trigger
  grammar. A new `TRIGGER_DOUBLER` detector recognizes doublers and extracts WHICH triggers they
  double from the same line: attack context emits `DOUBLES_ATTACK_TRIGGERS` (defining for Attack
  Triggers / Aggro — Isshin now reads `high`), enters context emits `DOUBLES_ETB_TRIGGERS`
  (supporting ETB Value / Blink — Panharmonicon). Also applied the day's supporting-bucket lesson
  to two more generic tokens: `card_advantage` no longer implies Theft and `lifegain` no longer
  implies Life Loss (this de-noised Atraxa), and the `theft` tag gained the "don't own" phrase
  (21 cards, all genuine theft — Gonti now reads `Theft: high` via its defining signal instead of
  `low` via noise). (`analyzer/content.py`, `analyzer/mapping.py`, `data/seed/card_tags.json`)
- **Conjunction-based repeatable-token detection + Vehicles de-noising (Fase 0 fixes).** Phase-0
  measurement (old vs new archetype system across 10 commanders) exposed two new-analyzer false
  positives. (1) `repeatable_token_maker` is a CONJUNCTION — repeatability AND token creation — that
  the substring tag vocabulary cannot express: its broad phrases wrongly tagged Gonti (combat-damage
  trigger, no tokens; 39 false positives measured) while precise phrases lost real makers. A new
  `REPEATABLE_TOKEN_MAKER` detector in the analyzer now requires a repeat marker (recurring/scheduled
  trigger or activated ability) AND `create`+`token` in the SAME oracle line (abilities are one line;
  sentences within a line are the same ability — this preserved Shorikai's multi-sentence activated
  ability), excluding tokens handed to opponents (Nettling Nuisance). Go Wide's defining bucket now
  uses the precise signal; the tag's over-broad phrase was removed from the vocab (tag remains for
  search shortlists). (2) `token_maker` was removed from Vehicles' supporting bucket — making tokens
  never implied being a vehicle (Krenko no longer reads Vehicles; Shorikai keeps `Vehicles: high` via
  its defining `VEHICLE` signal). Verified on 7 controls: Krenko/Quartzwood/Ophiomancer/Shorikai
  positive, Gonti/Regisaur/Nettling negative. (`analyzer/content.py`, `analyzer/mapping.py`,
  `analyzer/analyze.py`, `data/seed/card_tags.json`)
- **Saga chapter splitting + multi-role preservation (calibration batch pattern #5).** Sagas were
  analyzed as one text blob, muddling their distinct per-chapter roles. `split_faces` now splits a
  Saga on its chapter markers (I —, II —, III —) so each chapter is analyzed separately (Elspeth
  Conquers Death → removal / tax / recursion; Binding the Old Gods → removal / ramp / anthem). Added
  a tax detector (`TAX_COST_INCREASE` → Stax, catching "spells cost {N} more") that a Saga tax
  chapter previously missed, and refined the counter-sense classifier to treat an incidental single
  counter ("put a +1/+1 counter on it/that creature") as `COUNTER_MARKER_SELF` rather than a broad
  Counters Matter strategy — so a removal/recursion Saga no longer misreads as a high Counters Matter
  deck. Verified across Elspeth (self/incidental), Valgavoth (self via name), Hardened Scales
  (broad), Blowfly Infestation (-1/-1 minus). (`analyzer/structure.py`, `analyzer/content.py`,
  `analyzer/semantics.py`, `analyzer/mapping.py`)
- **Theft and Legendary Matters archetypes (calibration batch pattern #3).** The batch flagged
  several "missing archetype" misses, but verification showed 4 of 6 already existed (Minus Counters /
  Attrition, Attack Triggers / Aggro, Vehicles, Evoke-fed Aristocrats/Reanimator) — those misses were
  detection gaps on unusually-templated cards, not missing archetypes. The two genuinely missing were
  added: a `Theft` archetype (fed by the existing `theft` tag) and `Legendary Matters` (with a new
  `LEGENDARY_MATTERS` content detector that fires on legendary-synergy phrasings like "legendary
  creatures you control" / "cast a legendary spell", without false-positiving on a card merely being
  Legendary itself). Verified on Dihada (both), Jodah (legendary), with Pantlaza as a negative control.
  (`analyzer/content.py`, `analyzer/mapping.py`)
- **Commander allowlist for non-creature face commanders (calibration batch fix #1).** The
  `can_be_commander` heuristic (Legendary Creature or "can be your commander" text) can't detect face
  commanders printed as non-creatures with no oracle signal (e.g. the Legendary Vehicle Shorikai,
  Genesis Engine — which blocked a legal build in the batch). A curated allowlist
  (`data/seed/commander_overrides.json`) is now applied at card-hydration time (`row_to_card`) and in
  normalization, so such commanders resolve as legal without a DB rebuild, while non-commander
  vehicles (Esika's Chariot, Heart of Kiran) stay correctly blocked. BUILDER.md §7.0 adds a legality
  pre-check that falls back to web/user verification before adding new names — no guessing.
  (`cards/repository.py`, `data/normalize_cards.py`, `data/seed/commander_overrides.json`, `BUILDER.md`)
- **Conditional evasion vs absolute unblockable (calibration batch fix #2).** The analyzer's negation
  layer now distinguishes fear/intimidate/menace ("can't be blocked **except by** …", emitted as
  `CONDITIONAL_EVASION`) from true unblockable ("can't be blocked", `UNBLOCKABLE`), so a fear-granting
  card no longer reads as absolute evasion or over-supports Voltron. (`analyzer/semantics.py`)
- **`--log` audit trail on every command + `report` consolidation.** A global `--log` flag (usable
  on ANY command, in any position — handled centrally in `main()`, so no command declares it)
  captures each invocation into an on-going JSON staging file (`output/on-going-report.json`) as a
  flat, self-describing entry: `{seq, command, full_command, response, timestamp, exit_code}`, where
  `seq` is the global chronological order and `response` is parsed JSON when the command emitted JSON
  else raw text. `mtg report --name <file> [--note ...] [--keep]` serializes the accumulated log into
  `output/<name>.json` (with embedded `--note` comments) and clears the staging file. `--summary`
  additionally derives calibration metrics from the log (per-command call counts, every card passed
  to `analyze-card`, and any non-zero-exit commands) without changing what was captured. Gives builds
  a real, replayable record of everything the agent ran. (`logging_util.py`, `cli.py`)
- **(In progress, parallel) Universal card analyzer foundation (`analyzer/`).** A new evidence-first
  analyzer is being built alongside `oracle_hooks`/`card_profile` (not yet wired into the live
  pipeline). It models every conclusion as a `Signal` with a `Trace` (which rule fired, what text
  matched, where) and an `EvidenceKind` (fact / rule_relation / heuristic / meta_opinion), with
  ordinal `Confidence` bands instead of invented decimals and no scores or include/cut verdict.
  Extraction layers so far: scope/symmetry (generalizes the GF-1 punisher fix — targeted single vs
  mass one-sided), timing & replacement effects (a replacement clause is not read as a trigger),
  semantics (negation polarity: "can't be blocked" vs "can't attack"; and counter verb vs noun:
  Counterspell vs +1/+1), structure (multi-face/modal split + linked abilities), and content
  (trigger event families, value scaling incl. power/toughness, and tribal/creature-type detection —
  added after the Pantlaza calibration run surfaced these as misses). Trigger-family and count
  scaling reuse the existing oracle_hooks extractors. The Pantlaza calibration run also drove two
  precision fixes: `repeatable_token_maker` no longer matches one-shot ETB tokens (its phrase list
  now requires genuine recurrence — recurring triggers, attack/combat-damage triggers, or activated
  abilities — so a "when this enters, create a token" card is `token_maker` but not repeatable), and
  the archetype mapper dropped generic `evasion`/`buff` from Voltron support (trample/flying no
  longer imply Voltron) while surfacing the new content signals as archetypes (dynamic `<Type>
  Tribal`, and `ETB Value` from the enters-trigger family). A second calibration run (Valgavoth)
  drove two mapping/interpretation fixes: the counter-sense layer now distinguishes a self-counter
  (`+1/+1 counter on <this card>` — incidental self-growth, emitted as `COUNTER_MARKER_SELF`) from a
  broad counters strategy (`on target/each creature` — `COUNTER_MARKER`), so a commander that just
  grows itself no longer reads as a high Counters Matter deck; and a `Life Loss / Group Slug`
  archetype was added (fed by `group_slug` + the life-change trigger + `lifedrain`) so life-drain
  payoffs surface their real archetype instead of nothing. Validated against real cards; pure-logic
  and DB-free. (`analyzer/model.py`, `analyzer/scope.py`, `analyzer/timing.py`, `analyzer/semantics.py`,
  `analyzer/structure.py`, `analyzer/content.py`, `analyzer/mapping.py`, `analyzer/analyze.py`,
  `data/seed/card_tags.json`)
- **Four new search axes so the agent can prune by function instead of enumerating, plus a card
  function-profile keystone (`deckbuilder/card_profile.py`).** (1) Numeric creature-stat filters
  (`search --pow-gte/--pow-lte/--tou-gte/--tou-lte`, query tokens `pow>=`/`tou<=`) with safe
  coercion so `*`/variable/null power never matches a bound. (2) `search --trigger <family>` searches
  by the event a card triggers on, reusing the analyzer's 9 trigger families (`--list-triggers`).
  (3) `mtg similar "<Card>"` finds cards performing the same function (profiles the card's tags,
  ranked by shared facets) and `mtg complements "<Card>"` finds the other half of the interaction via
  a curated complement map (sac outlet → death-triggers/recursion; +1/+1 placer → proliferate). (4)
  `mtg deck-gaps --deck --commander` audits the built deck against its category targets and oracle
  hooks, listing what's thin (ranked by need) with a ready `search-tags` command per gap — closing
  the analyze→build→audit loop. The shared `card_function_profile` helper (card → tags/triggers/hooks)
  underpins similar/complements/deck-gaps so they share one definition of "function".
  (`cards/query_parser.py`, `cards/search.py`, `deckbuilder/card_profile.py`, `cli.py`)
- **`search-tags` now ranks by function-match and lists its vocabulary; one functional-search
  system, not two.** Rather than adding a parallel "concept" vocabulary, the existing tag system
  (`card_tags.json`, 97 functional tags) is the single source of truth. `search-tags` now ranks
  results by `tag_match_count` (how many of the requested tags' phrases a card hits, most
  on-function first), accepts multiple tags as a union, gained `--max-price` / `--mv-lte`, and
  added `--list-tags` for discoverability. Ranking is opt-in at the function level (`rank=`), so
  `suggest` and other callers keep their existing order. This lets the agent decompose a plan into
  functions (commander damage = evasion + damage_multiplier + protection) and pull a ranked
  shortlist per function — pruning ~38k cards to a few dozen without enumerating combinations.
  (`cards/search.py`, `cli.py`)
- **`--json-output` on every command + a contract test that enforces it.** `status`, `init_data`,
  `enrich`, and `export` were the last commands emitting only rich text; they now also support
  `--json-output`. A regression test introspects the Typer app and fails if any registered command
  lacks `--json-output`, so machine-readable output can't silently regress as new commands are
  added — the agent can rely on every command speaking JSON. (`cli.py`, `tests`)
- **`mtg preflight` — single finalization gate.** Runs every must-pass check in one command
  (commander legal & in the command zone, deck size, all cards exist, all Commander-legal,
  singleton, color identity, and budget when `--budget` is given), reusing the existing validator
  / deck-check / budget logic rather than reimplementing it. Prints a per-check ✓/✗ checklist
  ending in `READY` / `NOT READY` with exit code 0/1; quality notes are shown as non-blocking.
  This converts "remember and individually re-run 10 rules before finalizing" into "run one gate
  that the CLI enforces" — far harder for an agent to skip. `BUILDER.md`, `agents/system.md`, and
  `CLAUDE.md` now point their finalization rule at `mtg preflight` instead of bare `validate`. (`cli.py`)
- **General oracle-hook extraction (`deckbuilder/oracle_hooks.py`).** Instead of matching a
  commander against a fixed table of known archetypes (a treadmill — every new mechanic needed a
  hardcoded rule), the analyzer now reads the *structure* of the oracle text and derives generic
  features that work for ANY commander: named counters (slime / experience / +1/+1 / oil / …),
  token types, trigger event families (dies / enters / targeted-by-spell / you-cast / attacks /
  sacrifice), "for each / number of" scaling, asymmetric-punisher detection (acts on creatures
  "you don't control" / "each opponent"), and typed cost reduction. From those it derives generic
  `build_signals`, merged into `wanted_card_patterns`, and exposed as an `oracle_hooks` field.
  Concretely this fixes two correctness traps generically rather than per-commander: a custom
  counter (slime, experience) now recommends proliferate + any-counter payoffs and explicitly
  warns AGAINST dead +1/+1-specific payoffs; and a punisher commander is steered toward one-sided
  attrition rather than going wide. (`deckbuilder/oracle_hooks.py`, `deckbuilder/commander_analyzer.py`)
- **`mtg deck-swap`.** Swaps cards in a decklist (`--swap "Old=New"`, repeatable) and validates
  every incoming card *before writing anything*: it must exist in the DB, be Commander-legal, and
  (when a commander is known) fit the color identity; the result also can't create a duplicate
  non-basic card (singleton). If any check fails the whole operation aborts and nothing is written.
  This replaces hand-editing the decklist with a raw `python`/`sed` script — which silently skipped
  the color-identity, legality, and singleton checks. (`cli.py`)
- **`mtg budget --by-card` / high-cost-card flagging.** `budget` now returns a `breakdown`
  (every priced card with `line_total = usd_price * quantity`, sorted most-expensive first) and,
  when a `--budget` is set, a `high_cost_cards` list of single cards eating >= `--high-cost-pct`
  of the budget (default 20%, each with `pct_of_budget`). `--by-card` prints the top `--top`
  expensive cards in plain text. This replaces piping `prices-batch --json-output` through inline
  Python to sum `price*qty`, sort, and find the cuts (the budget-trim flow), and surfaces a single
  land/card silently eating the budget. (`deckbuilder/pricing.py`, `cli.py`)
- **`mtg cards-batch --verify`.** Reports only the names that weren't found (with suggestions)
  and exits non-zero if any are missing — so verifying a drafted `.txt` before `deck-write` no
  longer needs an inline Python filter for `found == false`. JSON mode returns a
  `{total_entries, found_count, not_found_count, not_found:[...]}` summary. (`cli.py`)
- **`mtg category-counts --table`.** Flat, ungrouped, plain-text table (one row per category,
  sorted by `need_score` descending) with `need_score`, `recommended_range`,
  `compressed_target_count`, and `priority` as explicit columns — the exact fields needed to
  judge compression per the Category Counts Contract. Replaces piping `--json-output` through an
  inline Python script to build this table by hand; no box-drawing chars or repeated per-priority
  headers like the default rich report, so it's safe to grep/awk/`column -t`. (`category_counts/output.py`, `cli.py`)
- **`mtg card --field <name>`.** Prints a single field's raw value (e.g. `oracle_text`,
  `mana_cost`, `power`) with no JSON wrapping or rich styling, so extracting one field no longer
  requires piping `--json-output` through `python -m json.tool` + `grep -A2` — a pattern that
  was also silently truncating multi-line oracle text past 2 lines. Errors clearly: unknown
  field name lists the real available fields and exits 1; a not-found card still emits the
  structured `{"found": false, ...}` JSON. (`cli.py`)
- **Targeted-spell-payoff commander modeling.** Commanders that reward their own creatures being
  targeted (e.g. Gargos, Vicious Watcher — "whenever a creature you control becomes the target of
  a spell …") are now detected as a `targeted_spell_payoff` engine. `wanted_card_patterns` surfaces
  the matching package — cheap spells/auras that target your own creatures and recurring/buyback
  auras (e.g. Whip Silk) to retrigger — which the analyzer previously could not suggest.
  (`deckbuilder/commander_analyzer.py`)
- **`.txt` decklist support for verification commands.** `cards-batch`, `prices-batch`,
  `budget`, and `enrich` now accept a plain-text decklist (`1 Card Name` per line) in addition
  to deck JSON, so a drafted list can be validated/enriched *before* `deck-write`. New
  `load_deck_file()` helper in `utils/deck_io.py`.
- Regression tests for all of the above (`tests/test_v7_fixes.py`).

### Docs / agent files
- README Krenko examples switched from `Archetype: Tribal` to engine-first
  `Archetype: tokens (go-wide)` with `Goblins` as the detail, matching the analyzer's behavior
  (Krenko reads as a `token_engine`; forcing `tribal` yields a low fit + forced-archetype warning).
- Clarified the "no helper scripts" rule in `BUILDER.md` and `agents/system.md`: read-only
  inspection/formatting of CLI output (`jq`, `json.tool`) is allowed; the prohibition is on
  scripts that generate or decide deck content outside the CLI.
- Strengthened the Category Counts Contract: `recommended_range` / `need_score` are the source
  of truth, **not** the more prominent `compressed_target_count`, which can shrink a
  High/Critical-need category to a misleadingly tiny target.
- Aligned the agent docs with the v0.7.0 behavior. `BUILDER.md` §6 and `agents/deck_builder.md`
  add a verify-before-build step (`cards-batch output/decklist.txt` catches bad names cheaply,
  and `cards-batch`/`prices-batch`/`budget` take the `.txt` directly). `agents/commander_analyzer.md`
  gains an "Engine Package" section explaining how to turn `engine_profile` / `synergy_tags` /
  `wanted_card_patterns` into card choices (incl. the `targeted_spell_payoff` class and cheap
  self-target / buyback-aura enablers), and documents the `low_confidence` archetype-fit fallback
  and the creature-size fit bump.
