"""GUI smoke test: opens the real Tkinter window against a temporary database,
visits every screen and drives the main workflows through the screens:
read from token -> inward -> issue to staff / return -> outward, plus exports
and backup. Message boxes are auto-answered and the token is simulated.
Run:  python tests/smoke_gui.py
"""
import os
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp()
os.environ["DSC_MANAGER_DB"] = os.path.join(tmp, "smoke.db")
os.environ["DSC_MANAGER_CONFIG"] = os.path.join(tmp, "smoke_config.json")   # never touch the real settings

shown = []
messagebox.showinfo = lambda *a, **k: shown.append(("info", a[:2]))
messagebox.showerror = lambda *a, **k: shown.append(("error", a[:2]))
messagebox.showwarning = lambda *a, **k: shown.append(("warn", a[:2]))
messagebox.askyesno = lambda *a, **k: True
messagebox.askyesnocancel = lambda *a, **k: True
filedialog.asksaveasfilename = lambda **k: os.path.join(tmp, k.get("initialfile", "out.csv"))
filedialog.askdirectory = lambda **k: tmp
import webbrowser  # noqa: E402
opened = []        # WhatsApp links the app would open
webbrowser.open = lambda url, *a, **k: opened.append(url)

from dsc_manager import dates, token_reader  # noqa: E402
from dsc_manager.sample_data import load_sample_data  # noqa: E402
from dsc_manager.ui.app import SCREENS, App  # noqa: E402


def errors():
    return [s for s in shown if s[0] == "error"]


# A simulated DSC token, so the test does not depend on what is plugged in.
fake = token_reader.TokenReadResult()
fake.method = "pkcs11"
fake.tokens = [{"token_serial": "SMOKE-TOKEN-1", "holder_name": "Smoke Holder", "cert_serial": "ABC123",
                "issuer": "Sample CA", "issue_date": "2025-01-01 11:00:00", "expiry_date": "2027-01-01 11:00:00",
                "token_label": "", "manufacturer": "", "driver": "Simulated", "driver_path": "",
                "source": "Token (PKCS#11)"}]
token_reader.read_tokens = lambda extra=(): fake

app = App()
load_sample_data(app.db)
for name in SCREENS:
    app.show(name)
    app.update()
for flt in ("7", "15", "30", "expired", "unknown", "renewal", "all"):
    app.show("alerts", flt=flt)
for holder in ("custodian", "staff", "consultant", "internal_overdue"):
    app.show("custody", view="custody", holder=holder)
app.show("custody", view="awaited")
app.update()

before = app.db.dashboard_counts()["custody"]
# --- Inward through the form, details read from the (simulated) token
scr = app.show("inward")
cid = app.db.add_client({"holder_name": "Smoke Holder", "pan": "ZZZPS9999Z", "mobile": "9000000001"})
scr.on_show()
scr._read_token()
assert scr.client.get_id() == cid, "client not matched from token holder name"
assert scr.token.get() == "SMOKE-TOKEN-1"
scr.purpose.set("ITR Filing")
scr._save()
assert not errors(), errors()
assert app.db.dashboard_counts()["custody"] == before + 1
assert opened and "phone=919000000001&text=Dear%20Smoke%20Holder" in opened[-1], opened
tok = app.db.find_token("SMOKE-TOKEN-1")
cert = app.db.get_current_certificate(tok["token_id"])
assert cert["expiry_date"] == "2027-01-01 11:00:00", cert
assert app.screens["dashboard"].cards["custody"].value.cget("text") == str(before + 1), "dashboard not refreshed"
inward_id = app.db.custody_register({"search": "Smoke Holder"})[0]["inward_id"]

# --- Movements: issue to staff (data layer), return through the screen
app.db.issue_to_staff(inward_id, "Smoke Staff")
mv = app.show("custody", inward_id=inward_id)
assert mv.action_table.selected()["with_type"] == "staff"
assert "disabled" not in mv.buttons["return_staff"].state()
assert "disabled" in mv.buttons["issue"].state()          # no staff-to-staff
out = app.show("outward", inward_id=inward_id)            # not with custodian -> refused
assert out.selected is None and errors(), "outward should refuse a token that is with staff"
shown.clear()
mv = app.show("custody", inward_id=inward_id)
mv._return_staff()
assert not errors(), errors()
assert app.menu_buttons["custody"].cget("text").startswith("5.  DSC in Custody"), app.menu_buttons["custody"].cget("text")
assert "movements" not in app.menu_buttons, "Movements is still in the menu"
assert app.db.custody_register({"search": "Smoke Holder"})[0]["with_type"] == "custodian"

