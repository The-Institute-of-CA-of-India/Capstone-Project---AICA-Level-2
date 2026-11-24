"""Phase 5 tests: Supabase adapter (offline, stand-in HTTP), database copy, briefing payload, Apps Script code,
MCP server protocol, plugin integrity, tool API, upload secret scan."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from cashsense.db.adapter import (TABLES, SQLiteDatabase, SupabaseDatabase, SupabaseError, copy_database,
                                  supabase_setup_sql)
from cashsense.db.load import load_phase1

ROOT = Path(__file__).resolve().parent.parent
P1 = ROOT / "data" / "phase1"
PLUGIN = ROOT / "plugin" / "cashsense"
MCP = PLUGIN / "mcp" / "cashsense_mcp.py"


class Resp:
    def __init__(self, code=200, body=None):
        self.status_code, self._b, self.text = code, body if body is not None else [], json.dumps(body)

    def json(self):
        return self._b


class FakePostgrest:
    """Minimal PostgREST stand-in: one table of 2,500 rows, records requests."""
    def __init__(self):
        self.rows = [{"line_id": f"L{i:04d}"} for i in range(2500)]
        self.calls = []

    def get(self, url, params, headers, timeout):
        self.calls.append(("GET", url, dict(params), dict(headers)))
        o, n = params.get("offset", 0), params.get("limit", 1000)
        return Resp(200, self.rows[o:o + n])

    def post(self, url, headers, json, timeout):
        self.calls.append(("POST", url, None, dict(headers)))
        return Resp(201, None)

    def patch(self, url, params, json, headers, timeout):
        self.calls.append(("PATCH", url, dict(params), dict(headers)))
        return Resp(200, [{"ok": 1}])

    def delete(self, url, params, headers, timeout):
        self.calls.append(("DELETE", url, dict(params), dict(headers)))
        return Resp(400, {"message": "permission denied"}) if "audit_log" in url else Resp(204, None)


class Phase5Tests(unittest.TestCase):
    # ---- Supabase adapter -----------------------------------------------------------------
    def test_supabase_keys_paging_cache(self):
        s = FakePostgrest()
        fake_key = "sb_" + "secret_" + "TESTKEY123456"     # built at runtime so the upload secret scan stays strict
        db = SupabaseDatabase("https://x.supabase.co", fake_key, session=s)
        rows = db.query("bank_lines")
        self.assertEqual(len(rows), 2500)
        self.assertEqual([c[2]["offset"] for c in s.calls], [0, 1000, 2000])
        self.assertNotIn("Authorization", s.calls[0][3], "new-style secret keys go only in the apikey header")
        self.assertEqual(s.calls[0][2]["order"], "line_id.asc")
        db.query("bank_lines")
        self.assertEqual(len(s.calls), 3, "second read within the cache window makes no request")
        db.update("bank_lines", {"line_id": "L0001"}, {"category": "x"})
        db.query("bank_lines")
        self.assertEqual(len([c for c in s.calls if c[0] == "GET"]), 6, "a write clears that table's cache")
        jwt = SupabaseDatabase("https://x.supabase.co", "eyJhbGciOiJIUzI1NiJ9.e30.x", session=FakePostgrest())
        self.assertTrue(jwt.headers["Authorization"].startswith("Bearer "))
        with self.assertRaises(SupabaseError) as cm:
            db.delete("audit_log", {"log_id": "1"})
        self.assertIn("permission denied", str(cm.exception))
        self.assertNotIn("TESTKEY", str(cm.exception))

    def test_supabase_setup_sql_enables_rls_everywhere(self):
        sql = supabase_setup_sql()
        for t in TABLES:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {t}", sql)
            self.assertIn(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;", sql)
        self.assertNotIn("CREATE POLICY", sql)

    def test_copy_database_keeps_everything(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            a, b = SQLiteDatabase(Path(tmp) / "a.db"), SQLiteDatabase(Path(tmp) / "b.db")
            try:
                load_phase1(a, P1, actor="test")
                b.init_schema()
                counts = copy_database(a, b, progress=lambda *_: None)
                for t in TABLES:
                    self.assertEqual(len(b.query(t)), counts[t], t)
                self.assertEqual(a.query("bank_lines", order="line_id"), b.query("bank_lines", order="line_id"))
            finally:
                a.close()
                b.close()

    # ---- briefing + Apps Script ------------------------------------------------------------
    def test_briefing_payload_and_send(self):
        from cashsense import briefing
        from cashsense.agents.reconciler import reconcile

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = SQLiteDatabase(Path(tmp) / "b.db")
            try:
                load_phase1(db, P1, actor="test")
                for acc in ("CA01", "CC01", "CL01", "EF01"):
                    reconcile(db, acc, date(2026, 3, 31), actor="test")
                b = briefing.build(db, date(2026, 3, 31))
            finally:
                db.close()
        self.assertEqual(b["cc_use_today"], "63%")
        self.assertTrue(b["all_brs_agreed"])
        self.assertEqual(len(b["scenarios"]), 4)
        self.assertEqual(b["worst_peak_use"], "109%")
        with mock.patch.dict(os.environ, {"APPS_SCRIPT_URL": ""}):
            self.assertFalse(briefing.send(b)["ok"])
        with mock.patch.dict(os.environ, {"APPS_SCRIPT_URL": "https://script.example/exec", "APPS_SCRIPT_SECRET": "s3"}), \
                mock.patch("cashsense.briefing.requests.post") as post:
            post.return_value.json.return_value = {"ok": True}
            self.assertTrue(briefing.send(b)["ok"])
            sent = post.call_args.kwargs["json"]
            self.assertEqual(sent["secret"], "s3")
            self.assertEqual(sent["briefing"]["as_of"], "2026-03-31")

    def test_apps_script_code(self):
        code = (ROOT / "apps_script" / "Code.gs").read_text(encoding="utf-8")
        for needed in ("function doPost", "body.secret !== secret", "function setup", "eveningReminder",
                       "staleCheck", "weeklyDigest", "MailApp.sendEmail", "SAMPLE"):
            self.assertIn(needed, code)
        manifest = json.loads((ROOT / "apps_script" / "appsscript.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["timeZone"], "Asia/Kolkata")

    # ---- MCP server ---------------------------------------------------------------------
    def _mcp(self, messages: list[dict], env: dict | None = None) -> list[dict]:
        p = subprocess.run([sys.executable, str(MCP)], input="\n".join(json.dumps(m) if isinstance(m, dict) else m
                                                                      for m in messages) + "\n",
                           capture_output=True, text=True, timeout=60, env={**os.environ, **(env or {})})
        return [json.loads(line) for line in p.stdout.splitlines() if line.strip()]

    def test_mcp_protocol(self):
        out = self._mcp([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "resources/list"},
            "this is not json",
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "cash_position", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "drop_tables", "arguments": {}}},
        ], env={"CASHSENSE_URL": "http://127.0.0.1:9", "CASHSENSE_API_KEY": "x"})
        by_id = {m.get("id"): m for m in out}
        self.assertEqual(len(out), 6, "the notification gets no reply")
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "cashsense")
        tools = by_id[2]["result"]["tools"]
        self.assertEqual(len(tools), 9)
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))
        self.assertEqual(by_id[3]["error"]["code"], -32601)
        self.assertEqual(by_id[None]["error"]["code"], -32700)
        self.assertTrue(by_id[4]["result"]["isError"])
        self.assertIn("not reachable", by_id[4]["result"]["content"][0]["text"])
        self.assertTrue(by_id[5]["result"]["isError"])

    # ---- plugin ---------------------------------------------------------------------------
    def test_plugin_integrity(self):
        meta = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["name"], "cashsense")
        mcp = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/mcp/cashsense_mcp.py", mcp["mcpServers"]["cashsense"]["args"])
        market = json.loads((ROOT / "plugin" / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "plugin" / market["plugins"][0]["source"]).is_dir())
        src = {p.parent.name: p.read_text(encoding="utf-8") for p in (ROOT / "skills").glob("*/SKILL.md")}
        dst = {p.parent.name: p.read_text(encoding="utf-8") for p in (PLUGIN / "skills").glob("*/SKILL.md")}
        self.assertEqual(src, dst, "plugin skills must match cashsense/skills (run scripts/build_plugin.py)")
        self.assertEqual(len(src), 6)
        for cmd in (PLUGIN / "commands").glob("*.md"):
            text = cmd.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\ndescription:"), cmd.name)

    # ---- tool API ---------------------------------------------------------------------------
    def test_tool_api(self):
        from fastapi.testclient import TestClient

        import cashsense.api as api

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "t.db"
            db = SQLiteDatabase(path)
            load_phase1(db, P1, actor="test")
            db.close()
            with mock.patch.dict(os.environ, {"CASHSENSE_API_KEY": "k", "CASHSENSE_DB": "sqlite",
                                              "CASHSENSE_SQLITE": str(path)}):
                c = TestClient(api.app)
                self.assertEqual(c.post("/api/tool/get_cash_position", json={}).status_code, 401)
                self.assertEqual(c.post("/api/tool/drop_tables", json={}, headers={"X-CashSense-Key": "k"}).status_code, 404)
                r = c.post("/api/tool/get_cash_position", json={"args": {}}, headers={"X-CashSense-Key": "k"})
                self.assertEqual(r.json()["cc_utilisation"], "63%")

    # ---- upload secret scan -----------------------------------------------------------------
    def test_upload_scan_finds_planted_secrets(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_upload

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "ok.txt").write_text("nothing here", encoding="utf-8")
            (d / "leak.py").write_text("KEY = 'AIza" + "B" * 35 + "'", encoding="utf-8")
            (d / "tg.txt").write_text("1234567890:AA" + "x" * 33, encoding="utf-8")
            import zipfile
            with zipfile.ZipFile(d / "book.xlsx", "w", zipfile.ZIP_DEFLATED) as z:   # secret hidden inside Excel
                z.writestr("xl/sharedStrings.xml", "<t>AIza" + "C" * 35 + "</t>")
            hits = build_upload.scan(d)
        self.assertEqual(len(hits), 3)
        self.assertTrue(any("book.xlsx" in h for h in hits))


if __name__ == "__main__":
    unittest.main()
