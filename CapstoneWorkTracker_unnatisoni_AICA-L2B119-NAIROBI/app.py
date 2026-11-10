"""Work Allocation & Review Tracker - run with:  streamlit run app.py"""
import os, io, html
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
import database as db
import ai_helper

st.set_page_config(page_title="Work Tracker", page_icon="✅", layout="wide")
db.init_db()
STATUS_ICON = {"Not Started": "⚪", "In Progress": "🔵", "Submitted for Review": "🟣",
               "Rework": "🟠", "Approved": "🟢", "Completed": "🟢"}
STATUS_COLOR = {"Not Started": "#9CA3AF", "In Progress": "#3B82F6", "Submitted for Review": "#8B5CF6",
                "Rework": "#F59E0B", "Approved": "#10B981", "Completed": "#10B981"}
PRIO_ICON = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp li, .stApp a,
.stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th, .stApp small,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
/* keep Streamlit's icon font so arrows and icons render properly */
[data-testid="stIconMaterial"], span[class*="material"], .material-icons, .material-symbols-rounded {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important; }
.stApp { background: #F6F7FB; }
.block-container { padding-top: 2.2rem; max-width: 1200px; }
footer, [data-testid="stAppDeployButton"], .stAppDeployButton { display: none !important; }
h1, h2, h3 { color: #1F2340; font-weight: 700; letter-spacing: -0.02em; }
h2 { font-size: 1.7rem; }

/* sidebar */
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #4F46E5 0%, #7C3AED 100%); }
section[data-testid="stSidebar"] * { color: #fff !important; }
section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,.16); border: none; border-radius: 10px; width: 100%; font-weight: 600; }
section[data-testid="stSidebar"] .stButton > button:hover { background: rgba(255,255,255,.28); }
section[data-testid="stSidebar"] label[data-baseweb="radio"] { padding: 6px 10px; border-radius: 10px; }
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover { background: rgba(255,255,255,.14); }
.brand { font-size: 1.25rem; font-weight: 700; margin: 4px 0 14px 0; }
.user-card { display: flex; align-items: center; gap: 12px; background: rgba(255,255,255,.14);
    padding: 10px 12px; border-radius: 14px; margin-bottom: 18px; }
.user-card .avatar { width: 38px; height: 38px; border-radius: 50%; background: #fff; display: flex;
    align-items: center; justify-content: center; font-weight: 700; color: #4F46E5 !important; }
.user-card .avatar * { color: #4F46E5 !important; }
.user-card small { opacity: .85; }

/* metric cards */
[data-testid="stMetric"] { background: #fff; border-radius: 14px; padding: 16px 18px;
    box-shadow: 0 1px 3px rgba(16,24,40,.06); border-top: 4px solid #4F46E5; }
[data-testid="stMetricLabel"] { color: #6B7280; font-weight: 500; }
[data-testid="stMetricValue"] { color: #1F2340; font-weight: 700; }
div[data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"] { border-top-color: #3B82F6; }
div[data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stMetric"] { border-top-color: #8B5CF6; }
div[data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stMetric"] { border-top-color: #F59E0B; }
div[data-testid="stHorizontalBlock"] > div:nth-child(5) [data-testid="stMetric"] { border-top-color: #10B981; }

/* cards, tables, forms */
[data-testid="stExpander"], [data-testid="stForm"] { background: #fff; border-radius: 14px;
    border: 1px solid #ECEEF5; box-shadow: 0 1px 3px rgba(16,24,40,.04); }
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(16,24,40,.06); }
[data-testid="stAlert"] { border-radius: 12px; }

/* buttons */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
    border-radius: 10px; font-weight: 600; border: 1px solid #DADDEA; transition: all .15s; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: #4F46E5; color: #4F46E5; }
button[kind="primary"], button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
    background: #4F46E5 !important; border-color: #4F46E5 !important; color: #fff !important; }
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background: #4338CA !important; color: #fff !important; }

[data-testid="stFormSubmitButton"] > button { width: 100%; }

/* login */
.login-title { font-size: 2rem; font-weight: 700; color: #1F2340; text-align: center; margin-top: 8vh; }
.login-sub { text-align: center; color: #6B7280; margin-bottom: 1.4rem; }
.login-sub b { color: #4F46E5; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def show_df(df):
    """Display-only copy with coloured status / priority dots."""
    d = df.copy()
    if "Status" in d:
        d["Status"] = d["Status"].map(lambda s: f"{STATUS_ICON.get(s, '')} {s}")
    if "Priority" in d:
        d["Priority"] = d["Priority"].map(lambda s: f"{PRIO_ICON.get(s, '')} {s}")
    return d


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ------------------------------------------------------------------ login
def login_screen():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown('<div class="login-title">✅ Work Tracker</div>'
                    '<div class="login-sub"><b>Allocate</b> · <b>Track</b> · <b>Review</b></div>',
                    unsafe_allow_html=True)
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                user = db.login(u.strip(), p)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Wrong username or password.")
        st.caption("First time? Username: admin  |  Password: admin123  (change it after logging in)")


def save_upload(task_id, f):
    safe = f"{task_id}_{datetime.now():%Y%m%d%H%M%S}_{os.path.basename(f.name)}"
    path = os.path.join(UPLOAD_DIR, safe)
    with open(path, "wb") as out:
        out.write(f.getbuffer())
    db.add_attachment(task_id, path)


def tasks_df(tasks, pretty=False):
    rows = [{
        "ID": t["id"], "Task": t["title"], "Client": t["client"], "Category": t["category"],
        "Assigned To": t["assignee"], "Priority": t["priority"], "Assigned": t["assigned_date"],
        "Due": t["due_date"], "Status": t["status"],
        "Overdue": "⚠️ Yes" if db.is_overdue(t) else "",
        "Review Comments": t["review_comments"], "Completed On": t["completed_date"],
    } for t in tasks]
    df = pd.DataFrame(rows)
    return show_df(df) if pretty else df


def to_excel(df):
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="Tasks")
    return buf.getvalue()


# ------------------------------------------------------------------ admin pages
def page_dashboard(user):
    st.header("Dashboard")
    tasks = db.get_tasks()
    if not tasks:
        st.info("No tasks yet. Go to 'Tasks' to create the first one.")
        return
    today = date.today().isoformat()
    overdue = [t for t in tasks if db.is_overdue(t)]
    pending_review = [t for t in tasks if t["status"] == "Submitted for Review"]
    done = [t for t in tasks if t["status"] == "Completed"]
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    done_week = [t for t in done if (t["completed_date"] or "") >= week_ago]
    in_progress = [t for t in tasks if t["status"] == "In Progress"]

    c = st.columns(5)
    c[0].metric("Total tasks", len(tasks))
    c[1].metric("In progress", len(in_progress))
    c[2].metric("Waiting for my review", len(pending_review))
    c[3].metric("Overdue", len(overdue))
    c[4].metric("Completed (7 days)", len(done_week))

    df = tasks_df(tasks)
    left, right = st.columns(2)
    with left:
        st.subheader("Tasks by status")
        counts = df["Status"].value_counts()
        st.bar_chart(counts, color="#4F46E5")
    with right:
        st.subheader("Tasks by person")
        pivot = df.groupby(["Assigned To", "Status"]).size().unstack(fill_value=0)
        st.bar_chart(pivot, color=[STATUS_COLOR.get(c, "#4F46E5") for c in pivot.columns])

    if overdue:
        st.subheader("⚠️ Overdue")
        st.dataframe(tasks_df(overdue, pretty=True)[["ID", "Task", "Assigned To", "Due", "Status", "Priority"]],
                     hide_index=True, width="stretch")
    soon = [t for t in tasks if t["due_date"] and today <= t["due_date"] <=
            (date.today() + timedelta(days=3)).isoformat() and t["status"] not in ("Completed", "Approved")]
    if soon:
        st.subheader("Due in the next 3 days")
        st.dataframe(tasks_df(soon, pretty=True)[["ID", "Task", "Assigned To", "Due", "Status", "Priority"]],
                     hide_index=True, width="stretch")


def task_form(user, task=None):
    employees = db.list_users(only_employees=True)
    if not employees:
        st.warning("Add employees first under 'Team'.")
        return
    names = {e["name"]: e["id"] for e in employees}
    idx = 0
    if task and task["assignee"] in names:
        idx = list(names).index(task["assignee"])
    with st.form("task_form_" + str(task["id"] if task else "new"), clear_on_submit=not task):
        title = st.text_input("Task title", value=task["title"] if task else "")
        desc = st.text_area("Description", value=(task["description"] or "") if task else "")
        c1, c2 = st.columns(2)
        client = c1.text_input("Client / Department", value=(task["client"] or "") if task else "")
        category = c2.text_input("Category (e.g. Bank Recon, GST, Audit)",
                                 value=(task["category"] or "") if task else "")
        c3, c4, c5 = st.columns(3)
        who = c3.selectbox("Assign to", list(names), index=idx)
        pr = c4.selectbox("Priority", db.PRIORITIES,
                          index=db.PRIORITIES.index(task["priority"]) if task else 1)
        due_default = date.fromisoformat(task["due_date"]) if task and task["due_date"] else date.today() + timedelta(days=3)
        due = c5.date_input("Due date", value=due_default)
        status = None
        if task:
            status = st.selectbox("Status", db.STATUSES, index=db.STATUSES.index(task["status"]))
        if st.form_submit_button("Save task" if task else "Create task", type="primary"):
            if not title.strip():
                st.error("Title is required.")
            elif task:
                fields = dict(title=title, description=desc, client=client, category=category,
                              priority=pr, assigned_to=names[who], due_date=str(due), status=status)
                if status == "Completed" and not task["completed_date"]:
                    fields["completed_date"] = date.today().isoformat()
                db.update_task(task["id"], who=user["username"], **fields)
                st.success("Task updated.")
            else:
                db.create_task(title, desc, client, category, pr, names[who], due, user["username"])
                st.success("Task created and assigned.")


def page_tasks(user):
    st.header("Tasks")
    tab1, tab2 = st.tabs(["All tasks", "Create new"])
    with tab2:
        task_form(user)
    with tab1:
        tasks = db.get_tasks()
        if not tasks:
            st.info("No tasks yet.")
            return
        df = tasks_df(tasks)
        f1, f2, f3 = st.columns(3)
        fp = f1.multiselect("Person", sorted(df["Assigned To"].dropna().unique()))
        fs = f2.multiselect("Status", db.STATUSES)
        fo = f3.checkbox("Overdue only")
        view = df
        if fp: view = view[view["Assigned To"].isin(fp)]
        if fs: view = view[view["Status"].isin(fs)]
        if fo: view = view[view["Overdue"] != ""]
        st.dataframe(show_df(view), hide_index=True, width="stretch")
        st.download_button("⬇️ Download as Excel", to_excel(view), "tasks.xlsx")

        st.divider()
        st.subheader("Edit / reassign / delete")
        pick = st.selectbox("Select task", [f"{t['id']} - {t['title']}" for t in tasks])
        task = next(t for t in tasks if t["id"] == int(pick.split(" - ")[0]))
        task_form(user, task)
        if st.button("🗑️ Delete this task"):
            st.session_state.confirm_del = task["id"]
        if st.session_state.get("confirm_del") == task["id"]:
            st.warning("Delete permanently?")
            if st.button("Yes, delete"):
                db.delete_task(task["id"], user["username"])
                st.session_state.confirm_del = None
                st.rerun()
        with st.expander("History and attachments"):
            for a in db.get_attachments(task["id"]):
                st.write("📎", os.path.basename(a["file_path"]))
            st.dataframe(pd.DataFrame(db.get_log(task["id"])), hide_index=True, width="stretch")


def page_review(user):
    st.header("Review queue")
    queue = [t for t in db.get_tasks() if t["status"] == "Submitted for Review"]
    if not queue:
        st.success("Nothing waiting for review.")
        return
    for t in queue:
        with st.expander(f"🟣 #{t['id']}  {t['title']}  —  {t['assignee']}  (due {t['due_date']})", expanded=True):
            st.write(t["description"] or "")
            if t["employee_remarks"]:
                st.info("Employee remarks: " + t["employee_remarks"])
            for a in db.get_attachments(t["id"]):
                with open(a["file_path"], "rb") as fh:
                    st.download_button("📎 " + os.path.basename(a["file_path"]), fh.read(),
                                       os.path.basename(a["file_path"]), key=f"dl{a['id']}")
            comment = st.text_area("Review comments", key=f"rc{t['id']}")
            c1, c2, c3 = st.columns(3)
            if c1.button("✅ Approve & complete", key=f"ap{t['id']}", type="primary"):
                db.update_task(t["id"], who=user["username"], status="Completed",
                               review_comments=comment, completed_date=date.today().isoformat())
                st.rerun()
            if c2.button("↩️ Send back for rework", key=f"rw{t['id']}"):
                db.update_task(t["id"], who=user["username"], status="Rework", review_comments=comment)
                st.rerun()


def page_team(user):
    st.header("Team")
    st.dataframe(pd.DataFrame(db.list_users(include_inactive=True)), hide_index=True, width="stretch")
    with st.form("add_user", clear_on_submit=True):
        st.subheader("Add a user")
        c1, c2, c3, c4 = st.columns(4)
        name = c1.text_input("Full name")
        uname = c2.text_input("Username")
        pw = c3.text_input("Temporary password", type="password")
        role = c4.selectbox("Role", ["employee", "admin"])
        if st.form_submit_button("Add"):
            try:
                if not (name and uname and pw):
                    st.error("All fields are required.")
                else:
                    db.add_user(name, uname.strip(), pw, role)
                    st.success("User added.")
            except Exception:
                st.error("That username already exists.")
    st.subheader("Reset password / deactivate")
    users = [u for u in db.list_users(include_inactive=True) if u["id"] != user["id"]]
    if users:
        sel = st.selectbox("User", [f"{u['id']} - {u['name']} ({u['username']})" for u in users])
        uid = int(sel.split(" - ")[0])
        c1, c2 = st.columns(2)
        newpw = c1.text_input("New password", type="password", key="resetpw")
        if c1.button("Reset password") and newpw:
            db.change_password(uid, newpw)
            st.success("Password reset.")
        u = next(x for x in users if x["id"] == uid)
        if c2.button("Deactivate" if u["active"] else "Reactivate"):
            db.set_user_active(uid, not u["active"])
            st.rerun()


def page_ai(user):
    st.header("🤖 AI Assistant (Google AI Studio / Gemini)")
    if not ai_helper.available():
        st.warning("No Gemini key found yet. Paste it below and click Save - no file editing needed.")
        key = st.text_input("Gemini API key (from aistudio.google.com)", type="password")
        if st.button("Save key") and key.strip():
            ai_helper.save_key(key)
            st.success("Key saved. Reloading...")
            st.rerun()
        st.caption(f"Key file location: {ai_helper.ENV_PATH}  |  file exists: {os.path.exists(ai_helper.ENV_PATH)}")
        return
    with st.expander("Model settings (use if you see a 404 or timeout error)"):
        st.write("Current model:", ai_helper.get_model())
        if st.button("Show models available to my key"):
            try:
                with st.spinner("Checking..."):
                    st.session_state.model_list = ai_helper.list_models()
            except Exception as e:
                st.error(f"Could not list models: {e}")
        if st.session_state.get("model_list"):
            st.write(st.session_state.model_list)
        new_model = st.text_input("Model name to use", value=ai_helper.get_model())
        if st.button("Save model") and new_model.strip():
            ai_helper.save_model(new_model)
            st.success("Saved.")
            st.rerun()
    employees = db.list_users(only_employees=True)
    names = {e["name"]: e["id"] for e in employees}
    st.subheader("Create a task by typing")
    text = st.text_area("Example: Ravi to reconcile HDFC bank for October by Friday, high priority")
    if st.button("Understand this instruction") and text:
        try:
            with st.spinner("Asking Gemini..."):
                st.session_state.parsed = ai_helper.parse_task(text, list(names))
        except Exception as e:
            st.error(f"AI error: {e}")
    p = st.session_state.get("parsed")
    if p:
        st.json(p)
        if st.button("Create this task", type="primary"):
            if p.get("assigned_to") in names:
                db.create_task(p.get("title") or "Untitled", p.get("description") or "",
                               p.get("client") or "", p.get("category") or "",
                               p.get("priority") if p.get("priority") in db.PRIORITIES else "Medium",
                               names[p["assigned_to"]], p.get("due_date"), user["username"])
                st.success("Task created.")
                st.session_state.parsed = None
            else:
                st.error("Could not match an employee. Use the Tasks page to assign manually.")
    st.divider()
    st.subheader("Weekly summary")
    if st.button("Generate summary"):
        try:
            with st.spinner("Asking Gemini..."):
                st.write(ai_helper.weekly_summary(db.get_tasks()))
        except Exception as e:
            st.error(f"AI error: {e}")


# ------------------------------------------------------------------ employee pages
def page_my_tasks(user):
    st.header(f"My tasks — {user['name']}")
    tasks = db.get_tasks(user_id=user["id"])      # restricted to own tasks
    if not tasks:
        st.info("No tasks assigned to you.")
        return
    c = st.columns(4)
    c[0].metric("Total", len(tasks))
    c[1].metric("In progress", sum(t["status"] == "In Progress" for t in tasks))
    c[2].metric("Overdue", sum(db.is_overdue(t) for t in tasks))
    c[3].metric("Completed", sum(t["status"] == "Completed" for t in tasks))
    for t in tasks:
        flag = " ⚠️ OVERDUE" if db.is_overdue(t) else ""
        with st.expander(f"{STATUS_ICON.get(t['status'], '')} #{t['id']}  {t['title']}  |  {t['status']}  |  due {t['due_date']}{flag}"):
            st.write(t["description"] or "")
            st.caption(f"Client: {t['client'] or '-'}  |  Priority: {t['priority']}")
            if t["review_comments"]:
                st.warning("Reviewer comments: " + t["review_comments"])
            locked = t["status"] in ("Completed", "Approved")
            if locked:
                st.success("This task is completed.")
                continue
            opts = db.EMPLOYEE_STATUSES
            cur = t["status"] if t["status"] in opts else "In Progress"
            new = st.selectbox("Status", opts, index=opts.index(cur), key=f"s{t['id']}")
            rem = st.text_area("Remarks", value=t["employee_remarks"] or "", key=f"r{t['id']}")
            up = st.file_uploader("Attach file", key=f"u{t['id']}")
            if st.button("Save update", key=f"b{t['id']}", type="primary"):
                db.update_task(t["id"], who=user["username"], employee_remarks=rem)
                if new != t["status"] or t["status"] == "Rework":
                    db.set_status(t["id"], new, user["username"])
                if up:
                    save_upload(t["id"], up)
                st.success("Updated.")
                st.rerun()


def page_password(user):
    st.header("Change password")
    with st.form("pw"):
        old = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        if st.form_submit_button("Change"):
            if db.login(user["username"], old) and len(new) >= 6:
                db.change_password(user["id"], new)
                st.success("Password changed.")
            else:
                st.error("Current password wrong, or new password shorter than 6 characters.")


# ------------------------------------------------------------------ main
def main():
    user = st.session_state.get("user")
    if not user:
        login_screen()
        return
    initials = "".join(w[0] for w in user["name"].split()[:2]).upper() or "U"
    st.sidebar.markdown(
        f'<div class="brand">✅ Work Tracker</div>'
        f'<div class="user-card"><div class="avatar"><span>{html.escape(initials)}</span></div>'
        f'<div><b>{html.escape(user["name"])}</b><br><small>{html.escape(user["role"].title())}</small></div></div>',
        unsafe_allow_html=True)
    if user["role"] == "admin":
        pages = {"📊  Dashboard": page_dashboard, "📝  Tasks": page_tasks, "🔍  Review queue": page_review,
                 "👥  Team": page_team, "🤖  AI Assistant": page_ai, "🔒  Change password": page_password}
    else:
        pages = {"📝  My tasks": page_my_tasks, "🔒  Change password": page_password}
    choice = st.sidebar.radio("Menu", list(pages), label_visibility="collapsed")
    st.sidebar.write("")
    if st.sidebar.button("Log out"):
        st.session_state.clear()
        st.rerun()
    pages[choice](user)


main()
