"""Tests for receipt parser — JSON extraction and data mapping."""

import json
from unittest.mock import MagicMock, patch

import pytest

from receipt_lens.parser import _extract_json, _confidence, parse_receipt
from receipt_lens.schemas import ParseResponse


SAMPLE_RECEIPT_JSON = {
    "store_name": "Biedronka",
    "date": "2026-03-21",
    "items": [
        {"name": "Mleko 1L", "quantity": 2, "unit_price": 3.49, "total_price": 6.98},
        {"name": "Chleb", "quantity": 1, "unit_price": 4.99, "total_price": 4.99},
    ],
    "subtotal": 11.97,
    "tax": 0.92,
    "total": 12.89,
    "currency": "PLN",
}


# --- _extract_json ---

def test_extract_json_clean():
    result = _extract_json(json.dumps(SAMPLE_RECEIPT_JSON))
    assert result["store_name"] == "Biedronka"


def test_extract_json_with_surrounding_text():
    text = f"Here is the parsed data:\n```json\n{json.dumps(SAMPLE_RECEIPT_JSON)}\n```"
    result = _extract_json(text)
    assert result["total"] == 12.89


def test_extract_json_fails_on_garbage():
    with pytest.raises(ValueError, match="Could not extract JSON"):
        _extract_json("This is not JSON at all, just plain text.")


def test_extract_json_partial():
    partial = '{"store_name": "Lidl", "total": 25.50}'
    result = _extract_json(partial)
    assert result["store_name"] == "Lidl"


# --- _confidence ---

def test_confidence_high_with_full_data():
    data = {"store_name": "Biedronka", "date": "2026-03-21", "total": 12.89, "items": [{"name": "x"}]}
    assert _confidence(data) == "high"


def test_confidence_medium_with_some_data():
    data = {"store_name": None, "date": None, "total": 12.89, "items": []}
    assert _confidence(data) == "medium"


def test_confidence_low_empty():
    assert _confidence({}) == "low"


# --- parse_receipt ---

def _mock_ollama_response(content: str):
    msg = MagicMock()
    msg.message.content = content
    return msg


def _make_dummy_image() -> bytes:
    from PIL import Image
    from io import BytesIO
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_parse_receipt_happy_path():
    image_bytes = _make_dummy_image()
    with patch("receipt_lens.parser.ollama.chat", return_value=_mock_ollama_response(json.dumps(SAMPLE_RECEIPT_JSON))):
        result = parse_receipt(image_bytes)

    assert isinstance(result, ParseResponse)
    assert result.receipt.store_name == "Biedronka"
    assert result.receipt.total == 12.89
    assert len(result.receipt.items) == 2
    assert result.confidence == "high"


def test_parse_receipt_bad_json_returns_empty():
    image_bytes = _make_dummy_image()
    with patch("receipt_lens.parser.ollama.chat", return_value=_mock_ollama_response("I can't read this receipt.")):
        result = parse_receipt(image_bytes)

    assert isinstance(result, ParseResponse)
    assert result.receipt.store_name is None
    assert result.receipt.items == []
    assert result.confidence == "low"


def test_parse_receipt_partial_json():
    image_bytes = _make_dummy_image()
    partial = '{"store_name": "Auchan", "total": 55.20, "items": []}'
    with patch("receipt_lens.parser.ollama.chat", return_value=_mock_ollama_response(partial)):
        result = parse_receipt(image_bytes)

    assert result.receipt.store_name == "Auchan"
    assert result.receipt.total == 55.20


def test_parse_receipt_items_mapped_correctly():
    image_bytes = _make_dummy_image()
    with patch("receipt_lens.parser.ollama.chat", return_value=_mock_ollama_response(json.dumps(SAMPLE_RECEIPT_JSON))):
        result = parse_receipt(image_bytes)

    first = result.receipt.items[0]
    assert first.name == "Mleko 1L"
    assert first.quantity == 2
    assert first.unit_price == 3.49
