# user-bulk — the cards you already OWN

`collection.txt` in this directory is your personal card collection. It tracks
**ownership, not quantity** — a card you own is **excluded from budget bills
entirely** (all copies free, since Commander is singleton and basics are
unlimited): `mtg budget` (and preflight's budget gate) prices an owned card at
$0 and shows it on a visible `Owned (user-bulk)` line. Disable per-run with
`budget --no-bulk`.

**Assumed by default:** even with an empty collection, you're assumed to own the
five basic lands, **Sol Ring**, and **Arcane Signet** — they're always free.

## Maintain it with the tool (validated)

```bash
mtg bulk-add --cards "Sol Ring;2 Arcane Signet;Rhystic Study"   # add (fuzzy did-you-mean on typos)
mtg bulk-add --remove "Rhystic Study"                            # remove / decrement
mtg bulk-add --import bought-deck.txt                            # BOUGHT a deck? import it whole (.txt or deck .json)
mtg bulk-add --list                                              # view with prices + known value
```

`--import` ports an entire bought deck into your collection card-by-card — a plain `.txt`
decklist OR a deck `.json` (its `main_deck` **and** the commander(s) become owned). Names not
found in the DB are warned and skipped (the rest still import). Ownership is a set — importing
a card you already own is a no-op.

## Or edit `collection.txt` by hand

One card **name** per line, `#` comments allowed. A leading `N ` quantity is tolerated but
**ignored** (the collection tracks ownership, not counts):

```text
# my staples box
Sol Ring
Arcane Signet
Mountain
```

Hand-written names are matched case-insensitively, but they must be the real
card names — run `mtg cards-batch user-bulk/collection.txt --verify` after a
manual edit to catch typos (the tool-managed path validates automatically).

## Two synced forms: `collection.txt` + `collection.json`

`mtg bulk-add` writes the collection in **both** a plain decklist
(`collection.txt`, the hand-editable source above) and a structured
`collection.json` (easier for the agent to read — `total_cards`,
`distinct_cards`, and a `cards: [{name, quantity}]` list). The `.txt` is
canonical; the loader reads it first and falls back to the `.json`. If you
hand-edit the `.txt`, the `.json` refreshes on the next `mtg bulk-add`. Both
stay local (git-ignored) — your collection is never uploaded.
