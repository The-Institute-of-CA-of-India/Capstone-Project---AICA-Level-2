"""Resume processing for documents left at 'uploaded'/'processing' after a network drop mid-run.

    python -m scripts.resume_october_processing

Retries each remaining document individually, forcing a fresh database connection on any network error
(instead of reusing the one dead connection for the whole run, which is what crashed the bulk script).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import auth_service, document_service as ds  # noqa: E402
from services.db import get_db, system_identity  # noqa: E402

CLIENT_NAME = "Royal Traders"
YEAR, MONTH = 2026, 10


def _force_reconnect():
    db = get_db()
    try:
        db._local.conn.close()
    except Exception:
        pass
    db._local.conn = None


def main():
    db = get_db()
    client = db.fetchone("select * from clients where name = ?", [CLIENT_NAME])
    cu = db.fetchone("select user_id from client_users where client_id = ?", [client["id"]])
    ctx = auth_service.build_context(cu["user_id"])
    auth_service.activate_request_identity(ctx)

    docs = db.fetchall("select id, original_filename, status from documents where client_id = ? and period_month = ? "
                       "and status in ('uploaded', 'processing') order by uploaded_at", [client["id"], MONTH])
    print(f"{len(docs)} document(s) to process")
    done = failed = 0
    for i, d in enumerate(docs, 1):
        for attempt in range(1, 4):
            try:
                with system_identity():  # matches how document_service.submit_documents runs auto-processing
                    status = ds.process_document(ctx, d["id"], _system=True)
                done += 1
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  [{i}/{len(docs)}] {d['original_filename']}: attempt {attempt} failed ({exc}); reconnecting…")
                _force_reconnect()
                time.sleep(1)
        else:
            failed += 1
            print(f"  [{i}/{len(docs)}] {d['original_filename']}: GAVE UP after 3 attempts")
            continue
        if i % 10 == 0 or i == len(docs):
            print(f"  [{i}/{len(docs)}] done so far: {done} ok, {failed} failed")

    sub = db.fetchone("select id from document_submissions where client_id = ? and period_month = ? order by created_at desc",
                      [client["id"], MONTH])
    if sub:
        db.update("document_submissions", sub["id"], {"status": "completed"})

    by_status = {}
    for d in ds.list_documents(ctx, client["id"], year=YEAR, month=MONTH):
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
    print("Final status breakdown:", by_status)


if __name__ == "__main__":
    main()
