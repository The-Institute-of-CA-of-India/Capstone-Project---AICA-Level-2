"""Automated checks for the business rules (README test checklist items 1-12).

Run from the application folder:   python -m unittest discover -s tests -v
"""
import csv
import os
import shutil
import sys
import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsc_manager import dates, token_reader  # noqa: E402
from dsc_manager.database import (CertificateConflict, Database, DuplicateCustodyError, InactiveTokenError,  # noqa: E402
                                  ValidationError, classify_expiry, days_text, is_valid_database)
from dsc_manager.sample_data import load_sample_data  # noqa: E402
from dsc_manager.ui.widgets import write_csv  # noqa: E402


def iso(offset):
    return (dates.today() + timedelta(days=offset)).isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "test.db")
        self.db = Database(self.path)
        self.cid = self.db.add_client({"holder_name": "Test Holder", "firm_name": "Test Firm",
                                       "pan": "AAAPT1234A", "mobile": "9876543210"})
        self.db.appoint_custodian("Cust A")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def inward(self, token="TKN-1", inward_date=None, cert=None, **kw):
        data = {"client_id": self.cid, "inward_date": inward_date or iso(-1), "holder_name": "Test Holder",
                "token_serial": token, "received_from": "Test Holder", "received_by": "Staff A",
                "purpose": "Tax Audit", "expected_return_date": iso(5)}
        data.update(kw)
        return self.db.save_inward(data, cert=cert)

    def custody_tokens(self):
        return [r["token_serial"] for r in self.db.custody_register()]


class ClientTests(Base):
    def test_client_code_generated_and_pan_unique(self):
        c = self.db.get_client(self.cid)
        self.assertEqual(c["client_code"], f"CL{self.cid:04d}")
        with self.assertRaises(ValidationError):
            self.db.add_client({"holder_name": "Other", "pan": "aaapt1234a", "mobile": "9000000002"})

    def test_invalid_pan_rejected(self):
        with self.assertRaises(ValidationError):
            self.db.add_client({"holder_name": "X", "pan": "12345", "mobile": "9000000003"})

    def test_pan_must_be_individual(self):
        for pan in ("AAACT1234A", "AAAFT1234A", "AAATT1234A", "AAAHT1234A"):
            with self.assertRaises(ValidationError) as cm:
                self.db.add_client({"holder_name": "Company", "pan": pan, "mobile": "9000000004"})
            self.assertIn("4th character", str(cm.exception))
        self.db.add_client({"holder_name": "Person", "pan": "ABCPS1234K", "mobile": "9000000005"})

    def test_cannot_delete_client_with_transactions(self):
        self.inward()
        with self.assertRaises(ValidationError):
            self.db.delete_client(self.cid)
        self.db.set_client_status(self.cid, "Inactive")
        self.assertEqual(self.db.list_clients(status="Inactive")[0]["client_id"], self.cid)

    def test_report_search_by_holder_and_client_name_only(self):
        other = self.db.add_client({"holder_name": "Ravi Kumar", "firm_name": "Kumar Steels", "pan": "CCCPK1234C", "mobile": "9000000006"})
        self.inward(token="TKN-1")
        self.db.save_inward({"client_id": other, "inward_date": iso(-1), "holder_name": "Sunil Kumar",
                             "token_serial": "TKN-2", "received_from": "Ravi Kumar", "purpose": "GST"})
        find = lambda text: sorted(r["token_serial"] for r in self.db.custody_register({"search": text}))  # noqa
        self.assertEqual(find("Sunil"), ["TKN-2"])           # DSC holder name
        self.assertEqual(find("Ravi"), ["TKN-2"])            # client name
        self.assertEqual(find("Steels"), ["TKN-2"])          # client firm name
        self.assertEqual(find("Test Holder"), ["TKN-1"])
        self.assertEqual(find("TKN"), [])                    # token numbers are not searched
        self.assertEqual(len(self.db.inward_register({"search": "kumar"})), 1)
        self.assertEqual(len(self.db.expiry_alerts("all", {"search": "Sunil"})), 1)

    def test_search_by_name_and_code(self):
        self.assertEqual(len(self.db.list_clients("Test Hol")), 1)
        self.assertEqual(len(self.db.list_clients(f"CL{self.cid:04d}")), 1)
        self.assertEqual(len(self.db.list_clients("nobody")), 0)


class CustodyTests(Base):
    def test_1_to_4_inward_custody_outward_registers(self):
        inw = self.inward()
        self.assertEqual(self.custody_tokens(), ["TKN-1"])                         # 2
        self.assertEqual(self.db.dashboard_counts()["custody"], 1)
        self.db.save_outward({"inward_id": inw, "outward_date": dates.today_iso(),
                              "returned_to": "Test Holder", "returned_by": "Staff A"})
        self.assertEqual(self.custody_tokens(), [])                                # 3
        self.assertEqual(self.db.dashboard_counts()["custody"], 0)
        self.assertEqual(len(self.db.inward_register()), 1)                         # 4
        self.assertEqual(len(self.db.outward_register()), 1)

    def test_second_outward_prevented(self):
        inw = self.inward()
        out = {"inward_id": inw, "outward_date": dates.today_iso(), "returned_to": "X", "returned_by": "Y"}
        self.db.save_outward(out)
        with self.assertRaises(ValidationError):
            self.db.save_outward(out)

    def test_duplicate_inward_warns_and_counts_once(self):
        first = self.inward()
        with self.assertRaises(DuplicateCustodyError):
            self.inward()
        self.assertEqual(len(self.db.inward_register()), 1)   # nothing saved by the failed attempt
        second = self.db.save_inward({"client_id": self.cid, "inward_date": dates.today_iso(),
                                      "holder_name": "Test Holder", "token_serial": "tkn-1",
                                      "received_from": "Test Holder", "received_by": "Staff B",
                                      "purpose": "GST"}, allow_duplicate=True)
        self.assertEqual(self.db.dashboard_counts()["custody"], 1)
        custody = self.db.custody_register()
        self.assertEqual(len(custody), 1)
        self.assertEqual(custody[0]["inward_id"], second)
        statuses = {r["inward_id"]: r["status"] for r in self.db.inward_register()}
        self.assertEqual(statuses, {first: "Superseded", second: "Active"})
        # Cancelling the newer receipt restores the older one.
        self.db.cancel_inward(second, "entered twice")
        self.assertEqual(self.db.custody_register()[0]["inward_id"], first)

    def test_token_belongs_to_one_client(self):
        self.inward()
        other = self.db.add_client({"holder_name": "Other", "pan": "BBBPT1234B", "mobile": "9000000007"})
        with self.assertRaises(ValidationError):
            self.db.save_inward({"client_id": other, "inward_date": iso(0), "holder_name": "Other",
                                 "token_serial": "TKN-1", "received_from": "Other", "received_by": "S",
                                 "purpose": "GST"})

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.inward(token="")
        with self.assertRaises(ValidationError):
            self.inward(inward_date=iso(1))                       # future
        with self.assertRaises(ValidationError):
            self.inward(expected_return_date=iso(-10))            # before inward date
        with self.assertRaises(ValidationError):
            self.inward(purpose="Something")
        inw = self.inward()
        with self.assertRaises(ValidationError):                  # outward before inward
            self.db.save_outward({"inward_id": inw, "outward_date": iso(-5), "returned_to": "X",
                                  "returned_by": "Y"})

    def test_cancel_outward_restores_custody(self):
        inw = self.inward()
        out = self.db.save_outward({"inward_id": inw, "outward_date": dates.today_iso(),
                                    "returned_to": "X", "returned_by": "Y"})
        self.db.cancel_outward(out, "wrong token")
        self.assertEqual(self.custody_tokens(), ["TKN-1"])
        self.assertEqual(len(self.db.outward_register({"include_cancelled": True})), 1)

    def test_overdue_filter(self):
        self.inward(token="T-OVER", inward_date=iso(-10), expected_return_date=iso(-2))
        self.inward(token="T-OK", inward_date=iso(-1), expected_return_date=iso(10))
        over = self.db.custody_register({"overdue": "overdue"})
        self.assertEqual([r["token_serial"] for r in over], ["T-OVER"])
        self.assertEqual(self.db.dashboard_counts()["overdue"], 1)

    def test_inward_inactive_client_rejected(self):
        self.db.set_client_status(self.cid, "Inactive")
        with self.assertRaises(ValidationError):
            self.inward()


