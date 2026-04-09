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


# --- /export/csv tests ---

EXPORT_PAYLOAD = {
    "receipt": {
        "store_name": "SuperMart",
        "date": "2026-04-01",
        "items": [
            {"name": "Milk", "quantity": 2, "unit_price": 1.5, "total_price": 3.0},
            {"name": "Bread", "quantity": 1, "unit_price": 2.5, "total_price": 2.5},
        ],
        "subtotal": 5.5,
        "tax": 0.44,
        "total": 5.94,
        "currency": "USD",
    },
    "model": "llava:7b",
    "confidence": "high",
}


def test_export_csv_returns_file():
    r = client.post("/export/csv", json=EXPORT_PAYLOAD)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "supermart.csv" in r.headers["content-disposition"]


def test_export_csv_contains_items():
    r = client.post("/export/csv", json=EXPORT_PAYLOAD)
    assert "Milk" in r.text
    assert "Bread" in r.text
    assert "1.5" in r.text
    assert "2.5" in r.text


def test_export_csv_contains_totals():
    r = client.post("/export/csv", json=EXPORT_PAYLOAD)
    assert "subtotal" in r.text
    assert "5.5" in r.text
    assert "tax" in r.text
    assert "total" in r.text
    assert "5.94" in r.text


def test_export_csv_no_store_name():
    payload = {**EXPORT_PAYLOAD, "receipt": {**EXPORT_PAYLOAD["receipt"], "store_name": None}}
    r = client.post("/export/csv", json=payload)
    assert r.status_code == 200
    assert "receipt.csv" in r.headers["content-disposition"]


# --- /export/pdf tests ---

def test_export_pdf_returns_pdf():
    r = client.post("/export/pdf", json=EXPORT_PAYLOAD)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_export_pdf_filename_uses_store_and_date():
    r = client.post("/export/pdf", json=EXPORT_PAYLOAD)
    cd = r.headers["content-disposition"]
    assert "supermart" in cd
    assert "2026-04-01" in cd
    assert ".pdf" in cd


def test_export_pdf_no_store_name():
    payload = {**EXPORT_PAYLOAD, "receipt": {**EXPORT_PAYLOAD["receipt"], "store_name": None}}
    r = client.post("/export/pdf", json=payload)
    assert r.status_code == 200
    assert "receipt" in r.headers["content-disposition"]


def test_export_pdf_no_items():
    payload = {**EXPORT_PAYLOAD, "receipt": {**EXPORT_PAYLOAD["receipt"], "items": []}}
    r = client.post("/export/pdf", json=payload)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_export_pdf_501_when_fpdf2_missing():
    with patch("receipt_lens.main.generate_pdf", side_effect=ImportError("fpdf2 not installed")):
        r = client.post("/export/pdf", json=EXPORT_PAYLOAD)
    assert r.status_code == 501


# --- /parse/batch tests ---

def test_batch_parse_two_files():
    img = _make_image()
    with patch("receipt_lens.main.parse_receipt", return_value=_mock_parse()):
        r = client.post(
            "/parse/batch",
            files=[
                ("files", ("a.jpg", img, "image/jpeg")),
                ("files", ("b.jpg", img, "image/jpeg")),
            ],
        )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0


def test_batch_parse_partial_failure():
    img = _make_image()

    def failing_parse(b):
        raise RuntimeError("model offline")

    with patch("receipt_lens.main.parse_receipt", side_effect=failing_parse):
        r = client.post(
            "/parse/batch",
            files=[("files", ("a.jpg", img, "image/jpeg"))],
        )
    data = r.json()
    assert data["failed"] == 1
    assert "model offline" in data["results"][0]["error"]


def test_batch_parse_unsupported_type():
    img = _make_image()
    r = client.post(
        "/parse/batch",
        files=[
            ("files", ("a.jpg", img, "image/jpeg")),
            ("files", ("doc.pdf", b"pdf", "application/pdf")),
        ],
    )
    data = r.json()
    assert data["succeeded"] == 0 or data["failed"] >= 1
    errors = [res for res in data["results"] if res["error"]]
    assert any("Unsupported" in e["error"] for e in errors)


def test_batch_parse_too_many_files():
    img = _make_image()
    files = [("files", (f"r{i}.jpg", img, "image/jpeg")) for i in range(11)]
    r = client.post("/parse/batch", files=files)
    assert r.status_code == 422
    assert "Too many" in r.json()["detail"]


# --- /history tests ---

def test_history_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("receipt_lens.main.settings",
        type("S", (), {"vision_model": "llava:7b", "max_image_size_mb": 10,
                       "max_batch_files": 10, "history_db": str(tmp_path / "h.db")})())
    monkeypatch.setattr("receipt_lens.history.settings",
        type("S", (), {"history_db": str(tmp_path / "h.db")})())
    r = client.get("/history")
    assert r.status_code == 200
    assert r.json()["scans"] == []
    assert r.json()["count"] == 0


def test_history_saved_after_parse(tmp_path, monkeypatch):
    db = str(tmp_path / "h.db")
    monkeypatch.setattr("receipt_lens.history.settings", type("S", (), {"history_db": db})())
    img = _make_image()
    with patch("receipt_lens.main.parse_receipt", return_value=_mock_parse("Lidl", 22.5)):
        client.post("/parse", files={"file": ("lidl.jpg", img, "image/jpeg")})

    from receipt_lens import history as h
    rows = h.list_scans()
    assert len(rows) == 1
    assert rows[0]["store"] == "Lidl"


def test_history_get_item(tmp_path, monkeypatch):
    db = str(tmp_path / "h.db")
    monkeypatch.setattr("receipt_lens.history.settings", type("S", (), {"history_db": db})())
    from receipt_lens import history as h
    mock = _mock_parse("Biedronka", 10.0)
    scan_id = h.save_scan("b.jpg", mock)
    row = h.get_scan(scan_id)
    assert row is not None
    assert row["store"] == "Biedronka"


def test_history_delete_item(tmp_path, monkeypatch):
    db = str(tmp_path / "h.db")
    monkeypatch.setattr("receipt_lens.history.settings", type("S", (), {"history_db": db})())
    from receipt_lens import history as h
    mock = _mock_parse("Aldi", 5.0)
    scan_id = h.save_scan("a.jpg", mock)
    assert h.delete_scan(scan_id) is True
    assert h.get_scan(scan_id) is None
