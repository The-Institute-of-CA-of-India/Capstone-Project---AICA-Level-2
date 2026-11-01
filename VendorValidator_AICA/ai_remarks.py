"""
ai_remarks.py - AI layer: turns rule-based check results into professional remarks.

Design principle (same as ICAI guidance on responsible AI):
  * Python rules DECIDE pass / fail.  The AI never changes a validation result.
  * The AI only WRITES: a vendor-wise remark + follow-up action, and a summary
    paragraph for the partner / client.
  * PAN, GSTIN and Udyam numbers are MASKED before anything is sent to the AI.
  * If no API key is configured, a rule-based remark writer is used (works offline).

Providers supported: Google Gemini, OpenAI (ChatGPT). Uses only the Python
standard library (urllib) so the .exe stays small.
"""
from __future__ import annotations

import json
import re
import urllib.request

from validators import FAIL, WARN, Vendor

# ------------------------------------------------------------------ PROMPTS
SYSTEM_PROMPT = """You are an audit assistant working for a Chartered Accountant firm in India.
You draft short, professional remarks for a VENDOR MASTER VALIDATION report covering
PAN (Income-tax Act), GSTIN (CGST Act, 2017) and Udyam Registration (MSMED Act, 2006).

Strict rules:
1. The validation results given to you are FINAL. Never change PASS / WARNING / FAIL.
2. Do not invent facts, sections, dates or numbers that are not in the input.
3. For each vendor write:
   - "remark": one or two sentences (max 45 words) stating what is wrong or that all is in order.
   - "action": the follow-up the accounts team should take with the vendor (max 25 words),
     e.g. "Obtain corrected GST certificate", "Collect Udyam certificate", "No action".
4. Where relevant mention the compliance impact in plain words: higher TDS u/s 206AA
   for missing/inoperative PAN, ITC risk for cancelled/invalid GSTIN, Sec. 43B(h)
   (Sec. 37(2)(g) of Income-tax Act, 2025) 45-day payment rule for Micro/Small enterprises.
5. Identifiers are masked; refer to them as "PAN", "GSTIN", "Udyam number".
6. Reply ONLY with valid JSON, no markdown."""

USER_PROMPT_TEMPLATE = """Write remarks for the following vendors.

Return JSON in exactly this shape:
{{"vendors": [{{"vendor_code": "...", "remark": "...", "action": "..."}}],
 "summary": "A 4-6 sentence summary for the partner covering how many vendors are approved,
             need review or must be fixed, the most common problems, and MSME (43B(h)) exposure."}}

Validation data (JSON):
{payload}"""


