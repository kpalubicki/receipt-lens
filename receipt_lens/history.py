"""SQLite-backed history of parsed receipts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from receipt_lens.config import settings


def _conn() -> sqlite3.Connection:
    Path(settings.history_db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.history_db)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            scanned_at TEXT NOT NULL,
            store    TEXT,
            date     TEXT,
            total    REAL,
            currency TEXT,
            confidence TEXT,
            model    TEXT,
            data     TEXT NOT NULL
        )
    """)
    conn.commit()


def save_scan(filename: str, result: Any) -> int:
    """Persist a ParseResponse to history. Returns the new scan ID."""
    receipt = result.receipt
    with _conn() as conn:
        _ensure_table(conn)
        cur = conn.execute(
            """INSERT INTO scans
               (filename, scanned_at, store, date, total, currency, confidence, model, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                filename,
                datetime.now(timezone.utc).isoformat(),
                receipt.store_name,
                receipt.date,
                receipt.total,
                receipt.currency,
                result.confidence,
                result.model,
                result.model_dump_json(),
            ),
        )
        return cur.lastrowid


def list_scans(limit: int = 50, offset: int = 0) -> list[dict]:
    """Return scan history rows, newest first."""
    with _conn() as conn:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT id, filename, scanned_at, store, date, total, currency, confidence, model "
            "FROM scans ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def get_scan(scan_id: int) -> dict | None:
    """Return a single scan with full data by ID."""
    with _conn() as conn:
        _ensure_table(conn)
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["data"] = json.loads(result["data"])
        return result


def delete_scan(scan_id: int) -> bool:
    """Delete a scan. Returns True if it existed."""
    with _conn() as conn:
        _ensure_table(conn)
        cur = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        conn.commit()
        return cur.rowcount > 0
