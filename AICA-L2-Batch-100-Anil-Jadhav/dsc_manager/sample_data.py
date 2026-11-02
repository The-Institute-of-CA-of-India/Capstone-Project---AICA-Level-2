"""Demonstration data. Every row is flagged is_sample = 1, every holder,
custodian and consultant name ends with "(Sample)" and every token/certificate
number starts with "SMPL-", so it can never be mistaken for real data.
Sample data can be removed from the Backup Database screen.

All dates are relative to now, so the dashboard always shows a realistic mix:
overdue returns, expired / expiring certificates (with and without a time of
day), unknown expiry dates, renewals, a superseded duplicate receipt,
cancelled entries, awaited DSCs, a custodian change with hand-over, tokens
issued to staff (one overdue), tokens with Company Secretaries and a token
the client collected from the CS directly.
"""
from datetime import datetime, time, timedelta

from . import dates

SAMPLE_REMARK = "SAMPLE DATA - for demonstration only"
STAFF = ["Priya Kulkarni", "Amit Deshpande", "Sneha Patil", "Rahul Verma", "Kiran Joshi"]
ISSUERS = ["Capricorn Identity Services Pvt Ltd.", "eMudhra Limited", "(n)Code Solutions", "Pantasign"]

# (holder, firm, mobile). Every client is an individual DSC holder (PAN 4th character 'P');
# two of them have no PAN yet ("PAN pending").
PAN_PENDING = {8, 11}
CLIENTS = [
    ("Rajesh Sharma", "Sharma Traders", "9820012345"),
    ("Meena Iyer", "Iyer Textiles Pvt Ltd", "9821023456"),
    ("Suresh Gupta", "Gupta & Sons LLP", "9822034567"),
    ("Anita Joshi", "Joshi Pharma Ltd", "9823045678"),
    ("Vikram Rao", "Rao Infra Pvt Ltd", "9824056789"),
    ("Kavita Nair", "Nair Exports", "9825067890"),
    ("Arjun Mehta", "Mehta Auto Components Pvt Ltd", "9826078901"),
    ("Pooja Reddy", "Reddy Foods LLP", "9827089012"),
    ("Sanjay Kulkarni", "", "9828090123"),
    ("Fatima Shaikh", "Shaikh Garments", "9829001234"),
    ("Harpreet Singh", "Singh Logistics Pvt Ltd", "9830012345"),
    ("Deepa Menon", "", "9831023456"),
    ("Rohit Agarwal", "Agarwal Steel Industries Ltd", "9832034567"),
    ("Neha Bansal", "Bansal Jewellers", "9832034567"),          # same mobile as Rohit Agarwal (family)
    ("Manoj Pillai", "Pillai Software Solutions Pvt Ltd", "9834056789"),
    ("Lakshmi Krishnan", "Krishnan Charitable Trust", "9835067890"),
    ("Imran Khan", "Khan Builders & Developers", "9836078901"),
    ("Gopal Das", "Das Cold Storage", "9837089012"),
]

# Token receipts:
# (key, client index, holder (None = client), expiry offset in days (None = unknown),
#  expiry time (None = not recorded), inward offset, purpose, expected-return offset,
#  outward offset (None = still in custody))
RECEIPTS = [
    ("T01", 0, None, -10, "15:12", -40, "Tax Audit", -5, None),
    ("T02", 1, None, 0, "23:30", -12, "Statutory Audit", 2, None),
    ("T03", 1, "Ravi Iyer", 45, "11:05", -12, "ROC Filing", 2, None),
    ("T04", 2, None, 5, "10:20", -8, "ITR Filing", 10, None),
    ("T05", 3, None, 12, "16:40", -20, "GST", -1, None),
    ("T06", 4, None, 25, "12:00", -3, "ROC Filing", 20, None),
    ("T07", 5, None, None, None, -2, "Bank Audit", 15, None),
    ("T08", 0, None, 400, "09:45", -60, "ITR Filing", -30, -35),
    ("T09", 6, None, 3, "18:15", -15, "Tax Audit", 5, None),
    ("T10", 6, "Nisha Mehta", 160, "14:30", -15, "ROC Filing", 5, None),
    ("T11", 7, None, -40, "13:00", -70, "GST", -55, -50),
    ("T12", 8, None, 200, "10:00", -25, "ITR Filing", -10, None),
    ("T13", 9, None, 9, None, -6, "GST", 1, None),
    ("T14", 10, None, 28, "17:20", -45, "Statutory Audit", -25, -20),
    ("T16", 12, None, -30, "12:30", -90, "Statutory Audit", -80, -80),
    ("T17", 12, "Sunita Agarwal", None, None, -10, "Tax Audit", 3, None),
    ("T18", 13, None, 60, "15:00", -30, "Bank Audit", -28, -28),
    ("T19", 14, None, 7, "11:00", -20, "ROC Filing", -12, None),
    ("T20", 15, None, -5, "16:00", -35, "Tax Audit", -15, -15),
    ("T21", 16, None, 20, None, -4, "GST", 10, None),
    ("T22", 17, None, -200, "10:10", -300, "Statutory Audit", -285, -280),
    ("T23", 3, "Prakash Joshi", 95, "13:45", -50, "Statutory Audit", -20, -22),
    ("T24", 4, "Asha Rao", 33, "09:30", -9, "Tax Audit", 6, None),
    ("T25", 10, "Gurpreet Kaur", 18, "17:00", -16, "ROC Filing", 4, None),
]