# --- Outward through the form
out = app.show("outward", inward_id=inward_id)
assert out.selected and out.selected["inward_id"] == inward_id
out._save()
assert not errors(), errors()
assert app.db.dashboard_counts()["custody"] == before
assert "has%20been%20returned" in opened[-1], opened[-1]
n_links = len(opened)
out.wa.set(False)                                         # box unticked: no WhatsApp

# --- Same token comes back with a RENEWED certificate: the screen says so and saves a renewal
import dsc_manager.ui.inward as inward_ui  # noqa: E402
fake.tokens[0].update(cert_serial="ABC999", issue_date="2026-12-30 11:00:00", expiry_date="2028-12-30 11:00:00")
scr = app.show("inward")
scr._read_token()
assert "RENEWED CERTIFICATE" in scr.token_info.cget("text"), scr.token_info.cget("text")
scr.purpose.set("GST")
scr._save()
assert not errors(), errors()
assert app.db.get_current_certificate(tok["token_id"])["cert_serial"] == "ABC999"
assert len(app.db.certificate_history(tok["token_id"])) == 2
renewed_inward = app.db.custody_register({"search": "Smoke Holder"})[0]["inward_id"]
app.show("outward", inward_id=renewed_inward)._save()

# --- A NEW token for the same client: the screen says so and offers to retire the old one
fake.tokens[0].update(token_serial="SMOKE-TOKEN-2", cert_serial="NEW111")
asked = []


class FakeReplace:
    def __init__(self, parent, client, serial, tokens):
        asked.append([t["token_serial"] for t in tokens])

    def show(self):
        return [tok["token_id"]]


inward_ui.ReplaceTokensDialog = FakeReplace
scr = app.show("inward")
scr._read_token()
assert scr.token_info.cget("text").startswith("NEW TOKEN"), scr.token_info.cget("text")
scr.purpose.set("GST")
scr._save()
assert not errors(), errors()
assert asked == [["SMOKE-TOKEN-1"]], asked
assert app.db.get_token(tok["token_id"])["status"] == "Inactive"
new_inward = app.db.custody_register({"search": "Smoke Holder"})[0]["inward_id"]
app.show("outward", inward_id=new_inward)._save()

# --- Clients: download the Excel template, fill it, import through the screen
import openpyxl  # noqa: E402
import dsc_manager.ui.clients as clients_ui  # noqa: E402
template = os.path.join(tmp, "Client_Import_Template.xlsx")
filedialog.asksaveasfilename = lambda **k: template
cl = app.show("clients")
cl._template()
assert os.path.exists(template)
wb = openpyxl.load_workbook(template)
wb["Clients"].append(["Imported One", "9811100011", "Imp & Co", "", "", ""])
wb["Clients"].append(["Imported Two", "", "", "", "", ""])          # no mobile: skipped
wb.save(template)
filedialog.askopenfilename = lambda **k: template
previews = []


class AutoImport:
    def __init__(self, parent, db, plan, name):
        previews.append(plan)
        self.db, self.plan = db, plan

    def show(self):
        return self.db.apply_client_import(self.plan)


clients_ui.ImportPreviewDialog = AutoImport
cl._import()
assert [r["action"] for r in previews[0]] == ["Import", "Skip"], previews
assert app.db.list_clients("Imported One"), "import did not save"
filedialog.asksaveasfilename = lambda **k: os.path.join(tmp, k.get("initialfile", "out.csv"))

# --- Typing in a client box shows the matching names
scr = app.show("inward")
cp = scr.client
cp.delete(0, "end")
cp.insert(0, "imported")
# Key events are sent straight to the handlers: a test window may not get keyboard focus from Windows.
key = type("Key", (), {"keysym": "d"})()
cp.autocomplete._typed(key)
app.update()
assert cp.autocomplete.visible() and cp.autocomplete.listbox.get(0, "end"), "no suggestions shown"
cp.autocomplete._move(1)
cp.autocomplete._enter(key)
app.update()
assert cp.get_id() == app.db.list_clients("Imported One")[0]["client_id"]
scr._clear_form()

# --- Filters are cleared when the user leaves a screen and comes back
reg = app.show("inward_register")
reg.panel.search.set("SMOKE")
reg.panel.cancelled.set(True)
reg.panel.refresh()
cust = app.show("custody")
cust.c_search.set("Sharma")
cust.c_overdue.set("Overdue")
al = app.show("alerts", flt="expired")
al.search.set("xyz")
mr = app.show("movement_register")
mr.search.set("xyz")
app.show("dashboard")
reg = app.show("inward_register")
assert reg.panel.search.get() == "" and not reg.panel.cancelled.get(), "inward register filters kept"
assert len(reg.panel.table.rows) == len(app.db.inward_register())
cust = app.show("custody")
assert (cust.c_search.get(), cust.c_overdue.get()) == ("", "All"), "custody filters kept"
al = app.show("alerts")
assert (al.search.get(), al.flt.get()) == ("", "30"), "alert filters kept"
assert app.show("movement_register").search.get() == "", "movement register filters kept"
reg = app.show("inward_register", from_date=dates.today_iso())   # a dashboard card still applies its period
assert reg.panel.from_d.get_iso("From") == dates.today_iso()