class AwaitedTests(Base):
    def test_5_6_awaited_until_received(self):
        eid = self.db.add_expected({"client_id": self.cid, "purpose": "ITR Filing", "expected_date": iso(2)})
        self.assertEqual([r["expected_id"] for r in self.db.awaited_list()], [eid])   # 5
        self.assertEqual(self.db.dashboard_counts()["awaited"], 1)
        inw = self.inward(expected_id=eid)
        self.assertEqual(self.db.awaited_list(), [])                                   # 6
        self.assertEqual(self.db.dashboard_counts()["awaited"], 0)
        self.db.cancel_inward(inw, "mistake")
        self.assertEqual(len(self.db.awaited_list()), 1)      # awaited again once the receipt is cancelled

    def test_auto_link_by_token_serial(self):
        self.db.add_expected({"client_id": self.cid, "purpose": "GST", "token_serial": "TKN-9"})
        self.inward(token="TKN-9")
        self.assertEqual(self.db.awaited_list(), [])


NOON = f"{dates.today_iso()} 12:00:00"   # a fixed 'now' for expiry tests


def iso_t(offset, hhmm):
    return f"{iso(offset)} {hhmm}:00"


class ExpiryTests(Base):
    def test_7_classification_boundaries(self):
        cases = {iso_t(-1, "18:00"): "Expired", iso_t(0, "18:00"): "Expires Today",
                 iso_t(7, "18:00"): "Expiring Within 7 Days", iso_t(15, "18:00"): "Expiring Within 15 Days",
                 iso_t(30, "18:00"): "Expiring Within 30 Days", iso_t(31, "18:00"): "Valid Beyond 30 Days"}
        for expiry, expected in cases.items():
            self.assertEqual(classify_expiry(expiry, NOON)[1], expected, expiry)
        self.assertEqual(classify_expiry(None, NOON), (None, "Expiry Date Unknown"))

    def test_expiry_time_of_day(self):
        # The user's example: expires at 11:00 AM on 26-10-2026; at 1:00 PM the same day it is Expired.
        self.assertEqual(classify_expiry("2026-10-26 11:00:00", "2026-10-26 13:00:00")[1], "Expired")
        self.assertEqual(classify_expiry("2026-10-26 11:00:00", "2026-10-26 10:59:00")[1], "Expires Today")
        self.assertEqual(classify_expiry("2026-10-26 11:00:00", "2026-10-26 11:00:00")[1], "Expired")
        # No time recorded -> taken as 12:00 AM: already expired at any time that day.
        self.assertEqual(classify_expiry("2026-10-26", "2026-10-26 00:30:00")[1], "Expired")
        self.assertEqual(classify_expiry("2026-10-27", "2026-10-26 23:00:00")[1], "Expiring Within 7 Days")
        days, status = classify_expiry("2026-10-26 11:00:00", "2026-10-26 13:00:00")
        self.assertEqual(days_text(days, status, "2026-10-26 11:00:00"), "Expired today at 11:00 AM")
        days, status = classify_expiry("2026-10-26 15:30:00", "2026-10-26 13:00:00")
        self.assertEqual(days_text(days, status, "2026-10-26 15:30:00"), "Expires today at 3:30 PM")

    def test_expiry_time_stored_and_listed(self):
        self.inward(token="TM", cert={"cert_serial": "C1", "expiry_date": iso_t(0, "11:00")})
        self.assertEqual(self.db.get_current_certificate(self.db.find_token("TM")["token_id"])["expiry_date"],
                         iso_t(0, "11:00"))
        self.assertEqual([r["token_serial"] for r in self.db.expiry_alerts("expired", as_of=iso_t(0, "13:00"))],
                         ["TM"])
        self.assertEqual([r["token_serial"] for r in self.db.expiry_alerts("today", as_of=iso_t(0, "09:00"))],
                         ["TM"])
        # Adding the time of day to a date-only expiry of the same certificate is not a conflict.
        self.inward(token="TD", cert={"cert_serial": "C2", "expiry_date": iso(40)})
        tid = self.db.find_token("TD")["token_id"]
        self.db.save_certificate(tid, {"cert_serial": "C2", "expiry_date": iso_t(40, "15:12")})
        self.assertEqual(self.db.get_current_certificate(tid)["expiry_date"], iso_t(40, "15:12"))
        self.assertEqual(len(self.db.certificate_history(tid)), 1)

    def test_7_alert_lists_and_counts(self):
        for n, offset in enumerate([-1, 0, 7, 15, 30, 31]):
            self.inward(token=f"T{n}", cert={"cert_serial": f"C{n}", "expiry_date": iso_t(offset, "18:00")})
        self.inward(token="T-UNKNOWN")                                                     # 8
        tokens = lambda flt: sorted(r["token_serial"] for r in self.db.expiry_alerts(flt, as_of=NOON))  # noqa
        self.assertEqual(tokens("expired"), ["T0"])
        self.assertEqual(tokens("today"), ["T1"])
        self.assertEqual(tokens("7"), ["T1", "T2"])
        self.assertEqual(tokens("15"), ["T1", "T2", "T3"])
        self.assertEqual(tokens("30"), ["T1", "T2", "T3", "T4"])
        self.assertEqual(tokens("beyond"), ["T5"])
        self.assertEqual(tokens("unknown"), ["T-UNKNOWN"])
        c = self.db.dashboard_counts(as_of=NOON)
        self.assertEqual((c["exp_7"], c["exp_15"], c["exp_30"], c["exp_expired"], c["exp_unknown"]),
                         (2, 3, 4, 1, 1))
        # Each list holds each certificate at most once.
        for flt in ("7", "15", "30"):
            lst = tokens(flt)
            self.assertEqual(len(lst), len(set(lst)))

    def test_9_expired_token_still_in_custody(self):
        self.inward(token="OLD", cert={"expiry_date": iso(-100)})
        self.assertEqual(self.custody_tokens(), ["OLD"])
        self.assertEqual(self.db.custody_register()[0]["expiry_status"], "Expired")

    def test_10_renewal_preserves_history(self):
        self.inward(token="REN", cert={"cert_serial": "OLD-CERT", "expiry_date": iso(5)})
        token_id = self.db.find_token("REN")["token_id"]
        with self.assertRaises(CertificateConflict):
            self.db.save_certificate(token_id, {"cert_serial": "NEW-CERT", "expiry_date": iso(735)})
        self.db.save_certificate(token_id, {"cert_serial": "NEW-CERT", "expiry_date": iso(735)}, action="renew")
        hist = self.db.certificate_history(token_id)
        self.assertEqual(len(hist), 2)
        old = [h for h in hist if h["cert_serial"] == "OLD-CERT"][0]
        self.assertEqual(old["expiry_date"], iso(5))
        self.assertEqual(old["is_current"], 0)
        self.assertEqual(self.db.get_current_certificate(token_id)["cert_serial"], "NEW-CERT")
        self.assertEqual(self.db.expiry_alerts("7"), [])          # alert now uses the renewed certificate

    def test_cert_added_later_and_returned_token_keeps_cert(self):
        inw = self.inward(token="LATER")
        token_id = self.db.find_token("LATER")["token_id"]
        self.db.save_certificate(token_id, {"cert_serial": "C-L", "expiry_date": iso(20)})
        self.assertEqual(self.db.inward_register()[0]["cert_serial"], "C-L")
        self.db.save_outward({"inward_id": inw, "outward_date": iso(0), "returned_to": "X", "returned_by": "Y"})
        row = self.db.expiry_alerts("30")[0]
        self.assertEqual((row["cert_serial"], row["custody"]), ("C-L", "Returned"))

    def test_inward_cert_conflict(self):
        inw = self.inward(token="CF", cert={"cert_serial": "A", "expiry_date": iso(10)})
        self.db.save_outward({"inward_id": inw, "outward_date": iso(0), "returned_to": "X", "returned_by": "Y"})
        with self.assertRaises(CertificateConflict):
            self.inward(token="CF", inward_date=iso(0), cert={"cert_serial": "B", "expiry_date": iso(400)})
        self.assertEqual(len(self.db.inward_register()), 1)       # rolled back
        self.db.save_inward({"client_id": self.cid, "inward_date": iso(0), "holder_name": "Test Holder",
                             "token_serial": "CF", "received_from": "X", "received_by": "Y", "purpose": "GST"},
                            cert={"cert_serial": "B", "expiry_date": iso(400)}, cert_action="renew")
        self.assertEqual(len(self.db.certificate_history(self.db.find_token("CF")["token_id"])), 2)


