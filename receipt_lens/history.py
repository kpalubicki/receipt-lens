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


def spending_analytics(currency: str | None = None) -> dict[str, Any]:
    """Return spending analytics derived from saved scans.

    Includes:
    - total_spent: sum of all receipt totals (optionally filtered by currency)
    - by_store: {store_name: total_spent} sorted descending
    - by_month: {YYYY-MM: total_spent} sorted chronologically
    - scan_count: total number of scans in history
    - receipts_with_total: how many scans had a parseable total
    """
    with _conn() as conn:
        _ensure_table(conn)
        if currency:
            rows = conn.execute(
                "SELECT store, date, total, currency FROM scans WHERE total IS NOT NULL AND UPPER(currency) = UPPER(?)",
                (currency,),
            ).fetchall()
            scan_count = conn.execute(
                "SELECT COUNT(*) FROM scans WHERE UPPER(currency) = UPPER(?)", (currency,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT store, date, total, currency FROM scans WHERE total IS NOT NULL"
            ).fetchall()
            scan_count = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]

    total_spent = 0.0
    by_store: dict[str, float] = {}
    by_month: dict[str, float] = {}

    for row in rows:
        store = row["store"] or "Unknown"
        total = row["total"] or 0.0
        date_str = row["date"] or ""

        total_spent += total
        by_store[store] = round(by_store.get(store, 0.0) + total, 2)

        # Try to extract YYYY-MM from various date formats
        month_key = _extract_month(date_str)
        if month_key:
            by_month[month_key] = round(by_month.get(month_key, 0.0) + total, 2)

    return {
        "scan_count": scan_count,
        "receipts_with_total": len(rows),
        "total_spent": round(total_spent, 2),
        "by_store": dict(sorted(by_store.items(), key=lambda x: -x[1])),
        "by_month": dict(sorted(by_month.items())),
    }


def _extract_month(date_str: str) -> str | None:
    """Try to extract YYYY-MM from a date string."""
    import re
    # ISO: 2026-04-25
    m = re.search(r"(\d{4})-(\d{2})", date_str)
    if m:
        return f"{m[1]}-{m[2]}"
    # DD/MM/YYYY or MM/DD/YYYY — take the year + last two-digit group as month guess
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", date_str)
    if m:
        return f"{m[3]}-{int(m[2]):02d}"
    return None


def budget_alert(threshold: float, currency: str | None = None) -> dict[str, Any]:
    """Return months where spending exceeded the given threshold.

    Returns:
    - threshold: the value used
    - currency: filter applied (or None for all)
    - alerts: list of {month, spent, over_by} for months above threshold
    - ok: True if no month exceeded the threshold
    """
    analytics = spending_analytics(currency=currency)
    alerts = []
    for month, spent in analytics["by_month"].items():
        if spent > threshold:
            alerts.append({
                "month": month,
                "spent": spent,
                "over_by": round(spent - threshold, 2),
            })
    return {
        "threshold": threshold,
        "currency": currency,
        "alerts": sorted(alerts, key=lambda x: x["month"]),
        "ok": len(alerts) == 0,
    }


def delete_scan(scan_id: int) -> bool:
    """Delete a scan. Returns True if it existed."""
    with _conn() as conn:
        _ensure_table(conn)
        cur = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        conn.commit()
        return cur.rowcount > 0
