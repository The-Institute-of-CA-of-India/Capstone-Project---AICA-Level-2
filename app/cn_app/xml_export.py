"""XML export of the contract note register (one file, notes with their script rows nested)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from .models import CHARGE_KEYS, CHARGE_LABELS


def _tag(label: str) -> str:
    return "".join(ch for ch in label.title() if ch.isalnum())


def _val(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def build_xml(frames: dict, path: Path, person_label: str, period_label: str) -> Path:
    root = ET.Element("ContractNoteRegister", {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "person": person_label, "period": period_label, "currency": "INR"})
    nf, sf = frames["notes"], frames["scrips"]
    by_note = {k: g for k, g in sf.groupby("Contract Note No")} if len(sf) else {}
    for _, n in nf.iterrows():
        cn = ET.SubElement(root, "ContractNote", {
            "number": str(n["Contract Note No"]), "tradeDate": str(n["Trade Date"]),
            "settlementDate": str(n["Settlement Date"] or ""), "broker": str(n["Broker"]),
            "client": str(n["Client / Account"]), "pan": str(n["PAN"] or ""), "ucc": str(n["UCC"] or ""),
            "status": str(n["Status"])})
        ET.SubElement(cn, "GrossPurchase").text = _val(n["Gross Purchase Value"])
        ET.SubElement(cn, "GrossSale").text = _val(n["Gross Sale Value"])
        ch = ET.SubElement(cn, "Charges")
        for k in CHARGE_KEYS:
            ET.SubElement(ch, _tag(CHARGE_LABELS[k])).text = _val(n[CHARGE_LABELS[k]])
        ET.SubElement(cn, "NetAmount", {"direction": "Dr" if str(n["Direction"]).startswith("Payable") else "Cr"}
                      ).text = _val(n["Net Amount (as printed)"])
        ET.SubElement(cn, "NetAmountRounded").text = str(n["Net Amount (Rs, rounded)"])
        rows = ET.SubElement(cn, "Scripts")
        group = by_note.get(n["Contract Note No"])
        for _, r in (group.iterrows() if group is not None else []):
            sc = ET.SubElement(rows, "Script", {"isin": str(r["ISIN"]), "symbol": str(r["Script"]),
                                                "side": str(r["Side"]), "exchange": str(r["Exchange"] or "")})
            ET.SubElement(sc, "CompanyName").text = str(r["Name of Company"] or "")
            ET.SubElement(sc, "AssetClass").text = str(r["Asset Class"] or "")
            ET.SubElement(sc, "Industry").text = str(r["Industry"] or "")
            ET.SubElement(sc, "Quantity").text = _val(r["Quantity"])
            ET.SubElement(sc, "AverageRate").text = f"{r['Avg Gross Rate']:.4f}"
            ET.SubElement(sc, "GrossValue").text = _val(r["Gross Value"])
            sch = ET.SubElement(sc, "Charges")
            for k in CHARGE_KEYS:
                ET.SubElement(sch, _tag(CHARGE_LABELS[k])).text = _val(r[CHARGE_LABELS[k]])
            ET.SubElement(sc, "TotalCharges").text = _val(r["Total Charges"])
            ET.SubElement(sc, "NetCostOrProceedsRupees").text = str(r["Net Cost / Proceeds (Rs)"])
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path
