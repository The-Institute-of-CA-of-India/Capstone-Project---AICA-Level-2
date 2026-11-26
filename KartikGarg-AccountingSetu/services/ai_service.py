"""Provider-independent AI layer.

Providers implement:
  extract_documents(file_bytes, mime, text, hints) -> list[{"page_from","page_to","data","confidence"}]
  interpret_question(question, intents) -> {"intent": str, "params": {...}} | None

* AnthropicProvider – Claude via the official ``anthropic`` SDK (needs ANTHROPIC_API_KEY).
  Uses structured JSON output; PDFs/images are sent as document/image blocks so scanned
  documents are read without a local OCR engine.
* LocalRulesProvider – deterministic regex parser (services/invoice_parser.py).

AI never computes accounting entries or report figures — it only reads documents and
interprets questions. All numbers are recomputed / validated in Python.
"""
from __future__ import annotations

import base64
import json
import logging

from config import settings
from services import invoice_parser

log = logging.getLogger("accounting_setu.ai")

_NULL_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
FIELDS = ["supplier_name", "supplier_gstin", "customer_name", "customer_gstin", "invoice_no", "invoice_date",
          "place_of_supply", "taxable_value", "cgst", "sgst", "igst", "cess", "discount", "round_off", "total",
          "original_invoice_no"]

EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["documents"],
    "properties": {
        "documents": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["page_from", "page_to", "doc_kind", "reverse_charge", "items", "fields", "confidence", "notes"],
                "properties": {
                    "page_from": {"type": "integer"},
                    "page_to": {"type": "integer"},
                    "doc_kind": {"type": "string", "enum": ["invoice", "credit_note", "debit_note", "bank_statement",
                                                            "salary_statement", "payment_receipt", "other"]},
                    "reverse_charge": {"type": "boolean"},
                    "fields": {"type": "object", "additionalProperties": False, "required": FIELDS,
                               "properties": {f: _NULL_STR for f in FIELDS}},
                    "confidence": {"type": "object", "additionalProperties": False, "required": FIELDS,
                                   "properties": {f: {"type": "number"} for f in FIELDS}},
                    "items": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["description", "hsn_sac", "quantity", "unit_price", "taxable_value", "gst_rate"],
                        "properties": {k: _NULL_STR for k in ["description", "hsn_sac", "quantity", "unit_price",
                                                              "taxable_value", "gst_rate"]}}},
                    "notes": {"type": "string"},
                },
            },
        }
    },
}

EXTRACTION_PROMPT = """You are reading Indian GST financial documents for a chartered accountant.
The file may contain ONE OR SEVERAL separate invoices/notes; return one entry per distinct document with its 1-based page range.
Rules:
- Copy values exactly as printed. Do NOT guess, infer or calculate a value that is not printed; use null instead.
- Amounts: plain numbers with 2 decimals, no currency symbols or commas (e.g. "11800.00").
- Dates: ISO format YYYY-MM-DD.
- GSTINs: 15 characters, uppercase. place_of_supply: 2-digit state code if determinable from the printed text, else null.
- confidence: 0..1 per field reflecting legibility/certainty (0 when null). Use < 0.8 whenever a character is unclear.
- notes: anything the reviewer should check (handwriting, stamps, cut-off text, multiple totals).
Context: the accountant's client GSTIN is {client_gstin}; the uploader labelled this file as "{declared}"."""


class AIProvider:
    name = "base"
    is_ai = False

    def extract_documents(self, file_bytes: bytes, mime: str, text: str, hints: dict) -> list[dict]:  # pragma: no cover
        raise NotImplementedError

    def interpret_question(self, question: str, intents: dict[str, str]) -> dict | None:
        return None


class LocalRulesProvider(AIProvider):
    name = "rules"

    def extract_documents(self, file_bytes, mime, text, hints):
        pages = hints.get("pages_text") or [text]
        ranges = invoice_parser.split_pages_into_invoices(pages) if hints.get("allow_split", True) else [(1, len(pages))]
        out = []
        for a, b in ranges:
            chunk = "\n".join(pages[a - 1:b])
            parsed = invoice_parser.parse_invoice_text(chunk, hints.get("client_gstin"))
            out.append({"page_from": a, "page_to": b, **parsed, "notes": "", "raw_text": chunk})
        return out


class AnthropicProvider(AIProvider):
    name = "anthropic"
    is_ai = True

    def __init__(self):
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    def _create(self, **kwargs):
        # Server-side refusal fallback (see Anthropic docs) — routes a declined request to a fallback model.
        resp = self.client.beta.messages.create(model=self.model, betas=["server-side-fallback-2026-07-01"],
                                                fallbacks="default", **kwargs)
        if resp.stop_reason == "refusal":
            raise RuntimeError("AI provider declined the request")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("AI response truncated (max_tokens)")
        return next(b.text for b in resp.content if b.type == "text")

    def extract_documents(self, file_bytes, mime, text, hints):
        content: list[dict] = []
        b64 = base64.standard_b64encode(file_bytes).decode()
        if mime == "application/pdf":
            content.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}})
        elif mime in ("image/png", "image/jpeg"):
            content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}})
        else:
            content.append({"type": "text", "text": f"Document text:\n{text[:150000]}"})
        content.append({"type": "text", "text": EXTRACTION_PROMPT.format(client_gstin=hints.get("client_gstin") or "unknown",
                                                                         declared=hints.get("declared_type") or "unknown")})
        raw = self._create(max_tokens=16000, output_config={"effort": "medium", "format": {"type": "json_schema",
                                                                                            "schema": EXTRACTION_SCHEMA}},
                           messages=[{"role": "user", "content": content}])
        parsed = json.loads(raw)
        out = []
        for d in parsed.get("documents", []):
            data = dict(d["fields"])
            data.update({"doc_kind": d["doc_kind"], "reverse_charge": d["reverse_charge"], "items": d["items"],
                         "hsn_codes": sorted({i["hsn_sac"] for i in d["items"] if i.get("hsn_sac")})})
            conf = {k: float(v) for k, v in d["confidence"].items()}
            conf["reverse_charge"] = 0.85
            out.append({"page_from": d["page_from"], "page_to": d["page_to"], "data": data, "confidence": conf,
                        "notes": d.get("notes", "")})
        return out

    def interpret_question(self, question, intents):
        schema = {"type": "object", "additionalProperties": False, "required": ["intent", "period", "top_n"],
                  "properties": {"intent": {"type": "string", "enum": list(intents)},
                                 "period": {"type": "string", "description": "this_month|last_month|this_fy|last_fy|YYYY-MM"},
                                 "top_n": {"type": "integer"}}}
        listing = "\n".join(f"- {k}: {v}" for k, v in intents.items())
        raw = self._create(max_tokens=1024, output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
                           messages=[{"role": "user", "content": f"Map the accountant's question to exactly one intent.\n"
                                                                 f"Intents:\n{listing}\nQuestion: {question}"}])
        return json.loads(raw)


_provider: AIProvider | None = None


def get_provider() -> AIProvider:
    global _provider
    if _provider is None:
        if settings.anthropic_enabled:
            try:
                _provider = AnthropicProvider()
            except Exception as exc:  # pragma: no cover
                log.error("Anthropic provider unavailable: %s", exc)
                _provider = LocalRulesProvider()
        else:
            _provider = LocalRulesProvider()
    return _provider


def set_provider(p: AIProvider) -> None:
    global _provider
    _provider = p


def fallback_provider() -> AIProvider:
    return LocalRulesProvider()
