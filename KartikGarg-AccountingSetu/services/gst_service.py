"""GST return preparation (GSTR-1, GSTR-3B) and GSTR-2B reconciliation from APPROVED records.

Nothing here files a return. Status 'filed_externally' can only be set by a user who records the
ARN obtained from the GST portal; the application never claims to have filed anything itself.
"""
from __future__ import annotations

import datetime as dt
import io
import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from config import settings
from services.audit_service import audit
from services.db import IntegrityError, get_db, now_iso
from services.gst_rules import b2cl_threshold, get_rules
from services.ocr_service import read_table
from services.tenancy import AuthContext, require_client, scoped_get
from utils.helpers import D, ZERO, month_bounds, normalize_invoice_no, parse_gst_period, to_date
from utils.validators import VALID_GST_RATES, gstin_state, validate_gstin

HEADS = ("igst", "cgst", "sgst", "cess")


def _q(x) -> Decimal:
    return D(x)


def _rate(inv: dict, items: list[dict]) -> tuple[Decimal, bool]:
    """Invoice GST rate: from items if single-rate, else derived; returns (rate, certain)."""
    rates = {D(i["gst_rate"]) for i in items if D(i.get("gst_rate")) > 0}
    if len(rates) == 1:
        return rates.pop(), True
    tv = D(inv["taxable_value"])
    tax = D(inv["igst"]) + D(inv["cgst"]) + D(inv["sgst"])
    if tv <= 0:
        return ZERO, True
    r = (tax * 100 / tv).quantize(Decimal("0.01"))
    nearest = min(VALID_GST_RATES, key=lambda x: abs(x - r))
    return nearest, abs(nearest - r) <= Decimal("0.05") and len(rates) <= 1


def _period_invoices(client_id: str, year: int, month: int, categories: tuple) -> list[dict]:
    start, end = month_bounds(year, month)
    marks = ",".join("?" for _ in categories)
    return get_db().fetchall(f"select * from invoices where client_id = ? and status = 'approved' and category in ({marks}) "
                             f"and invoice_date between ? and ? order by invoice_date, invoice_no",
                             [client_id, *categories, start, end])


def _items(invoice_id: str) -> list[dict]:
    return get_db().fetchall("select * from invoice_items where invoice_id = ? order by line_no", [invoice_id])


def _gst_date(d) -> str:
    return to_date(d).strftime("%d-%m-%Y")


