"""Build-time object models (Consistency-engine Fase 2, user design 2026-07-06).

CARD: a build-context card — agent judgment (purpose, note) + DB-hydrated facts.
DECK: a List of CARDs; the object that serializes to JSON.

These objects are EPHEMERAL — they live for the duration of a build session and
may be discarded once the build completes (the user keeps the DB updated; facts
are always re-hydrated fresh, never trusted from old serializations).
"""
from mtgcli.models.card import Card, CardNotFoundError, PURPOSES  # noqa: F401
from mtgcli.models.deck import COMBO_CLASSES, Deck, DeckError, IDEAL_CURVE  # noqa: F401
