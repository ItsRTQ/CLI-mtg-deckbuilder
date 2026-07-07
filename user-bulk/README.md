# user-bulk — the cards you already OWN

`collection.txt` in this directory is your personal card collection. Cards
listed here are **excluded from budget bills**: `mtg budget` (and preflight's
budget gate) prices an owned copy at $0, up to the quantity you own, and shows
what it excluded on a visible `Owned (user-bulk)` line. Disable per-run with
`budget --no-bulk`.

## Maintain it with the tool (validated)

```bash
mtg bulk-add --cards "Sol Ring;2 Arcane Signet;Rhystic Study"   # add (fuzzy did-you-mean on typos)
mtg bulk-add --remove "Rhystic Study"                            # remove / decrement
mtg bulk-add --list                                              # view with prices + known value
```

## Or edit `collection.txt` by hand

Plain decklist format, one card per line — quantity optional, `#` comments allowed:

```text
# my staples box
2 Sol Ring
Arcane Signet
17 Mountain
```

Hand-written names are matched case-insensitively, but they must be the real
card names — run `mtg cards-batch user-bulk/collection.txt --verify` after a
manual edit to catch typos (the tool-managed path validates automatically).
