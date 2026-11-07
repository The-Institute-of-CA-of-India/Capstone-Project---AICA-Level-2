"""Measure field-level OCR accuracy on the sample documents, clean and degraded.

The degraded set simulates a phone photo: 1.5 degree skew, blur, noise, uneven light, lower
resolution and JPEG compression. These are synthetic documents, so the results show how the
pipeline behaves, not how it will perform on real vendor invoices.

Run: python scripts/ocr_benchmark.py
Writes: docs/ocr_benchmark.json
"""
import io
import json
import random
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.invoices.ocr_engine import extract_invoice_data, load_pages  # noqa: E402

SAMPLES = ROOT / "tests" / "sample_invoices"
FIELDS = ("vendor", "gstin", "number", "date", "taxable", "cgst", "sgst", "igst", "total")


def degrade(image, seed):
    rng = random.Random(seed)
    photo = image.convert("RGB").rotate(rng.choice((-1.5, 1.5)), expand=True, fillcolor=(235, 235, 230), resample=Image.BICUBIC)
    photo = photo.resize((int(photo.width * .62), int(photo.height * .62)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(.8))
    pixels = photo.load()
    for y in range(0, photo.height):
        shade = 1 - .18 * (y / photo.height)  # light falling off down the page
        for x in range(0, photo.width, 1):
            r, g, b = pixels[x, y]
            noise = rng.randint(-10, 10)
            pixels[x, y] = tuple(max(0, min(255, int(c * shade) + noise)) for c in (r, g, b))
    buffer = io.BytesIO()
    photo.save(buffer, "JPEG", quality=60)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def compare(result, row):
    def money(field, key):
        return float(result[field] or 0) == float(row[key] or 0)
    return {"vendor": result["vendor_name"] == row["vendor"], "gstin": result["gstin"] == row["gstin"],
            "number": result["invoice_number"] == row["number"],
            "date": bool(result["invoice_date"]) and result["invoice_date"].isoformat() == row["date"],
            "taxable": money("taxable_amount", "taxable"), "cgst": money("cgst", "cgst"), "sgst": money("sgst", "sgst"),
            "igst": money("igst", "igst"), "total": money("total_amount", "total")}


def summarise(rows):
    per_field = {f: sum(r["fields"][f] for r in rows) / len(rows) for f in FIELDS}
    correct = sum(sum(r["fields"].values()) for r in rows)
    return {"documents": len(rows), "field_accuracy": round(correct / (len(rows) * len(FIELDS)), 3),
            "per_field": {k: round(v, 3) for k, v in per_field.items()},
            "average_confidence": round(sum(r["confidence"] for r in rows) / len(rows), 3)}


def main():
    expected = json.loads((SAMPLES / "expected.json").read_text(encoding="utf-8"))
    clean, degraded = [], []
    with tempfile.TemporaryDirectory() as scratch:
        for index, row in enumerate(expected):
            path = SAMPLES / row["file"]
            buyer = row.get("buyer_gstin")
            result = extract_invoice_data(path, exclude_gstin=buyer)
            clean.append({"file": row["file"], "fields": compare(result, row), "confidence": result["confidence"]})

            photo = degrade(load_pages(path, 1)[0], index)
            photo_path = Path(scratch) / f"photo_{index}.jpg"
            photo.save(photo_path, quality=90)
            result = extract_invoice_data(photo_path, exclude_gstin=buyer)
            degraded.append({"file": row["file"], "fields": compare(result, row), "confidence": result["confidence"]})
    report = {"note": "Synthetic sample documents. Not a measure of accuracy on real vendor invoices.",
              "clean": summarise(clean), "degraded_photo": summarise(degraded),
              "misses": {"clean": [{"file": r["file"], "fields": [k for k, v in r["fields"].items() if not v]} for r in clean if not all(r["fields"].values())],
                         "degraded_photo": [{"file": r["file"], "fields": [k for k, v in r["fields"].items() if not v]} for r in degraded if not all(r["fields"].values())]}}
    out = ROOT / "docs" / "ocr_benchmark.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
