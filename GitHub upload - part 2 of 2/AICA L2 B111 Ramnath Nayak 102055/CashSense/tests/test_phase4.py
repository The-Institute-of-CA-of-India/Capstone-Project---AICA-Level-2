"""Phase 4 acceptance tests: Forecaster, scenarios and alerts, commentary guard-rail, assistant tools and
agent loop, voice pipeline, Telegram voice/text questions, dashboard login, Power BI export.
Offline except the live test at the bottom (skipped when Gemini is unavailable)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from cashsense.agents.assistant import TOOLS, Tools, ask
from cashsense.agents.categoriser import categorise
from cashsense.agents.forecaster import (SCENARIOS, apply_scenario, commentary, forecast, forecast_all, known_flows,
                                         unverified_amounts, week_of)
from cashsense.agents.reconciler import reconcile
from cashsense.ai.gemini import GeminiClient, GeminiUnavailable
from cashsense.datagen.phase1 import generate as gen1
from cashsense.datagen.phase4 import generate as gen4
from cashsense.db.adapter import SQLiteDatabase
from cashsense.db.load import load_phase1

ROOT = Path(__file__).resolve().parent.parent
P1, P4 = ROOT / "data" / "phase1", ROOT / "data" / "phase4"
AS_OF = date(2026, 3, 31)


class FakeTg:
    available, chat_id = True, "111"

    def __init__(self, updates):
        self._u, self.sent, self.voices = list(updates), [], []

    def get_updates(self, offset=None, wait=0):
        out, self._u = self._u, []
        return out

    def send_message(self, text, buttons=None, chat_id=None):
        self.sent.append(text)
        return {"message_id": 1}

    def send_voice(self, ogg, caption="", chat_id=None):
        self.voices.append((ogg, caption))

    def download_file(self, fid):
        return b"OggS-fake-audio", "voice.oga"

    def answer_callback(self, *a, **k):
        pass

    def edit_message(self, *a, **k):
        pass


class ScriptedAI:
    """Stands in for Gemini function calling: calls the given tools, then answers with a template."""
    available, last_model = True, "fake-gemini"

    def __init__(self, calls, template):
        self.calls, self.template = calls, template

    def chat_with_tools(self, system, question, tools, run_tool, **kw):
        results = [run_tool(name, args) for name, args in self.calls]
        return {"answer": self.template(results), "tool_calls": [{"name": n, "args": a} for n, a in self.calls],
                "model": self.last_model}


class Phase4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (P1 / "manifest.json").exists():
            gen1(P1)
        gen4(P1, P4)
        cls.key = json.loads((P4 / "answer_key" / "expected_forecast_known_flows.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.dbpath = Path(cls.tmp.name) / "p4.db"
        cls.db = SQLiteDatabase(cls.dbpath)
        load_phase1(cls.db, P1, actor="test")
        categorise(cls.db, cls.db.query("bank_lines", order="line_id"), None, use_ai=False, actor="test")
        for a in ("CA01", "CC01", "CL01", "EF01"):
            reconcile(cls.db, a, AS_OF, actor="test")
        cls.fc = forecast_all(cls.db, AS_OF)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.tmp.cleanup()

    # ---- Forecaster -------------------------------------------------------------------
    def test_known_flows_match_independent_answer_key(self):
        for s, exp in self.key["known_weekly"].items():
            flows = apply_scenario(known_flows(self.db, AS_OF), s, AS_OF)
            got = {w: 0 for w in range(1, 14)}
            for f in flows:
                w = week_of(f.when, AS_OF)
                if 1 <= w <= 13:
                    got[w] += f.amount_paise
            self.assertEqual({str(k): v for k, v in got.items()}, exp, s)

    def test_opening_position_and_alerts(self):
        o = self.fc["base"]["opening"]
        self.assertEqual(o["cc_drawn_paise"], self.key["opening"]["cc_drawn_paise"])
        self.assertEqual(round(o["cc_drawn_paise"] / o["cc_limit_paise"] * 100), self.key["opening"]["cc_utilisation_pct"])
        for r in self.fc.values():
            self.assertEqual(len(r["weeks"]), 13)
            for w in r["weeks"]:
                self.assertEqual(bool(w["alert"]), w["cc_utilisation"] > 0.85)
                self.assertEqual(w["cc_headroom_paise"], o["cc_limit_paise"] - w["cc_drawn_paise"])
            alerts = [w["week"] for w in r["weeks"] if w["alert"]]
            self.assertEqual(r["summary"]["alert_weeks"], alerts)
            self.assertEqual(r["summary"]["first_alert_week"], alerts[0] if alerts else None)

    def test_position_rolls_forward(self):
        for r in self.fc.values():
            pos = r["opening"]["net_position_paise"]
            for w in r["weeks"]:
                pos += w["net_flow_paise"]
                self.assertEqual(pos, w["net_position_paise"])
                self.assertEqual(w["net_flow_paise"], sum(w["by_category"].values()))

    def test_scenarios_behave(self):
        base, late = self.fc["base"]["summary"], self.fc["late_15"]["summary"]
        self.assertLess(late["total_inflow_paise"], base["total_inflow_paise"])
        self.assertGreater(late["peak_utilisation"], base["peak_utilisation"])
        top = self.fc["base"]["summary"]["top_customer"]
        self.assertFalse(any(f["party_id"] == top and f["category"] == "customer_receipts"
                             for f in self.fc["top_customer_default"]["flows"]))
        capex = [f for f in self.fc["capex_forward"]["flows"] if f["category"] == "capex"]
        self.assertEqual(len(capex), 1)
        self.assertEqual(week_of(capex[0]["when"], AS_OF), 1)
        msme = [f for f in self.fc["base"]["flows"] if "MSME overdue" in f["label"]]
        overdue_msme = [b for b in self.db.query("ap_open") if b["msme"] and b["due_date"] <= AS_OF.isoformat()]
        self.assertEqual(len(msme), len(overdue_msme))
        self.assertTrue({"V002", "V005"} <= {f["party_id"] for f in msme}, "the sec 43B(h) bills are paid at once")
        self.assertTrue(all(week_of(f["when"], AS_OF) == 1 for f in msme))
        with self.assertRaises(ValueError):
            forecast(self.db, AS_OF, "moon_landing")

    def test_run_rate_uses_same_month_last_year(self):
        rr = [f for f in self.fc["base"]["flows"] if f["basis"] == "run_rate"]
        self.assertTrue(rr)
        self.assertTrue(all(f["label"].endswith("(same month last year)") for f in rr))
        self.assertTrue(all(AS_OF < date.fromisoformat(f["when"]) <= AS_OF + timedelta(days=91) for f in rr))
        import re
        months = {re.search(r"(\w{3} \d{4})", f["label"]).group(1) for f in rr}
        self.assertTrue(months <= {"Apr 2026", "May 2026", "Jun 2026"}, months)

    # ---- commentary guard-rail ----------------------------------------------------------
    def test_commentary_rejects_invented_amounts(self):
        peak = self.fc["late_15"]["summary"]["peak_cc_drawn_paise"]

        class AI:
            available, last_model = True, "fake"

            def generate_json(self, system, parts, schema, **kw):
                from cashsense.money import fmt_inr
                return {"headline": f"Peak drawing {fmt_inr(peak)} if customers pay late.",
                        "scenarios": [{"scenario": "late_15", "comment": "Also borrow Rs 3,33,33,333.00 extra."}],
                        "actions": ["Chase Rs 12 lakh from customers."]}

        res = commentary(self.db, self.fc, AI())
        self.assertTrue(res["ai_used"])
        self.assertIn(33333333, res["unverified_amounts"])
        self.assertIn(1200000, res["unverified_amounts"])
        self.assertNotIn(round(peak / 100), res["unverified_amounts"])
        self.assertTrue(res["warning"])
        self.assertEqual(unverified_amounts("Rs 1.26 crore", {"x": "Rs 1,26,32,553.34"}), [])

    # ---- assistant ----------------------------------------------------------------------
    def test_assistant_tools_are_read_only_and_correct(self):
        t = Tools(self.db, AS_OF)
        self.assertEqual(t.get_cash_position()["cc_utilisation"], f"{self.key['opening']['cc_utilisation_pct']}%")
        p = t.get_payables(msme_only=True)
        from cashsense.money import fmt_inr
        self.assertEqual(p["msme_beyond_45_days_total"], fmt_inr(self.key["msme_beyond_45"]["total_paise"]))
        self.assertIn("error", t.run("delete_everything", {}))
        self.assertIn("error", t.run("get_forecast", {"scenario": "nope"}))
        self.assertTrue(all(td["name"].startswith("get_") for td in TOOLS), "only read-only tools are exposed")
        before = {tbl: len(self.db.query(tbl)) for tbl in ("book_entries", "approvals", "risk_flags")}
        for td in TOOLS:
            t.run(td["name"], {})
        self.assertEqual(before, {tbl: len(self.db.query(tbl)) for tbl in before})

    def test_assistant_answer_amount_check(self):
        good = ScriptedAI([("get_payables", {"msme_only": True})],
                          lambda r: f"Total {r[0]['msme_beyond_45_days_total']} owed to MSME suppliers.")
        self.assertEqual(ask(self.db, "msme?", good, AS_OF)["unverified_amounts"], [])
        bad = ScriptedAI([("get_cash_position", {})], lambda r: "You have Rs 9,99,99,999.00 in the bank.")
        res = ask(self.db, "cash?", bad, AS_OF)
        self.assertEqual(res["unverified_amounts"], [99999999])
        self.assertIn("please verify", res["answer"])

    def test_gemini_function_calling_loop(self):
        class Resp:
            def __init__(self, body):
                self.status_code, self._b = 200, body

            def json(self):
                return self._b

        class Session:
            def __init__(self):
                self.bodies, self.urls = [], []

            def post(self, url, headers, json, timeout):
                import copy
                self.urls.append(url)
                self.bodies.append(copy.deepcopy(json))
                if len(self.bodies) == 1:
                    return Resp({"candidates": [{"content": {"role": "model", "parts": [
                        {"functionCall": {"name": "get_cash_position", "args": {}}, "thoughtSignature": "sig1"}]}}]})
                return Resp({"candidates": [{"content": {"role": "model", "parts": [{"text": "63% used."}]}}]})

        s = Session()
        c = GeminiClient(api_key="k", models=["gemini-9.0-flash"], session=s)
        out = c.chat_with_tools("sys", "cc?", TOOLS, lambda n, a: {"cc_utilisation": "63%"})
        self.assertEqual(out["answer"], "63% used.")
        second = s.bodies[1]["contents"]
        self.assertEqual(second[1]["parts"][0]["thoughtSignature"], "sig1", "model content is returned verbatim")
        self.assertEqual(second[2]["parts"][0]["functionResponse"]["name"], "get_cash_position")
        self.assertEqual(len(set(s.urls)), 1, "the same model is used for the whole conversation")

    # ---- voice --------------------------------------------------------------------------
    def test_voice_encoding(self):
        from cashsense.voice import _plain, pcm_to_ogg

        ogg = pcm_to_ogg(b"\x00\x00" * 24000, 24000)
        self.assertEqual(ogg[:4], b"OggS")
        cases = {
            "Owe Rs 1,26,32,553.34 now": "Owe 1 crore 26 lakh 32 thousand 553 rupees now",
            "limit Rs 2,00,00,000.00.": "limit 2 crore rupees.",
            "about Rs 10.41 lakh and Rs 1.26 crore": "about 10.41 lakh rupees and 1.26 crore rupees",
            "interest -Rs 92,754.91; paid Rs 5,00,000.": "interest minus 92 thousand 755 rupees; paid 5 lakh rupees.",
            "inflow 8,39,49,042.03; USD 51,665.59; 109% in week 10": "inflow 8 crore 39 lakh 49 thousand 42; "
                                                                      "USD 51,665.59; 109% in week 10",
        }
        for said, spoken in cases.items():
            self.assertEqual(_plain(said), spoken)

    @unittest.skipUnless(os.name == "nt", "Windows offline voice")
    def test_windows_offline_voice(self):
        from cashsense.voice import windows_tts_ogg

        self.assertEqual(windows_tts_ogg("Test")[:4], b"OggS")

    def test_telegram_voice_and_text_questions(self):
        from cashsense.notify import handle_updates

        class AI(ScriptedAI):
            def transcribe(self, audio, mime):
                return "what is my cc utilisation"

            def speak(self, text):
                return b"\x00\x00" * 2400, 24000

        ai = AI([("get_cash_position", {})], lambda r: f"CC use is {r[0]['cc_utilisation']}.")
        tg = FakeTg([{"update_id": 1, "message": {"message_id": 1, "chat": {"id": 111},
                                                  "voice": {"file_id": "v1", "mime_type": "audio/ogg"}}},
                     {"update_id": 2, "message": {"message_id": 2, "chat": {"id": 111}, "text": "cash position?"}}])
        out = handle_updates(self.db, tg, ai)
        self.assertEqual(len(out["questions"]), 2)
        self.assertTrue(any("You asked:" in m and "63%" in m for m in tg.sent))
        self.assertEqual(len(tg.voices), 1)
        self.assertEqual(tg.voices[0][0][:4], b"OggS")
        self.assertIn("Gemini TTS", tg.voices[0][1])

    # ---- dashboard ----------------------------------------------------------------------
    def test_dashboard_login_and_data(self):
        from fastapi.testclient import TestClient

        import cashsense.api as api

        env = {"CASHSENSE_DB": "sqlite", "CASHSENSE_SQLITE": str(self.dbpath), "DASHBOARD_PASSWORD": "pw-test-123",
               "SESSION_SECRET": "s" * 40, "CASHSENSE_API_KEY": "k"}
        with mock.patch.dict(os.environ, env):
            api._failures.clear()
            c = TestClient(api.app)
            r = c.get("/dashboard", follow_redirects=False)
            self.assertEqual((r.status_code, r.headers["location"]), (303, "/login"))
            self.assertEqual(c.get("/api/dash/data").status_code, 401)
            self.assertEqual(c.post("/login", content="password=wrong",
                                    headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code, 401)
            r = c.post("/login", content="password=pw-test-123", follow_redirects=False,
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
            self.assertEqual(r.status_code, 303)
            data = c.get("/api/dash/data").json()
            self.assertEqual(len(data["scenarios"]), 4)
            self.assertEqual(round(data["kpis"]["cc_util"] * 100), self.key["opening"]["cc_utilisation_pct"])
            self.assertIn("SAMPLE", c.get("/dashboard").text)
            c.cookies.clear()
            for _ in range(10):
                c.post("/login", content="password=x", headers={"Content-Type": "application/x-www-form-urlencoded"})
            self.assertEqual(c.post("/login", content="password=pw-test-123",
                                    headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code, 429)
            api._failures.clear()

    # ---- Power BI export -----------------------------------------------------------------
    def test_powerbi_export(self):
        from cashsense.powerbi import export

        with tempfile.TemporaryDirectory() as tmp:
            counts = export(self.db, AS_OF, Path(tmp))
            self.assertEqual(counts["fact_forecast_week"], 13 * len(SCENARIOS))
            self.assertEqual(counts["fact_bank_line"], len(self.db.query("bank_lines")))
            self.assertTrue((Path(tmp) / "measures.dax").read_text(encoding="utf-8").startswith("// CashSense"))
            header = (Path(tmp) / "fact_forecast_week.csv").read_text(encoding="utf-8").splitlines()[0]
            self.assertIn("cc_utilisation", header)


@unittest.skipUnless(GeminiClient().available, "GEMINI_API_KEY not set")
class LiveAssistantTests(unittest.TestCase):
    def test_question_bank(self):
        from cashsense.cli import check_answer
        from cashsense.db import get_database

        db = get_database()
        fc = forecast_all(db, AS_OF)
        qs = json.loads((P4 / "answer_key" / "assistant_questions.json").read_text(encoding="utf-8"))
        passed = 0
        for q in qs[:3]:
            try:
                res = ask(db, q["q"], GeminiClient(), AS_OF)
            except GeminiUnavailable as exc:
                self.skipTest(f"Gemini free tier busy ({str(exc)[:60]})")
            passed += check_answer(q, res["answer"], fc)[0]
        self.assertGreaterEqual(passed, 2)


if __name__ == "__main__":
    unittest.main()
