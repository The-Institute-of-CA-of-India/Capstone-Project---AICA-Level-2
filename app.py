"""Mini CFO: a CA-controlled pocket finance assistant (Streamlit). DEMO / dummy data only."""
from __future__ import annotations

import os
from datetime import date
from urllib.parse import quote

import pandas as pd
import streamlit as st

import db
from calc import compute, validate, inr, REQUIRED
from qa import CHIPS, DISCLAIMER, rule_answer, ai_answer, note_text

st.set_page_config(page_title="Mini CFO", page_icon="💼", layout="centered")
db.init()
ICON = {"Green": "🟢", "Amber": "🟠", "Red": "🔴"}
st.markdown("""<style>html,body,[class*="css"]{font-size:17px} .stButton>button{width:100%}
div[data-testid="stMetricValue"]{font-size:1.6rem}</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ helpers
@st.cache_data(show_spinner=False)
def _metrics(cid: str, sig: str):
    cl = db.get_client(cid)
    return compute(db.load_txns(cid), cl)


def metrics(cid: str):
    cl = db.get_client(cid)
    sig = "|".join(str(cl[k]) for k in ("opening_cash", "fixed_costs", "sales_target", "profit_target", "uploaded_at"))
    sig += str(os.path.getmtime(db.DATA / f"{cid}.csv"))
    return _metrics(cid, sig), cl


def api_key():
    return os.environ.get("GEMINI_API_KEY") or st.session_state.get("gemini_key", "")


def health_badge(c):
    return f"{ICON[c]} {c}"


# ------------------------------------------------------------------ login
def login_screen():
    st.title("💼 Mini CFO")
    st.caption("Your CA's finance assistant. Demo with dummy data only.")
    with st.form("login"):
        email = st.text_input("Email", value="")
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Log in"):
            u = db.login(email, pw)
            if u:
                st.session_state.user = u
                db.log(u["email"], "Logged in")
                st.rerun()
            else:
                st.error("Wrong email or password.")
    with st.expander("Demo logins"):
        st.write("CA: `ca@demo.com`  |  Owner (Sharma Traders): `owner@demo.com`  |  "
                 "Owner (Verma Foods): `owner2@demo.com`  |  Password for all: `Demo@12345`")


def consent_screen(u):
    st.title("Before you start")
    st.write("Your CA uses this app to share a summary of your business numbers with you.")
    ok = st.checkbox("I agree my business data may be processed by an AI tool for this app.")
    if st.button("Continue", disabled=not ok):
        db.set_consent(u["email"])
        db.log(u["email"], "Gave AI-processing consent")
        st.session_state.user["consent"] = 1
        st.rerun()


# ------------------------------------------------------------------ owner pages
def p_dashboard(cid):
    m, cl = metrics(cid)
    st.header(cl["name"])
    st.markdown(f"### {health_badge(m['health'])}")
    st.caption(" · ".join(m["health_reasons"]) + f"  |  Data as of {m['as_of']:%d %b %Y} (uploaded {cl['uploaded_at']})")
    c1, c2 = st.columns(2)
    c1.metric("Cash", inr(m["cash"]))
    c2.metric("Cash runway", "over 52 weeks" if m["runway"] > 52 else f"{m['runway']:.1f} weeks")
    c1.metric("Customers owe you", inr(m["total_receivables"]), f"{inr(m['overdue_receivables'])} overdue", delta_color="off")
    c2.metric("You owe suppliers", inr(m["total_payables"]))
    c1.metric("Profit (before fixed costs)", inr(m["profit"]),
              None if m["profit_chg"] is None else f"{m['profit_chg']:+.0f}% vs last month")
    c2.metric("Profit (after fixed costs)", inr(m["profit_after_fixed"]))
    st.subheader("Targets")
    if m["sales_pct"] is not None:
        st.write(f"Sales {inr(m['sales'])} of {inr(cl['sales_target'])}")
        st.progress(min(m["sales_pct"] / 100, 1.0))
        st.write(f"Profit after fixed costs {inr(m['profit_after_fixed'])} of {inr(cl['profit_target'])}")
        st.progress(max(0.0, min(m["profit_pct"] / 100, 1.0)))
    st.subheader("What changed since last month")
    for n, v, _ in m["changes"]:
        st.write(f"- {n}: {'up' if v > 0 else 'down'} {inr(abs(v))}")
    st.info("Cash, receivables and payables include GST (invoice totals). Profit excludes GST. "
            "Fixed costs are deducted from cash for each month in the data.")


def p_ask(cid, email):
    m, cl = metrics(cid)
    st.header("Ask CFO")
    st.caption(f"Data as of {m['as_of']:%d %b %Y}")
    cols = st.columns(2)
    clicked = None
    for i, q in enumerate(CHIPS):
        if cols[i % 2].button(q, key=f"chip{i}"):
            clicked = q
    typed = st.chat_input("Ask about your business (English or Hindi)")
    q = typed or clicked
    if q:
        faq = db.faq_lookup(cid, q)
        if faq:
            db.add_question(cid, email, q, faq, "Answered by CA (saved reply)")
        else:
            a = rule_answer(q, m)
            if a:
                txt = f"**{a['answer']}**\n\n{a['why']}\n\n➡️ {a['next']}"
                db.add_question(cid, email, q, txt)
            elif api_key() and (ai := ai_answer(q, m, api_key())):
                db.add_question(cid, email, q, ai)
            else:
                db.add_question(cid, email, q, "I don't have this information.", "Not answered")
        db.log(email, f"Asked: {q}")
    for row in reversed(db.questions_for(cid)[-8:]):
        with st.chat_message("user"):
            st.write(row["question"])
        with st.chat_message("assistant"):
            st.markdown(row["answer"])
            if row["reply"]:
                st.success(f"Reply from your CA: {row['reply']}")
            elif row["status"] == "Sent to CA":
                st.info("Sent to your CA")
            else:
                if st.button("Ask my CA", key=f"ask{row['id']}"):
                    db.forward_to_ca(row["id"])
                    db.log(email, f"Forwarded question {row['id']} to CA")
                    st.rerun()
            st.caption(DISCLAIMER)


def p_owed(cid):
    m, cl = metrics(cid)
    st.header("Money owed to me")
    r = m["receivables"]
    if r.empty:
        st.success("Nobody owes you money.")
        return
    st.write(r.groupby("Bucket")["Total"].sum().apply(inr).rename("Amount").to_frame())
    for row in r.itertuples():
        with st.container(border=True):
            st.write(f"**{row.Party}**: {inr(row.Total)} · {row.Description}")
            st.caption(f"Due {row.Due_Date:%d %b %Y}, " + (f"{row.Days_Overdue} days overdue" if row.Days_Overdue > 0 else "not yet due"))
            msg = (f"Dear {row.Party}, a gentle reminder that {inr(row.Total)} for {row.Description} "
                   f"was due on {row.Due_Date:%d %b %Y}. Kindly arrange payment at your earliest. "
                   f"Thank you. - {cl['name']}")
            st.link_button("Send reminder on WhatsApp", f"https://wa.me/?text={quote(msg)}")


def p_forecast(cid):
    m, _ = metrics(cid)
    st.header("Cash forecast: next 8 weeks")
    f = m["forecast"].set_index("Week")
    st.line_chart(f["Cash"])
    low = f["Cash"].idxmin()
    st.write(f"Lowest point: **{inr(m['lowest_cash'])}** at the end of week {low}.")
    st.dataframe(f.map(inr), use_container_width=True)
    st.caption("Known items only: unpaid customer bills (overdue ones assumed collected in week 1), unpaid supplier "
               "bills by due date and fixed costs. New sales and purchases are not predicted.")


def p_note(cid):
    m, cl = metrics(cid)
    st.header("Monthly CFO note")
    n = db.get_note(cid, m["cur_period"])
    if n and n["status"] == "Approved":
        st.success(f"Reviewed by CA on {n['approved_on']}")
        st.markdown(n["text"])
        st.download_button("Download note", n["text"], file_name=f"CFO_note_{cl['name']}_{m['cur_period']}.md")
    else:
        st.info("Your CA is preparing this month's note. It will appear here once reviewed.")


def p_targets(cid):
    m, cl = metrics(cid)
    st.header("My targets")
    st.write(f"**Sales target** {inr(cl['sales_target'])} · achieved {inr(m['sales'])} ({m['sales_pct']:.0f}%)")
    st.progress(min(m["sales_pct"] / 100, 1.0))
    st.write(f"**Profit target (after fixed costs)** {inr(cl['profit_target'])} · achieved {inr(m['profit_after_fixed'])} ({m['profit_pct']:.0f}%)")
    st.progress(max(0.0, min(m["profit_pct"] / 100, 1.0)))


# ------------------------------------------------------------------ CA pages
def ca_clients():
    st.header("Clients")
    rows = []
    for cl in db.get_clients():
        m, _ = metrics(cl["id"])
        rows.append((["Red", "Amber", "Green"].index(m["health"]), cl, m))
    for _, cl, m in sorted(rows, key=lambda x: x[0]):
        with st.container(border=True):
            st.subheader(f"{health_badge(m['health'])}  {cl['name']}")
            st.caption("; ".join(m["health_reasons"]))
            a, b, c = st.columns(3)
            a.metric("Cash", inr(m["cash"]))
            b.metric("Runway", f"{m['runway']:.1f} wk")
            c.metric("Overdue", inr(m["overdue_receivables"]))
    alerts = []
    for _, cl, m in rows:
        if m["health"] == "Red":
            alerts.append(f"{cl['name']} is Red")
        if m["runway"] < 4:
            alerts.append(f"{cl['name']}: runway below 4 weeks")
        if (m["receivables"]["Days_Overdue"] > 90).any():
            alerts.append(f"{cl['name']}: a receivable is over 90 days")
        if m["sales_pct"] is not None and m["sales_pct"] < 100:
            alerts.append(f"{cl['name']}: sales target missed")
    waiting = len(db.inbox())
    if waiting:
        alerts.append(f"{waiting} client question(s) in your inbox")
    st.subheader("Alerts")
    for a in alerts or ["No alerts."]:
        st.write(f"- {a}")


def ca_upload(email):
    st.header("Upload data")
    clients = {c["name"]: c["id"] for c in db.get_clients()}
    name = st.selectbox("Client", list(clients))
    cid = clients[name]
    cl = db.get_client(cid)
    with st.expander("Client settings (targets, fixed costs, opening cash)"):
        with st.form("settings"):
            oc = st.number_input("Opening cash + bank balance", value=float(cl["opening_cash"]), step=1000.0)
            fc = st.number_input("Monthly fixed costs (salary, rent, EMI)", value=float(cl["fixed_costs"]), step=1000.0)
            stg = st.number_input("Monthly sales target", value=float(cl["sales_target"]), step=1000.0)
            ptg = st.number_input("Monthly profit target (after fixed costs)", value=float(cl["profit_target"]), step=1000.0)
            if st.form_submit_button("Save settings"):
                db.update_client(cid, opening_cash=oc, fixed_costs=fc, sales_target=stg, profit_target=ptg)
                db.log(email, f"Updated settings for {name}")
                st.success("Saved.")
    st.write("CSV or Excel with columns: " + ", ".join(REQUIRED))
    f = st.file_uploader("Monthly data file", type=["csv", "xlsx"])
    if f:
        df = pd.read_csv(f) if f.name.lower().endswith(".csv") else pd.read_excel(f)
        clean, errs, warns = validate(df)
        for w in warns:
            st.warning(w)
        if errs:
            st.error("The file was not accepted. Fix these and upload again:")
            for e in errs[:30]:
                st.write(f"- {e}")
            return
        st.success(f"{len(clean)} rows look fine.")
        st.dataframe(clean.head(10))
        c1 = st.checkbox("All bank accounts included")
        c2 = st.checkbox("Month is complete")
        c3 = st.checkbox("No personal entries")
        if st.button("Save data", disabled=not (c1 and c2 and c3 and not warns)):
            db.save_txns(cid, clean[REQUIRED])
            db.log(email, f"Uploaded {len(clean)} rows for {name}")
            st.cache_data.clear()
            st.success("Data saved. Go to 'Review note' to prepare this month's note.")
        if warns:
            st.caption("Remove the flagged values from the file before saving.")


def ca_note(email):
    st.header("Review monthly note")
    clients = {c["name"]: c["id"] for c in db.get_clients()}
    name = st.selectbox("Client", list(clients))
    cid = clients[name]
    m, cl = metrics(cid)
    n = db.get_note(cid, m["cur_period"])
    if not n and st.button("Generate draft note"):
        db.save_note(cid, m["cur_period"], note_text(cl, m))
        db.log(email, f"Generated draft note for {name}")
        st.rerun()
    left, right = st.columns([1, 2])
    with left:
        st.markdown(f"**{health_badge(m['health'])}**")
        st.write(f"Sales {inr(m['sales'])}")
        st.write(f"Profit {inr(m['profit'])}")
        st.write(f"After fixed {inr(m['profit_after_fixed'])}")
        st.write(f"Cash {inr(m['cash'])}")
        st.write(f"Runway {m['runway']:.1f} wk")
        st.write(f"Owed to you {inr(m['total_receivables'])}")
    with right:
        if not n:
            st.info("No note yet for this month.")
            return
        st.caption(f"Status: {n['status']}" + (f" on {n['approved_on']}" if n["approved_on"] else ""))
        text = st.text_area("Edit the note", n["text"], height=420)
        a, b = st.columns(2)
        if a.button("Save draft"):
            db.save_note(cid, m["cur_period"], text, "Draft")
            db.log(email, f"Saved draft note for {name}")
            st.rerun()
        if b.button("Approve and publish"):
            db.save_note(cid, m["cur_period"], text, "Approved", f"{date.today():%d %b %Y}")
            db.log(email, f"Approved note for {name} ({m['cur_period']})")
            st.rerun()


def ca_inbox(email):
    st.header("Inbox")
    items = db.inbox()
    if not items:
        st.info("No questions forwarded yet.")
    for q in items:
        with st.container(border=True):
            st.write(f"**{q['client']}**: {q['question']}")
            st.caption(f"{q['ts']} · {q['status']}")
            st.markdown(q["answer"] or "")
            if q["status"] == "Sent to CA":
                txt = st.text_area("Your reply", key=f"r{q['id']}")
                faq = st.checkbox("Save as FAQ for this client", key=f"f{q['id']}")
                if st.button("Send reply", key=f"s{q['id']}") and txt.strip():
                    db.reply(q["id"], txt.strip(), faq)
                    db.log(email, f"Replied to question {q['id']}")
                    st.rerun()
            else:
                st.success(f"Replied: {q['reply']}")
    st.subheader("Most asked questions")
    for r in db.question_counts():
        st.write(f"- {r['q']} ({r['times']}x)")


def ca_log():
    st.header("Activity log")
    log = pd.DataFrame(db.get_log())
    st.dataframe(log, use_container_width=True)
    if not log.empty:
        st.download_button("Export log (CSV)", log.to_csv(index=False), file_name="activity_log.csv")


# ------------------------------------------------------------------ router
def main():
    u = st.session_state.get("user")
    if not u:
        return login_screen()
    if u["role"] == "owner" and not u["consent"]:
        return consent_screen(u)
    with st.sidebar:
        st.write(f"**{u['email']}**  ({'CA' if u['role'] == 'ca' else 'Owner'})")
        if u["role"] == "ca":
            page = st.radio("Go to", ["Clients", "Upload data", "Review note", "Inbox", "Activity log"])
            st.text_input("Gemini API key (optional)", type="password", key="gemini_key")
        else:
            page = st.radio("Go to", ["Dashboard", "Ask CFO", "Money owed to me", "Cash forecast", "Monthly note", "My targets"])
        if st.button("Log out"):
            db.log(u["email"], "Logged out")
            st.session_state.clear()
            st.rerun()
    cid = u["client_id"]
    if u["role"] == "ca":
        {"Clients": ca_clients, "Upload data": lambda: ca_upload(u["email"]), "Review note": lambda: ca_note(u["email"]),
         "Inbox": lambda: ca_inbox(u["email"]), "Activity log": ca_log}[page]()
    else:
        {"Dashboard": lambda: p_dashboard(cid), "Ask CFO": lambda: p_ask(cid, u["email"]),
         "Money owed to me": lambda: p_owed(cid), "Cash forecast": lambda: p_forecast(cid),
         "Monthly note": lambda: p_note(cid), "My targets": lambda: p_targets(cid)}[page]()


main()
