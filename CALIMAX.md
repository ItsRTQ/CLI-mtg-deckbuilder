# CALIMAX.md — Calibration build protocol for the universal card analyzer

CALIMAX is a **calibration harness**, not a normal deckbuilding session. Its purpose is to run
test builds whose real job is to **stress the new analyzer** (`mtg analyze-card`) across many
commanders and surface where its reads of cards are wrong, so we can fix the extraction rules and
grow a golden set. The deck is a byproduct; the calibration data is the product.

Read `@BUILDER.md` for all build mechanics (commands, command-zone model, validation,
final-build). CALIMAX only **overrides the decision defaults** and **adds a calibration loop** on
top of the standard workflow. Where CALIMAX is silent, BUILDER.md governs.

---

## 1. Standing defaults (do not ask the user — just proceed)

To keep calibration fast, CALIMAX builds run on fixed defaults. **Do not stop to ask the user
about build patterns.** Use these unless the user explicitly overrides them:

- **Budget:** $150 USD, **soft** (overage allowed; flag, don't block).
- **Every other build decision → agent choice.** Archetype, power level, philosophy, which cards,
  tradeoffs: decide yourself and state the choice in one line. Do not run option-pickers for build
  patterns during calibration.
- **Goal of this phase:** *global spectrum* coverage, not optimization. We want to see how the
  analyzer behaves across many different commanders and archetypes. Breadth over depth. Do not
  over-invest in perfecting any single deck.
- Only ask the user if something is genuinely blocking (a tool error, an ambiguous instruction
  about the calibration process itself) — never to choose a build pattern.

## 1b. Log EVERY command (mandatory audit trail)

During a CALIMAX run, **append `--log` to every single `mtg` command you execute** — searches,
analyses, suggests, validations, writes, preflight, all of them. `--log` captures the full command
and its response into an on-going audit file (`output/on-going-report.json`) in chronological order,
so the run report is backed by a real record of everything done, not your memory of it.

```bash
mtg analyze-card "Toxrill, the Corrosive" --json-output --log
mtg search-tags evasion --colors G --log
mtg deck-swap --deck output/deck.json --swap "A=B" --log
```

At the END of the run, consolidate the audit trail into a named report:

```bash
mtg report --name "calimax-<commander-slug>-<archetype>" --summary \
  --note "agent-chosen archetype: <x>" \
  --note "analyzer misses: <Card> (<rule_id>), ..." \
  --note "golden-set candidates: ..."
```

`report --summary` serializes the full chronological log to `logs/<name>.json` (including a derived
calibration summary: per-command counts, every card passed to `analyze-card` — your direct list of
reads to review — and any commands that failed) and clears the on-going file for the next run. Put
your calibration findings (misses, golden-set candidates, rule gaps) into `--note` comments so they
live inside the same artifact as the command history. Use one `report` per build.

## 2. Commander selection for global spectrum

Pick commanders to **maximize archetype/mechanic diversity** across runs, not to find the strongest
deck. Aim, over successive runs, to cover at least: aggro/Voltron, aristocrats, spellslinger,
+1/+1 counters, a custom-counter commander (e.g. slime/oil/experience), a punisher/asymmetric,
go-wide tokens, reanimator, blink/ETB, lands, stax-leaning, and a multi-face/modal-heavy pool.
Rotate; don't repeat an archetype until the spectrum is covered once.

## 3. The calibration loop (this is the point)

For each build, run the **standard BUILDER workflow**, but with an analyzer-observation pass woven
in:

1. Analyze the commander with ONE command — `mtg commander-analyze --commander "<name>"
   --json-output --log`. Since Fase 1 it carries BOTH reads: the legacy `archetype_fit` (numeric
   scores) and the preferred `analyzer.archetype_support` (evidence bands + signal IDs). Rules:
   - **Build from `analyzer.archetype_support`** (see BUILDER.md §7.0b). Treat `archetype_fit` as
     a hint at most.
   - **A disagreement between the two IS calibration signal** — record which is right and why.
   - **Coverage-gap protocol:** if `archetype_support` is empty or all-low but the commander
     clearly has a plan, record: (a) the archetype it SHOULD read, and (b) which `signals`/tags
     DID fire (that pairing is the map for adding the missing mapper rule). Then build from your
     own read of the oracle.
2. While drafting, for **representative cards** (especially anything non-obvious: asymmetric
   effects, multi-face, replacement effects, linked abilities, named counters, meta-triggers),
   check the analyzer's read. **Token discipline:** use the compact view (`mtg analyze-card
   "<Card>" --log`, no --json-output) for routine checks — it is ~5x smaller; reserve
   `--json-output` for the cards you will REPORT as misses, where the full trace matters.
   Check against ground truth:
   - Is the **scope/symmetry** right? (one-sided vs symmetric vs targeted)
   - Is the **timing** right? (trigger vs replacement; optional vs forced)
   - Is the **verb/noun** sense right? (counter the spell vs +1/+1 counter; self vs broad)
   - Are the **archetype bands** sane? (a confident wrong band is worse than an honest low)
   - Did a multi-face/Saga card get split into the right parts?
3. **Log every discrepancy** in the run report (see §4), CLASSIFIED by type — it routes the fix:
   - `detection` — a signal/mechanic that should have fired didn't (or fired wrongly).
   - `mapping` — signals/tags fired but the archetype/band is wrong or missing.
   - `vocab` — a tag phrase gap (an oracle phrasing the tag list doesn't cover).
   - `data` — wrong card data (legality, flags, prices).
   Include the trace (rule_id + matched_text) for detection/mapping misses — the trace is what
   makes the miss fixable. Fix the RULE, never the card.
4. Finish the build through `mtg preflight` as normal (soft $150). The deck still must be legal.

## 4. Run report (the calibration artifact)

Every CALIMAX run produces TWO things: the machine `logs/<name>.json` from `mtg report` (the full
command-by-command audit trail with your `--note` findings embedded), and a short human summary in
chat. The human summary mirrors the notes:

```
CALIMAX run: <Commander> (<archetype>, agent-chosen)
Deck: <N> cards, $<price>, preflight: READY/NOT READY
Audit: logs/<name>.json (<count> commands logged)

Archetype check: analyzer.archetype_support said <X> | legacy archetype_fit said <Y> |
  correct read: <Z> | verdict: analyzer right / legacy right / both / neither (coverage gap)

Analyzer hits (read matched reality): <count>, examples …
Analyzer misses (to fix), classified:
  - [detection|mapping|vocab|data] <Card>: analyzer said <X> (rule <rule_id>, matched '<text>');
    actually <Y>. Fix idea: <…>
Golden-set candidates (they feed the Fase 2 gate — use this exact shape):
  - <Card>: expected: <archetypes/signals it MUST read> | must_not_have: <reads it must NOT get>
New rule/pattern gaps observed: <…>
```

Misses and golden-set candidates are the real output — they drive the next round of rule fixes.
Golden-set candidates feed `data/golden/golden_cards.json` (the pinned regression net): a
candidate only gets pinned after a judge verifies the read is CORRECT — never pin an unverified
read.
Because every `analyze-card` call was logged, any miss can be re-examined later from the JSON with
its exact trace.

## 5. The iteration

test build → record analyzer misses (§4) → fix extraction rules + add golden-set entries →
re-run `mtg analyze-card` on the missed cards to confirm → next commander. Stay in *global
spectrum* mode (breadth) until the analyzer is reliably right across archetypes; only then move to
deep, archetype-specific calibration.

## 6. What NOT to do

- Don't optimize a deck at the expense of covering a new archetype.
- Don't ask the user to choose build patterns — agent choice, $150 soft, proceed.
- Don't "fix" a miss by special-casing one card; fix the **rule** so it generalizes (the whole
  point of the analyzer). A per-card patch is a calibration failure, not a fix.
- Don't trust a clean build as evidence the analyzer is right — a deck can be legal while the
  analyzer misread half its cards. Only the per-card `analyze-card` checks are calibration signal.