# --- New windows open and close cleanly; settings screen; WhatsApp reminder from Expiry Alerts
from dsc_manager.ui.dialogs import ClientDetailDialog, StartupSummaryDialog  # noqa: E402
cd = ClientDetailDialog(app, app.db, cid, app)
app.update()
assert cd.tokens.rows and cd.history.rows, "client detail view is empty"
cd.destroy()
sd = StartupSummaryDialog(app, app.db.attention_summary())
app.update()
sd.destroy()
st = app.show("settings")
assert "{name}" in st.text.get("1.0", "end")
al = app.show("alerts", flt="all")
al.table.select(lambda r: r["custody"] == "In Custody")
al._remind()
assert "expires%20on" in opened[-1], opened[-1]
app.toast("smoke test toast")
app.update()

# --- Undo on the success message reverses an outward entry
out = app.show("outward")
row = out.custody.select(lambda r: True)
before_undo = app.db.dashboard_counts()["custody"]
out._pick(row)
out.wa.set(False)
out._save()
assert app.db.dashboard_counts()["custody"] == before_undo - 1
undo_btn = [w for w in app._toast.winfo_children() if isinstance(w, tk.Button)]
assert undo_btn, "no Undo button on the message"
undo_btn[0].invoke()
app.update()
assert app.db.dashboard_counts()["custody"] == before_undo, "undo did not restore custody"

# --- Search box at the top finds clients and tokens; menu counts; sample-data strip; help screen
app._load_search_index()
found = app.search.master and [i for i in app._search_items if "Smoke Holder" in i["label"]]
assert found, "search index has no Smoke Holder"
assert "(" in app.menu_buttons["custody"].cget("text"), app.menu_buttons["custody"].cget("text")
assert app.sample_strip.winfo_ismapped(), "sample-data strip not shown"
app.show("help")
app.update()

# --- Correct Entry on an inward and an outward entry (the dialog is driven directly)
from dsc_manager.ui.dialogs import CorrectEntryDialog  # noqa: E402
inw_scr = app.show("inward")
inw_scr.nb.select(1)
inw_scr.register.refresh()
row = inw_scr.register.table.select(lambda r: r["status"] == "Active")
dlg = CorrectEntryDialog(inw_scr, app.db, "inward", row)
dlg.remarks.set("Corrected in smoke test")
dlg.reason.set("Remark was missing")
dlg.ok()
assert dlg.result and "Remarks" in dlg.result[0], dlg.result
inw_scr.register.refresh()
assert any(r["inward_id"] == row["inward_id"] and r["custody"].endswith("(corrected)")
           for r in inw_scr.register.table.rows), "inward not marked corrected"
out_scr = app.show("outward")
out_scr.nb.select(1)
out_scr.register.refresh()
orow = out_scr.register.table.select(lambda r: r["status"] == "Active" and r["returned_via"] == "Custodian")
dlg = CorrectEntryDialog(out_scr, app.db, "outward", orow)
dlg.reason.set("")
dlg.ok()                                          # no reason: refused, dialog stays open
assert dlg.result is None and errors(), "correction without a reason was accepted"
shown.clear()
dlg.person.set(orow["returned_to"] + " (son)")
dlg.reason.set("Name incomplete")
dlg.ok()
assert dlg.result, "outward correction not saved"
app.update()

# --- Settings > Custodian, Staff & Consultants: custodian, staff and consultants together; nothing left on Backup
from dsc_manager.ui import handlers  # noqa: E402
st = app.show("settings")
assert st.nb.tab(0, "text").strip() == "Custodian, Staff & Consultants" and st.nb.index("current") == 0
assert "masters" not in app.screens and not hasattr(app.show("backup"), "staff_list")
st = app.show("settings")
dh = st.handlers
assert dh.current.cget("text").startswith("Current custodian") and dh.custodians.rows
handlers.ask_text = lambda *a, **k: "Tab Staff"
dh._add_staff()
names = list(dh.staff_list.get(0, "end"))
assert "Tab Staff" in names and "Tab Staff" in app.db.list_staff()
dh.staff_list.selection_set(names.index("Tab Staff"))
dh._remove_staff()
assert "Tab Staff" not in dh.staff_list.get(0, "end")
st.nb.select(1)
app.show("settings", tab=0)                                # how the "no custodian" alert opens it
assert st.nb.index("current") == 0
n_cons = len(dh.consultants.rows)
assert n_cons == len(app.db.list_consultants())
app.update()

