# Archetype migration: legacy `archetype_fit` → evidence-first `analyzer.archetype_support`

**MIGRATION COMPLETE (v0.8.0).** Strangler-fig migration of the archetype system. The legacy
`archetype_fit` (weighted text scores, magic numbers) has been fully replaced by the analyzer's
`archetype_support` (ordinal bands with evidence traces), and the legacy fields were REMOVED in
v0.8.0. `analyzer.archetype_support` is now the ONLY archetype read; `analyzer.tags`/`signals`
are the single source for the commander's functions. Each phase was additive/reversible; the
legacy path was removed once nothing consumed it.

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
- **Fase 3 — retire legacy `archetype_fit`: REMOVAL SHIPPED (v0.8.0). Migration COMPLETE.**
  The legacy fields were physically DELETED from `commander_analysis.json`: `archetype_fit`,
  `commander_tags`, `commander_type_tags`, `synergy_tags`, `anti_synergy_tags`, and the
  interim `legacy_deprecations` block (also gone). category-counts dropped its
  `archetype_fit_score` field. The analyzer embed's `tags` list is the single source for the
  commander's functions, and `best_archetype` is now derived from the top analyzer band. All
  agent files (BUILDER §7.0b, agents/commander_analyzer.md, agents/system.md, CLAUDE.md,
  README) point exclusively at `analyzer.archetype_support`/`analyzer.tags`.

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

## The qualifier-interruption GENERAL mechanism (2026-07-06): wildcard tag phrases