# ================================================================= GSTR-1
def prepare_gstr1(ctx: AuthContext, client_id: str, year: int, month: int, rules_version: str | None = None) -> dict:
    client = require_client(ctx, client_id, "gst_prepare")
    rules = get_rules(rules_version or settings.gst_rules_version)
    own_state = (client.get("gstin") or "")[:2] or client.get("state_code")
    sec: dict[str, list] = {k: [] for k in ("b2b", "b2cl", "b2cs", "cdnr", "cdnur", "exp", "nil", "hsn")}
    warnings: list[str] = []
    b2cs_agg: dict[tuple, dict] = defaultdict(lambda: {"taxable_value": ZERO, "igst": ZERO, "cgst": ZERO, "sgst": ZERO, "cess": ZERO})
    nil_agg: dict[str, dict] = defaultdict(lambda: {"nil": ZERO, "exempt": ZERO, "non_gst": ZERO})
    hsn_agg: dict[tuple, dict] = defaultdict(lambda: {"qty": ZERO, "taxable_value": ZERO, "igst": ZERO, "cgst": ZERO, "sgst": ZERO,
                                                      "cess": ZERO, "total": ZERO})
    invoices = _period_invoices(client_id, year, month, ("sales",))
    docs = defaultdict(list)
    for inv in invoices:
        items = _items(inv["id"])
        rate, certain = _rate(inv, items)
        if not certain:
            warnings.append(f"Invoice {inv['invoice_no']}: multiple/non-standard rates without line items — split by rate before filing")
        pos = inv.get("place_of_supply") or gstin_state(inv.get("party_gstin")) or own_state
        inter = pos != own_state
        registered = bool(inv.get("party_gstin")) and validate_gstin(inv["party_gstin"])[0]
        supply = inv.get("supply_type") or "taxable"
        note = inv["note_type"]
        row = {"invoice_id": inv["id"], "invoice_no": inv["invoice_no"], "invoice_date": str(inv["invoice_date"]),
               "party": inv["party_name"], "gstin": inv.get("party_gstin"), "pos": pos, "rate": rate,
               "taxable_value": D(inv["taxable_value"]), "igst": D(inv["igst"]), "cgst": D(inv["cgst"]), "sgst": D(inv["sgst"]),
               "cess": D(inv["cess"]), "invoice_value": D(inv["total"]), "reverse_charge": bool(inv["reverse_charge"]),
               "supply_type": supply}
        sign = Decimal(-1) if note == "credit_note" else Decimal(1)
        if note == "invoice":
            docs["Invoices for outward supply"].append(inv["invoice_no"])
        else:
            docs["Credit Note" if note == "credit_note" else "Debit Note"].append(inv["invoice_no"])
        if supply in ("nil", "exempt", "non_gst"):
            key = ("INTER" if inter else "INTRA") + ("B2B" if registered else "B2C")
            nil_agg[key][supply] += sign * D(inv["taxable_value"])
            continue
        if note in ("credit_note", "debit_note"):
            row["note_type"] = "C" if note == "credit_note" else "D"
            row["original_invoice_no"] = inv.get("original_invoice_no")
            if registered:
                sec["cdnr"].append(row)
            elif supply.startswith("export") or (inter and D(inv["total"]) > b2cl_threshold(rules, to_date(inv["invoice_date"]))):
                row["ur_type"] = "EXPWP" if supply == "export_wpay" else "EXPWOP" if supply == "export_wopay" else "B2CL"
                sec["cdnur"].append(row)
            else:
                k = (pos, rate, "INTER" if inter else "INTRA")
                for f in ("taxable_value", "igst", "cgst", "sgst", "cess"):
                    b2cs_agg[k][f] += sign * row[f]
        elif supply.startswith("export"):
            row["export_type"] = "WPAY" if supply == "export_wpay" else "WOPAY"
            sec["exp"].append(row)
        elif registered:
            row["inv_type"] = {"sez_wpay": "SEWP", "sez_wopay": "SEWOP", "deemed_export": "DE"}.get(supply, "R")
            sec["b2b"].append(row)
        elif inter and D(inv["total"]) > b2cl_threshold(rules, to_date(inv["invoice_date"])):
            sec["b2cl"].append(row)
        else:
            k = (pos, rate, "INTER" if inter else "INTRA")
            for f in ("taxable_value", "igst", "cgst", "sgst", "cess"):
                b2cs_agg[k][f] += row[f]
        # HSN summary (Table 12): B2B vs B2C split
        split = "B2B" if registered else "B2C"
        if items:
            for it in items:
                tv = D(it["taxable_value"]) * sign
                share = (tv / D(inv["taxable_value"])) if D(inv["taxable_value"]) else ZERO
                k = (split, it.get("hsn_sac") or "UNSPECIFIED", D(it["gst_rate"]) or rate)
                hsn_agg[k]["qty"] += D(it.get("quantity")) * sign
                hsn_agg[k]["taxable_value"] += tv
                for h in HEADS:
                    hsn_agg[k][h] += (D(inv[h]) * share * sign).quantize(Decimal("0.01"), ROUND_HALF_UP) if share else ZERO
        else:
            warnings.append(f"Invoice {inv['invoice_no']}: no HSN line items — HSN summary incomplete")
            k = (split, "UNSPECIFIED", rate)
            hsn_agg[k]["taxable_value"] += D(inv["taxable_value"]) * sign
            for h in HEADS:
                hsn_agg[k][h] += D(inv[h]) * sign
    for (pos, rate, sply), v in sorted(b2cs_agg.items()):
        sec["b2cs"].append({"pos": pos, "rate": rate, "supply": sply, **v})
    for key, v in sorted(nil_agg.items()):
        sec["nil"].append({"supply_type": key, "nil_rated": v["nil"], "exempted": v["exempt"], "non_gst": v["non_gst"]})
    for (split, hsn, rate), v in sorted(hsn_agg.items()):
        v["total"] = v["taxable_value"] + v["igst"] + v["cgst"] + v["sgst"] + v["cess"]
        sec["hsn"].append({"table": split, "hsn": hsn, "rate": rate, **v})
        if hsn == "UNSPECIFIED":
            continue
        if len(hsn) < rules["hsn_min_digits_upto_5cr"]:
            warnings.append(f"HSN {hsn}: fewer digits than required")
    doc_summary = [{"nature": k, "from": min(v), "to": max(v), "total": len(v), "cancelled": 0} for k, v in docs.items()]
    totals = {
        "taxable_value": sum((D(i["taxable_value"]) * (-1 if i["note_type"] == "credit_note" else 1) for i in invoices), ZERO),
        **{h: sum((D(i[h]) * (-1 if i["note_type"] == "credit_note" else 1) for i in invoices), ZERO) for h in HEADS},
    }
    result = {"return_type": "GSTR1", "period": f"{month:02d}{year}", "gstin": client.get("gstin"), "rules_version":
              rules_version or settings.gst_rules_version, "sections": sec, "documents_issued": doc_summary,
              "totals": totals, "warnings": sorted(set(warnings)), "invoice_count": len(invoices)}
    if not client.get("gstin"):
        result["warnings"].insert(0, "Client GSTIN not set — GSTR-1 not applicable / cannot be prepared for upload")
    return result


