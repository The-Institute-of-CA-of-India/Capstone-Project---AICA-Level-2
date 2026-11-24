"""Phase 3 test data.

1. Offline verification pages for the browser agent (data/phase3/registry/):
   - ifsc_lookup.html     - IFSC -> bank, branch, city (fictitious ZZ banks only)
   - account_verify.html  - IFSC + account number -> registered account holder ("penny-drop" style)
   Plain HTML + JavaScript with the data embedded, so they work from file:// with no internet.
   The changed bank account used in the R01 payment is registered to a different holder.
2. Answer key (data/phase3/answer_key/): expected reconciliation items, risk flags and the
   verification outcome for every vendor bank account.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

BANKS = {
    "ZZAB": "Sample Arya Bank", "ZZCB": "Sample Coastal Bank", "ZZDB": "Sample Deccan Bank",
    "ZZEB": "Sample Eastern Bank", "ZZFB": "Sample Frontier Bank", "ZZGB": "Sample Ganga Bank",
    "ZZSB": "Sample Bank of India", "ZZHB": "Sample Heritage Bank", "ZZKB": "Sample Kaveri Bank",
    "ZZQB": "Sample Quick Bank", "ZZXB": "Sample Xpress Bank",
}
CITIES = {"PUN": "Pune", "MUM": "Mumbai", "NSK": "Nashik", "AUR": "Aurangabad", "KOL": "Kolhapur",
          "CHN": "Chennai", "BLR": "Bengaluru", "AMD": "Ahmedabad", "DEL": "New Delhi"}
DIVERTED = ("ZZQB0DEL404", "918273645501", "DEEPAK TRADING COMPANY")  # account used in the R01 payment


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def holder_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("(SAMPLE)", "")).strip().upper()


def _branch(ifsc: str) -> dict:
    city = CITIES.get(ifsc[5:8], "Pune")
    return {"ifsc": ifsc, "bank": BANKS.get(ifsc[:4], "Sample Bank") + " (SAMPLE)",
            "branch": f"{city} Branch {ifsc[8:]}", "city": city}


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
 body {{ font-family: Segoe UI, Arial, sans-serif; margin: 40px; background: #f4f6fa; color: #1b1f24; }}
 .banner {{ background: #b3261e; color: #fff; padding: 6px 12px; font-weight: 600; display: inline-block; }}
 .card {{ background: #fff; border: 1px solid #d0d7de; padding: 24px; margin-top: 16px; max-width: 640px; }}
 label {{ display: block; margin: 12px 0 4px; font-weight: 600; }}
 input {{ font-size: 16px; padding: 6px; width: 320px; }}
 button {{ margin-top: 16px; font-size: 16px; padding: 6px 18px; }}
 table {{ border-collapse: collapse; margin-top: 16px; }} td {{ border: 1px solid #d0d7de; padding: 6px 12px; }}
 #status {{ margin-top: 16px; font-weight: 600; }}
</style></head>
<body>
<div class="banner">SAMPLE / FICTITIOUS REGISTRY - OFFLINE TEST PAGE</div>
<h1>{title}</h1>
<div class="card">
{form}
<button id="search" onclick="go()">{button}</button>
<div id="status"></div>
<table id="result" hidden></table>
</div>
<script>
const DATA = {data};
function row(k, v) {{ return "<tr><td>" + k + "</td><td data-field='" + k + "'>" + v + "</td></tr>"; }}
function go() {{
 {script}
}}
</script>
</body></html>
"""


def ifsc_page(directory: dict) -> str:
    return PAGE.format(
        title="IFSC Lookup", button="Search",
        form='<label for="ifsc">IFSC code</label><input id="ifsc" maxlength="11">',
        data=json.dumps(directory, sort_keys=True),
        script="""const code = document.getElementById('ifsc').value.trim().toUpperCase();
 const t = document.getElementById('result'); const s = document.getElementById('status');
 const r = DATA[code];
 if (!r) { s.textContent = 'NOT FOUND'; t.hidden = true; return; }
 s.textContent = 'FOUND';
 t.innerHTML = row('IFSC', r.ifsc) + row('Bank', r.bank) + row('Branch', r.branch) + row('City', r.city);
 t.hidden = false;""")


