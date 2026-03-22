"""Vision-based receipt parser using Ollama."""

from __future__ import annotations

import base64
import json
import re
from io import BytesIO

from PIL import Image
import ollama

from receipt_lens.config import settings
from receipt_lens.schemas import ReceiptData, ReceiptItem, ParseResponse


PROMPT = """You are a receipt parser. Extract all information from this receipt image.

Return ONLY a valid JSON object with this exact structure (omit fields you can't find):
{
  "store_name": "string or null",
  "date": "string or null",
  "items": [
    {"name": "string", "quantity": number_or_null, "unit_price": number_or_null, "total_price": number_or_null}
  ],
  "subtotal": number_or_null,
  "tax": number_or_null,
  "total": number_or_null,
  "currency": "string or null"
}

Rules:
- All prices must be numbers (not strings)
- Do not include any text outside the JSON
- If you cannot read a value clearly, use null"""


def _prepare_image(image_bytes: bytes, max_mb: int = 10) -> tuple[str, str]:
    """Resize if needed and return base64 + mime type."""
    img = Image.open(BytesIO(image_bytes))
    mime = "image/jpeg" if img.format in (None, "JPEG") else f"image/{img.format.lower()}"

    # resize if too large
    max_bytes = max_mb * 1024 * 1024
    if len(image_bytes) > max_bytes:
        scale = (max_bytes / len(image_bytes)) ** 0.5
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        image_bytes = buf.getvalue()
        mime = "image/jpeg"

    return base64.b64encode(image_bytes).decode(), mime


def _extract_json(text: str) -> dict:
    """Extract JSON from model response, even if there's surrounding text."""
    text = text.strip()

    # try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # look for JSON block
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from model response: {text[:200]}")


def _confidence(data: dict) -> str:
    """Rough confidence based on how many fields were extracted."""
    filled = sum(1 for v in [data.get("store_name"), data.get("date"), data.get("total")] if v is not None)
    items = len(data.get("items", []))
    if filled >= 2 and items > 0:
        return "high"
    if filled >= 1 or items > 0:
        return "medium"
    return "low"


def parse_receipt(image_bytes: bytes) -> ParseResponse:
    """Parse a receipt image and return structured data."""
    img_b64, mime = _prepare_image(image_bytes, max_mb=settings.max_image_size_mb)

    response = ollama.chat(
        model=settings.vision_model,
        messages=[
            {
                "role": "user",
                "content": PROMPT,
                "images": [img_b64],
            }
        ],
    )

    raw_text = response.message.content.strip()

    try:
        data = _extract_json(raw_text)
    except ValueError:
        data = {}

    items = [
        ReceiptItem(
            name=item.get("name", "unknown"),
            quantity=item.get("quantity"),
            unit_price=item.get("unit_price"),
            total_price=item.get("total_price"),
        )
        for item in data.get("items", [])
        if isinstance(item, dict)
    ]

    receipt = ReceiptData(
        store_name=data.get("store_name"),
        date=data.get("date"),
        items=items,
        subtotal=data.get("subtotal"),
        tax=data.get("tax"),
        total=data.get("total"),
        currency=data.get("currency"),
        raw_text=raw_text,
    )

    return ParseResponse(
        receipt=receipt,
        model=settings.vision_model,
        confidence=_confidence(data),
    )