def gstr1_portal_json(prep: dict) -> dict:
    """Build JSON in the GSTN offline-tool layout (verify against the current schema before upload)."""
    def itm(r, with_csgst=True):
        num = int(D(r["rate"]) * 100) + 1
        det = {"txval": float(r["taxable_value"]), "rt": float(r["rate"]), "iamt": float(r["igst"]), "csamt": float(r["cess"])}
        if with_csgst:
            det.update({"camt": float(r["cgst"]), "samt": float(r["sgst"])})
        return {"num": num, "itm_det": det}

    s = prep["sections"]
    out: dict = {"gstin": prep["gstin"], "fp": prep["period"], "version": get_rules(prep["rules_version"])["gstr1_json_version"]}
    b2b = defaultdict(list)
    for r in s["b2b"]:
        b2b[r["gstin"]].append({"inum": r["invoice_no"], "idt": _gst_date(r["invoice_date"]), "val": float(r["invoice_value"]),
                                "pos": r["pos"], "rchrg": "Y" if r["reverse_charge"] else "N", "inv_typ": r["inv_type"],
                                "itms": [itm(r)]})
    if b2b:
        out["b2b"] = [{"ctin": k, "inv": v} for k, v in b2b.items()]
    b2cl = defaultdict(list)
    for r in s["b2cl"]:
        b2cl[r["pos"]].append({"inum": r["invoice_no"], "idt": _gst_date(r["invoice_date"]), "val": float(r["invoice_value"]),
                               "itms": [itm(r, False)]})
    if b2cl:
        out["b2cl"] = [{"pos": k, "inv": v} for k, v in b2cl.items()]
    if s["b2cs"]:
        out["b2cs"] = [{"sply_ty": r["supply"], "pos": r["pos"], "typ": "OE", "txval": float(r["taxable_value"]),
                        "rt": float(r["rate"]), "iamt": float(r["igst"]), "camt": float(r["cgst"]), "samt": float(r["sgst"]),
                        "csamt": float(r["cess"])} for r in s["b2cs"]]
    cdnr = defaultdict(list)
    for r in s["cdnr"]:
        cdnr[r["gstin"]].append({"ntty": r["note_type"], "nt_num": r["invoice_no"], "nt_dt": _gst_date(r["invoice_date"]),
                                 "val": float(r["invoice_value"]), "pos": r["pos"], "rchrg": "Y" if r["reverse_charge"] else "N",
                                 "inv_typ": "R", "itms": [itm(r)]})
    if cdnr:
        out["cdnr"] = [{"ctin": k, "nt": v} for k, v in cdnr.items()]
    if s["cdnur"]:
        out["cdnur"] = [{"typ": r["ur_type"], "ntty": r["note_type"], "nt_num": r["invoice_no"], "nt_dt": _gst_date(r["invoice_date"]),
                         "val": float(r["invoice_value"]), "pos": r["pos"], "itms": [itm(r, False)]} for r in s["cdnur"]]
    exp = defaultdict(list)
    for r in s["exp"]:
        exp[r["export_type"]].append({"inum": r["invoice_no"], "idt": _gst_date(r["invoice_date"]), "val": float(r["invoice_value"]),
                                      "itms": [{"txval": float(r["taxable_value"]), "rt": float(r["rate"]), "iamt": float(r["igst"]),
                                                "csamt": float(r["cess"])}]})
    if exp:
        out["exp"] = [{"exp_typ": k, "inv": v} for k, v in exp.items()]
    if s["nil"]:
        out["nil"] = {"inv": [{"sply_ty": r["supply_type"], "nil_amt": float(r["nil_rated"]), "expt_amt": float(r["exempted"]),
                               "ngsup_amt": float(r["non_gst"])} for r in s["nil"]]}
    if s["hsn"]:
        out["hsn"] = {}
        for tbl, key in (("B2B", "hsn_b2b"), ("B2C", "hsn_b2c")):
            rows = [r for r in s["hsn"] if r["table"] == tbl]
            if rows:
                out["hsn"][key] = [{"num": i + 1, "hsn_sc": r["hsn"], "qty": float(r["qty"]), "rt": float(r["rate"]),
                                    "txval": float(r["taxable_value"]), "iamt": float(r["igst"]), "camt": float(r["cgst"]),
                                    "samt": float(r["sgst"]), "csamt": float(r["cess"])} for i, r in enumerate(rows)]
    if prep["documents_issued"]:
        out["doc_issue"] = {"doc_det": [{"doc_num": i + 1, "docs": [{"num": 1, "from": d["from"], "to": d["to"],
                                                                     "totnum": d["total"], "cancel": d["cancelled"],
                                                                     "net_issue": d["total"] - d["cancelled"]}]}
                                        for i, d in enumerate(prep["documents_issued"])]}
    return out


