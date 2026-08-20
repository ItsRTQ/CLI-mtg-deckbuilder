# TCGplayer Mass Entry Verification Report

**Date:** 2026-07-14 · **Investigator:** Claude (automated + static analysis; manual browser checks pending where marked)
**Scope:** Verify the input rules and prefilled-URL behavior behind the one-click "Export to TCGplayer" feature.
**Method:** Official docs (blocked, see below) · **TCGplayer's own production JavaScript** (the Mass Entry page bundle — the strongest evidence available, it IS the parser) · live HTTP probes against `tcgplayer.com/massentry` · TCGplayer catalog naming resolved via Scryfall `tcgplayer_id` → product pages · in-the-wild partner URLs.

---

## 1. Officially Documented Rules

The official help article (`help.tcgplayer.com/hc/en-us/articles/360055768913-Getting-Started-With-Mass-Entry`) is behind bot protection (HTTP 403 to non-browser agents) and has **no Wayback Machine snapshot**, so its prose could not be captured in this automated investigation. From search-index snippets only:

- Mass Entry accepts entries like `1 Lightning Bolt #84 from Secret Lair Drop` (quantity + name + printing info).
- The page exists at `https://www.tcgplayer.com/massentry` and is the intended bulk-purchase entry point.

**Everything below comes from stronger evidence than the prose doc:** the deployed parser code itself, and live HTTP behavior.

## 2. Experimentally Verified Rules

### 2.1 The URL parser (from TCGplayer's deployed `MassEntry-D8eQp0KZ.js` + `constants-kK49jU1J.js`)

The Mass Entry page reads the query string with exactly this logic (deobfuscated):

```js
// constants bundle:
MassEntryQueryDelimiter = "||"
MassEntryExpressions = {
  ByProduct:             /^(?<quantity>\d+)(\s+(?<productName>\S.*)|-(?<productId>\d+))$/,
  ByProductAndSet:       /^(?<quantity>\d+)(\s+(?<productName>\S.*)|-(?<productId>\d+))\s+\[(?<setCode>.+)\]$/,
  ByProductSetAndNumber: /^(?<quantity>\d+)(\s+(?<productName>\S.*)|-(?<productId>\d+))\s+\[(?<setCode>.+)\]\s+(?<number>.+)$/,
}
// MassEntry page:
productline = route.query.productline || "Magic"
entries = route.query.c.split(MassEntryQueryDelimiter)
for (segment of entries) if (segment) {
  match = ByProductSetAndNumber.exec(segment) || ByProductAndSet.exec(segment) || ByProduct.exec(segment)
  if (match) push({quantity, productId, name, setCode: setCode||"", cardNumber: number||""})
  // no else — non-matching segments are silently dropped
}
```

Verified consequences (each provable from the code above):

| Question | Answer | Evidence |
|---|---|---|
| Delimiter inside `c` | `||` exactly | `MassEntryQueryDelimiter = "||"` |
| Leading `||` required? | **No — optional and harmless.** Empty segments are skipped (`if (segment)`) | loop guard |
| Trailing `||` | Also harmless (same guard); wild partner URLs carry one | MTGSalvation partner URL |
| Newlines as delimiter in `c` | **Not supported** — the split is on `||` only; a `\n`-separated payload is ONE segment (first line may match, rest lost) | split call |
| `productline=Magic` required? | **No — it's the default** (`|| "Magic"`). Including it is harmless and self-documenting | default expr |
| `Magic` case sensitivity | The default value is `Magic` (capital M); other casings unverified — keep `Magic` | constant |
| Quantity required? | **Yes.** All three regexes anchor on `^\d+`. `Sol Ring` (bare name) matches nothing → **silently dropped** | regexes |
| Quantity must be positive integer? | Must be an unsigned integer; `-1 X` / `abc X` fail `^\d+` → dropped. `0 X` **matches** the regex; downstream handling of a 0 quantity is unverified | regexes |
| Whitespace between qty and name | `\s+` — one or more spaces OR tabs both fine | regexes |
| Invalid lines | **Silently dropped from the URL path** (no error entry is created at parse time). Unmatched-name behavior after the catalog lookup is a UI question (see §4) | no-else |
| Section headers (`Commander`) | A bare word fails `^\d+` → dropped (harmless but our exporter never emits them anyway) | regexes |
| Duplicate lines merged? | Parser pushes each match separately; merge behavior in the UI unverified — **exporter should pre-merge** (ours does) | push loop |
| Set code syntax | `1 Name [SET]` and `1 Name [SET] NUMBER` — brackets required for set, number requires set. `1 Lightning Bolt 84` parses as product name `"Lightning Bolt 84"` (wrong) — never emit bare trailing numbers | regexes |
| Product-ID syntax | `1-<productId>` (e.g. `1-129813`) addresses an exact product directly — a future "exact printing" option | regexes |

