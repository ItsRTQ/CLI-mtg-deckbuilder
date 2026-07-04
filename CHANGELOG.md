# Changelog

## 0.8.0

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
