"""FastAPI application for receipt-lens."""

from __future__ import annotations

import csv
import io

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from receipt_lens.config import settings
from receipt_lens.history import delete_scan, get_scan, list_scans, save_scan
from receipt_lens.parser import parse_receipt
from receipt_lens.pdf import generate_pdf
from receipt_lens.schemas import HistoryResponse, ParseResponse, ScanSummary

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

    save_scan(file.filename or "unknown", result)
    return result


class BatchParseResult(BaseModel):
    filename: str
    result: ParseResponse | None = None
    error: str | None = None


class BatchParseResponse(BaseModel):
    results: list[BatchParseResult]
    total: int
    succeeded: int
    failed: int


@app.post("/parse/batch", response_model=BatchParseResponse)
async def parse_batch(files: list[UploadFile] = File(...)) -> BatchParseResponse:
    """Upload multiple receipt images and get back structured data for each."""
    if not files:
        raise HTTPException(status_code=422, detail="At least one file is required.")
    if len(files) > settings.max_batch_files:
        raise HTTPException(
            status_code=422,
            detail=f"Too many files. Maximum is {settings.max_batch_files}.",
        )

    max_bytes = settings.max_image_size_mb * 1024 * 1024
    results: list[BatchParseResult] = []

    for upload in files:
        filename = upload.filename or "unknown"
        if upload.content_type not in SUPPORTED_TYPES:
            results.append(BatchParseResult(
                filename=filename,
                error=f"Unsupported file type '{upload.content_type}'.",
            ))
            continue

        image_bytes = await upload.read()
        if len(image_bytes) > max_bytes:
            results.append(BatchParseResult(
                filename=filename,
                error=f"File too large. Maximum size is {settings.max_image_size_mb} MB.",
            ))
            continue

        try:
            parsed = parse_receipt(image_bytes)
            save_scan(filename, parsed)
            results.append(BatchParseResult(filename=filename, result=parsed))
        except Exception as e:
            results.append(BatchParseResult(filename=filename, error=str(e)))

    succeeded = sum(1 for r in results if r.result is not None)
    return BatchParseResponse(
        results=results,
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
    )


@app.get("/history", response_model=HistoryResponse)
def get_history(limit: int = 50, offset: int = 0) -> HistoryResponse:
    """List past receipt scans, newest first."""
    rows = list_scans(limit=limit, offset=offset)
    scans = [ScanSummary(**r) for r in rows]
    return HistoryResponse(scans=scans, count=len(scans))


@app.get("/history/{scan_id}")
def get_history_item(scan_id: int) -> dict:
    """Get full details of a single past scan including parsed receipt data."""
    scan = get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found.")
    return scan


@app.delete("/history/{scan_id}", status_code=204, response_model=None)
def delete_history_item(scan_id: int) -> None:
    """Delete a scan from history."""
    if not delete_scan(scan_id):
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found.")


@app.post("/export/pdf")
def export_pdf(result: ParseResponse) -> Response:
    """Return a formatted PDF of the receipt."""
    try:
        pdf_bytes = generate_pdf(result)
    except ImportError as e:
        raise HTTPException(status_code=501, detail=str(e))

    store = (result.receipt.store_name or "receipt").lower().replace(" ", "-")[:40]
    date = ("-" + result.receipt.date.replace("/", "-").replace(" ", "-")) if result.receipt.date else ""
    filename = f"{store}{date}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
