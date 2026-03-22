"""Tests for FastAPI endpoints."""

import json
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from receipt_lens.main import app
from receipt_lens.schemas import ParseResponse, ReceiptData


client = TestClient(app)


def _make_image(fmt: str = "JPEG") -> bytes:
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _mock_parse(store="Biedronka", total=12.89):
    return ParseResponse(
        receipt=ReceiptData(store_name=store, total=total, items=[]),
        model="llava:7b",
        confidence="high",
    )


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parse_jpeg_success():
    img = _make_image("JPEG")
    with patch("receipt_lens.main.parse_receipt", return_value=_mock_parse()):
        response = client.post(
            "/parse",
            files={"file": ("receipt.jpg", img, "image/jpeg")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["receipt"]["store_name"] == "Biedronka"
    assert data["receipt"]["total"] == 12.89
    assert data["confidence"] == "high"


def test_parse_png_success():
    img = _make_image("PNG")
    with patch("receipt_lens.main.parse_receipt", return_value=_mock_parse(store="Lidl")):
        response = client.post(
            "/parse",
            files={"file": ("receipt.png", img, "image/png")},
        )
    assert response.status_code == 200
    assert response.json()["receipt"]["store_name"] == "Lidl"


def test_parse_unsupported_type():
    response = client.post(
        "/parse",
        files={"file": ("doc.pdf", b"fake pdf content", "application/pdf")},
    )
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_parse_model_error_returns_502():
    img = _make_image()
    with patch("receipt_lens.main.parse_receipt", side_effect=RuntimeError("model offline")):
        response = client.post(
            "/parse",
            files={"file": ("receipt.jpg", img, "image/jpeg")},
        )
    assert response.status_code == 502
    assert "model offline" in response.json()["detail"]