FOLLOWUPS = {
    "T01": "Certificate expired - client asked to apply for new DSC",
    "T02": "Expires today - inform client immediately",
    "T04": "Client informed by phone about renewal",
    "T05": "Renewal form sent to client by email",
    "T13": "Remind client after GST filing",
}


def _token(key):
    return f"SMPL-TKN-{1000 + int(key[1:])}"


def _cert(key, suffix=""):
    return f"SMPL-CERT-{5000 + int(key[1:])}{suffix}"


def load_sample_data(db):
    if db.has_sample_data():
        return False
    t = dates.today()
    now = dates.now()

    def d(offset):
        return (t + timedelta(days=offset)).isoformat()

    def at(days, hhmm):
        """A clock time on a day relative to today, never later than now."""
        h, m = (int(x) for x in hhmm.split(":"))
        when = datetime.combine(t + timedelta(days=days), time(h, m))
        return min(when, now).strftime(dates.ISO_DT_FORMAT)

    def ago(hours):
        return (now - timedelta(hours=hours)).strftime(dates.ISO_DT_FORMAT)

    for name in STAFF:
        db.add_staff(name)

    # The first custodian was in office before the earliest receipt.
    db.appoint_custodian("Suresh Bhosale (Sample)", SAMPLE_REMARK, at=at(-400, "10:00"), is_sample=1)
    neha = db.add_consultant({"name": "CS Neha Kapoor (Sample)", "firm": "Kapoor & Associates (Sample)",
                              "kind": "CS", "mobile": "9845012345", "email": "neha.cs@example.com",
                              "remarks": SAMPLE_REMARK}, is_sample=1)
    rahul = db.add_consultant({"name": "CS Rahul Mehta (Sample)", "firm": "Mehta Corporate Advisors (Sample)",
                               "kind": "CS", "mobile": "9845023456", "email": "rahul.cs@example.com",
                               "remarks": SAMPLE_REMARK}, is_sample=1)

    client_ids = []
    for i, (holder, firm, mobile) in enumerate(CLIENTS):
        pan = None if i in PAN_PENDING else f"SM{chr(65 + i)}P{holder.split()[-1][0]}{1001 + i}{chr(75 + i % 15)}"
        email = f"{holder.split()[0].lower()}@example.com"
        client_ids.append(db.add_client({
            "holder_name": f"{holder} (Sample)", "firm_name": f"{firm} (Sample)" if firm else "",
            "pan": pan, "mobile": mobile, "email": email, "remarks": SAMPLE_REMARK, "status": "Active",
        }, is_sample=1))

    # DSCs the firm is waiting for. Deepa Menon's request is fulfilled by her receipt below.
    def expect(ci, purpose, offset, staff, token=None, remarks=SAMPLE_REMARK):
        return db.add_expected({"client_id": client_ids[ci], "purpose": purpose, "expected_date": d(offset),
                                "followup_staff": staff, "token_serial": token, "remarks": remarks}, is_sample=1)

    deepa_request = expect(11, "ITR Filing", -3, "Sneha Patil")

    def cert_for(key, exp, hhmm, n):
        if exp is None:
            return {}
        expiry = f"{d(exp)} {hhmm}:00" if hhmm else d(exp)
        issue = f"{d(exp - 730)} {hhmm}:00" if hhmm else d(exp - 730)
        return {"cert_serial": _cert(key), "issue_date": issue, "expiry_date": expiry,
                "issuer": ISSUERS[n % len(ISSUERS)]}

    inward_ids = {}
    for n, (key, ci, holder, exp, hhmm, inw, purpose, ret, out) in enumerate(RECEIPTS):
        client = db.get_client(client_ids[ci])
        holder_name = f"{holder} (Sample)" if holder else client["holder_name"]
        inward_ids[key] = db.save_inward({
            "client_id": client_ids[ci], "inward_date": d(inw), "holder_name": holder_name,
            "token_serial": _token(key), "received_from": holder_name,
            "purpose": purpose, "expected_return_date": d(ret), "remarks": SAMPLE_REMARK,
        }, cert=cert_for(key, exp, hhmm, n), is_sample=1)
        if out is not None:
            db.save_outward({"inward_id": inward_ids[key], "outward_date": d(out), "returned_to": holder_name,
                             "remarks": SAMPLE_REMARK}, is_sample=1)

    def token_id(key):
        return db.find_token(_token(key))["token_id"]

    # Rohit Agarwal: certificate renewed (old one kept in history), token received again.
    db.save_certificate(token_id("T16"), {"cert_serial": _cert("T16", "-R"), "issue_date": f"{d(-35)} 12:30:00",
                                          "expiry_date": f"{d(695)} 12:30:00", "issuer": ISSUERS[1],
                                          "remarks": "Renewed - " + SAMPLE_REMARK}, action="renew")
    rohit = db.get_client(client_ids[12])
    db.save_inward({"client_id": client_ids[12], "inward_date": d(-10), "holder_name": rohit["holder_name"],
                    "token_serial": _token("T16"), "received_from": "Office staff of client",
                    "purpose": "Tax Audit", "expected_return_date": d(3), "remarks": SAMPLE_REMARK}, is_sample=1)

    # Manoj Pillai: token received again while already in custody -> earlier receipt superseded.
    manoj = db.get_client(client_ids[14])
    db.save_inward({"client_id": client_ids[14], "inward_date": d(-5), "holder_name": manoj["holder_name"],
                    "token_serial": _token("T19"), "received_from": manoj["holder_name"],
                    "purpose": "ROC Filing", "expected_return_date": d(2),
                    "remarks": "Received again for ROC filing - " + SAMPLE_REMARK},
                   allow_duplicate=True, is_sample=1)

    # Administrative certificate statuses and follow-up notes.
    def update_cert(key, **changes):
        tid = token_id(key)
        cur = db.get_current_certificate(tid)
        data = {k: cur[k] for k in ("cert_serial", "issue_date", "expiry_date", "issuer", "admin_status",
                                     "remarks", "followup")}
        data.update(changes)
        db.save_certificate(tid, data)

    update_cert("T09", admin_status="Renewal in Progress", followup="Renewal applied with CA - awaiting new token")
    update_cert("T20", admin_status="Revoked", followup="Revoked by certifying authority on client request")
    for key, note in FOLLOWUPS.items():
        update_cert(key, followup=note)

    # Corrections handled by cancellation (history kept, marked Cancelled).
    sanjay = db.get_client(client_ids[8])
    wrong = db.save_inward({"client_id": client_ids[8], "inward_date": d(-18), "holder_name": sanjay["holder_name"],
                            "token_serial": "SMPL-TKN-9999", "received_from": sanjay["holder_name"],
                            "purpose": "ITR Filing", "remarks": SAMPLE_REMARK}, is_sample=1)
    db.cancel_inward(wrong, "Wrong token number entered - re-entered correctly")
    mistaken = db.save_outward({"inward_id": inward_ids["T04"], "outward_date": d(-3),
                                "returned_to": "Suresh Gupta (Sample)", "remarks": SAMPLE_REMARK}, is_sample=1)
    db.cancel_outward(mistaken, "Entered by mistake - token is still with the firm")

    # Tokens with Company Secretaries (in time order).
    db.hand_to_consultant(inward_ids["T10"], neha, "ROC Filing", at(-1, "18:00"), SAMPLE_REMARK,
                          at=at(-6, "11:00"), is_sample=1)                      # overdue back
    db.hand_to_consultant(inward_ids["T25"], rahul, "ROC Filing", f"{d(3)} 18:00:00", SAMPLE_REMARK,
                          at=at(-5, "12:00"), is_sample=1)
    db.hand_to_consultant(inward_ids["T03"], neha, "ROC Filing", None, SAMPLE_REMARK,
                          at=at(-4, "10:30"), is_sample=1)
    db.client_collected_from_consultant(inward_ids["T03"], "Ravi Iyer (Sample)",
                                        "Collected from CS office after ROC filing", at=at(-3, "15:00"),
                                        is_sample=1)

    # The custodian changed two days ago: tokens with the custodian were handed over.
    db.appoint_custodian("Meera Kale (Sample)", "Took over from Suresh Bhosale - " + SAMPLE_REMARK,
                         at=at(-2, "10:00"), is_sample=1)

    deepa = db.get_client(client_ids[11])
    inward_ids["T15"] = db.save_inward({
        "client_id": client_ids[11], "inward_date": d(-1), "holder_name": deepa["holder_name"],
        "token_serial": _token("T15"), "received_from": deepa["holder_name"],
        "purpose": "ITR Filing", "expected_return_date": d(6), "remarks": SAMPLE_REMARK,
        "expected_id": deepa_request,
    }, cert={"cert_serial": _cert("T15"), "issue_date": f"{d(14 - 730)} 11:30:00",
             "expiry_date": f"{d(14)} 11:30:00", "issuer": ISSUERS[0]}, is_sample=1)

    # Staff issues: one returned, one overdue, one out today.
    db.issue_to_staff(inward_ids["T06"], "Amit Deshpande", "ROC Filing", at(-1, "18:00"), SAMPLE_REMARK,
                      at=at(-1, "10:00"), is_sample=1)                          # not back: overdue
    db.issue_to_staff(inward_ids["T12"], "Kiran Joshi", "ITR Filing", None, SAMPLE_REMARK,
                      at=at(-1, "11:00"), is_sample=1)
    db.return_from_staff(inward_ids["T12"], SAMPLE_REMARK, at=at(-1, "16:30"), is_sample=1)
    db.issue_to_staff(inward_ids["T04"], "Sneha Patil", "ITR Filing", f"{d(0)} 23:59:00", SAMPLE_REMARK,
                      at=ago(3), is_sample=1)

    # Pooja Reddy got a NEW token after her old one (T11) expired: T11 becomes Inactive (replaced).
    pooja = db.get_client(client_ids[7])
    db.save_inward({"client_id": client_ids[7], "inward_date": d(-1), "holder_name": pooja["holder_name"],
                    "token_serial": _token("T26"), "received_from": pooja["holder_name"], "purpose": "GST",
                    "expected_return_date": d(5), "remarks": SAMPLE_REMARK},
                   cert={"cert_serial": _cert("T26"), "issue_date": at(-2, "16:05"),
                         "expiry_date": f"{d(728)} 16:05:00", "issuer": ISSUERS[2]},
                   replaces=[token_id("T11")], is_sample=1)

    # Asha Rao's token was lost by a staff member: marked Inactive, which ends the firm's custody.
    db.issue_to_staff(inward_ids["T24"], "Kiran Joshi", "Tax Audit", None, SAMPLE_REMARK,
                      at=at(-1, "12:00"), is_sample=1)
    db.set_token_inactive(token_id("T24"), "Lost - misplaced at client office by Kiran Joshi; client informed, "
                                           "revocation requested with CA", at=at(-1, "17:30"), is_sample=1)

    # More awaited DSCs (two overdue, one cancelled).
    expect(3, "Tax Audit", 3, "Sneha Patil")
    expect(5, "ITR Filing", -2, "Amit Deshpande")
    expect(7, "GST", -6, "Kiran Joshi")
    expect(10, "Tax Audit", 7, "Priya Kulkarni")
    expect(16, "ROC Filing", 12, "Rahul Verma")
    cancelled = expect(9, "Tax Audit", 5, "Kiran Joshi")
    db.cancel_expected(cancelled, "Client will sign the return personally")

    # Gopal Das has closed his business: history kept, client marked Inactive.
    db.set_client_status(client_ids[17], "Inactive")
    return True