class PersistenceTests(Base):
    def test_11_backup_and_csv(self):
        self.inward()
        dest = self.db.backup_to(self.tmp)
        self.assertTrue(os.path.basename(dest).startswith("DSC_Backup_"))
        self.assertTrue(is_valid_database(dest))
        b = Database(dest)
        self.assertEqual(len(b.inward_register()), 1)
        b.close()
        out = os.path.join(self.tmp, "x.csv")
        write_csv(out, ["Inward Date", "Token"], [["22-10-2026", "TKN-1"]])
        with open(out, encoding="utf-8-sig", newline="") as fh:
            self.assertEqual(list(csv.reader(fh)), [["Inward Date", "Token"], ["22-10-2026", "TKN-1"]])

    def test_12_reopen_keeps_records(self):
        self.inward()
        self.db.close()
        self.db = Database(self.path)
        self.assertFalse(self.db.is_new)
        self.assertEqual(self.custody_tokens(), ["TKN-1"])

    def test_sample_data_load_and_remove(self):
        self.db.close()
        os.remove(self.path)
        self.db = Database(self.path)
        self.cid = self.db.add_client({"holder_name": "Test Holder", "pan": "AAAPT1234A", "mobile": "9000000008"})
        self.assertTrue(load_sample_data(self.db))
        self.assertTrue(self.db.has_sample_data())
        c = self.db.dashboard_counts()
        self.assertEqual((c["custody"], c["awaited"]), (17, 5))
        self.assertEqual(len(self.db.custody_register()), 17)   # superseded receipt counted once
        self.assertEqual((c["with_custodian"], c["with_staff"], c["with_consultant"]), (13, 2, 2))
        self.assertEqual((c["staff_overdue"], c["consultant_overdue"]), (1, 1))
        self.assertEqual(self.db.current_custodian()["name"], "Meera Kale (Sample)")
        self.db.remove_sample_data()
        self.assertFalse(self.db.has_sample_data())
        self.assertEqual(len(self.db.list_clients()), 1)
        self.assertIsNone(self.db.current_custodian())   # sample custodians removed too


class CustodianTests(Base):
    def test_inward_needs_custodian_and_goes_to_custodian(self):
        inw = self.inward()
        row = self.db.custody_register()[0]
        self.assertEqual((row["with_type"], row["with_name"]), ("custodian", "Cust A"))
        self.assertEqual(self.db.inward_register()[0]["received_by"], "Cust A")
        fresh = Database(os.path.join(self.tmp, "fresh.db"))
        cid = fresh.add_client({"holder_name": "X", "pan": "XXXPX1234X", "mobile": "9000000009"})
        with self.assertRaises(ValidationError):
            fresh.save_inward({"client_id": cid, "inward_date": iso(0), "holder_name": "X", "token_serial": "Z",
                               "received_from": "X", "purpose": "GST"})
        fresh.close()
        self.assertTrue(inw)

    def test_one_custodian_and_handover(self):
        a = self.inward(token="A")
        b = self.inward(token="B")
        self.db.issue_to_staff(b, "Staff S")
        old = self.db.current_custodian()
        self.db.appoint_custodian("Cust B")
        self.assertEqual(self.db.current_custodian()["name"], "Cust B")
        hist = {c["name"]: c for c in self.db.list_custodians()}
        self.assertIsNotNone(hist["Cust A"]["relieved_at"])
        self.assertEqual(sum(1 for c in self.db.list_custodians() if c["relieved_at"] is None), 1)
        handovers = self.db.movement_register({"kind": "handover"})
        self.assertEqual([h["token_serial"] for h in handovers], ["A"])      # B is with staff, not handed over
        self.assertEqual((handovers[0]["from_name"], handovers[0]["to_name"]), (old["name"], "Cust B"))
        self.db.return_from_staff(b)
        rows = {r["token_serial"]: r for r in self.db.custody_register()}
        self.assertEqual(rows["B"]["with_name"], "Cust B")                  # returns to the new custodian
        self.assertEqual(rows["A"]["with_name"], "Cust B")
        with self.assertRaises(ValidationError):
            self.db.appoint_custodian("cust b")                              # already in office
        self.assertTrue(a)
        with self.assertRaises(sqlite3.IntegrityError):                      # the database allows only one
            with self.db.conn:
                self.db.conn.execute("INSERT INTO custodians (name, appointed_at) VALUES ('X', '2026-01-01')")


class MovementTests(Base):
    def holder(self):
        r = self.db.custody_register()[0]
        return r["with_type"], r["with_name"]

    def test_staff_issue_and_return_with_system_time(self):
        inw = self.inward()
        before = dates.now()
        self.db.issue_to_staff(inw, "Staff S", "ITR Filing")
        self.assertEqual(self.holder(), ("staff", "Staff S"))
        m = self.db.movement_register()[0]
        moved = dates.iso_to_datetime(m["moved_at"])
        self.assertTrue(before <= moved <= dates.now())                      # stamped from the system clock
        self.assertEqual(m["expected_return"], f"{m['moved_at'][:10]} 23:59:00")   # default: end of the day
        self.db.return_from_staff(inw)
        self.assertEqual(self.holder(), ("custodian", "Cust A"))

    def test_no_staff_to_staff_and_everything_through_custodian(self):
        inw = self.inward()
        cs = self.db.add_consultant({"name": "CS One", "kind": "CS"})
        self.db.issue_to_staff(inw, "Staff S")
        with self.assertRaises(ValidationError) as cm:
            self.db.issue_to_staff(inw, "Staff T")
        self.assertIn("Staff-to-staff", str(cm.exception))
        with self.assertRaises(ValidationError):
            self.db.hand_to_consultant(inw, cs)
        with self.assertRaises(ValidationError):                             # outward only from the custodian
            self.db.save_outward({"inward_id": inw, "outward_date": iso(0), "returned_to": "X"})
        with self.assertRaises(ValidationError):
            self.db.return_from_consultant(inw)
        self.db.return_from_staff(inw)
        self.db.hand_to_consultant(inw, cs, "ROC Filing")
        self.assertEqual(self.holder(), ("consultant", "CS One"))
        with self.assertRaises(ValidationError):
            self.db.issue_to_staff(inw, "Staff S")
        with self.assertRaises(ValidationError):
            self.db.cancel_inward(inw, "x")
        self.db.return_from_consultant(inw)
        self.db.save_outward({"inward_id": inw, "outward_date": iso(0), "returned_to": "Test Holder"})
        self.assertEqual(self.db.outward_register()[0]["returned_by"], "Cust A")
        self.assertEqual(self.db.custody_register(), [])

    def test_client_collected_from_consultant(self):
        inw = self.inward()
        cs = self.db.add_consultant({"name": "CS One", "kind": "CS"})
        self.db.hand_to_consultant(inw, cs, "ROC Filing")
        self.db.client_collected_from_consultant(inw, "Test Holder", "collected at CS office")
        self.assertEqual(self.db.custody_register(), [])                     # custody ended
        out = self.db.outward_register()[0]
        self.assertEqual((out["returned_by"], out["returned_to"], out["returned_via"]),
                         ("CS One", "Test Holder", "Collected from consultant"))
        kinds = [m["kind"] for m in self.db.movement_register()]
        self.assertEqual(kinds, ["client_collected", "to_consultant"])
        events = [e["event"] for e in self.db.token_history(self.db.find_token("TKN-1")["token_id"])]
        self.assertEqual(events, ["Inward (received from client)", "Handed to consultant",
                                  "Client collected from consultant"])
        # Cancelling that outward puts the token back with the consultant.
        self.db.cancel_outward(out["outward_id"], "wrong token")
        self.assertEqual(self.holder(), ("consultant", "CS One"))

    def test_cancel_only_latest_movement(self):
        inw = self.inward()
        first = self.db.issue_to_staff(inw, "Staff S")
        self.db.return_from_staff(inw)
        with self.assertRaises(ValidationError):
            self.db.cancel_movement(first, "x")
        last = self.db.custody_register()[0]["with_movement_id"]
        self.db.cancel_movement(last, "returned by mistake")
        self.assertEqual(self.holder(), ("staff", "Staff S"))
        self.assertEqual(len(self.db.movement_register({"include_cancelled": True})), 2)
        self.assertEqual(len(self.db.movement_register()), 1)

    def test_overdue_back_to_custodian(self):
        inw = self.inward()
        self.db.issue_to_staff(inw, "Staff S", expected_return=dates.now_iso())
        later = (dates.now() + timedelta(minutes=5)).strftime(dates.ISO_DT_FORMAT)
        row = self.db.custody_register(as_of=later)[0]
        self.assertTrue(row["internal_overdue"])
        self.assertEqual(self.db.dashboard_counts(as_of=later)["staff_overdue"], 1)
        self.assertEqual(len(self.db.custody_register({"holder": "internal_overdue"}, as_of=later)), 1)


