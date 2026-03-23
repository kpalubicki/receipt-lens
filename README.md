# receipt-lens

I kept putting off entering receipts into a spreadsheet. Then I kept putting off writing a script to do it. This is the script — it takes a photo of a receipt and returns structured JSON. Store name, line items, prices, total. Runs llava:7b locally through Ollama.

Results vary. Blurry photos, thermal paper that's faded, anything handwritten — expect `"confidence": "low"`. Clear supermarket receipts work well.

## quick start

You need Ollama. Get it from https://ollama.ai/, then:

```bash
git clone https://github.com/kpalubicki/receipt-lens.git
cd receipt-lens
pip install -e .
ollama pull llava:7b
uvicorn receipt_lens.main:app --reload
```

Swagger at http://localhost:8001/docs.

## example

```bash
curl -X POST http://localhost:8001/parse \
  -F "file=@receipt.jpg"
```

```json
{
  "receipt": {
    "store_name": "Biedronka",
    "date": "2026-03-15",
    "items": [
      {"name": "Mleko 3.2%", "quantity": 2, "unit_price": 3.49, "total_price": 6.98},
      {"name": "Chleb tostowy", "quantity": 1, "unit_price": 4.29, "total_price": 4.29}
    ],
    "subtotal": 11.27,
    "tax": 0.90,
    "total": 12.17,
    "currency": "PLN"
  },
  "model": "llava:7b",
  "confidence": "high"
}
```

## configuration

`.env` file, all optional:

```
VISION_MODEL=llava:7b
MAX_IMAGE_SIZE_MB=10
APP_PORT=8001
```

## tests

```bash
pip install -e ".[dev]"
pytest
```

## stack

Python 3.10+, FastAPI, Pillow, Ollama

## license

MIT
