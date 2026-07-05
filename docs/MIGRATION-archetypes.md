# Archetype migration: legacy `archetype_fit` → evidence-first `analyzer.archetype_support`

Strangler-fig migration of the archetype system. The legacy `archetype_fit` (weighted text scores,
magic numbers) is being replaced by the parallel analyzer's `archetype_support` (ordinal bands with
evidence traces). Each phase is additive/reversible; the legacy path is only removed once nothing
consumes it.

## Status

- **Fase 0 — measure disagreement: DONE.** 10-commander head-to-head exposed new-analyzer false
  positives (Krenko→Vehicles, Gonti→Go Wide) and coverage gaps (Isshin empty). Blocked a premature
  migration. All findings fixed.
- **Fase 0.2 — measure generalization: DONE.** Mixed set (regression / generalization / new
  territory) confirmed the fixes were rules, not per-card patches (Wulfgar, Adeline read correctly
  untouched). Surfaced and fixed: missing Lands/Landfall archetype, Spellslinger generic-token
  noise, a theft phrasing gap.
- **Fase 1 — additive embed: DONE (this change).** `commander_analysis.json` now carries an
  `analyzer` object (archetype_support bands, signal IDs, dominant_symmetry, warnings) alongside the
  untouched legacy `archetype_fit`. BUILDER.md §7.0b and CLAUDE.md instruct agents to prefer the
  analyzer read when the two disagree. The parallel analyzer is guarded so it can never break the
  legacy analysis. Signals are compacted to IDs for token efficiency (full traces via
  `mtg analyze-card`).
- **Fase 2 — consumers switch: DONE (2026-07-04).** Gate opened by batch #15 (9/10,
  CW=0). All three consumers migrated, tests green between each: (1) `_score_provides`
  reads analyzer signals with per-branch oracle fallback (spot-check 10: 8 same, 2
  better, 0 worse — the Esika mana-ability class); (2) `deck-gaps` audits the deck
  against the analyzer's high bands ("Commander plan check" + `plan_gaps`); (3)
  `suggest --synergy` / `wanted_card_patterns` consume the high-band plan phrases. All
  three share ONE vocabulary — `mapping._ARCHETYPE_RULES` ∩ card_tags — so archetype
  context cannot drift between consumers. Exact certero re-measure pending on the
  110-commander judgment dataset (not in repo); the 208-sentinel golden net is the
  standing regression evidence.
- **Fase 3 — retire legacy `archetype_fit`: DEPRECATION SHIPPED (2026-07-04); delete in
  v0.10.** The analysis JSON now carries a machine-readable `legacy_deprecations` block
  (archetype_fit, commander_tags, synergy_tags → deprecated, replaced_by, removal v0.10),
  the analyzer embed exposes `tags` (the single-source replacement for the tag lists), and
  all agent files (BUILDER §7.0b, agents/commander_analyzer.md, agents/system.md rule 11,
  CLAUDE.md) name the deprecation. The fields themselves remain until v0.10 so no consumer
  breaks — the v0.10 release executes the physical delete.

## Fase 2 gate (agreed criteria — do not start Fase 2 until ALL hold)

1. **Golden set materialized and green — DONE.** `data/golden/golden_cards.json` (60 cards,
   every read hand-verified before pinning) runs as a parametric suite
   (`tests/test_golden_set.py`) with acceptable-band lists, must_not_have bands, and
   expected/forbidden signals. Growth flow: CALIMAX runs propose candidates; only verified reads
   get pinned.
2. **Fresh-spectrum batch: analyzer right ≥ 8/10 with ZERO confidently-wrong.** A new 10-commander
   batch on archetypes/commanders never used for calibration. An honest empty/low read is
   acceptable; a wrong high band is not.
3. **Common-archetype coverage closed.** At minimum: mill, wheels, artifacts-matter,
   superfriends/planeswalkers, group hug/politics exist as archetypes in the mapper (they are
   common Commander strategies the mapper does not cover yet).
4. **The "timid goodstuff" case resolved or explicitly accepted — RESOLVED.** Recon showed the
   real failure was over-confidence, not timidity (Kenrith: one of five modes dominating). Resolved
   via `MODAL_TOOLBOX` (structural signal on 4+ activated abilities) + `Toolbox / Goodstuff`
   archetype + a warning routing mode choice to the user-feedback flow. Atraxa-style all-low on
   true value-pile commanders is accepted as the honest read.