# ------------------------------------------------------------------ masking
def mask(text: str) -> str:
    text = re.sub(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]{3}\b", "[GSTIN]", text)
    text = re.sub(r"\b[A-Z]{5}\d{4}[A-Z]\b", "[PAN]", text)
    text = re.sub(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", "[UDYAM]", text)
    return text


def build_payload(vendors: list[Vendor]) -> list[dict]:
    data = []
    for v in vendors:
        issues = [{"stage": c.stage, "dept": c.department, "field": c.field, "check": c.check,
                   "result": c.status, "detail": mask(c.message)}
                  for c in v.checks if c.status in (FAIL, WARN)]
        u = (v.online.get("UDYAM") or {}).get("data") or {}
        data.append({"vendor_code": v.vendor_code or str(v.row), "vendor_name": v.name,
                     "constitution": v.constitution, "overall": v.overall(),
                     "msme_type": u.get("enterprise_type", ""), "sec_43bh": u.get("sec_43bh", ""),
                     "issues": issues})
    return data


# ------------------------------------------------------------------ providers
def _post(url: str, body: dict, headers: dict, timeout=90) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def call_llm(provider: str, api_key: str, model: str, user_prompt: str) -> str:
    if provider == "gemini":
        model = model or "gemini-2.5-flash"
        res = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                     "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                     "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}},
                    {"x-goog-api-key": api_key})
        return res["candidates"][0]["content"]["parts"][0]["text"]
    if provider == "openai":
        model = model or "gpt-4o-mini"
        res = _post("https://api.openai.com/v1/chat/completions",
                    {"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
                     "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                  {"role": "user", "content": user_prompt}]},
                    {"Authorization": f"Bearer {api_key}"})
        return res["choices"][0]["message"]["content"]
    raise ValueError(f"Unknown AI provider '{provider}'")


# ------------------------------------------------------------------ rule-based fallback
ACTION_MAP = [
    ("PAN", "PAN provided", "Obtain PAN copy from vendor (else TDS @ 20% u/s 206AA)."),
    ("PAN", "PAN status", "Ask vendor to make PAN operative (link Aadhaar); deduct higher TDS meanwhile."),
    ("PAN", "Structure", "Obtain correct PAN copy - number is mistyped."),
    ("PAN", "Constitution vs PAN", "Correct constitution in vendor master as per PAN."),
    ("GST", "Check digit", "Obtain GST registration certificate - GSTIN is mistyped."),
    ("GST", "PAN inside GSTIN", "Obtain GST certificate; GSTIN belongs to a different PAN."),
    ("GST", "GSTIN status", "Stop ITC claim; obtain revised details or treat as unregistered."),
    ("UDYAM", "Structure", "Obtain valid Udyam Registration certificate."),
    ("UDYAM", "Found on portal", "Obtain valid Udyam Registration certificate."),
]


def rule_based_remarks(vendors: list[Vendor]) -> tuple[dict, str]:
    out = {}
    for v in vendors:
        bad = [c for c in v.checks if c.status == FAIL]
        warn = [c for c in v.checks if c.status == WARN]
        if not bad and not warn:
            u = (v.online.get("UDYAM") or {}).get("data") or {}
            msme = f" MSME: {u['enterprise_type']} - 43B(h): {u.get('sec_43bh')}." if u.get("enterprise_type") else ""
            out[v.vendor_code or str(v.row)] = "All checks passed. No action." + msme
            continue
        parts = [f"{c.department}: {c.message}" for c in (bad + warn)[:3]]
        actions = {a for d, chk, a in ACTION_MAP for c in bad if c.department == d and c.check == chk}
        out[v.vendor_code or str(v.row)] = " | ".join(parts) + (
            "  ACTION: " + " ".join(sorted(actions)) if actions else "  ACTION: Review with vendor.")
    res = {k: sum(1 for v in vendors if v.overall() == k) for k in ("APPROVED", "REVIEW", "REJECT / FIX")}
    summary = (f"{len(vendors)} vendors validated: {res['APPROVED']} approved, {res['REVIEW']} need review and "
               f"{res['REJECT / FIX']} must be corrected before payment / ITC claim.")
    return out, summary


def generate_remarks(vendors: list[Vendor], cfg: dict, log=print) -> tuple[dict, str, str]:
    """Returns (remarks by vendor code, summary text, engine used)."""
    provider = (cfg.get("ai_provider") or "none").lower()
    key = cfg.get("ai_api_key", "").strip()
    if provider in ("none", "") or not key:
        r, s = rule_based_remarks(vendors)
        return r, s, "Rule-based (no AI key configured)"
    remarks, summaries = {}, []
    try:
        payload = build_payload(vendors)
        for i in range(0, len(payload), 25):               # batches of 25 vendors
            chunk = payload[i:i + 25]
            log(f"AI: drafting remarks for vendors {i + 1}-{i + len(chunk)} ...")
            txt = call_llm(provider, key, cfg.get("ai_model", ""),
                           USER_PROMPT_TEMPLATE.format(payload=json.dumps(chunk, ensure_ascii=False, indent=1)))
            txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.M)
            data = json.loads(txt)
            for item in data.get("vendors", []):
                remarks[str(item.get("vendor_code"))] = f"{item.get('remark', '')}  ACTION: {item.get('action', '')}"
            if data.get("summary"):
                summaries.append(data["summary"])
        fallback, fsum = rule_based_remarks(vendors)
        for k, v in fallback.items():
            remarks.setdefault(k, v)
        return remarks, " ".join(summaries) or fsum, f"AI ({provider} {cfg.get('ai_model', '')})".strip()
    except Exception as e:
        log(f"AI call failed ({e}); using rule-based remarks.")
        r, s = rule_based_remarks(vendors)
        return r, s, "Rule-based (AI call failed)"