### 2.2 Live HTTP behavior (curl probes, 2026-07-14)

| Probe | Result |
|---|---|
| `GET /massentry?productline=Magic&c=%7C%7C1+Sol+Ring…` (114 chars) | **200 OK**, no redirect |
| Wild-style, no leading `||`, no productline (113 chars) | **200 OK** |
| URL length 3,556 (100 entries) | 200 |
| URL length 7,056 (200 entries) | 200 |
| URL length 8,211 | 200 |
| URL length 8,421 | **414 URI Too Long** |
| URL length 14,056 / 21,056 | 414 |

**The server's URL limit sits between 8,211 and 8,421 characters** (consistent with a classic 8 KB request-line cap). A realistic worst-case 100-card Commander deck with long names measured **3,320 chars**; a real 100-card deck from this repo measured **1,921 chars** — both comfortably safe.

### 2.3 TCGplayer catalog naming for multi-face layouts

Resolved via Scryfall (`tcgplayer_id`, public API) to the exact TCGplayer product pages:

| Layout | Scryfall name | TCGplayer product title | Export rule |
|---|---|---|---|
| `split` | Wear // Tear | **"Wear // Tear"** (product 67878/227383) | **full `A // B` name** |
| `aftermath` (split) | Cut // Ribbons | **"Cut // Ribbons"** (product 129813) | **full `A // B` name** |
| `transform` | Delver of Secrets // Insectile Aberration | **"Delver of Secrets"** (products 56246/248082/497033) | **front face only** |
| `modal_dfc` | Valakut Awakening // Valakut Stoneforge | **"Valakut Awakening"** (product 221774 — the exact tcgid Scryfall maps) | **front face only** |
| `adventure` | Bonecrusher Giant // Stomp | **"Bonecrusher Giant"** (product 273681) | **front face only** |
| `meld` | Brisela, Voice of Nightmares | melded face has **no product** (tcgplayer_id: none); the two component cards are normal products | export components by their normal names; never emit the melded name |

### 2.4 Encoding round-trip (automated, `scripts/verify_tcgplayer_mass_entry.py`)

`urllib.parse.urlencode({"productline": "Magic", "c": payload})` in one pass:
- Spaces → `+`, `||` → `%7C%7C`, `,` → `%2C`, `/` → `%2F`, `û` → UTF-8 percent-escapes. Apostrophes and hyphens are safe either way.
- `parse_qs` round-trip of the `c` param **equals the original payload exactly** for punctuation, Unicode, and `//` names — no double encoding (`%252F`/`%257C` never appear).

### 2.5 No API key / no automation required

All 200-OK probes above were plain unauthenticated GETs. The `c=` mechanism is client-side page behavior — no developer key, no REST API call, no Selenium/Playwright, no login. (No cart, checkout, or purchase action was attempted at any point.)

## 3. Unverified Assumptions (need one manual browser pass)

The Mass Entry page is a JS SPA — what the *field actually displays* cannot be confirmed by HTTP probes. Pending manual confirmation via `scripts/verify_tcgplayer_mass_entry.py --case <X> --open`:

1. That parsed entries visibly populate the Mass Entry field (the parse code exists and partner sites rely on it, so confidence is high, but seeing is knowing).
2. How the UI shows **unmatched names** (e.g. `1 Not A Real Magic Card`) — error list vs silent drop.
3. Whether the UI **merges duplicate** entries or lists them twice (exporter pre-merges, so this is informational).
4. `0 Sol Ring` downstream behavior (parses; probably a useless row).
5. Whether name→product matching is exact or fuzzy (e.g. does `1 Wear` find "Wear // Tear"? Do NOT rely on it).
6. Lowercase set codes / promo collector numbers in `[SET] NUM` matching (parse-side fine; catalog-side unverified).
7. Whether TCGplayer falls back to another printing when `[SET]`/number is invalid.
8. That basic lands (`1 Island`) resolve to some printing without issue.

