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
- **Fase 2 — consumers switch: NOT STARTED. Gated (below).**
- **Fase 3 — retire legacy `archetype_fit`: NOT STARTED.** Only when no consumer reads it.

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

## Known-gaps (annotated, non-blocking)

From gate batch #11 (honest empties/partials, fix in a future session): Tymna (combat-damage-to-
opponents draw phrasing), Xenagos (power-doubling go-tall — "X is its power" not in POWER_MATTERS),
Kozilek (colorless battlecruiser), Jhoira (historic/storm), Ikra (toughness-matters, same class as
Arcades defenders).

From gate batch #8 (PASS — streak 1/2; fixes FROZEN until the streak resolves): Sygg (opponent
lost-life-this-turn draw niche) and Surrak (flash/uncounterable creature-combat support) read
honest empty. Fix AFTER the gate.

From gate batch #5 (judged honest, not gate-breaking): Volo (clone/copy value has no archetype),
Galea (Aura/Equipment Voltron underbanded — equipment/aura tags are supporting-only), Old
Stickfingers (tutor-to-graveyard self-mill niche reads empty).

Golden-judging backlog (5 verified misses): ALL FIXED — death-doubler context, "artifact spell",
mill phrasings, symmetric pingers, regex SAC_OUTLET. Sentinels pinned (68-card set).

- Trigger-doubler cast-context not extracted (covered today by tag redundancy — Veyran reads right
  via magecraft).
- Elder Brain theft phrasing ("exile ... then you may play them") not in the theft tag.
- Legacy `archetype_fit` remains confidently wrong on some commanders; that is expected and why the
  preference rule exists.
