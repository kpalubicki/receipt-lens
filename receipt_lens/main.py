"""FastAPI application for receipt-lens."""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

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