class MigrationTests(unittest.TestCase):
    def test_old_database_is_upgraded(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "old.db")
        db = Database(path)
        db.close()
        conn = sqlite3.connect(path)           # make it look like a first-release file
        conn.execute("ALTER TABLE certificates DROP COLUMN issuer")
        conn.execute("ALTER TABLE outward DROP COLUMN collected_by")
        conn.execute("DROP TABLE movements")
        conn.commit()
        conn.close()
        db = Database(path)
        cols = {r[1] for r in db.conn.execute("PRAGMA table_info(certificates)")}
        self.assertIn("issuer", cols)
        self.assertIn("collected_by", {r[1] for r in db.conn.execute("PRAGMA table_info(outward)")})
        self.assertTrue(db._scalar("SELECT COUNT(*) FROM sqlite_master WHERE name = 'movements'"))
        db.close()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------- token reading
def _der(tag, body):
    n = len(body)
    length = bytes([n]) if n < 128 else bytes([0x80 | ((n.bit_length() + 7) // 8)]) + n.to_bytes(
        (n.bit_length() + 7) // 8, "big")
    return bytes([tag]) + length + body


def _seq(*parts):
    return _der(0x30, b"".join(parts))


def _name(cn, org=None):
    rdns = [_der(0x31, _seq(_der(0x06, bytes.fromhex("550403")), _der(0x0C, cn.encode())))]
    if org:
        rdns.append(_der(0x31, _seq(_der(0x06, bytes.fromhex("55040a")), _der(0x0C, org.encode()))))
    return _seq(*rdns)


INDIAN_CLASS3_POLICY = bytes.fromhex("608264640203")   # 2.16.356.100.2.3 (CCA India, Class 3)


def make_cert(cn, issuer_org, not_before, not_after, serial=0x1A2B3C, policy=INDIAN_CLASS3_POLICY):
    """A minimal (unsigned) end-entity X.509 certificate, enough for the parser."""
    alg = _seq(_der(0x06, bytes.fromhex("2a864886f70d01010b")), _der(0x05, b""))
    validity = _seq(_der(0x17, not_before.strftime("%y%m%d%H%M%SZ").encode()),
                    _der(0x17, not_after.strftime("%y%m%d%H%M%SZ").encode()))
    parts = [_der(0xA0, _der(0x02, b"\x02")), _der(0x02, serial.to_bytes(4, "big")), alg,
             _name("Issuing CA", issuer_org), validity, _name(cn), _seq(alg, _der(0x03, b"\x00\x01"))]
    if policy:   # certificatePolicies extension
        policies = _seq(_seq(_der(0x06, policy)))
        parts.append(_der(0xA3, _seq(_seq(_der(0x06, bytes.fromhex("551d20")), _der(0x04, policies)))))
    return _seq(_seq(*parts), alg, _der(0x03, b"\x00\x01"))


class TokenReaderTests(unittest.TestCase):
    def test_parse_certificate_times_in_local_time(self):
        nb = datetime(2024, 11, 9, 9, 42, 47, tzinfo=timezone.utc)
        na = datetime(2026, 11, 9, 9, 42, 47, tzinfo=timezone.utc)
        c = token_reader.parse_certificate(make_cert("Test Holder", "Sample CA Ltd", nb, na))
        self.assertEqual((c["holder_name"], c["issuer"], c["is_ca"]), ("Test Holder", "Sample CA Ltd", False))
        self.assertEqual(c["cert_serial"], "1A2B3C")
        local = na.astimezone().replace(tzinfo=None).strftime(dates.ISO_DT_FORMAT)
        self.assertEqual(c["expiry_date"], local)

    def test_indian_dsc_recognised_by_cca_policy(self):
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        dsc = token_reader.parse_certificate(make_cert("Sample Holder", "Capricorn", when, when))
        self.assertEqual(dsc["policies"], ["2.16.356.100.2.3"])
        self.assertTrue(dsc["is_indian_dsc"])
        other = token_reader.parse_certificate(make_cert("3bdd925f-1f1e", "MS-Organization-Access", when, when,
                                                         policy=None))
        self.assertFalse(other["is_indian_dsc"])

    def test_windows_store_fallback_offers_only_dsc_certificates(self):
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        store = [(make_cert("3bdd925f-1f1e", "MS-Organization-Access", when, when, serial=1, policy=None),
                  "x509_asn", True),
                 (make_cert("Adobe Content", "Adobe Systems", when, when, serial=2, policy=None), "x509_asn", True),
                 (make_cert("Sample Holder", "Capricorn", when, when, serial=3), "x509_asn", True)]
        with mock.patch.object(token_reader, "_pkcs11_module", return_value=None), \
                mock.patch.object(token_reader.ssl, "enum_certificates", return_value=store, create=True):
            result = token_reader.read_tokens()
        self.assertEqual([t["holder_name"] for t in result.tokens], ["Sample Holder"])
        self.assertEqual(result.method, "store")

    def test_missing_driver_points_to_the_tokens_own_installer(self):
        with mock.patch.object(token_reader, "_pkcs11_module", return_value=object()), \
                mock.patch.object(token_reader, "find_drivers", return_value=[]), \
                mock.patch.object(token_reader, "installer_hints", return_value=["F:\\HyperPKI_HYP2003_Setup.exe"]), \
                mock.patch.object(token_reader, "_read_store", lambda result: None):
            result = token_reader.read_tokens()
        self.assertEqual(result.tokens, [])
        self.assertTrue(any("HyperPKI_HYP2003_Setup.exe" in n for n in result.notes), result.notes)

    @unittest.skipUnless(hasattr(__import__("ssl"), "enum_certificates"), "Windows only")
    def test_parse_windows_root_certificates(self):
        import ssl
        roots = [der for der, enc, _ in ssl.enum_certificates("ROOT") if enc == "x509_asn"]
        parsed = [token_reader.parse_certificate(d) for d in roots]
        self.assertTrue(roots)
        self.assertTrue(all(p and p["expiry_date"] and p["is_ca"] for p in parsed))

    def test_read_tokens_from_simulated_pkcs11_driver(self):
        der = make_cert("Simulated Holder", "Sample CA Ltd",
                        datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, 5, 30, tzinfo=timezone.utc))

        class Info:
            serialNumber, label, manufacturerID = "  TOKEN0001  ", "My Token", "Fake Ltd"

        class Session:
            def findObjects(self, template):
                return ["cert"]

            def getAttributeValue(self, obj, attrs):
                return [list(der)]

            def closeSession(self):
                pass

        class Lib:
            def load(self, path):
                pass

            def getSlotList(self, tokenPresent=True):
                return [0]

            def getTokenInfo(self, slot):
                return Info()

            def openSession(self, slot):
                return Session()

        fake = type("FakePyKCS11", (), {"PyKCS11Lib": Lib, "CKA_CLASS": 0, "CKO_CERTIFICATE": 1, "CKA_VALUE": 17})
        tmp = tempfile.mkdtemp()
        dll = os.path.join(tmp, "fake_p11.dll")
        open(dll, "wb").close()
        with mock.patch.object(token_reader, "_pkcs11_module", return_value=fake):
            result = token_reader.read_tokens([dll])
        self.assertEqual(result.method, "pkcs11")
        self.assertEqual(len(result.tokens), 1)              # same token through several drivers counted once
        t = result.tokens[0]
        self.assertEqual((t["token_serial"], t["holder_name"], t["issuer"]),
                         ("TOKEN0001", "Simulated Holder", "Sample CA Ltd"))
        self.assertTrue(t["expiry_date"].startswith("2027-01-01"))
        shutil.rmtree(tmp, ignore_errors=True)

    def test_no_pkcs11_falls_back_without_crashing(self):
        with mock.patch.object(token_reader, "_pkcs11_module", return_value=None), \
                mock.patch.object(token_reader, "_read_store", lambda result: None):
            result = token_reader.read_tokens()
        self.assertEqual(result.tokens, [])
        self.assertTrue(any("PyKCS11" in n for n in result.notes))


class ClientRuleTests(Base):
    def test_pan_optional_mobile_required(self):
        a = self.db.add_client({"holder_name": "No Pan One", "mobile": "9111111111"})
        self.db.add_client({"holder_name": "No Pan Two", "mobile": "9111111112"})   # many blank PANs allowed
        self.assertIsNone(self.db.get_client(a)["pan"])
        self.assertEqual(sorted(c["holder_name"] for c in self.db.list_clients(status="PAN pending")),
                         ["No Pan One", "No Pan Two"])
        with self.assertRaises(ValidationError):
            self.db.add_client({"holder_name": "No Mobile", "pan": "DDDPD1234D"})
        self.db.update_client(a, {"holder_name": "No Pan One", "mobile": "9111111111", "pan": "EEEPE1234E"})
        self.assertEqual(self.db.get_client(a)["pan"], "EEEPE1234E")

    def test_same_mobile_only_with_a_different_name(self):
        self.db.add_client({"holder_name": "Rohit Agarwal", "mobile": "9832034567"})
        self.db.add_client({"holder_name": "Neha Agarwal", "mobile": "9832034567"})      # family member: allowed
        for same in ("rohit agarwal", "Rohit  Agarwal.", "ROHIT-AGARWAL"):
            with self.assertRaises(ValidationError):
                self.db.add_client({"holder_name": same, "mobile": "+91 98320 34567"})
        self.db.add_client({"holder_name": "Rohit Agarwal", "mobile": "9000099999"})      # other mobile: allowed
        cid = self.db.list_clients("Neha Agarwal")[0]["client_id"]
        self.db.update_client(cid, {"holder_name": "Neha Agarwal", "mobile": "9832034567", "remarks": "x"})

    def test_old_database_with_mandatory_pan_is_upgraded(self):
        from dsc_manager import database as dbm
        path = os.path.join(self.tmp, "pan_required.db")
        conn = sqlite3.connect(path)
        conn.executescript(dbm.SCHEMA.replace("pan         TEXT UNIQUE,", "pan         TEXT NOT NULL UNIQUE,"))
        conn.execute("INSERT INTO clients (client_code, holder_name, pan, mobile) VALUES ('CL0001', 'Old', "
                     "'OLDPX1234X', '9000000000')")
        conn.commit()
        conn.close()
        db = Database(path)
        notnull = {r[1]: r[3] for r in db.conn.execute("PRAGMA table_info(clients)")}
        self.assertEqual(notnull["pan"], 0)
        self.assertEqual(db.list_clients()[0]["pan"], "OLDPX1234X")
        db.add_client({"holder_name": "New", "mobile": "9000000001"})
        db.close()


class TokenStatusTests(Base):
    def test_lost_while_with_staff_ends_custody_and_leaves_alerts(self):
        inw = self.inward(token="LOST", cert={"cert_serial": "C1", "expiry_date": iso_t(3, "18:00")})
        self.db.issue_to_staff(inw, "Staff S")
        tid = self.db.find_token("LOST")["token_id"]
        self.db.set_token_inactive(tid, "Lost - at client office")
        self.assertEqual(self.db.custody_register(), [])
        out = self.db.outward_register()[0]
        self.assertEqual((out["returned_via"], out["returned_by"]), ("Token made inactive", "Staff S"))
        self.assertEqual(self.db.expiry_alerts("7"), [])
        self.assertEqual([r["token_serial"] for r in self.db.expiry_alerts("all")], ["LOST"])
        self.assertEqual(self.db.dashboard_counts()["exp_7"], 0)
        self.assertEqual(self.db.movement_register({"kind": "token_inactive"})[0]["from_name"], "Staff S")
        with self.assertRaises(ValidationError):
            self.db.cancel_outward(out["outward_id"], "x")
        events = [e["event"] for e in self.db.token_history(tid)]
        self.assertIn("Custody ended - token made inactive", events)
        self.assertIn("Token made Inactive", events)

    def test_inactive_token_received_again(self):
        inw = self.inward(token="BACK")
        self.db.save_outward({"inward_id": inw, "outward_date": iso(0), "returned_to": "Test Holder"})
        tid = self.db.find_token("BACK")["token_id"]
        self.db.set_token_inactive(tid, "Lost")
        with self.assertRaises(InactiveTokenError):
            self.inward(token="BACK", inward_date=iso(0))
        self.db.save_inward({"client_id": self.cid, "inward_date": iso(0), "holder_name": "Test Holder",
                             "token_serial": "BACK", "received_from": "Test Holder", "purpose": "GST"},
                            reactivate=True)
        self.assertEqual(self.db.get_token(tid)["status"], "Active")
        self.assertEqual(self.custody_tokens(), ["BACK"])
        statuses = [e["status"] for e in self.db.token_history(tid) if e["event"].startswith("Token made")]
        self.assertEqual(statuses, ["Inactive", "Active"])

    def test_new_token_replaces_old_one(self):
        inw = self.inward(token="OLD-T", cert={"cert_serial": "C-OLD", "expiry_date": iso(-5)})
        self.db.save_outward({"inward_id": inw, "outward_date": iso(0), "returned_to": "Test Holder"})
        old_id = self.db.find_token("OLD-T")["token_id"]
        other = self.db.add_client({"holder_name": "Someone Else", "mobile": "9555555555"})
        self.db.save_inward({"client_id": other, "inward_date": iso(0), "holder_name": "Someone Else",
                             "token_serial": "OTHER-T", "received_from": "X", "purpose": "GST"})
        with self.assertRaises(ValidationError):                        # must be the same client's token
            self.db.save_inward({"client_id": self.cid, "inward_date": iso(0), "holder_name": "Test Holder",
                                 "token_serial": "NEW-T", "received_from": "X", "purpose": "GST"},
                                replaces=[self.db.find_token("OTHER-T")["token_id"]])
        self.db.save_inward({"client_id": self.cid, "inward_date": iso(0), "holder_name": "Test Holder",
                             "token_serial": "NEW-T", "received_from": "X", "purpose": "GST"},
                            cert={"cert_serial": "C-NEW", "expiry_date": iso(700)}, replaces=[old_id])
        old = self.db.get_token(old_id)
        self.assertEqual(old["status"], "Inactive")
        self.assertIn("Replaced by new token NEW-T", old["inactive_reason"])
        self.assertEqual(old["replaced_by"], self.db.find_token("NEW-T")["token_id"])
        self.assertEqual(self.db.expiry_alerts("expired"), [])           # the old expired token left the alerts
        self.assertEqual([t["token_serial"] for t in self.db.tokens_for_client(self.cid, active_only=True)],
                         ["NEW-T"])

    def test_status_changes_need_a_reason(self):
        self.inward(token="R")
        tid = self.db.find_token("R")["token_id"]
        with self.assertRaises(ValidationError):
            self.db.set_token_inactive(tid, "")
        self.db.set_token_inactive(tid, "Damaged")
        with self.assertRaises(ValidationError):
            self.db.set_token_active(tid, " ")
        self.db.set_token_active(tid, "Found in office")
        self.assertEqual(self.db.get_token(tid)["status"], "Active")


class ClientImportTests(Base):
    def fill(self, rows):
        import openpyxl
        from dsc_manager import client_import
        path = os.path.join(self.tmp, "clients.xlsx")
        client_import.make_template(path)
        wb = openpyxl.load_workbook(path)
        ws = wb["Clients"]
        for r, values in enumerate(rows, start=2):
            for c, v in enumerate(values, start=1):
                ws.cell(row=r, column=c, value=v)
        wb.save(path)
        return client_import.read_rows(path)

    def test_template_round_trip(self):
        from dsc_manager import client_import
        self.assertEqual(self.fill([]), [])
        rows = self.fill([["Asha Patil", 9812345678, "Patil & Co", "", "", ""], [None] * 6,
                          ["Ravi Patil", "+91 98123 45679", "", "ABCPR1234K", "ravi@example.com", "note"]])
        self.assertEqual([r[0] for r in rows], [2, 4])                      # the empty row 3 is left out
        self.assertEqual(rows[0][1]["mobile"], "9812345678")                # a number cell comes back as text
        self.assertEqual(rows[1][1]["pan"], "ABCPR1234K")
        bad = os.path.join(self.tmp, "other.xlsx")
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.title = "Sheet1"
        wb.save(bad)
        with self.assertRaises(client_import.TemplateError):
            client_import.read_rows(bad)

    def test_import_rules(self):
        rows = self.fill([
            ["", "9811111111", "", "", "", ""],                                  # 2 no name
            ["No Mobile", "", "", "", "", ""],                                   # 3 no mobile
            ["Bad Mobile", "12345", "", "", "", ""],                             # 4 too short
            ["Bad Start", "5123456789", "", "", "", ""],                         # 5 not 6-9
            ["test  holder", "+91 98765 43210", "", "", "", ""],                # 6 already in app (name+mobile)
            ["Other Person", "9876543210", "", "", "", ""],                     # 7 same mobile, new name: import
            ["Asha Patil", "9822222222", "", "ZZZCZ1234Z", "bad-email", ""],    # 8 import, PAN+email dropped
            ["A. Patil", "9822222222", "", "", "", ""],                          # 9 different name: import
            ["Asha  Patil.", "09822222222", "", "", "", ""],                     # 10 duplicate of row 8
            ["Has Old Pan", "9833333333", "", "AAAPT1234A", "", ""],            # 11 PAN already in app
            ["Pan One", "9844444444", "", "PQRPS1234K", "", ""],                # 12 import
            ["Pan Two", "9855555555", "", "pqrps1234k", "", ""],                # 13 same PAN as row 12
        ])
        plan = {r["row"]: r for r in self.db.plan_client_import(rows)}
        self.assertEqual({n for n, r in plan.items() if r["action"] == "Import"}, {7, 8, 9, 12})
        self.assertIn("missing", plan[2]["reason"])
        self.assertIn("missing", plan[3]["reason"])
        self.assertIn("not valid", plan[4]["reason"])
        self.assertIn("not valid", plan[5]["reason"])
        self.assertIn("Already in the app as CL", plan[6]["reason"])
        self.assertIn("row 8", plan[10]["reason"])
        self.assertIn("already belongs", plan[11]["reason"])
        self.assertIn("row 12", plan[13]["reason"])
        self.assertIn("without PAN", plan[8]["reason"])
        self.assertIn("without email", plan[8]["reason"])
        before = len(self.db.list_clients())
        self.assertEqual(self.db.apply_client_import(list(plan.values())), 4)
        self.assertEqual(len(self.db.list_clients()), before + 4)
        asha = self.db.list_clients("Asha Patil")[0]
        self.assertEqual((asha["pan"], asha["email"], asha["mobile"]), (None, "", "9822222222"))
        # importing the same file again adds nobody
        again = self.db.plan_client_import(rows)
        self.assertEqual([r for r in again if r["action"] == "Import"], [])

    def test_mobile_structure_in_client_form(self):
        for bad in ("5123456789", "98765", "98765432101"):
            with self.assertRaises(ValidationError):
                self.db.add_client({"holder_name": f"M {bad}", "mobile": bad})
        for good in ("+919812345671", "09812345672", "7812345673"):
            self.db.add_client({"holder_name": f"M {good}", "mobile": good})


class WhatsAppTests(Base):
    def test_messages_and_editable_wording(self):
        from dsc_manager import firm_info, whatsapp
        inw = self.inward(token="WA-1", purpose="ITR Filing")
        with mock.patch.object(firm_info, "FIRM_NAME", "ABC & Associates"):
            mobile, client, text = whatsapp.for_inward(self.db, inw)
            self.assertEqual(mobile, "9876543210")
            self.assertEqual(text, f"Dear Test Holder,\nWe have received your DSC token (WA-1) on "
                                   f"{dates.to_display(iso(-1))} for ITR Filing.\n\nABC & Associates")
            out = self.db.save_outward({"inward_id": inw, "outward_date": iso(0), "returned_to": "Test Holder"})
            self.assertIn("has been returned to Test Holder", whatsapp.for_outward(self.db, out)[2])
            whatsapp.set_template(self.db, "inward", "Hello {name}, token {token} received. {unknown}\n\n{firm}")
            self.assertEqual(whatsapp.for_inward(self.db, inw)[2],
                             "Hello Test Holder, token WA-1 received. {unknown}\n\nABC & Associates")
            whatsapp.set_template(self.db, "inward", "")                       # empty = back to the default
            self.assertTrue(whatsapp.get_template(self.db, "inward").startswith("Dear {name}"))
        # without a firm name (running from source) the signature line is simply left out
        self.assertTrue(whatsapp.for_inward(self.db, inw)[2].endswith("for ITR Filing."))
        self.assertEqual(whatsapp.chat_url("+91 98765 43210", "Hi there & bye", mode="desktop"),
                         "whatsapp://send?phone=919876543210&text=Hi%20there%20%26%20bye")
        self.assertEqual(whatsapp.chat_url("9876543210", "Hi", mode="web"),
                         "https://web.whatsapp.com/send?phone=919876543210&text=Hi")
        self.assertIsNone(whatsapp.chat_url("12345", "x"))
        with mock.patch.object(whatsapp.config, "get_setting", return_value="auto"), \
                mock.patch.object(whatsapp, "desktop_installed", return_value=False):
            self.assertEqual(whatsapp.current_mode(), "web")             # no Desktop app: WhatsApp Web
        with mock.patch.object(whatsapp.config, "get_setting", return_value="auto"), \
                mock.patch.object(whatsapp, "desktop_installed", return_value=True):
            self.assertEqual(whatsapp.current_mode(), "desktop")         # installed: straight into the app

    def test_collected_and_expiry_messages(self):
        from dsc_manager import whatsapp
        inw = self.inward(token="WA-2", cert={"cert_serial": "C", "expiry_date": iso_t(20, "15:12")})
        cs = self.db.add_consultant({"name": "CS One", "kind": "CS"})
        self.db.hand_to_consultant(inw, cs)
        out = self.db.client_collected_from_consultant(inw, "Test Holder")
        self.assertIn("collected by Test Holder from CS One", whatsapp.for_outward(self.db, out)[2])
        tid = self.db.find_token("WA-2")["token_id"]
        self.assertIn("expires on " + dates.to_display_dt(iso_t(20, "15:12")), whatsapp.for_expiry(self.db, tid)[2])


class SafetyTests(Base):
    def test_attention_summary(self):
        self.inward(token="E1", cert={"expiry_date": iso_t(3, "18:00")})
        texts = " | ".join(t for t, _, _ in self.db.attention_summary(as_of=NOON))
        self.assertIn("1 certificate(s) expire within 7 days", texts)
        self.assertIn("No backup", texts)
        self.db.backup_to(self.tmp)
        texts = " | ".join(t for t, _, _ in self.db.attention_summary(as_of=NOON))
        self.assertNotIn("backup", texts.lower())
        self.db.set_meta("last_backup_at", f"{iso(-9)} 10:00:00")
        self.assertIn("9 days ago", " | ".join(t for t, _, _ in self.db.attention_summary()))

    def test_auto_backup_one_per_day_keeps_last_30(self):
        folder = os.path.join(self.tmp, "auto")
        os.makedirs(folder)
        for day in range(1, 36):
            open(os.path.join(folder, f"DSC_AutoBackup_2026-01-{day:02d}.db" if day <= 31
                              else f"DSC_AutoBackup_2026-02-{day - 31:02d}.db"), "w").close()
        self.db.auto_backup(folder)
        self.db.auto_backup(folder)                                         # same day: same file, overwritten
        files = sorted(f for f in os.listdir(folder) if f.startswith("DSC_AutoBackup_"))
        self.assertEqual(len(files), 30)
        self.assertEqual(files[-1], f"DSC_AutoBackup_{dates.today_iso()}.db")
        self.assertTrue(is_valid_database(os.path.join(folder, files[-1])))
        self.assertEqual(self.db.days_since_backup(), 0)

    def test_single_user_lock(self):
        from dsc_manager import single_user
        first = single_user.acquire(self.path)
        self.assertIsNotNone(first)
        self.assertIsNone(single_user.acquire(self.path))                   # a second copy is refused
        single_user.release(first, self.path)
        again = single_user.acquire(self.path)
        self.assertIsNotNone(again)
        single_user.release(again, self.path)

    def test_excel_export_with_firm_heading(self):
        import openpyxl
        from dsc_manager.ui.widgets import write_xlsx
        path = os.path.join(self.tmp, "r.xlsx")
        write_xlsx(path, ["Token", "Days"], [["T1", 5], ["T2", 7]],
                   preamble=[["ABC & Associates"], ["Pune"], ["Custody Register"], ["Generated on x"], []])
        ws = openpyxl.load_workbook(path).active
        self.assertEqual([ws.cell(row=r, column=1).value for r in range(1, 9)],
                         ["ABC & Associates", "Pune", "Custody Register", "Generated on x", None, "Token", "T1", "T2"])
        self.assertEqual(ws.cell(row=7, column=2).value, 5)                  # numbers stay numbers
        self.assertEqual(ws.auto_filter.ref, "A6:B8")


class DashboardHelperTests(Base):
    def test_today_summary(self):
        a = self.inward(token="T-TODAY", inward_date=iso(0), cert={"expiry_date": iso_t(0, "23:59")})
        b = self.inward(token="T-OLD", inward_date=iso(-3))
        self.db.save_outward({"inward_id": b, "outward_date": iso(0), "returned_to": "Test Holder"})
        self.db.issue_to_staff(a, "Staff S")                                 # due back by end of today
        self.db.add_expected({"client_id": self.cid, "purpose": "GST", "expected_date": iso(0)})
        t = self.db.today_summary(as_of=f"{iso(0)} 09:00:00")
        self.assertEqual(t, {"received": 1, "returned": 1, "due_back": 1, "expiring": 1, "awaited": 1})

    def test_search_index_finds_clients_and_tokens(self):
        self.inward(token="EP2003-777")
        items = self.db.search_index()
        find = lambda q: [i["kind"] for i in items if q.lower() in f"{i['label']} {i['text']}".lower()]  # noqa
        self.assertIn("client", find("9876543210"))          # mobile
        self.assertIn("client", find("AAAPT1234A"))          # PAN
        self.assertEqual(find("EP2003-777"), ["token"])      # token serial
        self.assertIn("token", find("Test Holder"))          # holder name finds the token too


class CorrectionTests(Base):
    """Correct Entry: inward and outward details fixed with a reason, old values kept."""

    def test_correct_inward_keeps_old_values_and_shows_in_history(self):
        inw = self.inward(token="CR-1", inward_date=iso(-5), purpose="Tax Audit")
        changes = self.db.correct_inward(inw, {"inward_date": iso(-4), "purpose": "ITR Filing",
                                               "received_from": "Driver Ramesh"}, "Typed wrong")
        self.assertEqual(changes, [f"Inward Date: {dates.to_display(iso(-5))} -> {dates.to_display(iso(-4))}",
                                   "Received From: Test Holder -> Driver Ramesh", "Purpose: Tax Audit -> ITR Filing"])
        row = next(r for r in self.db.inward_register() if r["inward_id"] == inw)
        self.assertEqual((row["inward_date"], row["purpose"], row["received_from"]), (iso(-4), "ITR Filing",
                                                                                      "Driver Ramesh"))
        self.assertEqual(row["custody"], "In Custody (corrected)")
        self.assertEqual(len(self.db.corrections_for("inward", inw)), 3)
        tid = self.db.find_token("CR-1")["token_id"]
        line = next(e for e in self.db.token_history(tid) if e["event"] == f"Inward #{inw} corrected")
        self.assertIn("Purpose: Tax Audit -> ITR Filing", line["details"])
        self.assertIn("Reason: Typed wrong", line["details"])
        self.assertEqual(self.custody_tokens(), ["CR-1"])              # custody itself is unchanged

    def test_inward_correction_rules(self):
        inw = self.inward(token="CR-2", inward_date=iso(-5))
        with self.assertRaisesRegex(ValidationError, "reason"):
            self.db.correct_inward(inw, {"purpose": "ITR Filing"}, "  ")
        with self.assertRaisesRegex(ValidationError, "Nothing was changed"):
            self.db.correct_inward(inw, {}, "No change")
        with self.assertRaisesRegex(ValidationError, "future"):
            self.db.correct_inward(inw, {"inward_date": iso(1)}, "x")
        with self.assertRaisesRegex(ValidationError, "Expected Return Date"):
            self.db.correct_inward(inw, {"expected_return_date": iso(-6)}, "x")
        with self.assertRaisesRegex(ValidationError, "Purpose"):
            self.db.correct_inward(inw, {"purpose": "Something else"}, "x")
        self.db.issue_to_staff(inw, "Staff B", at=f"{iso(-3)} 10:00:00")
        with self.assertRaisesRegex(ValidationError, "first handed over"):
            self.db.correct_inward(inw, {"inward_date": iso(-2)}, "x")
        self.db.return_from_staff(inw, at=f"{iso(-3)} 12:00:00")
        out = self.db.save_outward({"inward_id": inw, "outward_date": iso(-1), "returned_to": "Test Holder"})
        self.db.cancel_outward(out, "Wrong token")
        self.db.cancel_inward(inw, "Duplicate")
        with self.assertRaisesRegex(ValidationError, "cancelled entry"):
            self.db.correct_inward(inw, {"purpose": "ITR Filing"}, "x")

    def test_correct_outward(self):
        inw = self.inward(token="CR-3", inward_date=iso(-5))
        out = self.db.save_outward({"inward_id": inw, "outward_date": iso(-1), "returned_to": "Wrong Name"})
        changes = self.db.correct_outward(out, {"returned_to": "Test Holder", "outward_date": iso(-2)}, "Spelling")
        self.assertEqual(len(changes), 2)
        row = next(r for r in self.db.outward_register() if r["outward_id"] == out)
        self.assertEqual((row["returned_to"], row["outward_date"]), ("Test Holder", iso(-2)))
        self.assertEqual((row["status"], row["status_text"]), ("Active", "Active (corrected)"))
        with self.assertRaisesRegex(ValidationError, "before the Inward Date"):
            self.db.correct_outward(out, {"outward_date": iso(-6)}, "x")
        with self.assertRaisesRegex(ValidationError, "Returned To"):
            self.db.correct_outward(out, {"returned_to": ""}, "x")
        self.db.cancel_outward(out, "Not returned after all")          # a corrected entry can still be cancelled
        self.assertEqual(self.custody_tokens(), ["CR-3"])

    def test_outward_date_fixed_when_collected_from_consultant(self):
        con = self.db.add_consultant({"name": "CS Mehta", "kind": "CS"})
        inw = self.inward(token="CR-4", inward_date=iso(-5))
        self.db.hand_to_consultant(inw, con, at=f"{iso(-4)} 10:00:00")
        self.db.client_collected_from_consultant(inw, "Test Holder", at=f"{iso(-3)} 10:00:00")
        out = self.db.outward_register()[0]
        with self.assertRaisesRegex(ValidationError, "system clock"):
            self.db.correct_outward(out["outward_id"], {"outward_date": iso(-2)}, "x")
        self.db.correct_outward(out["outward_id"], {"remarks": "Collected by son"}, "Detail added")


class RestoreTests(Base):
    def test_restore_brings_back_the_backup_and_keeps_a_safety_copy(self):
        from dsc_manager.database import backup_summary
        self.inward(token="RS-1")
        folder = os.path.join(self.tmp, "backups")
        os.makedirs(folder)
        backup = self.db.backup_to(folder)
        self.inward(token="RS-2")                                        # made after the backup
        self.assertEqual(sorted(self.custody_tokens()), ["RS-1", "RS-2"])
        summary = backup_summary(backup)
        self.assertEqual((summary["inward"], summary["clients"]), (1, 1))
        safety = self.db.restore_from(backup)
        self.db.close()
        self.db = Database(self.path)
        self.assertEqual(self.custody_tokens(), ["RS-1"])
        self.assertTrue(os.path.basename(safety).startswith("DSC_BeforeRestore_"))
        self.assertEqual(os.path.dirname(safety), self.tmp)
        undo = Database(safety)                                           # the safety copy has the later entry
        self.assertEqual(sorted(r["token_serial"] for r in undo.custody_register()), ["RS-1", "RS-2"])
        undo.close()

    def test_restore_refuses_wrong_files(self):
        with self.assertRaisesRegex(ValidationError, "in use"):
            self.db.restore_from(self.path)
        junk = os.path.join(self.tmp, "junk.db")
        with open(junk, "w") as fh:
            fh.write("not a database")
        with self.assertRaisesRegex(ValidationError, "not a DSC Management Tool backup"):
            self.db.restore_from(junk)
        self.assertEqual([f for f in os.listdir(self.tmp) if f.startswith("DSC_BeforeRestore_")], [])

    def test_restore_of_older_backup_is_upgraded(self):
        older = os.path.join(self.tmp, "older.db")
        self.db.backup_to(self.tmp, "older.db")
        conn = sqlite3.connect(older)
        conn.execute("DROP TABLE corrections")                          # as made before Correct Entry existed
        conn.commit()
        conn.close()
        self.db.restore_from(older)
        self.db.close()
        self.db = Database(self.path)
        inw = self.inward(token="RS-3")
        self.db.correct_inward(inw, {"remarks": "ok"}, "Works after restore")


class MovedFolderTests(unittest.TestCase):
    """The folder copied to another PC: dsc_config.json still names the old PC's path."""

    def setUp(self):
        from dsc_manager import config
        self.config = config
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.local = os.path.join(self.tmp, "data", config.DB_FILENAME)
        self.saved = os.path.join(self.tmp, "old_pc", "data", config.DB_FILENAME)
        for patch in (mock.patch.object(config, "DEFAULT_DB_PATH", self.local),
                      mock.patch.object(config, "CONFIG_PATH", os.path.join(self.tmp, "dsc_config.json")),
                      mock.patch.object(config, "env_db_path", return_value=None)):
            patch.start()
            self.addCleanup(patch.stop)
        config.save_config({"db_path": self.saved, "text_size": 11})

    def make_local_db(self):
        os.makedirs(os.path.dirname(self.local))
        open(self.local, "w").close()

    def choose(self, answer):
        from dsc_manager.ui import app
        with mock.patch.object(app.messagebox, "askyesno", return_value=answer) as asked, \
                mock.patch.object(app, "pick_folder", return_value="picked") as picked:
            return app.choose_db_path(None), asked, picked

    def test_database_next_to_the_app_is_offered_and_remembered(self):
        self.make_local_db()
        path, asked, picked = self.choose(True)
        self.assertEqual(path, self.local)
        self.assertIn(self.local, asked.call_args[0][1])
        picked.assert_not_called()
        self.assertEqual(self.config.load_config()["db_path"], self.local)
        self.assertEqual(self.config.get_setting("text_size"), 11)      # other settings are kept

    def test_answering_no_goes_to_the_folder_picker(self):
        self.make_local_db()
        path, _, picked = self.choose(False)
        self.assertEqual(path, "picked")
        picked.assert_called_once()
        self.assertEqual(self.config.load_config()["db_path"], self.saved)

    def test_no_database_next_to_the_app_warns_and_picks(self):
        from dsc_manager.ui import app
        with mock.patch.object(app.messagebox, "showwarning") as warned:
            path, asked, _ = self.choose(True)
        self.assertEqual(path, "picked")
        warned.assert_called_once()
        asked.assert_not_called()

    def test_saved_folder_still_present_is_left_alone(self):
        self.make_local_db()
        os.makedirs(os.path.dirname(self.saved))
        self.assertIsNone(self.config.moved_db_path(self.saved))


class GoogleSheetTests(Base):
    """The reports sent to the partners' Google Sheet (dsc_manager/gsheet.py and its Apps Script)."""

    def test_masking(self):
        from dsc_manager import gsheet
        self.assertEqual(gsheet.mask_pan("abcpx1234f"), "ABCPX****F")
        self.assertEqual(gsheet.mask_pan(""), "")
        self.assertEqual(gsheet.mask_mobile("98765 43210"), "98XXXXXX10")
        self.assertEqual(gsheet.mask_mobile(None), "")

    def test_payload_has_every_report_and_no_full_pan_or_mobile(self):
        import json
        from dsc_manager import gsheet
        inw = self.inward(token="GS-1", inward_date=iso(-3))
        self.db.issue_to_staff(inw, "Staff B")
        p = gsheet.build_payload(self.db, "k1")
        self.assertEqual([t["name"] for t in p["tabs"]], [
            "DSC in Custody", "DSC Awaited", "Expiry Alerts", "Inward Register", "Outward Register",
            "Movement Register", "Holdings by Person", "Clients"])
        for t in p["tabs"] + [p["dashboard"]["out_now"], p["dashboard"]["expiring"]]:
            self.assertEqual(len(t["headings"]), len(t["kinds"]))
            self.assertEqual(len(t["rows"]), len(t["colors"]))
            self.assertTrue(all(len(r) == len(t["headings"]) for r in t["rows"]))
        text = json.dumps(p)
        self.assertNotIn("AAAPT1234A", text)
        self.assertNotIn("9876543210", text)
        clients = p["tabs"][-1]
        self.assertIn("AAAPT****A", clients["rows"][0])
        custody = p["tabs"][0]
        row = dict(zip(custody["headings"], custody["rows"][0]))
        self.assertEqual(row["Inward Date"], iso(-3))            # dates go as YYYY-MM-DD for the sheet
        self.assertEqual(row["Currently With"], "Staff: Staff B")
        self.assertEqual(p["key"], "k1")
        self.assertEqual(p["dashboard"]["holders"], [["Custodian", 0], ["Staff", 1], ["Consultants", 0]])
        self.assertEqual(len(p["dashboard"]["out_now"]["rows"]), 1)

    def test_link_key_and_script(self):
        from dsc_manager import gsheet
        with self.assertRaises(ValueError):
            gsheet.set_url(self.db, "https://example.com/exec")
        gsheet.set_url(self.db, " https://script.google.com/macros/s/abc/exec ")
        self.assertEqual(gsheet.get_url(self.db), "https://script.google.com/macros/s/abc/exec")
        key = gsheet.get_key(self.db)
        self.assertEqual(gsheet.get_key(self.db), key)              # made once, then kept
        script = gsheet.script_text(self.db)
        self.assertIn(f"var KEY = '{key}';", script)
        self.assertNotIn("PUT-KEY-HERE", script)
        gsheet.record_result(self.db, "no internet")
        self.assertIn("no internet", gsheet.status(self.db)["last_error"])
        gsheet.record_result(self.db)
        self.assertEqual(gsheet.status(self.db)["last_error"], "")
        self.assertTrue(gsheet.status(self.db)["last_ok"])

    def test_post_follows_google_redirect_and_reports_problems(self):
        import json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from dsc_manager import gsheet
        received = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):   # like Google: run the script, then redirect to its reply
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(302)
                self.send_header("Location", "/reply?" + self.path.strip("/"))
                self.end_headers()

            def do_GET(self):
                body = {"reply?ok": b'{"ok": true, "tabs": 9}', "reply?bad": b'{"ok": false, "error": "Wrong key"}',
                        "reply?html": b"<html>Sign in</html>"}[self.path.strip("/")]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}/"
        try:
            self.assertEqual(gsheet.post(base + "ok", {"key": "k", "x": "₹"})["tabs"], 9)
            self.assertEqual(received[0], {"key": "k", "x": "₹"})
            with self.assertRaisesRegex(RuntimeError, "Wrong key"):
                gsheet.post(base + "bad", {})
            with self.assertRaisesRegex(RuntimeError, "did not answer like"):
                gsheet.post(base + "html", {})
        finally:
            server.shutdown()
            server.server_close()
        with self.assertRaisesRegex(RuntimeError, "Could not reach Google"):
            gsheet.post(base + "ok", {}, timeout=2)

    def test_sheet_script_with_node_mock(self):
        """Runs the Apps Script against a mock of Google Sheets (skipped when Node.js is not installed)."""
        import json
        import subprocess
        from dsc_manager import config, gsheet
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js not installed")
        sample = Database(os.path.join(self.tmp, "sample.db"))
        load_sample_data(sample)
        with open(os.path.join(self.tmp, "payload.json"), "w", encoding="utf-8") as fh:
            json.dump(gsheet.build_payload(sample, "secret"), fh)
        sample.close()
        out = subprocess.run([node, os.path.join(os.path.dirname(__file__), "sheet_script_mock.js"), self.tmp,
                              config.asset("google_sheet_script.gs")], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('run 2 {"ok":true,"tabs":9', out.stdout)
        self.assertIn('empty data: {"ok":true', out.stdout)
        self.assertIn('wrong key: {"ok":false', out.stdout)
        self.assertIn("tabs: Dashboard(1c 1p -) DSC in Custody(0c 1p F)", out.stdout)
        self.assertNotIn("Sheet1", out.stdout)


class FirmInfoTests(unittest.TestCase):
    def test_firm_name_and_address_on_title_and_reports(self):
        from dsc_manager import firm_info
        with mock.patch.object(firm_info, "FIRM_NAME", "ABC & Associates"), \
                mock.patch.object(firm_info, "FIRM_ADDRESS", "Office 101, Shivaji Nagar\nPune 411005"):
            self.assertEqual(firm_info.window_title(), "ABC & Associates - DSC Management Tool")
            self.assertEqual(firm_info.report_header("Inward Register"),
                             [["ABC & Associates"], ["Office 101, Shivaji Nagar"], ["Pune 411005"],
                              ["Inward Register"]])
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "r.csv")
        write_csv(out, ["Token"], [["T1"]], preamble=[["ABC & Associates"], ["Inward Register"], []])
        with open(out, encoding="utf-8-sig", newline="") as fh:
            self.assertEqual(list(csv.reader(fh)),
                             [["ABC & Associates"], ["Inward Register"], [], ["Token"], ["T1"]])
        shutil.rmtree(tmp, ignore_errors=True)

    def test_build_script_writes_firm_details(self):
        import build_exe
        with open(build_exe.FIRM_FILE, encoding="utf-8") as fh:
            original = fh.read()
        src = build_exe.firm_source(original, "ABC & Associates", "Office 101\nPune")
        ns = {}
        exec(compile(src, "firm_info", "exec"), ns)
        self.assertEqual((ns["FIRM_NAME"], ns["FIRM_ADDRESS"]), ("ABC & Associates", "Office 101\nPune"))
        self.assertEqual(ns["window_title"](), "ABC & Associates - DSC Management Tool")


class DateTests(unittest.TestCase):
    def test_parse_and_display(self):
        self.assertEqual(dates.parse_display("05-03-2026"), "2026-03-05")
        self.assertEqual(dates.parse_display("5/3/2026"), "2026-03-05")
        self.assertEqual(dates.parse_display("05032026"), "2026-03-05")         # typed without dashes
        self.assertEqual(dates.parse_display("050326"), "2026-03-05")
        self.assertEqual(dates.parse_display("5-3-26"), "2026-03-05")
        self.assertEqual(dates.to_display("2026-03-05"), "05-03-2026")
        self.assertIsNone(dates.parse_display(""))
        for bad in ("31-02-2026", "2026-03-05", "abc"):
            with self.assertRaises(ValueError):
                dates.parse_display(bad)


if __name__ == "__main__":
    unittest.main()
