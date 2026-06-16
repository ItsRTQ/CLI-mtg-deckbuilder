# Changelog

## 0.7.0

Quality and agent-ergonomics pass driven by full end-to-end builds (Krenko, Mob Boss; Gargos, Vicious Watcher).

### Fixed
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