The standing structural gap (5 sightings — Mirko #21 the founding member, Hallar #22,
Kumena #30, Athreos #28, and Angelic Accord as the FIRST production case in full build
#3, where deck-gaps undercounted a genuinely-covered category) is CLOSED as a
mechanism, not another literal variant:

- **`utils/phrase_match.py`** — single source of truth for tag-phrase matching. A
  phrase may carry the ``" * "`` wildcard: literal parts in order with a BOUNDED
  same-clause gap (40 chars, never crossing `.`/`;`/newline). An unbounded gap would
  recreate the naked-substring false positives this project keeps killing; the bound
  covers every measured sighting ("you own" 7, "4 or more" 9, "with power less than
  Mirko's" 29) with margin.
- **All SIX phrase consumers ported** (cards/search.py SQL via `phrase_to_like`
  %-mapping + Python rank re-check, deck_check ×2, card_profile — which feeds the
  analyzer's matched_tags —, suggestion_scorer, ramp_rules, deck-gaps `_matching`):
  the multi-consumer drift class is structurally closed for phrase matching. Plain
  phrases behave byte-for-byte as before — zero behavior change until a wildcard
  phrase ships.
- **First wildcard phrases, measured:** reanimation "creature card * from your
  graveyard to/onto the battlefield" (273+2, all genuine — **Mirko reads Reanimator
  very_high**, Alesha's power-2-or-less form is a free improvement, Otrimi's to-HAND
  control still excluded because the phrase anchors the battlefield tail) and
  lifegain_payoff "you gained * life this turn" (57/57 — **Angelic Accord reads
  Lifegain Matters high**; Ragost's deck-gaps count went 4→6).

Same round: deck-gaps' plan check now returns and prints WHICH cards it counted
(`analyzer_support[].cards`, `plan_gaps[].cards`, human "counted: ..." line) — the
fix-or-justify decision no longer requires guessing. Mirko pin updated + Angelic
Accord/Alesha sentinels (376-card set, sanity "377 passed"); suite 1218 green.
Audit: logs/polish-media-items.json.

## Post-30 fix round (2026-07-06, user-requested): the mature 2-member queue closed

Two NEW archetypes, six measured tag extensions, one STRUCTURAL tribal fix, two
measured rejects (suite 1199 green, 374 sentinels, sanity "375 passed"; audit:
logs/post-30-fixround.json):

NEW archetypes: **Devotion** ("devotion to" 67/67 clean — Nylea's #21 honest empty
CLOSED; Klothys and Athreos read their god clauses; Gray Merchant pinned as the
payoff-side control) and **Coin Flips** (payoff forms only: "wins a coin flip" 4 +
"flip you win" 4 — Yusri/Okaun/Zndrsplt; the naked "flip a coin" 81 REJECTED like
the d20-roller class).

Extensions (all measured): spell_payoff += "instant and sorcery spells you cast
cost" (22/22 all LESS-direction — **the Electromancer gap closed: Vadrik #26 and
Baral #29 read Spellslinger high**); clone_copy += "becomes a copy of" (73 clones —
**Volrath #26 and Brudiclad #29 read Clones high**; the Krark "copy that spell"
guard untouched); group_hug += "attacking player draws" (2/2 incentive — Breena
reads the Goad + Politics + Counters triple); death_trigger += "another creature
you own dies" (1/1 qualifier variant — Athreos reads Aristocrats high); land_payoff
+= "land you control is put into a graveyard" (2/2 with Long Feng — Titania reads
Lands + Go Wide, her full truth); investigate += "you sacrifice a clue" (14/14
payoffs).

STRUCTURAL (the real Thelon root cause, batch #30): the tribal capture's lazy
`+?` with optional `s?` ate the trailing s of s-ENDING types ("Fungus"→"fungu",
"Pegasus"→"pegasu") and -ves plurals captured "elve"/"wolve" — none ever hit the
whitelist. Word resolution now tries raw / s-stripped / s-restored / ves→f
candidates (Thelon reads Fungus Tribal high; Elvish Archdruid-class anthems
improve). Plus a NEW global-anthem pattern "(all|each) <Type> get" — whitelist-
filtered (26 regex hits, tribal-clean: Slivers, Saprolings, Nightmares, Squirrels;
"all CREATURES get" / "each ATTACKING creature" excluded by the whitelist).

REJECTED measured-dirty: "target opponent draws" (4/8 are leave-the-battlefield
drawback RIDERS — the Thought-Knot Seer class, pinned as guard; Bumbleflower's hug
half stays honest-missing on the naked form) and naked "flip a coin". DEFERRED:
the general qualifier-interruption mechanism (regex-tags — 4+ members, but every
member so far closed via a cheap measured variant; revisit if a member appears
that variants can't express). Twelve pins updated to lock the new truths + 2 new
guards (374 sentinels).

## Calibration batch #30 (post-gate, blind-first, 2026-07-06): FAIL — fixed; THE
## 30-BATCH PLAN IS COMPLETE

Tally: right 5 (Kotori — **Vehicles validating fresh** on the crew-enabler form —,
Klothys — symmetric-pinger slug + punisher warning —, Kumena — the clean "each
Merfolk you control" in mode 3 fired tribal despite the untapped-qualifier in modes
1–2, beating the blind —, Eloise — Aristocrats + clue value engine —, Edgar, Charmed
Groom — Vampire Tribal + Go Wide, and the DFC control of the batch: the Coffin's
bloodline counter read COUNTER_MARKER_SELF, so the per-face card_name plumbing
works), partial 2 (Titania — the land-GY family's 3rd form "a land you control is
put into a graveyard from the battlefield" —, Thelon — global symmetric anthem "Each
Fungus creature gets" misses the tribal patterns; his Counters high is true), empty
2 (Michiko — generic incoming-DAMAGE form, the 3rd incoming variant —, Yusri —
coin-flip class), **CW 1 → FAIL** (unpredicted — the blind watched Grimgrin's
destroy-effect boundary, not his untap drawback):
- **Grimgrin:** `Stax: high` from "Grimgrin enters tapped and doesn't untap during
  your untap step" — his OWN drawback, at BOTH layers: UNTAP_RESTRICTION was missing
  from the SELF_RESTRICTION guard's signal list (the #18 audit-the-alternation
  lesson applied to a guard's SIGNAL list), and the stax TAG carried a naked
  "doesn't untap" (the scope-check-only-in-signal-layer annotation finally producing
  a real lie). Fixed at both: the guard now covers UNTAP_RESTRICTION (self subject
  before + "during your untap step" after — so Winter Orb's "their controllers'" and
  Frost Titan's "its controller's" keep their true Stax) with _self_subjects
  extended to this artifact/land/enchantment (the Mana Vault class); the tag split
  directionally ("doesn't untap during its controller" 179 + "don't untap during
  their controllers" 35 stay; the your-untap-step drawback form 54 out). Controls:
  Winter Orb, Frost Titan, Meekstone, Mana Vault, Medomai, Peacekeeper — all green.
  Grimgrin reads Aristocrats medium (SAC_OUTLET), his truth.
New known-gaps: coin-flip class (Yusri), generic incoming-damage (Michiko — 3rd
incoming form), land-GY 3rd form (Titania), global symmetric anthem (Thelon),
devotion 2nd member (Klothys). Twelve sentinels — 10 batch + Winter Orb/Mana Vault
untap-split controls (372-card set, sanity "373 passed"); suite 1197 green. Audits:
logs/calibration-batch-30.json, logs/calibration-batch-30-fixround.json.

**Plan status: 30/30 batches complete.** Post-gate record: 7 PASS / 7 FAIL-fixed,
every CW root-caused and pinned same-session; zero unfixed lies across the entire
run. The mature two-member gap queue for the next fix round: Electromancer typed
cost-reduction (Vadrik + Baral), "becomes a copy" (Volrath + Brudiclad), gift-draw
(Bumbleflower + Breena), qualifier-interruption general mechanism (4 members),
investigate-defining (Lonis + Eloise), devotion (Nylea + Klothys).

## Calibration batch #29 (post-gate, blind-first, 2026-07-06): FAIL — the attack
## DIRECTION family completed (all four directions), plus the #11 name class at a
## second site

Tally: right 3 (Beckett Brass — Pirate + Theft + Attack triple true —, Wort —
conspire copy-slinger via the typed instant/sorcery form —, Cadira — deployment side
of #19), partial 4 (Baral — **2nd ELECTROMANCER member confirmed**, the #26 typed
cost-reduction gap is now firmly measurable —, Brudiclad — **2nd "becomes a copy"
member** —, Go-Shintai — Shrine identity unread —, Atraxa PV — the proliferate-only
class: 4 honest lows, no defining), empty 0, **CW 3 → FAIL** — all three ONE family
(attack/restriction direction-scope), two predicted blind as high risk:
- **Medomai (CW 1):** `Stax: high` from "Medomai can't attack during extra turns" —
  his OWN drawback. The SELF_RESTRICTION guard built its subject via split(",")[0],
  which keeps the FULL name for no-comma legends while oracle text uses the first
  name — the batch-11 name class at a SECOND site (semantics.detect_negation).
  Fixed: first-name subject fallback (articles skipped). Gadrak/Peacekeeper controls
  green. Extra-turns class = new known-gap.
- **Breena (CW 2, predicted):** `Attack Triggers: high` from "Whenever a player
  attacks one of your opponents" — the THIRD-PARTY direction (the table attacking
  your opponents = politics incentive). The attack family now knows all FOUR
  directions: self / board / incoming-you / third-party. Fixed: new
  THIRD_PARTY_ATTACK_INCENTIVE signal → Goad / Forced Combat defining (measured 14,
  all incentive class: Calculating Lich, Maeve, Gahiji, Combat Calligrapher, Death
  Kiss; Mazzy borderline accepted — raw text is table-scope). Breena reads Goad +
  Counters, her truth. Marisi/Cadira controls green.
- **Teysa EoG (CW 3, predicted):** `Attack: high` + `Go Wide: high` from "Whenever a
  creature deals combat damage to YOU, destroy it. Create a Spirit" — the
  saboteur-INVERSE incoming form escaped the #22 guard ("attacks you"), and her
  compensation Spirits fed the token conjunction. Fixed: incoming regex extended
  with "deals combat damage to you" (measured 7/7 defensive: Hixus, Contested War
  Zone, Harsh Justice) + incoming-compensation guard in the token conjunction
  (measured 2/2: Teysa's Spirits, Search the Premises' Clue). She reads Pillowfort
  high. Isperia control green.
New known-gaps: extra-turns class (Medomai), Shrine identity (Go-Shintai — Shrine is
an enchantment type outside the creature whitelist), proliferate-only commanders
under-banded (Atraxa PV — proliferate defines nothing), gift-draw 2nd member
(Breena's "that attacking player draws" joins Bumbleflower's), "becomes a copy" 2nd
member (Brudiclad joins Volrath), Electromancer 2nd member (Baral joins Vadrik —
ripest two-member gap in the queue). Ten sentinels — 3 CW pins with signal asserts
(360-card set, sanity "361 passed"); suite 1185 green. Audits:
logs/calibration-batch-29.json, logs/calibration-batch-29-fixround.json.

## Calibration batch #28 (post-gate, blind-first, 2026-07-06): PASS

Tally: right 5 (Vadmir — **Crimes Matter (#27) validating fresh**, his self counters
correctly SELF —, Trelasarra — **Lifegain Matters (#27) validating fresh** —, Fain —
**MODAL_TOOLBOX validating fresh** on a virgin member of the measured 4-commander
class: menu warning fired, per-mode bands are options —, Neheb the Worthy — Minotaur
Tribal; his saboteur discard is VALUE, no Attack band —, Runo//Krothuss — DFC split
working; copies entering TAPPED AND ATTACKING = the deployment side of the #19
boundary, Attack high TRUE, plus Clones), partial 3 (Light-Paws, Marina Vendrell,
Ms. Bumbleflower), empty 2 (Ulamog CH, Athreos — both honest), **CW 0** → the SEVENTH
post-gate PASS. The #19 attack boundary held on BOTH sides in one batch (value-side:
Neheb, Ulamog; deployment-side: Krothuss). Zero changes per PASS protocol. New
known-gaps, all measurable:
- Aura-cast-enters payoff (Light-Paws: "Whenever an Aura you control enters, if you
  cast it" — not in aura_equipment_payoff).
- Rooms/doors class (Marina: "lock or unlock a door", "Room you control") +
  enchantment-dig-to-hand form ("put all enchantment cards from among them into your
  hand").
- Gift-draw hug form (Bumbleflower: "target opponent DRAWS a card" imperative —
  group_hug only carries "target opponent may draw"; alternation gap).
- **Qualifier-interruption 4th member** (Athreos: "another creature YOU OWN dies") —
  the general regex-tag mechanism (Mirko/Tayam/Hallar) gains pressure.
- Defending-player exile-mill (Ulamog: "defending player exiles the top twenty
  cards") + eldrazi-titan battlecruiser class (no annihilator text).
- Symmetric each-player discard (Neheb's hellbent half — small).
Ten sentinels (350-card set, sanity "351 passed"); suite 1175 green.
Audit: logs/calibration-batch-28.json.

## Calibration batch #27 (post-gate, blind-first, 2026-07-06): FAIL — fixed, plus
## two new archetypes

Tally: right 6 (Anthousa — **Targeted Spell Payoff / Heroic validating fresh** on the
heroic ability-word form; her Warrior Tribal high from animated-land token types is a
plan-aligned watch-item —, Satsuki — **Sagas Matter validating fresh**, with Counters
via lore-counter MANIPULATION, the Vorel class: proliferate genuinely accelerates
Sagas —, Higure — **Ninjutsu / Sneak validating fresh** + Ninja Tribal via the #19
tutor pattern; his saboteur self-trigger correctly did NOT band Attack, the #19/#20
boundary held —, Henzie — Creature Spells + Aristocrats both true; the blitz REMINDER's
death-value read is the tags-see-reminder family landing defensible again —, Phylath —
Landfall high via the M5 ability-word strip —, Inalla — Wizard Tribal + Clones + Life
Loss triple true; the EPHEMERAL guard kept Go Wide out), partial 2 (Aragorn KoG —
**MONARCH validating fresh**; his attack-enabler half unread —, Amalia), empty 1
(Marchesa, Dealer of Death — honest), **CW 1 → FAIL**:
- **Jhoira of the Ghitu:** `Counters Matter: high` from sense.counter_marker.v1
  matching "put four time counters on" — but suspend time counters are a COUNTDOWN
  (fewer = the card casts sooner): proliferate is actively ANTI-plan. The
  counter-direction family (Grenzo #12, batch-19 untap) in the counter-sense layer.
  **FIXED structurally: new COUNTER_CLOCK sense** — a put-time-counters form whose
  same line (reminder-stripped) carries suspend-countdown context (gains/has/have
  suspend, is suspended, "last time counter is removed" — the alternation audited per
  the #18 lesson, catching Alaundo's TEXTUAL grant and Curse of the Cabal) never feeds
  Counters Matter. Measured over all 39 "put ... time counter(s) on" cards: 12/12
  countdown-grants excluded, 27 accumulators kept (Rose Tyler, Kate Stewart, As
  Foretold — where MORE counters is the plan). Controls held: Kate Stewart (accumulator
  keep side, pinned), Rose Tyler (SELF), Vorel (doubling), Satsuki (lore manipulation).
Coverage same round: NEW archetype **Crimes Matter** (the crime class hit its 2nd
commander-member — conditional-rider revocation precedent; `crime_payoff`: "you commit
a crime" 19 + "you've committed a crime" 7, all your-crime payoffs, the opponent form
excluded — Marchesa DoD empty→high, Magda the Hoardmaster reads Crimes + Treasures);
NEW archetype **Lifegain Matters** (pure MAPPING fix, Fynn/Poison precedent — the
`lifegain_payoff` tag existed with "whenever you gain life" 88 but fed no archetype;
generic `lifegain` stays out per the Tatyova lesson — Amalia reads her truth, Vito
reads Lifegain high + drain medium, both true). New known-gaps: suspend archetype
(Jhoira honest-empty — payoff-form vocab would be reminder-dirty), can't-block-as-
offense (Aragorn: BLOCK_RESTRICTION inside your own attack trigger's effect is
combat-feed, not stax — measurable), blitz keyword class (Henzie), explore keyword
(Amalia). Twelve sentinels — 10 batch + 2 clock-split controls (340-card set, sanity
"341 passed"); suite 1165 green. Audits: logs/calibration-batch-27.json,
logs/calibration-batch-27-fixround.json.

## Calibration batch #26 (post-gate, blind-first, 2026-07-06): PASS

Tally: right 6 (Beluna Grandsquall — **Adventures Matter validating fresh** —, Farideh —
**Dice Rolling validating fresh**, the ability-word prefix stripped by the M5 fix —,
Yeva — **Flash / Instant Speed validating fresh on the enabler form** that motivated the
archetype —, Daxos the Returned — Enchantments + Go Wide double-high, experience counters
read via SCALES_WITH with no false Counters band —, Rakdos, Lord of Riots — Creature
Spells + Life Loss double-high; LOST_LIFE_PAYOFF caught the cast condition "an opponent
lost life this turn", beating the blind prediction of medium —, Volrath — Minus Counters
high), partial 4 (Ishkanah, Kathril, Yasharn, Vadrik — all honest, mechanism identified),
empty 0, **CW 0** → the SIXTH post-gate PASS, fourth consecutive. Three of the seven
post-#25 archetypes validated on virgin commanders in one batch. Blind calibration:
predicted right ~6 / partial ~4 / CW 0-1 — landed exactly (Vadrik and Volrath swapped
right/partial). Guards that held: Ishkanah's one-shot ETB tokens correctly NOT Go Wide;
Kathril's final +1/+1 correctly COUNTER_MARKER_SELF; Beluna's imperative "Mill seven
cards" (self-fill to hand) never read opponent Mill. Zero analyzer changes per PASS
protocol. New known-gaps, ALL measurable:
- **Typed spell cost-reduction → Spellslinger** (Vadrik: "Instant and sorcery spells you
  cast cost {X} less" only fires the generic cost_reducer tag — the Goblin Electromancer
  family; the ripest gap of the batch).
- Delirium class (Ishkanah: "four or more card types among cards in your graveyard" —
  GY-card-types payoff family).
- Anti-sac/pay-life stax form (Yasharn: "Players can't pay life or sacrifice nonland
  permanents" — symmetric hatebear, not in the post-#9 stax vocab; predicted blind).
- Keyword-counter class (Kathril: named ability counters placed from GY keywords +
  GY-as-resource dependency).
- Clone form "becomes a copy of" (Volrath — outside the Clones phrases; watch the Krark
  guard if extending; predicted blind).
Ten sentinels (328-card set, sanity "329 passed"); suite 1153 green.
Audit: logs/calibration-batch-26.json.

## Full build #2 calibration note (2026-07-05): the speed mechanic

Mendicant Core, Guidelight (Aetherdrift "Start your engines!") read `Artifacts Matter:
high` (true) + `Life Loss / Group Slug: high` — the latter from the REMINDER text of
the speed keyword ("It increases once on each of your turns when an opponent loses
life"). The band is strategically right by accident (a speed deck genuinely wants
opponents losing life every turn), but it produced a spurious deck-gaps plan_gap
(0 slug cards) that had to be consciously justified (thopters attacking raise speed).
Known-gap: the **speed mechanic has no class** ("start your engines!" / "max speed" —
measure when more speed commanders appear); the tags-see-reminder family strikes again,
this time landing on a defensible read.

## Post-#25 fix round (2026-07-05, user-requested): the #23–#25 measurable queue closed

Seven NEW archetypes, six extensions, two structural fixes — every measurable gap from
batches #23–#25 closed (suite 1140 green, 318 sentinels, sanity "319 passed"; audit:
logs/post-25-fixround.json):

NEW archetypes: **Targeted Spell Payoff / Heroic** (the Gargos/Anax/Ivy family —
**Gargos, the project's ORIGINAL calibration class, finally reads his own plan**;
"heroic —" 46 + "you control becomes the target of a spell" 25 + "spell that targets
only a single" 12), **Dice Rolling** (Wyll + Mr. House; payoff forms only), **Flash /
Instant Speed** (Raff + Errant and Giada), **Storm** ("storm (" keyword form 42 — the
naked substring REJECTED with 19 self-reference FPs like Windstorm), **Ninjutsu /
Sneak** (50), **Adventures Matter** (25), **Cycling** ("you cycle" 86).

Extensions: exploit → Aristocrats supporting (Sidisi UV medium), escape_gy → GY Value
supporting (Uro medium), investigate → Treasures supporting (Lonis), land_payoff +
singular "land card is put into your graveyard" (Slogurk Lands HIGH), extra_land_drop +
"land card from your hand onto the battlefield" (51 — the Uro/Kodama form), reanimation
+ "permanent card from your graveyard to the battlefield" (14, directional), POWER_MATTERS
+ "greatest power among" (PS Zegana Stompy HIGH), self_mill + PUNCTUATED imperative
forms.

Structural: (1) **modal-bullet merge** — bullet lines now belong to their header
ability in the token conjunction (Caesar reads Go Wide HIGH; the recurring layout
cause #2 closed for REPEATABLE_TOKEN_MAKER); (2) **"you control attack"** added to the
attacks_or_combat family at the oracle_hooks single source (Neyali reads Attack HIGH —
plural board subjects like "tokens you control attack a player").

The net at work: the naked "mill a card" matched Bruvac's REMINDER text and his
historical pin caught it within seconds → replaced with punctuated imperative forms
("mill a card." / "mill a card, then" — 39+57+70+5+14+22 measured, Bruvac excluded);
the unpunctuated forms were latent FPs ("target player mill two cards"). Sixteen pins
tightened. Still open (honest): Mothman's Mill-archetype band (his self_mill low is
correct), the GENERAL qualifier-interruption mechanism (Mirko/Tayam — needs regex-capable
tag phrases), tags-see-reminder (deliberate family).

## Calibration batch #25 (post-gate, blind-first, 2026-07-05): PASS

Tally: right 5 (Zevlor, Balmor, Eriette — Pillowfort + Life Loss + Stax triple, the
#22 Pillowfort archetype validating fresh —, Bright-Palm — the Vorel counter-doubling
class —, Mr. House), partial 4 (Lonis — his clue-steal reads genuine THEFT_CONTROL —,
The Wise Mothman, Old Rutstein, Ivy), empty 1 (Gorion, honest), **CW 0** → the FIFTH
post-gate PASS, third consecutive. Process note: "Zimone, Wisdom Faucet" turned out to
be an invented name — the not-found path caught it before use (verify-early working as
designed); replaced with Old Rutstein. New known-gaps:
- Adventure class (Gorion — and spell_copy correctly did NOT fire on "copy it": no
  Spellslinger lie, pinned as guard).
- Investigate/clue class (Lonis).
- PASSIVE mill form "cards are milled" (Mothman) and IMPERATIVE mill form "mill a
  card" — now a 3-member family (Kagha, Tayam, Rutstein).
- Dice-roll class now 2 members (Wyll + Mr. House) — measurable.
- **Targeted-spell-payoff / heroic archetype (Ivy)** — the Gargos/Anax/Ivy family has
  3+ members and oracle_hooks already detects it (targeted_spell_payoff engine); the
  ripest archetype candidate in the queue.
Ten sentinels (318-card set, sanity "319 passed"); suite 1140 green.
Audit: logs/calibration-batch-25.json.

## Calibration batch #24 (post-gate, blind-first, 2026-07-05): PASS

Tally: right 4 (Gavi — Wheels + Go Wide via the session-2 draw_trigger_payoff —, Kamiz,
Tazri — the #18 Party archetype validating fresh —, Gyrus — Attack + Clones + GY Value
triple-high, and the predicted ephemeral-variant risk did NOT materialize), partial 4
(Sidisi UV, Anax and Cymede, Prime Speaker Zegana, Uro — the Zur rule correctly
suppressed his value "enters or attacks"), empty 2 (Satoru, Malfegor — honest), **CW 0**
→ the FOURTH post-gate PASS, second consecutive. Zero changes per protocol. New
known-gaps (all measurable): ninjutsu class (Satoru — no tribal word either), heroic
ability-word class (Anax — the trigger family reads, no archetype), exploit class
(Sidisi UV), escape class (Uro), "greatest power among" comparative (PS Zegana),
land-put-from-hand form (the Uro/Kodama family), cycling keyword (Gavi reads right
regardless). Ten sentinels incl. Gyrus pinned with must_not Go Wide (his end-of-combat
copies) and Uro as Zur-rule control (308-card set, sanity "309 passed"); suite 1130
green. Audit: logs/calibration-batch-24.json.

## Calibration batch #23 (post-gate, blind-first, 2026-07-05): PASS

Tally: right 4 (Caesar, Otharri, Baeloth — the #19 Goad archetype validating fresh —,
Shanid — Legendary Matters validating), partial 5 (Wyll, Aeve, Neyali, Tayam, Slogurk),
empty 1 (Errant and Giada, honest), **CW 0** → the THIRD post-gate PASS (#17, #21,
#23). Zero analyzer changes per protocol. Direction guards held: Neyali's and Errant &
Giada's SELF-library impulse never read Theft. New known-gaps — all MEASURABLE,
queued for the next fix round:
- Token-attack trigger form: "one or more TOKENS you control attack" misses the attack
  family (Neyali stuck at lows; the board forms expect creatures).
- Singular/plural: "a land card IS put into your graveyard" misses the Gitrog phrase
  ("land cards ARE put") — Slogurk at lows.
- Flash-enabler class now has 2 members (Raff #22 + Errant and Giada) — measurable.
- Storm keyword class (Aeve — his Ooze Tribal read is right, storm is the missing half).
- Dice-roll class (Wyll).
- Reanimation type-variant: "return a PERMANENT card ... from your graveyard to the
  battlefield" (Tayam — the phrase family only knows creature cards).
- Modal BULLETS break the same-line token conjunction (Caesar's tokens at low — the
  recurring layout cause #2; the bullet line holds "create" but the trigger sits on the
  header line).
Ten sentinels (298-card set, sanity "299 passed"); suite 1120 green.
Audit: logs/calibration-batch-23.json.

## Calibration batch #22 (post-gate, blind-first, 2026-07-05): FAIL — fixed, and a
## standing gap closed

Tally: right 1 (Millicent — quadruple-high, all four true), partial 7, empty 1 (Tom
Bombadil), **CW 2 → FAIL**:
- **Isperia (PREDICTED blind):** "Whenever a creature attacks YOU" banded Attack
  Triggers — direction inversion (incoming attack = defense). Fixed: new
  INCOMING_ATTACK_TRIGGER guard (19/19 measured pillowfort) + NEW archetype
  **Pillowfort / Defense** (defining: pillowfort tag + the new signal). Isperia reads
  her truth.
- **Hallar:** `Spellslinger: high` from "whenever you cast a spell, IF that spell was
  kicked" — the SECOND member of the conditional-rider class, revoking the batch-20
  "1-card" ruling. Measured properly: **23 cards**, all "cast a spell, if <rider>"
  forms (mana thresholds, kicked, bargained, treasure-mana). Fixed structurally: new
  CONDITIONAL_CAST_RIDER detector + a mapper exclusion (the batch-16 wide-vs-tall
  precedent) — a non-spell-type rider demotes spell_payoff from Spellslinger defining
  to supporting. **The batch-20 standing known-gap is CLOSED: Raggadragga now reads
  Spellslinger low.** Controls held: Birgi (no rider) and Alania (rider names
  instant/sorcery) keep their genuine highs.
Coverage same round: NEW archetype **Sagas Matter** (~15 measured; "lore counter"
REJECTED — 239 matches would band every printed Saga) — Tom Bombadil empty→high;
plural pair-anthem tribal patterns ("Skeletons and Zombies you control", 29 pairs) —
Gisa reads Zombie + Skeleton Tribal; `graveyard_recast` += "from among cards in your
graveyard" (4/4) — Kagha medium→high. New known-gaps: **tags see reminder text**
(Raff read Artifacts high from "(Artifacts, legendaries...)" — no global strip:
attacks_alone/poison DELIBERATELY rely on reminder text; a per-tag strip list would be
the fix if it ever produces a real lie), kicker class (tiny), crime class, deploy-chain
(Kodama ET), flash-enabler (Raff). Qualifier-interruption grew to 3 instances (Mirko,
Hallar's drain, Kagha — Kagha's form fixed via phrase; the general regex-tag mechanism
still open). Eleven sentinels + 2 updates (288-card set, sanity "289 passed"); suite
1110 green. Audit: logs/calibration-batch-22.json.

## Calibration batch #21 (post-gate, blind-first, 2026-07-05): PASS

Tally: right 6 (Moraug, Osgir, Karlach, Dina — very_high on her drain —, Birgi, Myrkul),
partial 3 (Mirko, Ranar, Strefan), empty 1 (Nylea honest), **CW 0** → the second
post-gate PASS (with #17). Zero analyzer changes per protocol. Generalization
positives: GRAVEYARD_CLONE caught Osgir's PLURAL "create two tokens that are copies"
(the singular clone_copy tag would have missed it); the comma-form spell_payoff read
Birgi's ritual storm correctly (confirming the Raggadragga gap is the RIDER, not the
phrase); the Kaalia rule read Strefan's "tapped and attacking" cheat as a true attack
theme. New known-gaps:
- **Qualifier-interruption (GENERAL class):** Mirko's "return target creature card
  WITH POWER LESS THAN MIRKO'S from your graveyard to the battlefield" breaks the
  contiguous reanimation phrase → medium instead of high. Same family as the tribal
  nontoken-skip (batch #16); candidate fix: optional-qualifier patterns for the
  reanimation/recursion phrase family.
- Foretell/exile-matters (Ranar — his Go Wide high is real, the primary is unread).
- Tribal cheat-from-hand form ("put a Vampire card from your hand onto the
  battlefield" — Strefan).
- LOST_LIFE relative-clause form ("each player WHO lost life this turn").
- Devotion class (Nylea honest empty — measure "devotion to" in a future round).
- Boast (tiny class).
Ten sentinels (277-card set, sanity "278 passed"); suite 1099 green.
Audit: logs/calibration-batch-21.json.

## Full build #1 friction fix (2026-07-05): the assigns-by-toughness class

The Felothar test build surfaced exactly one friction: `toughness_matters` covered only
the batch-11 Arcades forms ("with defender", toughness-lifegain) — the ASSIGNS class
("assigns combat damage equal to its toughness") and the defender-attack enablers ("as
though it/they didn't have defender") were invisible, so Felothar read only
`Aristocrats: medium` while his primary plan was blank. Fixed with three measured
phrases: "damage equal to its toughness" (24 — Arcades, Doran, Felothar, Bedrock
Tortoise, Ancient Lumberknot) + both didn't-have-defender forms (49+5). "attack as
though" REJECTED ("as though it had haste" — Instill Energy FP). Felothar now reads
Toughness / Defenders high + Aristocrats medium (his exact deck); Doran/Arcades pinned
as class controls. 267 sentinels, "268 passed"; suite 1089 green.

## Pre-build fix round (2026-07-05, user-requested): batch #17–#20 leftovers swept

A verification sweep over every still-open gap from the last four batches — each one
either fixed (measured) or explicitly rejected with the measurement that rejects it:

FIXED:
- **stax tag direction split (closes the session-2 Colfenor's Plans finding):** "costs
  more" was DEAD vocabulary (0 DB matches — real wording is "costs {1} more"), removed;
  "can't cast more than" split directionally — "each player can't cast more than" (8,
  the Rule of Law symmetric class) + "enchanted player..." (1, Curse of Exhaustion)
  stay; "you can't cast more than" (4, the card's OWN drawback — Colfenor's Plans,
  Moderation) excluded. Colfenor's false `Stax: high` is dead; Rule of Law pinned as
  control.
- **EXILE_MILL detector (closes the batch-18 Circu gap):** targeted top-of-library
  exile with NO play permission anywhere on the card (4/4 measured: Ashiok, Circu,
  Scrib Nibblers, Mindreaver) → Mill defining. The each-player forms measured dirty
  (Pako is theft-fetch, Share the Spoils is hug) and the play-permission forms are
  Theft (Gonti/Etali unaffected). Circu now reads Mill + Stax co-primary — his exact
  deck.
- **Broad-phrase audit:** the `enchantress` "draw a card" landmine is INERT for banding
  (enchantress/engine/combo_piece feed no archetype — search-only); remaining short
  phrases in archetype-feeding tags are legitimate keywords.

REJECTED (measured):
- Yennett free-cast class: "without paying its mana cost" = 526, direction-less. Stays
  honest empty.
- Bruna aura-attach: her forms measure 1 card each. Stays low (pinned ANY).
- Dorks-matter (Raggadragga), Imodane's exact pinger phrase (7, mixed with copy
  payoffs), untap-tempo (Derevi), day-night (tribal covers Tovolar): all rejected.

STANDING deliberate known-gaps: conditional-rider (Raggadragga), Volo's copy-that-spell
form (guards pinned), desert (1 card), curses (2), end-turn tricks (Obeka).
Two pins updated + Rule of Law/Ashiok controls added → 265 sentinels, sanity "266
passed"; suite 1087 green. Audit: logs/pre-build-fixround.json.

## Calibration batch #20 (post-gate, blind-first, 2026-07-05): FAIL — fixed

Tally: right 3 (Elsha, Kalemne — Creature Spells Matter validating on the experience-
counter class —, Imodane — Group Slug + Spellslinger both true), partial 5, empty 1
(Obeka honest — end-turn tricks), **CW 2 → FAIL**:
- **Otrimi (PREDICTED in the blind phase):** the batch-19 "creature card" combat-feed
  boundary lacked direction — his "return target creature card ... to your HAND" is
  card advantage, not deployment. Fixed: compound check ("creature card" counts only
  with onto/to the battlefield in the same line; Gishath control stays high). The same
  card exposed a second direction trap: the `reanimation` tag carried the NAKED phrase
  "return target creature card" (284 matches, ~139 non-battlefield) — replaced with
  battlefield-directional forms (145+1); Otrimi's false `Reanimator: high` died,
  Sefris intact.
- **Raggadragga:** `Spellslinger: high` from "whenever you cast a spell," whose rider
  ("if at least seven mana was spent") makes it a big-mana payoff. Measured: the
  big-mana-rider subclass is EXACTLY 1 card (himself) — per the Jetmir precedent no
  per-card patch; documented as the **conditional-rider awareness** known-gap (a future
  detector feature: an "if <threshold>" rider between trigger and payoff changes the
  archetype target). Pinned as-is with the gap note.
Coverage same round: whitelist +47 real creature types (satyr, scarecrow, skeleton...
— Gallia reads Satyr Tribal, the class was invisible), 2 new tribal patterns ("other X
creatures" anthem + "another X you control" trigger — Reaper King reads Scarecrow
Tribal), "for each aura attached" (8/8 clean — Uril reads Voltron high, the
Bruna-class sibling), `attacks_alone` (95, the exalted family) as Voltron SUPPORTING
(Rafiq medium; defining would make Noble Hierarch lie — pinned as guard), NEW archetype
**Mutate** (39 — Otrimi's truth). Eleven sentinels (263-card set, sanity "264
passed"); suite 1085 green. Audit: logs/calibration-batch-20.json.

## Calibration batch #19 (post-gate, blind-first, niche-mechanics spectrum, 2026-07-05): FAIL — fixed

Tally: right 3 (Sefris, Marisi, Grolnok — the singular tribal pattern generalized to
Frogs), partial 2 (Tovolar, Sliver Overlord), empty 2 (Lynde honest — curses is a 2-card
class, rejected per the Jetmir precedent; Yennett honest — **the Zur rule WORKED**,
suppressing her self-attack free-cast trigger), **CW 3 → FAIL** (Jorn, Nine-Fingers
Keene, Yidris). All three CWs were ONE class (the batch-#10 pattern): a SELF-combat
trigger with a VALUE effect banding `Attack Triggers / Aggro: high`. Two sub-bugs:
- (a) the self-scope check covered "Whenever <name> attacks" but not the SABOTEUR form
  "<name> deals combat damage to a player" — Keene (digs Gates) and Yidris (grants
  cascade) escaped to the generic band.
- (b) the untap combat-feed exemption was directionless — Jorn's "untap each snow
  permanent" is MANA, not attackers (measured: 101 creature-untaps vs 94 other).
Fix: self_subjects gained the deals-combat-damage forms; the untap exemption is now
directional (untap it/them/all creatures...); and the golden net caught Lathril/Gishath
within seconds, drawing the EXACT boundary — **creature deployment in the effect
(Lathril's Elves, Gishath's Dinosaurs) still feeds the combat plan; noncreature value
(Gates, cascade, snow untaps, Zur's enchantments) is an engine event**. Ragavan
improved as a side effect: he now reads his true Theft + Treasures instead of a false
attack band.

Same round, 5 NEW archetypes (all keyword-family clean): **Snow Matters** ("snow
permanent" 24; "snow land" REJECTED — Thermokarst land-hate FPs; "snow creature"
REJECTED — "non-snow" negation FPs), **Gates Matter** (29), **Dungeons / Venture**
(67), **Cascade** (55), **Goad / Forced Combat** (85). And 3 new tribal patterns:
or-conjunction pairs ("a Wolf or Werewolf you control" — Tovolar reads Wolf + Werewolf
Tribal) and the tutor form ("search your library for a Sliver card" — Sliver Overlord
reads Sliver Tribal beside his genuine THEFT_CONTROL). Known-gaps: odd/even-topdeck
cheat class (Yennett), day-night mechanic. Twelve sentinels incl. Godo as directional-
untap control and Ragavan as improvement pin (252-card set, sanity "253 passed");
suite 1074 green. Audit: logs/calibration-batch-19.json.

## Coverage fix round post-#18 (2026-07-05, user-requested): the #17/#18 gap backlog closed

The accumulated coverage known-gaps from batches #17/#18 were measured and fixed in one
pass — 4 NEW archetypes, 2 defining extensions, 1 new detector form (suite 1062 green,
240 sentinels, sanity "241 passed"; audit: logs/coverage-fixround-post-18.json):

- **Enchantments Matter** (the Anikthea gap): `enchantment_payoff` (constellation 35,
  "whenever an enchantment you control enters" 37, "whenever you cast an enchantment" 19,
  "enchantments you control" 13, "enchantment creature(s) you control" 7+3) +
  `enchantment_recursion` supporting ("enchantment card from your graveyard" 40).
  "enchantment spell" REJECTED (8 counterspell FPs — Annul pinned as guard). The legacy
  `enchantress` tag was NOT used: it carries a naked "draw a card" phrase (landmine,
  still annotated). Anikthea now reads Enchantments + Clones + GY Value triple-high;
  Sythis control reads Enchantments high.
- **Energy** (the Satya gap): "{e}" (146, the symbol only appears on energy cards).
- **Forced Discard** (the Tinybones gap): `opponent_discard_payoff` ("whenever an
  opponent discards" 15, "each opponent discards" 68, "an opponent discarded" 1 riding
  the family) — distinct from self-discard/Wheels.
- **Clones / Copies** (partial close of the old Volo gap): `clone_copy` ("token that's a
  copy" 352, "as a copy of" 75). "copy target" REJECTED (Fork/Twincast = Spellslinger);
  Volo's "copy that spell" form stays deliberately unread (would misband Krark/
  Jin-Gitaxias — Krark pinned as must_not guard).
- **THEFT_TOPDECK** detector form (the Xanathar gap): same-line "top card of
  their/opponent's library" + "you may play/cast" (37 measured, all genuine — Gonti CA,
  Grenzo HR, Ragavan, Etali, Daxos). Xanathar now reads Stax + Theft.
- **Vehicles defining += `vehicle_payoff`** (the Greasefang gap): "vehicle card from
  your graveyard" 8, "vehicles/vehicle you control" 25/39, "whenever a vehicle" 10.

Still open (annotated, honest): exile-mill detector (Circu — needs play-permission
exclusion), Bruna aura-attach-from-zones, untap-tempo (Derevi), desert-landfall (1-card),
Volo's spell-copy-of-creature form, the enchantress-tag "draw a card" landmine. Process
bug caught during measurement: regex `libraries?` does not match singular "library"
(the s-optional trap) — a 0-hit measurement was debugged character-by-character before
anything shipped.

## Calibration batch #18 (post-gate, blind-first self-run, 2026-07-05): FAIL — fixed

Tally: right 4 (Commodore Guff, Lathliss, Satya, Karametra — the session-2 Creature
Spells Matter archetype validated on a virgin commander same-day), partial 5 (Fynn,
Bruna, Circu, Hazezon, Burakos), empty 0, **CW 1** → FAIL. The CW: **Phelddagrif read
`Go Wide: high` from Hippo tokens he GIFTS to opponents** — "Target opponent creates"
was missing from `_OPPONENT_TOKEN_RE`'s alternation (it covered that player/each
opponent/an opponent/defending player). Fix round (all measured):
- `_OPPONENT_TOKEN_RE` += "target opponent creates" (23, all gifts — Hunted cycle,
  Clackbridge Troll, Forbidden Orchard). "target player creates" REJECTED: usually
  self-targeted modal support (Dark Salvation creates YOUR Zombies).
- `group_hug` += "target opponent may draw" (4/4 — Phelddagrif now reads his truth,
  Group Hug high). "target opponent gains" REJECTED (24 "gains control" FPs).
- NEW archetype **Poison / Infect** (defining: the existing `poison` tag — infect 70 /
  toxic 71 / "poison counter" 182 — which had never been mapped; Fynn empty→high on his
  primary). A pure MAPPING fix: the vocabulary was already measured.
- NEW archetype **Party** ("in your party", 31 measured, all genuine — Burakos reads
  Party + Treasures co-primary).
- `lifedrain` += "defending player loses" (31, the afflict/attack-drain class).
Generalization positives on fresh commanders: nontoken tribal (#16)→Lathliss, the
ephemeral-copy guard (#3)→Satya (pay-E-or-sac copies did NOT read Go Wide), the Zur
self-attack rule (#11)→Burakos (value trigger did not band attack theme). New
known-gaps: exile-mill needs a detector with play-permission exclusion (Circu — the
phrase family is dominated by impulse-theft, Tibalt would read Mill), Bruna's
aura-attach-from-zones class (honest lows), energy archetype (Satya), desert-landfall
(1-card class, per-card patch rejected per Jetmir precedent). Blind calibration: all
four predicted coverage-partials landed; the CW was NOT predicted (guard-alternation
completeness is a new failure family — audit regex alternations when a scope guard
exists). Eleven sentinels (238-card set, sanity "239 passed"); suite 1060 green.
Audit: logs/calibration-batch-18.json (post-fix re-log; the blind-phase staging log was
lost to a test-suite run clearing output/on-going-report.json — process note: run
`mtg report` BEFORE running pytest).

## Calibration batch #17 (post-gate, blind-first self-run, 2026-07-05): PASS

Tally: right 4 (Syr Gwyn, Zaffai, Vorel — the COUNTER_MARKER doubling read beat the blind
prediction of empty —, Chainer NA), partial 5 (Xanathar, Greasefang, Derevi, Anikthea,
Preston), empty 1 (Tinybones, honest), wrong 0, **CW 0** → right+partial 9/10, CW=0.
Per the PASS protocol no analyzer changes were made. Positive generalization on fresh
commanders: GRAVEYARD_CLONE (batch #16 detector) read Anikthea right; graveyard_recast
read Chainer; aura_equipment_payoff read Syr Gwyn; SAC_OUTLET fired genuinely on Preston.
Blind-prediction calibration: the 3 predicted risks landed exactly; CW predicted 0-1,
actual 0. Ten sentinels pinned improvement-friendly (227-card set, sanity "228 passed").
Audit: logs/calibration-batch-17.json. New known-gaps recorded:

- **Theft form "play the top card of their library"** (Xanathar class) — his Stax high is
  true but his theft identity is unread.
- **Vehicle reanimation** — "return target Vehicle card from your graveyard to the
  battlefield" (Greasefang) matches neither the reanimation tag (creature-card phrasings)
  nor VEHICLE (detects being one, not vehicle-matters); vehicle-payoff class unread.
- **Opponent-discard payoff class** (Tinybones) — "if an opponent discarded a card this
  turn" has no tag; threshold lifedrain "each opponent WITH NO CARDS IN HAND loses"
  breaks the "each opponent loses" substring.
- **Enchantments Matter archetype does not exist** (Anikthea class — the parallel of
  Artifacts Matter; her GY-recursion half reads high, the enchantments half is invisible).
- **Untap/tap tempo engine has no archetype** (Derevi class).

## Known-gaps session 2 (2026-07-05): the whole annotated backlog closed

Every open detection gap from batches #14/#15/#16 and session 1 was measured and fixed
(suite 1032 green, 217 sentinels, sanity "218 passed"):

- **morph_facedown FP class FIXED:** the tag's naked "face down"/"face-down" (517 cards:
  305 morphish, 145 exile-face-down, 67 hidden-info) rebuilt with directional forms
  ("turn it face up", "turned face up", "morph {"/"morph—"/"morph cost"/"morph ability",
  "manifest", "disguise", "face-down creature" — union 189, missing only 4 clone-name
  FPs like Surgical Metamorph). Gonti and Kotose no longer read Morph; Kadena/Ixidor keep
  their high.
- **theft "exiled with" FIXED:** phrase removed from the tag; THEFT_EXILE gains a v2
  card-level conjunction (an opponent-zone exile line AND an "exiled with" play-permission
  line — measured 12, all genuine: Nightveil Specter, Jeleva, Kheru Mind-Eater, Muse
  Vessel, Valki//Tibalt). Colfenor's Plans (own-card impulse) no longer reads Theft.
- **cast-creature engine class FIXED (batch #14/#15):** new `creature_cast_payoff` tag
  ("whenever you cast a creature spell" 72, "creature spells you cast cost" 28, "each
  creature spell you cast" 4) → new archetype `Creature Spells Matter`. Animar and
  Chulane empty→high; Thalia-style taxers excluded by the "you cast" anchor.
- **X-spell payoff class FIXED (batch #15):** new `x_spell_payoff` tag ("cast a spell
  with {x}" 7, "costs that contain {x}" 4, "contains {x}" 2) → new archetype `X Spells
  Matter`. Zaxara and Rosheen high; the hate forms (Gaddock Teeg, Frontline Medic) are
  excluded by the cast/cost anchors.
- **0/0-with-counters tokens FIXED (batch #15):** counter-body guard in the 0/X fodder
  branch — a token that gets +1/+1 counters in the same clause is a real body (30
  measured: the Fractal cycle, Zaxara's Hydras, Gimbal). Zaxara's false `Aristocrats:
  medium` dead; Atla's Eggs (184 true-fodder makers) unaffected.
- **Rielle wheel vocab + madness class FIXED (batch #15 + #16):** new `discard_payoff`
  tag — ONE directional phrase ("whenever you discard", 48 measured, all genuine) covers
  Rielle's "one or more cards for the first time", Anje's madness untap, Inti and
  Glint-Horn. Defining of Wheels / Forced Draw.
- **amass class FIXED (batch #16):** new `amass_payoff` tag ("amass" 60 — all keyword
  incl. conjugated "amasses"; "army you control" 52) → new archetype `Amass / Army`.
  Sauron reads Amass + Attack Triggers.
- **Ghyrson pinger class FIXED (batch #14):** new `pinger_payoff` tag ("deals exactly",
  "whenever a source you control deals", "source you control deals damage", "deals
  noncombat damage" — union 19, all genuine) → new archetype `Pingers / Damage Matters`.
  Deliberately NOT the pre-existing broad `damage_payoff` tag (its "whenever a creature
  deals combat damage" is saboteur territory). Ghyrson and Taii Wakeen empty→high.
- **Locust God co-primary FIXED (batch #16):** new `draw_trigger_payoff` tag ("whenever
  you draw a card" 48, "whenever you draw your second card" 51) defining of Wheels.
  Locust God reads Go Wide + Wheels co-primary; Sheoldred reads Wheels high.
- **Marchesa BR dethrone FIXED (batch #14/#15):** `dethrone` tag (keyword, 10 measured)
  as Counters Matter SUPPORTING — with counter_enabler that's 2 supporting → medium.
  Deliberately not defining (one dethrone creature is not a counters plan).
- **Grismold death-payoff FIXED (batch #15):** "creature token dies" (2 measured, zero
  FP) added to death_trigger. Aristocrats + Go Wide co-primary high.
- **deck-check Bolt/Chaos Warp vocab FIXED (old pending):** `removal`/`creature_removal`
  gain "damage to any target" (733), "damage to target creature" (530, 2 prevention FPs),
  "owner of target" (22, tuck removal — Chaos Warp/Oblation class). Healing Salve still
  counts zero.

NEW findings annotated (not fixed):
- **stax tag self-restriction in the TAG layer:** Colfenor's Plans reads `Stax: high`
  because its own drawback "You can't cast more than one spell each turn" matches the
  stax tag — the batch-3 SELF-RESTRICTION scope check exists only in the signal/negation
  layer, not for tag phrases. Needs the same self-vs-opponents scope test at the tag
  consumption site.
- ~~Deglamer/Unravel the Aether tuck class unread as removal~~ **FIXED same-day:** the
  same-line "target" + "shuffles it into" conjunction in deck_check
  (`_is_targeted_tuck_removal`; measured 13/13 removal vs 8/8 self-shuffle). The general
  lesson is recorded as the "uncertain bucket" pattern (CHECK-LIST): when a rule CAN
  decide, write the rule; when it can't, flag the match as uncertain for the agent to
  verify — never count doubt as certainty.

From gate batch #11: ALL FIVE CLOSED by the batch-11 fix round (verified live 2026-07-04:
Tymna, Xenagos, Kozilek, Jhoira, Ikra all read their archetype high) — the known-gap
annotation was stale.

From gate batch #8: Sygg FIXED (above); Surrak documented honest empty.

From gate batch #5: Volo FP fixed + honest empty (clone/copy value archetype still a gap —
the ONLY remaining detection gap from the batch backlog);
Galea CLOSED by the aura_equipment_payoff promotion (stale annotation); Old Stickfingers
FIXED (above).

Golden-judging backlog (5 verified misses): ALL FIXED — death-doubler context, "artifact spell",
mill phrasings, symmetric pingers, regex SAC_OUTLET. Sentinels pinned (68-card set).

- Trigger-doubler cast-context not extracted (covered today by tag redundancy — Veyran reads right
  via magecraft).
- Legacy `archetype_fit` was confidently wrong on some commanders; that motivated the migration,
  and it has now been removed (v0.8.0) — `analyzer.archetype_support` is the only read.