### 3.1 CONFIRMED failure class: variant-suffixed product titles (field report 2026-07-14)

User-observed: `The Swarmweaver` and `Eshki, Temur's Roar` fail in Mass Entry with
"Something went wrong". Investigation:

- Both export lines are **well-formed** (`1 <name>` matches `ByProduct`) and both cards
  exist in the local DB with the correct canonical names — parsing is not the problem.
- Both cards **exist on TCGplayer** (tcgids 575275/575276/575277 and 623910, resolved via
  Scryfall), BUT every product title carries a **parenthetical variant suffix**:
  "The Swarmweaver **(0236)** / **(0301)** / **(Showcase)**" and
  "Eshki, Temur's Roar **(Borderless)**". **No product is titled by the clean card name.**
- Conclusion: Mass Entry's name→product resolution needs a product whose title matches the
  entered name; when all printings are variant-suffixed (common in 2024+ sets, where
  TCGplayer disambiguates same-set versions with collector numbers/treatments), a clean
  name resolves to nothing and the row errors.

This is a TCGplayer **catalog-side** limitation — no name-only exporter can avoid it. The
local DB carries no set/collector/product-ID data, so the `[SET] NUMBER` / `1-<productId>`
syntaxes can't be emitted from local data today (possible future enhancement via a
Scryfall enrichment pass). Manual candidates to test which alternate syntax resolves:
`1 The Swarmweaver [DSK] 236`, `1 Eshki, Temur's Roar [TDC] 3` (set+number), or the
suffixed title itself. Until then: affected rows must be completed by hand in the Mass
Entry page (its in-page search does find the suffixed products).

## 4. Input Compatibility Matrix

| Input Type | Example | Parses (URL path) | Correct match | Recommended export |
|---|---|---|---|---|
| Basic card | `1 Sol Ring` | Yes (code-verified) | Yes* | `1 Sol Ring` |
| No quantity | `Sol Ring` | **No — dropped** | — | never emit; always `1 <name>` |
| Zero/negative qty | `0 Sol Ring` / `-1 X` | 0: parses / -1: dropped | unknown / — | exporter must skip (ours does) |
| Multiple spaces/tab | `1    Sol Ring` | Yes (`\s+`) | Yes* | single space, canonical |
| Section header | `Commander` | No — dropped | — | never emit |
| Duplicates | `1 Sol Ring` ×2 | both parse | UI merge unknown | pre-merge to `2 Sol Ring` |
| Punctuation/Unicode | `1 Lim-Dûl's Vault` | Yes (`\S.*`) | Yes* (encoding round-trips) | exact DB name |
| Split | `1 Wear // Tear` | Yes | **Yes — catalog name** | **full `A // B`** |
| Split, front only | `1 Wear` | Yes | **unreliable** (no such product title) | avoid |
| Aftermath | `1 Cut // Ribbons` | Yes | Yes — catalog name | full `A // B` |
| Transform DFC | `1 Delver of Secrets` | Yes | **Yes — catalog name** | **front face** |
| Transform, full name | `1 Delver of Secrets // Insectile Aberration` | Yes | unreliable (title is front-only) | avoid |
| Modal DFC | `1 Valakut Awakening` | Yes | Yes — catalog name | front face |
| Adventure | `1 Bonecrusher Giant` | Yes | Yes — catalog name | front face |
| Meld (melded face) | `1 Brisela, Voice of Nightmares` | Yes | **No product exists** | never emit melded names |
| Exact printing | `1 Lightning Bolt [SLD] 84` | Yes (dedicated regex) | catalog-side unverified | optional future feature |
| Bare collector number | `1 Lightning Bolt 84` | parses as name "Lightning Bolt 84" | **No** | never emit |
| Variant-suffixed-only card | `1 The Swarmweaver` | Yes | **No — "Something went wrong"** (every product title is suffixed: "(0236)"/"(Borderless)"; §3.1) | clean name (catalog-side limit; user completes by hand) |
| Product ID | `1-129813` | Yes (dedicated branch) | exact by construction | future "exact printing" option |

\* "Yes" = name matches the TCGplayer product title pattern; final visual confirmation is manual (§3).

## 5. Prefilled URL Findings

