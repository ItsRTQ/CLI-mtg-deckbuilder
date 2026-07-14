"""Shared FastAPI dependencies."""
from fastapi import HTTPException

from mtgcli.cards.repository import CardRepository
from mtgcli.config import SQLITE_PATH


def get_repo_optional():
    """CardRepository, or None when the DB isn't built — for endpoints where card
    data is decoration (deck listings), not a requirement."""
    return CardRepository(str(SQLITE_PATH)) if SQLITE_PATH.exists() else None


def get_repo() -> CardRepository:
    """CardRepository for request handlers; 503 with the project's JSON error
    contract when the card database has not been built yet."""
    if not SQLITE_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail={"error": {"type": "environment",
                              "message": "Card database not found — run `mtg init-data` "
                                         "(or use the data-download button)."}},
        )
    return CardRepository(str(SQLITE_PATH))
