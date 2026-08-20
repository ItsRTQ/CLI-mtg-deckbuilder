import gzip
import shutil
import requests
from pathlib import Path
from mtgcli.config import RAW_CARDS_PATH

SCRYFALL_BULK_API_URL = "https://api.scryfall.com/bulk-data"

HEADERS = {
    "User-Agent": "mtgcli/1.0",
    "Accept": "application/json",
}

def download_default_cards() -> Path:
    """
    Downloads Scryfall bulk card data and saves it to data/raw/scryfall_cards.json.

    Scryfall serves bulk data either as a plain JSON array (legacy
    ``download_uri``) or as gzipped JSONL (``jsonl_download_uri``, current API).
    Both are handled; gzipped payloads are decompressed on the fly so the file
    on disk is always plain text (JSON array or JSONL).

    Returns:
        Path: The path to the saved JSON file.

    Raises:
        RuntimeError: If the API request fails or the required bulk data type is not found.
    """
    response = requests.get(SCRYFALL_BULK_API_URL, headers=HEADERS)
    if not response.ok:
        raise RuntimeError(f"Failed to fetch bulk data metadata: {response.status_code}")

    bulk_metadata = response.json()

    # Find the 'default_cards' bulk object
    download_uri = None
    for data_obj in bulk_metadata.get("data", []):
        if data_obj.get("type") == "default_cards":
            download_uri = data_obj.get("download_uri") or data_obj.get("jsonl_download_uri")
            break

    if not download_uri:
        raise RuntimeError("Could not find 'default_cards' bulk data type in Scryfall metadata.")

    # Download the actual card data
    with requests.get(download_uri, headers=HEADERS, stream=True) as r:
        if not r.ok:
            raise RuntimeError(f"Failed to download card data: {r.status_code}")

        RAW_CARDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RAW_CARDS_PATH, "wb") as f:
            if download_uri.endswith(".gz"):
                # The gzip is the file's own compression, not transport encoding
                r.raw.decode_content = True
                with gzip.GzipFile(fileobj=r.raw) as gz:
                    shutil.copyfileobj(gz, f)
            else:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

    return RAW_CARDS_PATH
