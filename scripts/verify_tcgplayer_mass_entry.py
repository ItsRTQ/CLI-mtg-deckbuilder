#!/usr/bin/env python3
"""Standalone TCGplayer Mass Entry verification utility (investigation only).

Builds candidate `c=` payloads for controlled card lists, prints the raw payload,
the encoded URL, and its length, and (optionally) opens the URL in the default
browser for MANUAL visual confirmation of what Mass Entry actually displays.

Isolated from production code on purpose: it imports nothing from mtgcli and
never modifies any deck. It never adds to cart, logs in, or purchases anything —
opening the page is as far as it goes.

Usage:
    python scripts/verify_tcgplayer_mass_entry.py --case basic
    python scripts/verify_tcgplayer_mass_entry.py --case split --open
    python scripts/verify_tcgplayer_mass_entry.py --case full-commander --variant no-leading

Variants (payload structure before encoding):
    leading    ||1 A||1 B||1 C     (current exporter behavior)
    no-leading 1 A||1 B||1 C       (matches partner URLs seen in the wild)
    newline    1 A\n1 B\n1 C       (expected to FAIL: parser splits on || only)
"""
import argparse
import sys
import webbrowser
from urllib.parse import parse_qs, urlencode, urlsplit

BASE = "https://www.tcgplayer.com/massentry"

CASES = {
    "basic": [
        "1 Sol Ring", "1 Arcane Signet", "1 Command Tower",
    ],
    "quantities": [
        "1 Sol Ring", "Sol Ring", "0 Sol Ring", "-1 Sol Ring",
        "abc Sol Ring", "1", "1    Sol Ring", "1 Sol Ring", "1 Sol Ring",
    ],
    "punctuation": [
        "1 Shorikai, Genesis Engine", "1 Urza's Saga", "1 Boseiju, Who Endures",
        "1 Eiganjo, Seat of the Empire", "1 Lim-Dûl's Vault", "1 Swords to Plowshares",
    ],
    "split": [
        "1 Wear // Tear", "1 Wear//Tear", "1 Wear / Tear", "1 Wear",
        "1 Fire // Ice", "1 Cut // Ribbons",
    ],
    "dfc": [
        "1 Delver of Secrets", "1 Delver of Secrets // Insectile Aberration",
        "1 Valakut Awakening", "1 Valakut Awakening // Valakut Stoneforge",
        "1 Bonecrusher Giant", "1 Bonecrusher Giant // Stomp",
        "1 Fable of the Mirror-Breaker",
    ],
    "exact-printing": [
        "1 Lightning Bolt", "1 Lightning Bolt [M11]", "1 Lightning Bolt [SLD] 84",
        "1 Lightning Bolt [sld] 84", "1 Lightning Bolt 84", "1 Lightning Bolt [INVALID] 84",
    ],
    "invalid": [
        "0 Sol Ring", "-1 Sol Ring", "1", "1 Not A Real Magic Card",
        "abc Sol Ring", "1 Lightning Bolt [INVALID] 999", "1 Island",
    ],
    # 100 entries with realistically long names — worst-case URL length probe.
    "full-commander": (
        ["1 Fable of the Mirror-Breaker"] * 30
        + ["1 Shorikai, Genesis Engine"] * 30
        + ["1 Boseiju, Who Endures"] * 40
    ),
}


def build_payload(entries, variant: str) -> str:
    if variant == "newline":
        return "\n".join(entries)
    body = "||".join(entries)
    return ("||" + body) if variant == "leading" else body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--case", choices=sorted(CASES), default="basic")
    ap.add_argument("--variant", choices=["leading", "no-leading", "newline"],
                    default="leading")
    ap.add_argument("--no-productline", action="store_true",
                    help="Omit productline=Magic (the page defaults to Magic)")
    ap.add_argument("--open", action="store_true",
                    help="Open the URL in the default browser for manual confirmation")
    args = ap.parse_args()

    entries = CASES[args.case]
    payload = build_payload(entries, args.variant)
    params = {} if args.no_productline else {"productline": "Magic"}
    params["c"] = payload
    url = f"{BASE}?{urlencode(params)}"

    print(f"case: {args.case}  variant: {args.variant}  entries: {len(entries)}")
    print("--- raw payload " + "-" * 44)
    print(payload)
    print("--- encoded URL " + "-" * 44)
    print(url)
    print("--- stats " + "-" * 50)
    print(f"url length: {len(url)} chars (observed 414 threshold: ~8.2-8.4k)")

    # Round-trip check: the decoded c param must equal the raw payload exactly
    # (single-pass encoding, no %252F/%257C double-encode artifacts).
    decoded = parse_qs(urlsplit(url).query)["c"][0]
    print(f"round-trip decode == payload: {decoded == payload}")

    if args.open:
        print("\nOpening browser — MANUALLY record which entries Mass Entry shows,")
        print("which are unmatched, and whether duplicates merged. Do NOT add to cart.")
        webbrowser.open(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
