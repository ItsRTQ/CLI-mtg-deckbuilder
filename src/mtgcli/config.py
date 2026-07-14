from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SEED_DATA_DIR = DATA_DIR / "seed"

OUTPUT_DIR = PROJECT_ROOT / "output"
FINAL_BUILDS_DIR = PROJECT_ROOT / "final-builds"
USER_BULK_DIR = PROJECT_ROOT / "user-bulk"
USER_BULK_FILE = USER_BULK_DIR / "collection.txt"
USER_BULK_JSON = USER_BULK_DIR / "collection.json"
LOGS_DIR = PROJECT_ROOT / "logs"

RAW_CARDS_PATH = RAW_DATA_DIR / "scryfall_cards.json"
SQLITE_PATH = PROCESSED_DATA_DIR / "mtg.sqlite"

# GUI (v0.9.0): built frontend served by gui_api when present (no mkdir — optional).
FRONTEND_DIST = PROJECT_ROOT / "gui" / "dist"

# Ensure all directories exist
for path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, SEED_DATA_DIR, OUTPUT_DIR, FINAL_BUILDS_DIR, LOGS_DIR, USER_BULK_DIR]:
    path.mkdir(parents=True, exist_ok=True)