When the gate holds, Fase 2 = migrate consumers (`wanted_card_patterns`, `suggest`, `deck-gaps`,
`category-counts`) one at a time, tests green between each, then Fase 3.

## Fase 2 consumer priority (from the Gargos BUILDER build)

`category_counts/scoring.py::_score_provides` re-implements oracle heuristics that the analyzer
already computes better (SCOPE_TARGET_OPPOSING_CREATURE, removal detectors...). It is the FIRST
consumer to migrate when the gate opens: commander_scores should read analyzer signals, keeping
the oracle heuristics only as fallback.

## Gate batch #13 (confirmation batch): FAIL (CW 1) — fixed, batch consumed

Blind-first self-run (batch-4 protocol; audit: `logs/gate-validation-batch-13.json`, fixes:
`logs/gate-batch-13-fixround.json`). Tally: right 6 (Feather, Ezuri, Mogis, Savra, Wyleth,
Esika), partial 2 (Jetmir, GAAIV), empty 1 (Roon), wrong 1 (Windgrace, CW). right+partial
8/10 ≥ 6 but CW=1 → FAIL. Positives: aura_equipment_payoff and the DFC split generalized to
fresh commanders (Wyleth very_high, Esika high).

Fixes (all class-level, 13 sentinels pinned → 179-card set, sanity line "180 passed"):
- **Loyalty split (the CW):** only +N:/0: loyalty lines are repeat markers; a minus ability
  consumes loyalty (a big minus is once-per-game) — its token creation is a finisher, not an
  engine. Windgrace Go Wide high→low; 81 minus ultimates stop, 53 plus/0 engines keep.
- **land_recursion vocab:** + "land card(s) from your graveyard to the battlefield" — Windgrace
  now surfaces Lands/Landfall.
- **blink vocab:** + the activated delayed-flicker phrasing (22/22 pure: Roon, Flickerwisp,
  Mistmeadow class) — Roon empty→Blink high.
- **Tax split:** TAX_COST_INCREASE (general tax) promoted to DEFINING Stax; new TARGETED_TAX
  for targeting-conditional taxes (Kopala/Charix/Esior protection class + Hinata) which never
  feeds Stax — GAAIV/Thalia now read Stax high without creating the Erebos CW class.
- **sacrifice_outlet direction:** rebuilt with directional forms (colon-cost / you-may /
  additional-cost); the naked phrase caught opponent edicts ("unless THEY sacrifice" — Mogis).

