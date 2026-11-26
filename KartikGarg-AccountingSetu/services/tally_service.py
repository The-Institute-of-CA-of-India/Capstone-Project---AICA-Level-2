"""Tally-compatible XML export of APPROVED vouchers.

Format: the standard Tally XML import envelope (TALLYREQUEST 'Import Data', REPORTNAME 'Vouchers'),
accounting-voucher view. Debit lines carry ISDEEMEDPOSITIVE=Yes and a negative AMOUNT, credits
ISDEEMEDPOSITIVE=No and a positive AMOUNT (Tally's sign convention). Ledger masters can be included
so that import does not fail on missing ledgers. Validate on a test company in your TallyPrime
version before importing into live books — this module does not push data into Tally directly.
"""
from __future__ import annotations

import datetime as dt
from xml.etree import ElementTree as ET

from services import accounting_engine as ae
from services.audit_service import audit
from services.db import get_db, now_iso
from services.storage_service import get_storage
from services.tenancy import AuthContext, require_client
from utils.helpers import D, ZERO, to_date

TALLY_GROUPS = set(ae.GROUP_NATURE)
GROUP_MAP = {"Secured Loans": "Secured Loans", "Unsecured Loans": "Unsecured Loans",
             "Loans & Advances (Asset)": "Loans & Advances (Asset)", "Deposits (Asset)": "Deposits (Asset)"}
IMPORT_INSTRUCTIONS = """How to import into TallyPrime
1. Back up the company data in Tally.
2. Open the target company in TallyPrime (company name should match the name used in this file).
3. Import the ledger-masters XML first (Import → Masters), then the vouchers XML (Import → Transactions).
4. Select 'File format: XML', choose the downloaded file, and set 'Behaviour of import if voucher already exists'
   to 'Combine/Skip' as per your practice. Vouchers carry a REMOTEID so re-imports can be identified.
5. Review the import log (tally.imp) for any rejected vouchers, e.g. ledger name mismatches or locked periods.
6. Verify the trial balance in Tally against the Accounting Setu trial balance for the same period.
Tested structure: standard Tally XML envelope. Validate against your TallyPrime release on a test company first."""


class TallyExportError(Exception):
    pass


def preview(ctx: AuthContext, client_id: str, date_from: dt.date, date_to: dt.date) -> dict:
    require_client(ctx, client_id, "export_tally")
    db = get_db()
    vouchers = db.fetchall("select * from accounting_vouchers where client_id = ? and status = 'approved' and voucher_date between ? and ? "
                           "order by voucher_date, voucher_no", [client_id, date_from, date_to])
    drafts = db.scalar("select count(*) from accounting_vouchers where client_id = ? and status = 'draft' and voucher_date between ? and ?",
                       [client_id, date_from, date_to])
    ledgers = ae.ledger_index(client_id)
    issues: list[str] = []
    exported = {}
    for r in db.fetchall("select voucher_ids, created_at from tally_exports where client_id = ?", [client_id]):
        for vid in (r["voucher_ids"] or []):
            exported[vid] = str(r["created_at"])[:10]
    lines_by_voucher = ae.bulk_voucher_lines([v["id"] for v in vouchers])
    rows = []
    for v in vouchers:
        lines = lines_by_voucher[v["id"]]
        dr, cr = ae.totals(lines)
        flags = []
        if dr != cr:
            flags.append("UNBALANCED")
        for ln in lines:
            led = ledgers.get(ln["ledger_id"])
            if not led or not led["name"].strip():
                flags.append("missing ledger")
            elif any(ch in led["name"] for ch in "<>&\"") or len(led["name"]) > 100:
                flags.append(f"ledger name '{led['name'][:30]}' needs review")
        if v["id"] in exported:
            flags.append(f"already exported {exported[v['id']]}")
        rows.append({"id": v["id"], "date": str(v["voucher_date"]), "type": v["voucher_type"], "number": v["voucher_no"],
                     "amount": D(v["total_amount"]), "narration": v.get("narration"), "lines": len(lines),
                     "flags": ", ".join(flags)})
        issues += [f"{v['voucher_no']}: {f}" for f in flags if f == "UNBALANCED" or f == "missing ledger"]
    if drafts:
        issues.append(f"{drafts} draft voucher(s) in range are NOT exported (approve them first)")
    seen = {}
    for v in vouchers:
        k = (v["voucher_type"], v["voucher_no"])
        if k in seen:
            issues.append(f"Duplicate voucher number {v['voucher_no']}")
        seen[k] = True
    return {"vouchers": rows, "issues": issues, "draft_count": drafts,
            "blocking": any("UNBALANCED" in r["flags"] or "missing ledger" in r["flags"] for r in rows)}


def _sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, tag, attrs)
    if text is not None:
        el.text = str(text)
    return el


def _envelope(report_name: str, company: str):
    env = ET.Element("ENVELOPE")
    hdr = _sub(env, "HEADER")
    _sub(hdr, "TALLYREQUEST", "Import Data")
    imp = _sub(_sub(env, "BODY"), "IMPORTDATA")
    req = _sub(imp, "REQUESTDESC")
    _sub(req, "REPORTNAME", report_name)
    _sub(_sub(req, "STATICVARIABLES"), "SVCURRENTCOMPANY", company)
    return env, _sub(imp, "REQUESTDATA")


def _serialize(env) -> bytes:
    ET.indent(env)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(env, encoding="utf-8")