# ================================================================= GSTR-3B
def utilise_itc(liability: dict, itc: dict) -> dict:
    """Set-off per Rule 88A / Sec 49: IGST credit first (IGST, then CGST/SGST), CGST→CGST then IGST,
    SGST→SGST then IGST. CGST and SGST credits never cross-utilise. Cess only against cess."""
    L = {h: D(liability.get(h)) for h in HEADS}
    C = {h: D(itc.get(h)) for h in HEADS}
    used = {f"{src}->{dst}": ZERO for src in HEADS for dst in HEADS}

    def use(src, dst):
        amt = min(C[src], L[dst])
        if amt > 0:
            C[src] -= amt
            L[dst] -= amt
            used[f"{src}->{dst}"] += amt

    use("igst", "igst")
    # allocate remaining IGST credit to the CGST/SGST shortfall that own credits cannot cover
    need_c = max(ZERO, L["cgst"] - C["cgst"])
    need_s = max(ZERO, L["sgst"] - C["sgst"])
    for dst, need in (("cgst", need_c), ("sgst", need_s)):
        amt = min(C["igst"], need)
        if amt > 0:
            C["igst"] -= amt
            L[dst] -= amt
            used[f"igst->{dst}"] += amt
    use("igst", "cgst")
    use("igst", "sgst")
    use("cgst", "cgst")
    use("sgst", "sgst")
    use("cgst", "igst")
    use("sgst", "igst")
    use("cess", "cess")
    return {"cash_payable": L, "itc_balance_carried_forward": C, "utilisation": {k: v for k, v in used.items() if v}}


def prepare_gstr3b(ctx: AuthContext, client_id: str, year: int, month: int, *, itc_basis: str = "books",
                   interest: dict | None = None, late_fee: dict | None = None, rules_version: str | None = None) -> dict:
    client = require_client(ctx, client_id, "gst_prepare")
    rules = get_rules(rules_version or settings.gst_rules_version)
    own_state = (client.get("gstin") or "")[:2] or client.get("state_code")
    warnings: list[str] = []
    z = lambda: {"taxable_value": ZERO, "igst": ZERO, "cgst": ZERO, "sgst": ZERO, "cess": ZERO}  # noqa: E731
    t31 = {"a": z(), "b": z(), "c": z(), "d": z(), "e": z()}
    t32: dict[str, dict] = defaultdict(lambda: {"taxable_value": ZERO, "igst": ZERO})
    for inv in _period_invoices(client_id, year, month, ("sales",)):
        sign = Decimal(-1) if inv["note_type"] == "credit_note" else Decimal(1)
        supply = inv.get("supply_type") or "taxable"
        key = ("b" if supply.startswith(("export", "sez")) else "c" if supply in ("nil", "exempt")
               else "e" if supply == "non_gst" else "a")
        t31[key]["taxable_value"] += sign * D(inv["taxable_value"])
        if key in ("a", "b"):
            for h in HEADS:
                t31[key][h] += sign * D(inv[h])
        pos = inv.get("place_of_supply") or own_state
        if key == "a" and pos != own_state and not inv.get("party_gstin"):
            t32[pos]["taxable_value"] += sign * D(inv["taxable_value"])
            t32[pos]["igst"] += sign * D(inv["igst"])
    purchases = _period_invoices(client_id, year, month, ("purchase", "expense"))
    recon_status = {}
    if itc_basis == "gstr2b_matched":
        rec = get_db().fetchone("select id from gst_reconciliations where client_id = ? and period = ? order by created_at desc",
                                [client_id, f"{month:02d}{year}"])
        if not rec:
            warnings.append("No GSTR-2B reconciliation for this period — ITC computed from books")
            itc_basis = "books"
        else:
            for r in get_db().fetchall("select invoice_id, status from gst_reconciliation_items where reconciliation_id = ? "
                                       "and invoice_id is not null", [rec["id"]]):
                recon_status[r["invoice_id"]] = r["status"]
    t4 = {k: {h: ZERO for h in HEADS} for k in ("A1", "A2", "A3", "A4", "A5", "B1", "B2", "D1", "D2")}
    t5 = {"inter_exempt_nil": ZERO, "intra_exempt_nil": ZERO, "inter_non_gst": ZERO, "intra_non_gst": ZERO}
    pending = 0
    for inv in purchases:
        sign = Decimal(-1) if inv["note_type"] == "credit_note" else Decimal(1)
        tax = {h: sign * D(inv[h]) for h in HEADS}
        supply = inv.get("supply_type") or "taxable"
        sup_state = gstin_state(inv.get("party_gstin")) or own_state
        if supply in ("nil", "exempt", "non_gst") and not any(tax.values()):
            k = ("inter" if sup_state != own_state else "intra") + ("_non_gst" if supply == "non_gst" else "_exempt_nil")
            t5[k] += sign * D(inv["taxable_value"])
            continue
        if inv["reverse_charge"]:
            t31["d"]["taxable_value"] += sign * D(inv["taxable_value"])
            for h in HEADS:
                t31["d"][h] += tax[h]
        elig = inv.get("itc_eligibility")
        if elig == "pending":
            pending += 1
            continue
        if itc_basis == "gstr2b_matched" and not inv["reverse_charge"] and recon_status.get(inv["id"]) not in ("matched", "amount_mismatch"):
            continue
        bucket = "A3" if inv["reverse_charge"] else "A5"
        if elig == "eligible":
            for h in HEADS:
                t4[bucket][h] += tax[h]
        elif elig == "blocked" and rules["blocked_itc_reported_in_4A_and_reversed_4B1"]:
            for h in HEADS:
                t4[bucket][h] += tax[h]
                t4["B1"][h] += tax[h]
        elif elig in ("ineligible", "blocked"):
            for h in HEADS:
                t4["D2"][h] += tax[h]
    if pending:
        warnings.append(f"{pending} purchase invoice(s) with ITC eligibility pending — excluded from Table 4 until decided")
    a_total = {h: sum((t4[k][h] for k in ("A1", "A2", "A3", "A4", "A5")), ZERO) for h in HEADS}
    b_total = {h: t4["B1"][h] + t4["B2"][h] for h in HEADS}
    t4["C"] = {h: a_total[h] - b_total[h] for h in HEADS}
    t51 = {"interest": {h: D((interest or {}).get(h)) for h in HEADS},
           "late_fee": {h: D((late_fee or {}).get(h)) for h in ("cgst", "sgst")}}
    liability = {h: t31["a"][h] + t31["b"][h] for h in HEADS}
    rcm_cash = {h: t31["d"][h] for h in HEADS}
    setoff = utilise_itc(liability, {h: max(ZERO, t4["C"][h]) for h in HEADS})
    cash = {h: setoff["cash_payable"][h] + rcm_cash[h] + t51["interest"][h] for h in HEADS}
    for h in ("cgst", "sgst"):
        cash[h] += t51["late_fee"][h]
    if any(v < 0 for v in liability.values()):
        warnings.append("Net outward liability is negative (credit notes exceed supplies) — review")
    warnings.append("Table 3.1.1 (e-commerce u/s 9(5)), imports (4A1/4A2) and ISD (4A4) are not captured from documents — enter manually if applicable")
    return {"return_type": "GSTR3B", "period": f"{month:02d}{year}", "gstin": client.get("gstin"), "itc_basis": itc_basis,
            "rules_version": rules_version or settings.gst_rules_version, "table_3_1": t31,
            "table_3_1_1": {"note": "not captured"}, "table_3_2": [{"pos": k, **v} for k, v in sorted(t32.items())],
            "table_4": t4, "table_5": t5, "table_5_1": t51, "liability": liability, "rcm_liability_cash": rcm_cash,
            "setoff": setoff, "cash_payable": cash, "warnings": warnings}


