"""PDF export for parsed receipts."""

from __future__ import annotations

from receipt_lens.schemas import ParseResponse

_CONFIDENCE_COLOR = {
    "high": (40, 167, 69),
    "medium": (255, 153, 0),
    "low": (220, 53, 69),
}


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if value == int(value) else f"{value:.2f}"


def _fmt_price(value: float | None, currency: str | None) -> str:
    if value is None:
        return ""
    sym = {"USD": "$", "EUR": "E", "GBP": "L"}.get((currency or "").upper(), "")
    return f"{sym}{value:.2f}"


def generate_pdf(result: ParseResponse) -> bytes:
    """Render a ParseResponse as a PDF and return the raw bytes."""
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise ImportError(
            "PDF export requires 'fpdf2'. Install it with: pip install fpdf2"
        ) from exc

    r = result.receipt
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin

    # --- Header ---
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_fill_color(30, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(0, 14, r.store_name or "Receipt", fill=True, align="C")
    pdf.ln(2)

    # --- Meta ---
    meta_parts = []
    if r.date:
        meta_parts.append(f"Date: {r.date}")
    if r.currency:
        meta_parts.append(f"Currency: {r.currency}")
    if meta_parts:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, "   |   ".join(meta_parts), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # --- Items table ---
    col_name = usable_w * 0.45
    col_qty = usable_w * 0.15
    col_unit = usable_w * 0.20
    col_total = usable_w * 0.20

    # Header
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(col_name, 7, "Item", border=1, fill=True)
    pdf.cell(col_qty, 7, "Qty", border=1, fill=True, align="R")
    pdf.cell(col_unit, 7, "Unit price", border=1, fill=True, align="R")
    pdf.cell(col_total, 7, "Total", border=1, fill=True, align="R")
    pdf.ln()

    # Rows — draw name with multi_cell to handle wrapping, then fill remaining cells
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(50, 50, 50)
    row_h = 6

    for item in r.items:
        row_y = pdf.get_y()

        # Draw name cell (may wrap)
        pdf.set_xy(pdf.l_margin, row_y)
        pdf.multi_cell(col_name, row_h, item.name, border=1)
        actual_h = pdf.get_y() - row_y

        # Fill remaining 3 cells at same y, using actual height
        pdf.set_xy(pdf.l_margin + col_name, row_y)
        pdf.cell(col_qty, actual_h, _fmt(item.quantity), border=1, align="R")
        pdf.cell(col_unit, actual_h, _fmt_price(item.unit_price, r.currency), border=1, align="R")
        pdf.cell(col_total, actual_h, _fmt_price(item.total_price, r.currency), border=1, align="R")
        pdf.set_xy(pdf.l_margin, row_y + actual_h)

    if not r.items:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 8, "No items extracted.", new_x="LMARGIN", new_y="NEXT")

    # --- Totals ---
    pdf.ln(3)
    for label, value in [("Subtotal", r.subtotal), ("Tax", r.tax), ("TOTAL", r.total)]:
        if value is None:
            continue
        bold = label == "TOTAL"
        pdf.set_font("Helvetica", "B" if bold else "", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(usable_w * 0.8, 7, label, align="R")
        pdf.cell(usable_w * 0.2, 7, _fmt_price(value, r.currency), align="R",
                 new_x="LMARGIN", new_y="NEXT")

    # --- Footer ---
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    cr, cg, cb = _CONFIDENCE_COLOR.get(result.confidence, (100, 100, 100))
    pdf.set_text_color(cr, cg, cb)
    pdf.cell(0, 5, f"Confidence: {result.confidence.upper()}   |   Model: {result.model}", align="C")

    return bytes(pdf.output())


def generate_analytics_pdf(data: dict, title: str = "Spending Report") -> bytes:
    """Render spending analytics as a PDF report."""
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise ImportError("PDF export requires 'fpdf2'. Install it with: pip install fpdf2") from exc

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin

    def _section(label: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(50, 50, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 9, label, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def _table_row(left: str, right: str, bold: bool = False) -> None:
        pdf.set_font("Helvetica", "B" if bold else "", 9)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(usable_w * 0.7, 6, left, border="B")
        pdf.cell(usable_w * 0.3, 6, right, border="B", align="R", new_x="LMARGIN", new_y="NEXT")

    # Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_fill_color(30, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(0, 13, title, fill=True, align="C")
    pdf.ln(4)

    # Summary
    _section("Summary")
    _table_row("Total receipts scanned", str(data.get("scan_count", 0)))
    _table_row("Receipts with totals", str(data.get("receipts_with_total", 0)))
    _table_row("Total spent", f"{data.get('total_spent', 0.0):.2f}", bold=True)
    pdf.ln(5)

    # By category
    by_category = data.get("by_category", {})
    if by_category:
        _section("By Category")
        for category, total in by_category.items():
            _table_row(category.capitalize(), f"{total:.2f}")
        pdf.ln(5)

    # By store
    by_store = data.get("by_store", {})
    if by_store:
        _section("By Store")
        for store, total in list(by_store.items())[:15]:  # cap at 15 to avoid pagination issues
            _table_row(store, f"{total:.2f}")
        pdf.ln(5)

    # By month
    by_month = data.get("by_month", {})
    if by_month:
        _section("By Month")
        for month, total in by_month.items():
            _table_row(month, f"{total:.2f}")

    return bytes(pdf.output())
