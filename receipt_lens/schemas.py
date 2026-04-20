from pydantic import BaseModel


class ReceiptItem(BaseModel):
    name: str
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None


class ReceiptData(BaseModel):
    store_name: str | None = None
    date: str | None = None
    items: list[ReceiptItem] = []
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    currency: str | None = None
    raw_text: str | None = None
    category: str | None = None


class ParseResponse(BaseModel):
    receipt: ReceiptData
    model: str
    confidence: str  # "high" | "medium" | "low"


class ScanSummary(BaseModel):
    id: int
    filename: str
    scanned_at: str
    store: str | None
    date: str | None
    total: float | None
    currency: str | None
    confidence: str | None
    model: str | None
    category: str | None = None


class HistoryResponse(BaseModel):
    scans: list[ScanSummary]
    count: int