# ================================================================= persistence & approval
def _jsonable(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    return o


def save_return(ctx: AuthContext, client_id: str, prep: dict) -> str:
    client = require_client(ctx, client_id, "gst_prepare")
    db = get_db()
    row = db.fetchone("select * from gst_returns where client_id = ? and return_type = ? and period = ?",
                      [client_id, prep["return_type"], prep["period"]])
    if row and row["status"] in ("approved", "filed_externally"):
        raise ValueError(f"{prep['return_type']} {prep['period']} is {row['status']}; unapprove it before re-preparing")
    vals = {"data": _jsonable(prep), "warnings": prep.get("warnings", []), "status": "prepared", "prepared_by": ctx.user_id,
            "rules_version": prep["rules_version"]}
    if row:
        db.update("gst_returns", row["id"], vals)
        rid = row["id"]
    else:
        rid = db.insert("gst_returns", {"firm_id": client["firm_id"], "client_id": client_id, "return_type": prep["return_type"],
                                        "period": prep["period"], "created_at": now_iso(), **vals})
    audit(ctx, "gst.prepared", "gst_returns", rid, client_id=client_id, after={"type": prep["return_type"], "period": prep["period"]})
    return rid


def approve_return(ctx: AuthContext, return_id: str) -> None:
    r = scoped_get(ctx, "gst_returns", return_id, "gst_approve")
    if r["status"] != "prepared":
        raise ValueError("Only prepared returns can be approved")
    get_db().update("gst_returns", return_id, {"status": "approved", "approved_by": ctx.user_id, "approved_at": now_iso()})
    audit(ctx, "gst.approved", "gst_returns", return_id, client_id=r["client_id"])


def record_external_filing(ctx: AuthContext, return_id: str, arn: str) -> None:
    """User declares the return was filed on the GST portal and records the ARN. Not verified by this app."""
    r = scoped_get(ctx, "gst_returns", return_id, "gst_approve")
    if r["status"] != "approved":
        raise ValueError("Approve the prepared data first")
    if not arn or len(arn.strip()) < 10:
        raise ValueError("Enter the ARN shown on the GST portal")
    get_db().update("gst_returns", return_id, {"status": "filed_externally", "external_arn": arn.strip()})
    audit(ctx, "gst.marked_filed_externally", "gst_returns", return_id, client_id=r["client_id"], after={"arn": arn.strip()})


def list_returns(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    return get_db().fetchall("select id, return_type, period, status, rules_version, external_arn, approved_at, created_at "
                             "from gst_returns where client_id = ? order by period desc", [client_id])


# ================================================================= GSTR-2B
def parse_gstr2b(data: bytes, filename: str) -> list[dict]:
    name = filename.lower()
    records: list[dict] = []
    if name.endswith(".json"):
        js = json.loads(data.decode("utf-8-sig"))
        root = js.get("data", js)
        docdata = root.get("docdata", root)
        for sup in docdata.get("b2b", []):
            for inv in sup.get("inv", []):
                items = inv.get("items", [])
                rec = {"section": "B2B", "supplier_gstin": sup.get("ctin"), "supplier_name": sup.get("trdnm"),
                       "supplier_period": sup.get("supprd"), "invoice_no": str(inv.get("inum")),
                       "invoice_date": to_date(inv.get("dt")), "invoice_value": D(inv.get("val")),
                       "itc_available": str(inv.get("itcavl", "Y")).upper() != "N", "reason": inv.get("rsn")}
                for k_json, k in (("txval", "taxable_value"), ("igst", "igst"), ("cgst", "cgst"), ("sgst", "sgst"), ("cess", "cess")):
                    rec[k] = sum((D(i.get(k_json)) for i in items), ZERO)
                records.append(rec)
        for sup in docdata.get("cdnr", []):
            for nt in sup.get("nt", []):
                items = nt.get("items", [])
                sign = Decimal(-1) if str(nt.get("typ", "C")).upper() == "C" else Decimal(1)
                rec = {"section": "CDNR", "supplier_gstin": sup.get("ctin"), "supplier_name": sup.get("trdnm"),
                       "supplier_period": sup.get("supprd"), "invoice_no": str(nt.get("ntnum")), "invoice_date": to_date(nt.get("dt")),
                       "invoice_value": sign * D(nt.get("val")), "itc_available": str(nt.get("itcavl", "Y")).upper() != "N",
                       "reason": nt.get("rsn")}
                for k_json, k in (("txval", "taxable_value"), ("igst", "igst"), ("cgst", "cgst"), ("sgst", "sgst"), ("cess", "cess")):
                    rec[k] = sign * sum((D(i.get(k_json)) for i in items), ZERO)
                records.append(rec)
        return records
    ext = ".csv" if name.endswith(".csv") else ".xlsx"
    df = read_table(data, ext)
    norm = {c: " ".join(str(c).lower().replace("(", " ").replace(")", " ").replace("₹", " ").split()) for c in df.columns}

    def col(*names):
        for n in names:
            for c, v in norm.items():
                if v == n or v.startswith(n):
                    return c
        return None

    c_g = col("gstin of supplier", "supplier gstin", "gstin", "ctin")
    c_n = col("trade/legal name", "supplier name", "trade name", "legal name")
    c_i = col("invoice number", "invoice no", "note number", "document number", "inum")
    c_d = col("invoice date", "date", "note date")
    c_v = col("invoice value", "note value", "value")
    c_t = col("taxable value", "taxable")
    c_ig, c_cg, c_sg, c_ce = col("integrated tax", "igst"), col("central tax", "cgst"), col("state/ut tax", "state tax", "sgst"), col("cess")
    c_itc = col("itc availability", "itc available")
    if not (c_g and c_i):
        raise ValueError("Could not find 'GSTIN of supplier' and 'Invoice number' columns in the GSTR-2B file")
    for _, r in df.iterrows():
        g = str(r[c_g]).strip().upper()
        if len(g) != 15:
            continue
        records.append({"section": "B2B", "supplier_gstin": g, "supplier_name": str(r[c_n]).strip() if c_n else None,
                        "supplier_period": None, "invoice_no": str(r[c_i]).strip(), "invoice_date": to_date(str(r[c_d]).strip()) if c_d else None,
                        "invoice_value": D(r[c_v]) if c_v else ZERO, "taxable_value": D(r[c_t]) if c_t else ZERO,
                        "igst": D(r[c_ig]) if c_ig else ZERO, "cgst": D(r[c_cg]) if c_cg else ZERO,
                        "sgst": D(r[c_sg]) if c_sg else ZERO, "cess": D(r[c_ce]) if c_ce else ZERO,
                        "itc_available": (str(r[c_itc]).strip().upper()[:1] != "N") if c_itc else True, "reason": None})
    return records


def import_gstr2b(ctx: AuthContext, client_id: str, period: str, filename: str, data: bytes) -> str:
    client = require_client(ctx, client_id, "gst_prepare")
    records = parse_gstr2b(data, filename)
    if not records:
        raise ValueError("No GSTR-2B records found in the file")
    db = get_db()
    with db.transaction():
        uid = db.insert("gstr2b_uploads", {"firm_id": client["firm_id"], "client_id": client_id, "period": period,
                                           "source_filename": filename, "record_count": len(records), "uploaded_by": ctx.user_id,
                                           "created_at": now_iso()})
        for r in records:
            db.insert("gstr2b_records", {"firm_id": client["firm_id"], "client_id": client_id, "upload_id": uid, **r})
    audit(ctx, "gstr2b.imported", "gstr2b_uploads", uid, client_id=client_id, after={"period": period, "records": len(records)})
    return uid


def reconcile_2b(ctx: AuthContext, client_id: str, upload_id: str, rules_version: str | None = None) -> dict:
    client = require_client(ctx, client_id, "gst_prepare")
    up = scoped_get(ctx, "gstr2b_uploads", upload_id, "gst_prepare")
    if up["client_id"] != client_id:
        raise ValueError("Upload belongs to another client")
    rules = get_rules(rules_version or settings.gst_rules_version)
    tol = rules["match_tolerance"]
    db = get_db()
    year, month = parse_gst_period(up["period"])
    start, end = month_bounds(year, month)
    records = db.fetchall("select * from gstr2b_records where upload_id = ?", [upload_id])
    books_all = db.fetchall("select * from invoices where client_id = ? and status = 'approved' and category in ('purchase','expense') "
                            "and reverse_charge = ?", [client_id, False])
    in_period = [b for b in books_all if start <= to_date(b["invoice_date"]) <= end]

    def key(g, no):
        return ((g or "").upper(), normalize_invoice_no(no))

    book_index: dict[tuple, list[dict]] = defaultdict(list)
    for b in books_all:
        book_index[key(b.get("party_gstin"), b["invoice_no"])].append(b)
    by_no: dict[str, list[dict]] = defaultdict(list)
    for b in books_all:
        by_no[normalize_invoice_no(b["invoice_no"])].append(b)
    items, used_books = [], set()
    rec_keys = defaultdict(int)
    for r in records:
        rec_keys[key(r["supplier_gstin"], r["invoice_no"])] += 1
    for r in records:
        k = key(r["supplier_gstin"], r["invoice_no"])
        matches = book_index.get(k, [])
        detail = {"supplier_gstin": r["supplier_gstin"], "supplier": r.get("supplier_name"), "invoice_no": r["invoice_no"],
                  "2b_taxable": str(r["taxable_value"]), "2b_tax": str(D(r["igst"]) + D(r["cgst"]) + D(r["sgst"]) + D(r["cess"]))}
        if rec_keys[k] > 1:
            items.append({"status": "duplicate", "invoice_id": None, "record_id": r["id"], "details": {**detail, "issue": "Duplicate in GSTR-2B"}})
            continue
        if len(matches) > 1:
            for b in matches:
                used_books.add(b["id"])
            items.append({"status": "duplicate", "invoice_id": matches[0]["id"], "record_id": r["id"],
                          "details": {**detail, "issue": f"{len(matches)} entries in purchase register"}})
            continue
        if not matches:
            alt = [b for b in by_no.get(normalize_invoice_no(r["invoice_no"]), [])
                   if abs(D(b["total"]) - D(r["invoice_value"])) <= tol and b["id"] not in used_books]
            if alt:
                used_books.add(alt[0]["id"])
                items.append({"status": "gstin_mismatch", "invoice_id": alt[0]["id"], "record_id": r["id"],
                              "details": {**detail, "books_gstin": alt[0].get("party_gstin"),
                                          "issue": "Invoice found in books under a different GSTIN"}})
            else:
                items.append({"status": "missing_in_books", "invoice_id": None, "record_id": r["id"],
                              "details": {**detail, "issue": "In GSTR-2B but not in purchase register"}})
            continue
        b = matches[0]
        used_books.add(b["id"])
        diffs = {}
        for f in ("taxable_value", "igst", "cgst", "sgst", "cess"):
            d = D(b[f]) - D(r[f])
            if abs(d) > tol:
                diffs[f] = str(d)
        bdate = to_date(b["invoice_date"])
        if diffs:
            status = "amount_mismatch"
        elif not (start <= bdate <= end):
            status = "period_mismatch"
        elif not r["itc_available"]:
            status = "itc_not_available"
        elif b["itc_eligibility"] in ("ineligible", "blocked"):
            status = "ineligible_in_books"
        else:
            status = "matched"
        items.append({"status": status, "invoice_id": b["id"], "record_id": r["id"],
                      "details": {**detail, "differences": diffs, "books_date": str(bdate),
                                  "books_itc": b["itc_eligibility"], "2b_itc_available": bool(r["itc_available"])}})
    for b in in_period:
        if b["id"] in used_books:
            continue
        tax = D(b["igst"]) + D(b["cgst"]) + D(b["sgst"]) + D(b["cess"])
        if not b.get("party_gstin"):
            continue  # unregistered purchases are not expected in 2B
        items.append({"status": "missing_in_2b", "invoice_id": b["id"], "record_id": None,
                      "details": {"supplier_gstin": b.get("party_gstin"), "supplier": b["party_name"], "invoice_no": b["invoice_no"],
                                  "books_tax": str(tax), "issue": "In purchase register but not in GSTR-2B — ITC at risk"}})
    counts: dict[str, int] = defaultdict(int)
    for it in items:
        counts[it["status"]] += 1
    itc_books = sum((D(b["igst"]) + D(b["cgst"]) + D(b["sgst"]) + D(b["cess"]) for b in in_period
                     if b["itc_eligibility"] in ("eligible", "pending")), ZERO)
    itc_2b = sum((D(r["igst"]) + D(r["cgst"]) + D(r["sgst"]) + D(r["cess"]) for r in records if r["itc_available"]), ZERO)
    matched_ids = {it["invoice_id"] for it in items if it["status"] == "matched"}
    itc_matched = sum((D(b["igst"]) + D(b["cgst"]) + D(b["sgst"]) + D(b["cess"]) for b in books_all if b["id"] in matched_ids), ZERO)
    summary = {"counts": dict(counts), "itc_as_per_books": str(itc_books), "itc_as_per_2b": str(itc_2b),
               "itc_matched": str(itc_matched), "difference": str(itc_books - itc_2b)}
    with db.transaction():
        rid = db.insert("gst_reconciliations", {"firm_id": client["firm_id"], "client_id": client_id, "period": up["period"],
                                                "upload_id": upload_id, "summary": summary, "created_by": ctx.user_id,
                                                "created_at": now_iso()})
        for it in items:
            db.insert("gst_reconciliation_items", {"firm_id": client["firm_id"], "client_id": client_id, "reconciliation_id": rid,
                                                   "status": it["status"], "invoice_id": it["invoice_id"], "record_id": it["record_id"],
                                                   "details": it["details"]})
    audit(ctx, "gstr2b.reconciled", "gst_reconciliations", rid, client_id=client_id, after=summary)
    return {"reconciliation_id": rid, "summary": summary, "items": items}


def latest_reconciliation(ctx: AuthContext, client_id: str, period: str) -> dict | None:
    require_client(ctx, client_id, "view")
    db = get_db()
    rec = db.fetchone("select * from gst_reconciliations where client_id = ? and period = ? order by created_at desc", [client_id, period])
    if not rec:
        return None
    rec["items"] = db.fetchall("select * from gst_reconciliation_items where reconciliation_id = ?", [rec["id"]])
    return rec


def set_itc_eligibility(ctx: AuthContext, invoice_id: str, eligibility: str, reason: str = "") -> None:
    from services.period_service import assert_period_open

    inv = scoped_get(ctx, "invoices", invoice_id, "gst_prepare" if ctx.can("gst_prepare") else "prepare_vouchers")
    if eligibility not in ("eligible", "ineligible", "blocked", "pending"):
        raise ValueError("invalid eligibility")
    if inv["category"] == "sales":
        raise ValueError("ITC applies to purchases only")
    assert_period_open(inv["client_id"], to_date(inv["invoice_date"]))
    get_db().update("invoices", invoice_id, {"itc_eligibility": eligibility, "itc_reason": reason or None})
    audit(ctx, "invoice.itc_eligibility", "invoices", invoice_id, client_id=inv["client_id"],
          before={"itc": inv["itc_eligibility"]}, after={"itc": eligibility, "reason": reason})


def gst_summary(ctx: AuthContext, client_id: str, date_from: dt.date, date_to: dt.date) -> dict:
    require_client(ctx, client_id, "view")
    rows = get_db().fetchall("select category, note_type, taxable_value, igst, cgst, sgst, cess, itc_eligibility, reverse_charge "
                             "from invoices where client_id = ? and status = 'approved' and invoice_date between ? and ?",
                             [client_id, date_from, date_to])
    out = {"output": {h: ZERO for h in HEADS}, "input_eligible": {h: ZERO for h in HEADS}, "input_other": {h: ZERO for h in HEADS},
           "rcm": {h: ZERO for h in HEADS}}
    for r in rows:
        sign = Decimal(-1) if r["note_type"] == "credit_note" else Decimal(1)
        for h in HEADS:
            v = sign * D(r[h])
            if r["category"] == "sales":
                out["output"][h] += v
            elif r["reverse_charge"]:
                out["rcm"][h] += v
                if r["itc_eligibility"] == "eligible":
                    out["input_eligible"][h] += v
            elif r["itc_eligibility"] == "eligible":
                out["input_eligible"][h] += v
            else:
                out["input_other"][h] += v
    out["estimated_net_liability"] = {h: out["output"][h] + out["rcm"][h] - out["input_eligible"][h] for h in HEADS}
    return out


def gstr1_excel(prep: dict) -> bytes:
    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, rows in prep["sections"].items():
            df = pd.DataFrame([{k: (float(v) if isinstance(v, Decimal) else v) for k, v in r.items() if k != "invoice_id"} for r in rows])
            (df if not df.empty else pd.DataFrame({"note": ["No records"]})).to_excel(xw, sheet_name=name[:31], index=False)
        pd.DataFrame(prep["documents_issued"] or [{"note": "none"}]).to_excel(xw, sheet_name="docs", index=False)
        pd.DataFrame({"warnings": prep["warnings"] or ["none"]}).to_excel(xw, sheet_name="warnings", index=False)
    return buf.getvalue()


__all__ = ["IntegrityError"]