New known-gap (measured, honest): Jetmir threshold anthems ("as long as you control N or more
creatures") = 3 cards in the DB — too narrow for a rule; every broader form measured dirty
(anthem→defining flips 92 commanders incl. Mikaeus; stacked-anthem catches one-shot tricks).
Jetmir stays partial (Go Wide low, directionally right).

**Per the sequential gate rule the batch is consumed: criterion (c) needs a fresh
confirmation batch #14.**

## Gate batch #14 (confirmation batch): FAIL (CW 1) — fixed, batch consumed

Blind-first self-run (audit: `logs/gate-validation-batch-14.json`, fixes:
`logs/gate-batch-14-fixround.json`). Tally: right 5 (Gisela, First Sliver, Omnath LoC, Tivit,
Brimaz), partial 1 (Marchesa BR), empty 3 (Chulane, Mimeoplasm, Ghyrson), wrong 1 (Queen
Marchesa, CW). right+partial 6/10 ≥ 6 but CW=1 → FAIL. Batch-13 fixes generalized clean:
Tivit's Treasures/Clues did NOT read Go Wide, Brimaz's attacking Cats did, Gisela's
replacement effect wasn't read as a trigger.

Fixes (class-level, 9 sentinels pinned → 188-card set, sanity "189 passed"):
- **Deterrent-token guard (the CW):** token creation conditioned on an OPPONENT state ("if
  an opponent is the monarch / controls more lands than you", "if you have less life") is
  insurance/catch-up, not an army — measured 15 cards, all parity effects. Queen Marchesa
  Go Wide high→low.
- **MONARCH signal:** "becomes? the monarch" → defining Group Hug / Politics (measured ~60
  cards / 13 commanders, all monarch-politics). Queen Marchesa now reads her truth.
- **Reminder-text guard on counterspell:** COUNTERSPELL_INTERACTION matches rules text only
  (ward reminder fed a false Spellslinger band on Ghyrson); the counter-MARKER branch keeps
  reminder text deliberately (dethrone's counters read is real).

**Batch consumed → criterion (c) needs confirmation batch #15.**

## Gate batch #15 (confirmation batch): **PASS — gate criterion (c) satisfied**

Blind-first self-run (audit: `logs/gate-validation-batch-15.json`). Tally: right 5 (Yawgmoth,
Kwain, Syr Konrad — a triple-theme commander reading all three highs correctly, Emiel,
Multani), partial 4 (Zaxara, Grismold, Rielle, Vito — all honest underbands, zero lies),
empty 1 (Animar, honest), wrong 0, **CW 0**. right+partial 9/10 ≥ 6 AND CW=0 → PASS.
Per the PASS protocol no analyzer changes were made; 10 sentinels pinned with
improvement-friendly band lists (198-card set, sanity "199 passed"). **Fase 2 is open.**

## Calibration batch #16 (post-gate, Chishiro by user request): CW 1 — four class fixes

Blind-first self-run (audit: `logs/calibration-batch-16.json`, fixes:
`logs/calibration-batch-16-fixround.json`). Tally: right 3 (Gyome, Sauron, Zada), partial 3
(Raffine, Anje, Locust God), empty 3 (Miirym, Ojer Axonil, Feldon), wrong 1 (Chishiro, CW).
The CW was a **promotion regression**: Chishiro read right in batch #2, then the
`aura_equipment_payoff` → defining-Voltron promotion (certero 67→71 pass) made him read
`Voltron: very_high` — but his payoff scopes "EACH modified creature you control" (wide),
the opposite of one-threat Voltron. First CW of the promotion-regression type.

Fixes (all class-level, 10 sentinels → 208-card set, sanity "209 passed"):
- **Wide-vs-tall exclusion (the CW):** when evidence carries REPEATABLE_TOKEN_MAKER AND
  broad COUNTER_MARKER, aura_equipment_payoff demotes from Voltron defining to supporting.
  Measured over all 24 commanders with the tag: only the Chishiro class has both wide
  signals — Sram/Galea/Wyleth/Kemba/Stangg untouched.
- **attacks_or_combat family + "you attack"** (player-scope form; 156 cards — Raffine,
  Adeline, Inti).
- **Tribal patterns skip an optional "nontoken" qualifier** (Miirym's "another nontoken
  Dragon"; negation guard for "non-Human" intact).
- **New GRAVEYARD_CLONE conjunction detector** (same-line graveyard + copy; 90 cards
  measured, all genuine — Lazav family, Scarab God, Feldon, embalm/eternalize cycle) →
  defining Graveyard Value. **Closes the batch-14 Mimeoplasm known-gap.**

## Known-gaps session (post-gate, 2026-07-04): the annotated backlog worked

Live verification found the batch-11 list and Galea ALREADY CLOSED by later fix rounds
(stale annotations), one NEW confidently-wrong regression, and four workable gaps. All
fixes measured against the DB; sentinels pinned; suite 1025 green, sanity "211 passed"
(the golden set also got 5 historical duplicate-name entries consolidated — 210 unique
sentinels).

- **Volo CW regression (batch-16 fallout) FIXED:** GRAVEYARD_CLONE fired on Volo's
  REMINDER text ("(A copy of a creature spell becomes a token.)") next to a NEGATIVE
  graveyard condition — a false `Graveyard Value: high`. The detector now strips reminder
  text (the batch-14 lesson applied at a second site) with two measured compensations:
  embalm/eternalize keywords (their copy semantics live only in reminder) and the
  directional "from ... graveyard ... copy it/them/that card" recast form (Kaervek/Nashi/
  Shiko class). Re-measured: 112 cards all genuine; 7 reminder FPs dropped, 20 genuine
  recasters gained. Volo returns to honest empty (clone/copy value archetype REMAINS a
  known-gap, per honesty-over-coverage).
- **Sygg (batch-8) FIXED:** new LOST_LIFE_PAYOFF regex detector ("(an opponent|a player|
  each opponent|each player) lost (N or more )?life this turn") — the threshold variant is
  a variable-number class the substring vocabulary cannot enumerate (SAC_OUTLET lesson).
  40 cards measured, all genuine (spectacle cycle, Bloodchief Ascension); "you've lost
  life" self-payoffs excluded. Defining Life Loss / Group Slug (Tymna precedent). Sygg
  empty→high.
- **Vito (batch-15) IMPROVED:** lifedrain gains "target opponent loses" (104 cards
  measured, all drain). Vito low→medium (honest, floor pinned).
- **Old Stickfingers (batch-5) FIXED:** new GRAVEYARD_SCALING detector ("equal to (twice )
  the number of ... in your graveyard", 46 cards measured — the Lhurgoyf/Undergrowth
  class), supporting Graveyard Value; self_mill gains "revealed this way into your
  graveyard" (6) and "rest into your graveyard" (76, the Commune with the Gods class).
  Stickfingers empty→medium.
- **Elder Brain (backlog) FIXED:** new THEFT_EXILE conjunction detector — same-line
  exile + opponent-zone + "you may play/cast", order-free (Gonti's zone precedes the
  verb), reminder text stripped (Kaervek's crime reminder says "their graveyards" while
  he recasts his OWN), "you own" excluded (Triple Triad self-play). 97 cards measured,
  all genuine you-play-theirs. Elder Brain, Etali, Stolen Strategy read Theft high.
  **Data-drift catch:** Gonti, Lord of Luxury had silently LOST his Theft read — the
  fresh Scryfall data reworded him away from the measured "don't own" phrase. THEFT_EXILE
  restores it; sentinel pinned. Lesson: oracle rewording can invalidate measured phrases —
  golden pins on the CARD (not the phrase) are what catch it.
- **Surrak (batch-8): honest empty, documented.** Protection + trample support
  ("creature spells can't be countered") defines no archetype without forcing (Jetmir
  precedent).

## Known-gaps (annotated, non-blocking)

NEW findings from the known-gaps session (2026-07-04):
- **morph_facedown FP class:** Gonti, Lord of Luxury reads `Morph / Face-down: high`
  because "exile one of them face down" matches the morph tag — exile-face-down
  (Gonti/Kotose class) is not a morph deck. Needs a measured direction split of the
  "face down" phrases (turn-face-up context vs exile context).
- **theft tag "exiled with" is dirty:** measured 191 cards — ~38 opponents' cards, ~76
  OWN-card impulse/storage (Bomat Courier, Colfenor's Plans — the latter reads a false
  `Theft: high` today), ~77 O-Ring-style exile-removal. Removing it outright would lose
  the multi-line Nightveil Specter class (trigger on one line, play-permission on
  another); needs a measured rebuild with directional forms.

From calibration batch #16: madness class (Anje), amass mechanic (Sauron), Locust God
wheels co-primary underband (Marchesa BR class).

From gate batch #15 (all honest underbands/empties, fix post-gate): cast-creature engine
class (Animar + Chulane — "whenever you cast a creature spell" cost-reduction/draw engines
read nothing), X-spell payoff class (Zaxara — "spell with {X} in its mana cost"), the 0/X
utility-token rule misreads 0/0-with-X-counters tokens as fodder (Zaxara's Hydras), wheel
vocab misses "discard one or more cards for the first time each turn" (Rielle), Grismold
death-payoff co-primary underbands. (Vito lifedrain: fixed above.)

From gate batch #14: Chulane (cast-creature draw engine has no archetype), Ghyrson Starn
("deals exactly N damage" pinger payoff unread), Marchesa BR (dethrone counters co-primary
underbands at low). (Mimeoplasm: closed by batch #16 GRAVEYARD_CLONE.)

From gate batch #11: ALL FIVE CLOSED by the batch-11 fix round (verified live 2026-07-04:
Tymna, Xenagos, Kozilek, Jhoira, Ikra all read their archetype high) — the known-gap
annotation was stale.

From gate batch #8: Sygg FIXED (above); Surrak documented honest empty.

From gate batch #5: Volo FP fixed + honest empty (clone/copy value archetype still a gap);
Galea CLOSED by the aura_equipment_payoff promotion (stale annotation); Old Stickfingers
FIXED (above).

Golden-judging backlog (5 verified misses): ALL FIXED — death-doubler context, "artifact spell",
mill phrasings, symmetric pingers, regex SAC_OUTLET. Sentinels pinned (68-card set).

- Trigger-doubler cast-context not extracted (covered today by tag redundancy — Veyran reads right
  via magecraft).
- Legacy `archetype_fit` remains confidently wrong on some commanders; that is expected and why the
  preference rule exists.
