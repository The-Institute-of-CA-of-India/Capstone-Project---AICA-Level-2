"""Import pipeline: files -> text -> parsed notes -> allocation -> checks -> store."""
from __future__ import annotations

import re
from pathlib import Path

from . import tradebook
from .allocate import allocate
from .extract import extract_text, iter_documents
from .parsers import iifl, kotak, phillip, zerodha
from .parsers.base import ParseError
from .paths import Layout
from .store import Store

PARSERS = [iifl, zerodha, phillip, kotak]
TOLERANCE = 0.05   # rupees; a note must reconcile within 5 paise to be saved


def remedy(text: str) -> str:
    """Plain advice for the most common import problems."""
    t = text.lower()
    if "damaged" in t or "not a real pdf" in t:
        return ("The file is damaged or was only partly downloaded. Download the contract note again from the broker "
                "(or the email) and import it again.")
    if "password" in t:
        return ("The PDF is password protected. Add its password (usually the client code or PAN) in "
                "Settings > PDF passwords, then import the file again.")
    if "not reconciled" in t or "differs from printed net" in t:
        return ("The totals read from the note do not match its printed net amount, so it was not saved. Open the PDF "
                "to check it is complete and readable; if it is, send it to me so the reader can be corrected.")
    if "unknown format" in t or "no parser" in t:
        return ("This broker's contract note layout is not supported yet. Send one sample note and a reader will be "
                "added in the next version.")
    if "bad zip" in t:
        return "The ZIP file is damaged or incomplete. Download it again from the broker and re-import."
    if "annexure" in t:
        return "Import the main contract note together with its annexure (same folder or same ZIP)."
    if "parse error" in t or "could not find" in t or "not found" in t:
        return ("Part of the note could not be read (it may be scanned, cut off or a new layout). Check the file; "
                "if it looks fine, send it to me so the reader can be improved.")
    if "permission" in t or "being used" in t or "access" in t:
        return "The file is open in another program or not accessible. Close it and try again."
    return "Check the file and try again. The Import Log has the full details."


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _.-]+", "", name).strip().replace(" ", "_")


def import_paths(paths, store: Store, data_dir: Path, passwords=(), accept_unreconciled=False, echo=print):
    summary = {"files": 0, "notes_saved": 0, "duplicates": 0, "errors": 0, "unreconciled": 0, "tradebook": 0,
               "problems": []}
    problem_status = {"Error", "Parse error", "Unknown format", "Not reconciled", "Annexure unmatched"}
    pending_notes, annexures, review = [], [], []

    def log(src, status, msg=""):
        store.log(src, status, msg)
        if status in problem_status:
            summary["problems"].append({"source": src, "status": status, "message": msg,
                                        "remedy": remedy(f"{status} {msg}")})
        echo(f"  [{status}] {src} {('- ' + msg) if msg else ''}")

    for doc in iter_documents(paths, log):
        summary["files"] += 1
        if store.file_seen(doc.sha256):
            summary["duplicates"] += 1
            log(doc.origin, "Duplicate file", "identical file already imported")
            continue
        extract_text(doc, passwords)
        if doc.error:
            summary["errors"] += 1
            log(doc.origin, "Error", doc.error)
            continue

        if doc.kind == "excel":
            n = tradebook.try_import(doc, store, log)
            if n is not None:
                summary["tradebook"] += n
                store.add_file(doc.sha256, doc.name, doc.origin, "tradebook", "Imported")
            else:
                log(doc.origin, "Skipped", "Excel file is not a recognised tradebook (use the master/opening commands)")
            continue

        parser, layout = next(((p, p.detect(doc.text)) for p in PARSERS if p.detect(doc.text)), (None, None))
        if parser is None:
            summary["errors"] += 1
            log(doc.origin, "Unknown format", "no parser recognised this contract note layout yet")
            continue
        try:
            if parser is phillip and layout == "annexure":
                annexures.append((doc, *phillip.parse_annexure(doc.text)))
                continue
            notes = parser.parse(doc.text, layout)
        except (ParseError, ValueError) as exc:
            summary["errors"] += 1
            log(doc.origin, "Parse error", str(exc))
            continue
        for cn in notes:
            cn.source_file, cn.source_hash = doc.origin, doc.sha256
            pending_notes.append((doc, cn))

    # link PhillipCapital annexures to their notes
    for adoc, ucc, cn_no, trades in annexures:
        target = next((cn for _, cn in pending_notes if cn.broker == phillip.BROKER and cn.cn_no == cn_no
                       and (not ucc or cn.ucc == ucc)), None)
        if target:
            phillip.link_annexure(target, trades)
            target.source_file += f" + {Path(adoc.origin).name}"
            store.add_file(adoc.sha256, adoc.name, adoc.origin, "annexure", "Linked")
        else:
            log(adoc.origin, "Annexure unmatched", f"contract {cn_no} not in this import")

    saved_docs = set()
    for doc, cn in pending_notes:
        src = f"{doc.origin} [{cn.cn_no}]"
        if store.note_exists(cn):
            summary["duplicates"] += 1
            log(src, "Duplicate note", "contract note already in database")
            continue
        held = store.trades_already_held(cn)
        if held:
            summary["duplicates"] += 1
            log(src, "Duplicate trades", f"{held} trade(s) already recorded under another note")
            continue
        allocate(cn)
        if abs(cn.recon_diff) > TOLERANCE and not accept_unreconciled:
            summary["unreconciled"] += 1
            review.append(cn)
            log(src, "Not reconciled", f"computed net differs from printed net by {cn.recon_diff:,.2f}")
            continue
        store.save_note(cn)
        summary["notes_saved"] += 1
        _file_copy(doc, cn, store, data_dir)
        saved_docs.add(doc.sha256)
        log(src, "Saved", f"{cn.trade_date} {cn.client_name} net {cn.net_amount:,.2f}")

    for doc, _ in pending_notes:
        if doc.sha256 in saved_docs:
            store.add_file(doc.sha256, doc.name, doc.origin, doc.kind, "Imported")
    return summary, review


def _file_copy(doc, cn, store: Store, data_dir: Path):
    """Keep the original contract note in the client's own folder."""
    folder = Layout(data_dir).notes / _safe(f"{cn.pan or cn.ucc}_{cn.client_name}") / "contract_notes" / cn.trade_date[:4]
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / _safe(doc.name)
    if not target.exists():
        target.write_bytes(doc.data)
    store.ensure_client(cn.pan or cn.ucc, cn.client_name, cn.ucc, str(folder.parent.parent))