# --- Small screen: everything stays reachable; scrollbars appear only when the page does not fit
from tkinter import ttk  # noqa: E402
app.minsize(1, 1)
app.state("normal")
app.geometry("1093x520+0+0")
app.update()
inw_scr = app.show("inward")
inw_scr.nb.select(0)
app.update()
inw_scr.scroll.layout()
app.update()
assert inw_scr.scroll.needs_scroll(), "no scrollbar on a page that does not fit"
saves = [w for w in inw_scr.nb.nametowidget(inw_scr.nb.tabs()[0]).winfo_children() if isinstance(w, ttk.Frame)]
inw_scr.scroll.canvas.yview_moveto(1)
app.update()
assert all(w.winfo_height() >= w.winfo_reqheight() for w in saves), "Inward form squeezed on a small screen"
app.state("zoomed")
app.update()
inw_scr.scroll.layout()
app.update()
assert not inw_scr.scroll.needs_scroll(), "scrollbar shown on a page that fits"

# --- Google Sheet for the partners: a local server stands in for Google (redirect, then the reply)
import json  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from http.server import BaseHTTPRequestHandler, HTTPServer  # noqa: E402
from dsc_manager import gsheet  # noqa: E402
posts = []


class FakeGoogle(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        posts.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(302)
        self.send_header("Location", "/reply")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok": true, "tabs": 9}')


server = HTTPServer(("127.0.0.1", 0), FakeGoogle)
threading.Thread(target=server.serve_forever, daemon=True).start()


def run_sheet_update(manual):
    done = []
    app.update_sheet(manual=manual, on_done=done.append)
    end = time.time() + 30
    while not done and time.time() < end:
        app.update()
        time.sleep(0.05)
    return done


st = app.show("settings")
st.nb.select(2)
app.update()
assert "Not set up" in st.sheet_status.cget("text")
app.db.set_meta(gsheet.META_URL, f"http://127.0.0.1:{server.server_port}/exec")   # Save & Test needs a Google link
app.refresh_dashboard()
assert app._sheet_job, "an entry did not schedule a Google Sheet update"
assert run_sheet_update(manual=True) == [None]
assert len(posts) == 1 and len(posts[0]["tabs"]) == 8 and posts[0]["key"] == gsheet.get_key(app.db), posts[:1]
st._show_sheet_status()
assert "Last updated" in st.sheet_status.cget("text"), st.sheet_status.cget("text")
server.shutdown()
server.server_close()
assert run_sheet_update(manual=False) and gsheet.status(app.db)["last_error"], "no-internet case not recorded"
app.db.set_meta(gsheet.META_URL, "")
st._show_sheet_status()

# --- Exports and backup
for name in ("inward_register", "outward_register"):
    app.show(name).panel.export()
cust = app.show("custody")
cust.live.export_csv("DSC_Custody_Register")
cust.awaited.export_csv("DSC_Awaited_From_Clients")
app.show("alerts", flt="all")._export()
app.show("movement_register").table.export_csv("DSC_Movement_Register")
hold = app.show("holdings")
hold.people.select(lambda g: g["type"] == "custodian")
hold._show_person(hold.people.selected())
hold.tokens.export_csv("DSC_Holdings_By_Person")
app.show("backup")._backup()
app.update()
csvs = [f for f in os.listdir(tmp) if f.endswith(".xlsx") and not f.startswith("Client_Import")]
backups = [f for f in os.listdir(tmp) if f.startswith("DSC_Backup_")]
assert len(csvs) == 7, csvs
assert backups, "no backup written"

# --- Restore from Backup: an entry made after the backup disappears; the safety copy keeps it
before = app.db.dashboard_counts()["inward"]
app.db.add_client({"holder_name": "After Backup Client", "mobile": "9111111111"})
filedialog.askopenfilename = lambda **k: os.path.join(tmp, backups[0])
app.show("backup")._restore()
app.update()
assert not [c for c in app.db.list_clients() if c["holder_name"] == "After Backup Client"], "restore did not apply"
assert app.db.dashboard_counts()["inward"] == before
assert app.current == "dashboard" and not errors(), errors()
safety = [f for f in os.listdir(os.path.dirname(app.db.path)) if f.startswith("DSC_BeforeRestore_")]
assert safety, "no safety copy before restore"
app.close()
saved = json.load(open(os.environ["DSC_MANAGER_CONFIG"], encoding="utf-8"))
assert saved.get("column_widths"), "column widths were not saved"
print("GUI smoke test passed.", len(csvs), "Excel exports,", len(opened), "WhatsApp messages,", len(backups), "backup,",
      len(posts), "Google Sheet update; errors shown:", errors())
