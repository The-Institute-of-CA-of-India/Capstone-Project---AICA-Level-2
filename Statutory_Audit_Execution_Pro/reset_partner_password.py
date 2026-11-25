"""Emergency recovery - run ONLY on the server computer. Not reachable from the web interface.
Resets a Partner password, then PROVES the new password works, and shows which data file it changed."""
import getpass, sys
try:
    from auditexec.core import database as db
    db.init_db()
except Exception as e:
    print("\nCould not open the database:", e); input("\nPress Enter to close"); sys.exit(1)

print("\nThis data file is being used:\n   ", db.DB_PATH)
print("\nAll logins in it:")
for r in db.query("SELECT username,name,role,active FROM users ORDER BY id"):
    print(f"   {r['username']:<14}{r['name']:<22}{r['role']:<9}{'active' if r['active'] else 'DISABLED'}")
un = input("\nType the Partner username to reset (e.g. vivek): ").strip().lower()
row = db.one("SELECT * FROM users WHERE lower(username)=? AND role='Partner'", (un,))
if not row:
    print("No Partner with that username in the list above. Nothing was changed."); input("\nPress Enter to close"); sys.exit(1)
pw = input("Type the NEW password (min 6 characters; it is shown on screen so you can see it): ").strip()
if len(pw) < 6:
    print("Too short. Nothing was changed."); input("\nPress Enter to close"); sys.exit(1)
db.execute("UPDATE users SET password_hash=?, active=1, must_change=1 WHERE id=?", (db.new_hash(pw), row["id"]))
db.execute("DELETE FROM login_attempts")
u, msg = db.login(un, pw)
if u:
    print(f"\nSUCCESS. Sign in as  {un}  with password  {pw}\nYou will then be asked to choose your own password (type this one as the 'current password').")
else:
    print("\nFAILED - the new password did not verify:", msg)
print("\nIMPORTANT: make sure the server window (START_SERVER.bat) is the one started from THIS same folder:\n   ", db.ROOT)
input("\nPress Enter to close")
