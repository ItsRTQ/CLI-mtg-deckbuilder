"""Regression tests for the Scryfall bulk-data format migration (JSON array -> gzipped JSONL).

Scryfall dropped ``download_uri`` from the bulk-data metadata in favor of
``jsonl_download_uri`` (gzipped JSONL). The downloader must accept either key
and store plain text on disk; the SQLite ingest must parse both file formats.
"""

import gzip
import io
import json
from unittest.mock import patch, MagicMock

import pytest

from mtgcli.data import download_cards
from mtgcli.data.build_sqlite import _iter_raw_cards


CARDS = [
    {"name": "Sol Ring", "oracle_id": "aaa"},
    {"name": "Arcane Signet", "oracle_id": "bbb"},
]


class TestIterRawCards:
    def test_json_array(self):
        f = io.BytesIO(json.dumps(CARDS).encode())
        assert list(_iter_raw_cards(f)) == CARDS

    def test_jsonl(self):
        payload = b"\n".join(json.dumps(c).encode() for c in CARDS) + b"\n"
        f = io.BytesIO(payload)
        assert list(_iter_raw_cards(f)) == CARDS

    def test_jsonl_skips_blank_lines(self):
        payload = b"\n" + json.dumps(CARDS[0]).encode() + b"\n\n"
        f = io.BytesIO(payload)
        assert list(_iter_raw_cards(f)) == [CARDS[0]]

    def test_json_array_with_leading_whitespace(self):
        f = io.BytesIO(b"  \n" + json.dumps(CARDS).encode())
        assert list(_iter_raw_cards(f)) == CARDS


def _metadata_response(entry):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {"data": [entry]}
    return resp


def _stream_response(body: bytes):
    resp = MagicMock()
    resp.ok = True
    resp.raw = io.BytesIO(body)
    resp.iter_content = lambda chunk_size: iter([body])
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: False
    return resp


class TestDownloadDefaultCards:
    def _run(self, tmp_path, entry, body):
        target = tmp_path / "scryfall_cards.json"
        with patch.object(download_cards, "RAW_CARDS_PATH", target), \
             patch.object(download_cards.requests, "get") as mock_get:
            mock_get.side_effect = [_metadata_response(entry), _stream_response(body)]
            result = download_cards.download_default_cards()
        assert result == target
        return target.read_bytes()

    def test_jsonl_gz_uri_is_used_and_decompressed(self, tmp_path):
        jsonl = b"\n".join(json.dumps(c).encode() for c in CARDS)
        entry = {
            "type": "default_cards",
            "jsonl_download_uri": "https://data.scryfall.io/default-cards/x.jsonl.gz",
        }
        written = self._run(tmp_path, entry, gzip.compress(jsonl))
        assert written == jsonl  # stored decompressed

    def test_legacy_download_uri_still_works(self, tmp_path):
        body = json.dumps(CARDS).encode()
        entry = {
            "type": "default_cards",
            "download_uri": "https://data.scryfall.io/default-cards/x.json",
        }
        written = self._run(tmp_path, entry, body)
        assert written == body

    def test_missing_default_cards_raises(self, tmp_path):
        entry = {"type": "oracle_cards", "jsonl_download_uri": "https://x/y.jsonl.gz"}
        with pytest.raises(RuntimeError, match="default_cards"):
            self._run(tmp_path, entry, b"")