- **Base URL:** `https://www.tcgplayer.com/massentry` (200, no redirect).
- **Required params:** only `c`. `productline` defaults to `Magic`; keep sending it explicitly (harmless, self-documenting). Parameter order irrelevant (standard query-string semantics).
- **Delimiter:** `||` between entries. Leading `||`: **not required, not harmful** (Variant A and B both work; C/D — newlines — do not).
- **Encoding:** single-pass `urllib.parse.urlencode`; round-trip verified clean.
- **URL length:** server 414s between **8,211 and 8,421 chars**. Recommended conservative threshold: **8,000 chars**. Real Commander decks measure 1.9–3.3K — the limit is ~2.5–4× headroom. Fallback (rare): never truncate silently — print/copy the plain list instead (CLI `--print-url` output or the GUI "Copy decklist" path) and tell the user to paste it into Mass Entry manually.
- **Undocumented/unstable:** the whole `c=` mechanism is undocumented by TCGplayer's help center but is (a) implemented explicitly in their production code with named constants, and (b) load-bearing for partner/affiliate sites (observed in the wild since at least the MTGSalvation era) — low risk of silent removal, but it can change without notice; a broken export degrades to an empty Mass Entry page, never to a wrong purchase.

## 6. Recommended Normalization Rules

```python
def get_tcgplayer_export_name(card):
    # TCGplayer product titles (verified §2.3):
    #   split/aftermath -> "Left // Right" (both halves)
    #   transform / modal_dfc / adventure (and other true DFCs) -> front face only
    #   meld -> component cards are normal products; the melded face has none
    if card.layout in ("split", "aftermath"):
        return card.name                      # keep "A // B" exactly as stored
    if " // " in card.name:                   # transform, modal_dfc, adventure, ...
        return card.name.split(" // ")[0]     # front face
    return card.name                          # normal (incl. meld components)
```

Everything else already in the exporter stays: quantity ≥ 1 validation, skip-and-report invalid entries, case-insensitive duplicate merge (post-normalization), commander first at quantity 1, single-pass `urlencode`.

## 7. Recommended Implementation Changes (vs the shipped exporter)

| Current behavior / assumption | Verdict | Action |
|---|---|---|
| `c` parameter is supported | **Correct** (production code + wild URLs) | none |
| Entries separated by `||` | **Correct** (named constant) | none |
| Leading `||` is required | **Incorrect — it's optional** (empty segments skipped). Harmless as-is | optional cleanup; keeping it is safe |
| `productline=Magic` is required | **Incorrect — it's the default.** Harmless as-is | keep (explicit > implicit) |
| Full Commander decks fit in a URL | **Correct with evidence**: 1.9–3.3K vs ~8.2K limit | add an 8,000-char guard that falls back to print-URL/copy-list with a clear message (never silently truncate) |
| ALL `A // B` names → front face (current code) | **Incorrect for `split`/`aftermath`** — TCGplayer's product is titled "Wear // Tear"; exporting `1 Wear` is unreliable | **APPLIED 2026-07-14**: front-face reduction is now layout-aware (§6) via an optional `layout_lookup` (CLI: CardRepository; GUI endpoint: `get_repo_optional`); no DB → front-face fallback |
| DFC (transform/modal_dfc/adventure) → front face | **Correct** (catalog titles are front-face) | none |
| Quantity validation (skip <1, non-int) | **Correct and necessary** (parser drops or mis-parses them) | none |
| Duplicate pre-merge | **Correct and necessary** (UI merge unverified) | none |
| Invalid entries reported, not fatal | **Correct** (parser drops silently — our report is the only visibility) | none |

## 8. Final Decision

```text
SUPPORTED WITH FALLBACK
The prefilled URL works, but the exporter needs a clipboard or plain-text fallback.
```

**Evidence:** the `c=||`-delimited mechanism is implemented explicitly in TCGplayer's deployed parser (named constants `MassEntryQueryDelimiter`, `MassEntryExpressions`), served 200 OK to every well-formed probe, and is relied on by partner sites in the wild. It is, however, (a) officially undocumented, (b) hard-capped by a server 414 at ~8.2–8.4K chars, and (c) a client-side contract that can change without notice — so the export must keep a no-browser path (`--print-url`, the GUI copy-decklist) as the documented fallback, add the 8,000-char guard, and fix the split/aftermath naming rule before the export can claim reliable coverage of multi-face cards. One manual browser pass over `scripts/verify_tcgplayer_mass_entry.py --case basic|split|dfc|invalid --open` closes the remaining §3 unknowns.