def build_masters_xml(client: dict, ledger_ids: set[str], ledgers: dict[str, dict], company_name: str | None = None) -> bytes:
    env, data = _envelope("All Masters", company_name or client["name"])
    for lid in sorted(ledger_ids, key=lambda x: ledgers[x]["name"]):
        led = ledgers[lid]
        msg = _sub(data, "TALLYMESSAGE", **{"xmlns:UDF": "TallyUDF"})
        lel = _sub(msg, "LEDGER", NAME=led["name"], ACTION="Create")
        _sub(lel, "NAME", led["name"])
        _sub(lel, "PARENT", GROUP_MAP.get(led["group_name"], led["group_name"]))
        if led.get("party_gstin"):
            _sub(lel, "PARTYGSTIN", led["party_gstin"])
        _sub(lel, "ISBILLWISEON", "Yes" if led["group_name"] in ("Sundry Debtors", "Sundry Creditors") else "No")
    return _serialize(env)


def build_xml(client: dict, vouchers: list[dict], ledgers: dict[str, dict], company_name: str | None = None) -> bytes:
    env, data = _envelope("Vouchers", company_name or client["name"])
    for v in vouchers:
        msg = _sub(data, "TALLYMESSAGE", **{"xmlns:UDF": "TallyUDF"})
        vel = _sub(msg, "VOUCHER", REMOTEID=v["id"], VCHTYPE=v["voucher_type"], ACTION="Create", OBJVIEW="Accounting Voucher View")
        _sub(vel, "DATE", to_date(v["voucher_date"]).strftime("%Y%m%d"))
        _sub(vel, "VOUCHERTYPENAME", v["voucher_type"])
        _sub(vel, "VOUCHERNUMBER", v["voucher_no"])
        if v.get("reference_no"):
            _sub(vel, "REFERENCE", v["reference_no"])
        party = ledgers.get(v.get("party_ledger_id") or "")
        if party:
            _sub(vel, "PARTYLEDGERNAME", party["name"])
        _sub(vel, "NARRATION", v.get("narration") or "")
        _sub(vel, "PERSISTEDVIEW", "Accounting Voucher View")
        for ln in v["lines"]:
            led = ledgers[ln["ledger_id"]]
            amt = D(ln["amount"])
            signed = f"{-amt if ln['dr_cr'] == 'Dr' else amt:.2f}"
            e = _sub(vel, "ALLLEDGERENTRIES.LIST")
            _sub(e, "LEDGERNAME", led["name"])
            _sub(e, "ISDEEMEDPOSITIVE", "Yes" if ln["dr_cr"] == "Dr" else "No")
            _sub(e, "AMOUNT", signed)
            if ln.get("bill_ref") and led["group_name"] in ("Sundry Debtors", "Sundry Creditors"):
                b = _sub(e, "BILLALLOCATIONS.LIST")
                _sub(b, "NAME", ln["bill_ref"])
                _sub(b, "BILLTYPE", "New Ref" if v["voucher_type"] in ("Sales", "Purchase") else "Agst Ref")
                _sub(b, "AMOUNT", signed)
    return _serialize(env)


def export(ctx: AuthContext, client_id: str, date_from: dt.date, date_to: dt.date, *, include_masters: bool = True,
           skip_already_exported: bool = True, company_name: str | None = None) -> tuple[bytes, dict]:
    """Returns (vouchers_xml, info). info['masters_xml'] holds the ledger-masters file (import it first)."""
    client = require_client(ctx, client_id, "export_tally")
    pv = preview(ctx, client_id, date_from, date_to)
    if pv["blocking"]:
        raise TallyExportError("Fix unbalanced vouchers / missing ledgers before export: " + "; ".join(pv["issues"]))
    ids = [r["id"] for r in pv["vouchers"] if not (skip_already_exported and "already exported" in r["flags"])]
    if not ids:
        raise TallyExportError("No approved vouchers to export in this range")
    db = get_db()
    ledgers = ae.ledger_index(client_id)
    marks = ",".join("?" for _ in ids)
    by_id = {v["id"]: v for v in db.fetchall(f"select * from accounting_vouchers where id in ({marks})", ids)}
    lines_by_voucher = ae.bulk_voucher_lines(ids)
    vouchers = []
    for vid in ids:
        v = by_id[vid]
        v["lines"] = lines_by_voucher[vid]
        dr, cr = ae.totals(v["lines"])
        if dr != cr or dr == ZERO:
            raise TallyExportError(f"Voucher {v['voucher_no']} is not balanced")
        vouchers.append(v)
    xml = build_xml(client, vouchers, ledgers, company_name)
    masters = build_masters_xml(client, {ln["ledger_id"] for v in vouchers for ln in v["lines"]}, ledgers, company_name)         if include_masters else None
    path = f"{client['firm_id']}/{client_id}/exports/tally_{date_from:%Y%m%d}_{date_to:%Y%m%d}_{now_iso().replace(':', '')}.xml"
    get_storage().put_overwrite(path, xml)
    eid = db.insert("tally_exports", {"firm_id": client["firm_id"], "client_id": client_id, "period_from": date_from,
                                      "period_to": date_to, "voucher_ids": ids, "voucher_count": len(ids), "storage_path": path,
                                      "created_by": ctx.user_id, "created_at": now_iso()})
    audit(ctx, "tally.exported", "tally_exports", eid, client_id=client_id, after={"vouchers": len(ids)})
    return xml, {"export_id": eid, "count": len(ids), "masters_xml": masters}
