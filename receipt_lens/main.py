"""FastAPI application for receipt-lens."""

from __future__ import annotations

import csv
import io

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from receipt_lens.config import settings
from receipt_lens.parser import parse_receipt
from receipt_lens.schemas import ParseResponse

SUPPORTED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}

app = FastAPI(
    title="receipt-lens",
    description="Drop in a receipt photo, get back structured data.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": settings.vision_model}


@app.post("/parse", response_model=ParseResponse)
async def parse(file: UploadFile = File(...)) -> ParseResponse:
    """Upload a receipt image and get back structured JSON data."""
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Use JPEG, PNG, or WEBP.",
        )

    image_bytes = await file.read()
    max_bytes = settings.max_image_size_mb * 1024 * 1024
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_image_size_mb} MB.",
        )

    try:
        result = parse_receipt(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model error: {e}") from e

    return result


@app.post("/export/csv")
def export_csv(result: ParseResponse) -> Response:
    """Return receipt items as a downloadable CSV file."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "quantity", "unit_price", "total_price"])
    for item in result.receipt.items:
        writer.writerow([item.name, item.quantity, item.unit_price, item.total_price])
    writer.writerow([])
    if result.receipt.subtotal is not None:
        writer.writerow(["subtotal", "", "", result.receipt.subtotal])
    if result.receipt.tax is not None:
        writer.writerow(["tax", "", "", result.receipt.tax])
    if result.receipt.total is not None:
        writer.writerow(["total", "", "", result.receipt.total])

    store = (result.receipt.store_name or "receipt").lower().replace(" ", "-")
    filename = f"{store}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