def verify_page(accounts: dict) -> str:
    return PAGE.format(
        title="Beneficiary Account Verification", button="Verify",
        form='<label for="ifsc">IFSC code</label><input id="ifsc" maxlength="11">'
             '<label for="acct">Account number</label><input id="acct" maxlength="20">',
        data=json.dumps(accounts, sort_keys=True),
        script="""const key = document.getElementById('ifsc').value.trim().toUpperCase() + '|' +
             document.getElementById('acct').value.trim();
 const t = document.getElementById('result'); const s = document.getElementById('status');
 const r = DATA[key];
 if (!r) { s.textContent = 'ACCOUNT NOT FOUND'; t.hidden = true; return; }
 s.textContent = 'ACCOUNT ACTIVE';
 t.innerHTML = row('Account holder', r.holder) + row('Account type', r.type) + row('Opened', r.opened);
 t.hidden = false;""")


def generate(p1: Path, out_dir: Path) -> dict:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    reg, key = out_dir / "registry", out_dir / "answer_key"
    reg.mkdir(parents=True)
    key.mkdir(parents=True)
    parties = _rows(p1 / "counterparties.csv")
    accounts = _rows(p1 / "bank_accounts.csv")

    directory, holders = {}, {}
    for p in parties:
        if p["ifsc"]:
            directory[p["ifsc"]] = _branch(p["ifsc"])
            holders[f"{p['ifsc']}|{p['account_no']}"] = {"holder": holder_name(p["name"]), "type": "Current",
                                                         "opened": "2015-06-01"}
    for a in accounts:
        directory[a["ifsc"]] = _branch(a["ifsc"])
        holders[f"{a['ifsc']}|{a['account_no']}"] = {"holder": "SAMPLE PRECISION COMPONENTS PVT LTD",
                                                     "type": "Current" if a["currency"] == "INR" else "EEFC",
                                                     "opened": "2012-04-02"}
    ifsc, acct, holder = DIVERTED
    directory[ifsc] = _branch(ifsc)
    holders[f"{ifsc}|{acct}"] = {"holder": holder, "type": "Current", "opened": "2026-02-27"}
    directory["ZZXB0PUN555"] = _branch("ZZXB0PUN555")
    # bank-portal beneficiary list export (full account numbers, who added each beneficiary and when)
    portal = out_dir / "bank_portal"
    portal.mkdir()
    with (portal / "beneficiaries.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["beneficiary_name", "ifsc", "account_no", "added_on", "added_by", "linked_vendor_id"])
        for p in parties:
            if p["ifsc"] and p["party_type"] == "vendor":
                w.writerow([holder_name(p["name"]), p["ifsc"], p["account_no"], "2024-04-15", "accounts.maker1",
                            p["party_id"]])
        w.writerow(["DECCAN CASTINGS", ifsc, acct, "2026-02-27", "ops.user2", "V002"])
    (reg / "ifsc_lookup.html").write_text(ifsc_page(directory), encoding="utf-8")
    (reg / "account_verify.html").write_text(verify_page(holders), encoding="utf-8")

    # ---- answer key ----
    recon = json.loads((p1 / "answer_key" / "recon_items_2026-03-31.json").read_text(encoding="utf-8"))
    risks = json.loads((p1 / "answer_key" / "risk_flags.json").read_text(encoding="utf-8"))
    verifications = []
    for p in parties:
        if p["ifsc"] and p["party_type"] == "vendor":
            verifications.append({"party_id": p["party_id"], "ifsc": p["ifsc"], "account_no": p["account_no"],
                                  "vendor_name": holder_name(p["name"]), "expected_holder": holder_name(p["name"]),
                                  "expected_result": "match"})
    verifications.append({"party_id": "V002", "ifsc": ifsc, "account_no": acct, "vendor_name": "DECCAN CASTINGS",
                          "expected_holder": holder, "expected_result": "mismatch"})
    (key / "expected_recon_items.json").write_text(json.dumps(recon, indent=1), encoding="utf-8")
    (key / "expected_risk_flags.json").write_text(json.dumps(risks, indent=1), encoding="utf-8")
    (key / "expected_verifications.json").write_text(json.dumps(verifications, indent=1), encoding="utf-8")
    # after every proposed entry is approved, only timing items should remain in the BRS
    timing = {aid: [i for i in rec["items"] if i["side"] == "books_only"] for aid, rec in recon.items()}
    (key / "expected_after_approval.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")

    files = sorted(p for p in out_dir.rglob("*") if p.is_file())
    manifest = {"phase": 3, "files": {p.relative_to(out_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in files}}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
