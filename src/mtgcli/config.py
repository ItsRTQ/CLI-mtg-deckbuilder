from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SEED_DATA_DIR = DATA_DIR / "seed"

OUTPUT_DIR = PROJECT_ROOT / "output"
FINAL_BUILDS_DIR = PROJECT_ROOT / "final-builds"

RAW_CARDS_PATH = RAW_DATA_DIR / "scryfall_cards.json"
SQLITE_PATH = PROCESSED_DATA_DIR / "mtg.sqlite"

# Ensure all directories exist
for path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, SEED_DATA_DIR, OUTPUT_DIR, FINAL_BUILDS_DIR]:
    path.mkdir(parents=True, exist_ok=True)
