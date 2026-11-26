"""Live Row Level Security check against SUPABASE_DB_URL. Everything runs in ONE transaction that is rolled back.

    python -m scripts.rls_check

Creates two firms (A, B), staff (admin A, unassigned accountant A, admin B), clients (A1, A2, B1), client users,
documents/vouchers/audit rows, then queries as each user with role 'authenticated' + JWT claims and asserts isolation.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.apply_migrations import connect  # noqa: E402

U = lambda: str(uuid.uuid4())  # noqa: E731
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


def main():
    c = connect()
    c.run("begin")
    try:
        ids = {k: U() for k in ("sa", "adminA", "acctA", "adminB", "cuA1", "cuB1", "firmA", "firmB", "A1", "A2", "B1",
                                "stA", "stAcct", "stB", "docA1", "docB1", "ledA1", "ledA1b", "vA1")}
        for k, sa in (("sa", True), ("adminA", False), ("acctA", False), ("adminB", False), ("cuA1", False), ("cuB1", False)):
            c.run("insert into user_profiles(id,email,full_name,is_super_admin) values (:i,:e,:n,:s)",
                  i=ids[k], e=f"{k}@rlscheck.invalid", n=k, s=sa)
        for f in ("firmA", "firmB"):
            c.run("insert into firms(id,name,email,status) values (:i,:n,:e,'active')", i=ids[f], n=f, e=f"{f}@x.invalid")
        c.run("insert into firm_staff(id,firm_id,user_id,role) values (:i,:f,:u,'firm_admin')", i=ids["stA"], f=ids["firmA"], u=ids["adminA"])
        c.run("insert into firm_staff(id,firm_id,user_id,role) values (:i,:f,:u,'accountant')", i=ids["stAcct"], f=ids["firmA"], u=ids["acctA"])
        c.run("insert into firm_staff(id,firm_id,user_id,role) values (:i,:f,:u,'firm_admin')", i=ids["stB"], f=ids["firmB"], u=ids["adminB"])
        for cl, f in (("A1", "firmA"), ("A2", "firmA"), ("B1", "firmB")):
            c.run("insert into clients(id,firm_id,name) values (:i,:f,:n)", i=ids[cl], f=ids[f], n=cl)
        c.run("insert into client_staff_assignments(id,firm_id,client_id,staff_id) values (:i,:f,:c,:s)",
              i=U(), f=ids["firmA"], c=ids["A1"], s=ids["stAcct"])
        c.run("insert into client_users(id,firm_id,client_id,user_id) values (:i,:f,:c,:u)", i=U(), f=ids["firmA"], c=ids["A1"], u=ids["cuA1"])
        c.run("insert into client_users(id,firm_id,client_id,user_id) values (:i,:f,:c,:u)", i=U(), f=ids["firmB"], c=ids["B1"], u=ids["cuB1"])
        for d, cl, f in (("docA1", "A1", "firmA"), ("docB1", "B1", "firmB")):
            c.run("insert into documents(id,firm_id,client_id,period_year,period_month,original_filename,storage_path,sha256) "
                  "values (:i,:f,:c,2025,4,'x.pdf',:p,'h')", i=ids[d], f=ids[f], c=ids[cl], p=f"{ids[f]}/{ids[cl]}/x.pdf")
        c.run("insert into ledgers(id,firm_id,client_id,name,group_name,nature) values (:i,:f,:c,'Cash','Cash-in-Hand','asset')",
              i=ids["ledA1"], f=ids["firmA"], c=ids["A1"])
        c.run("insert into ledgers(id,firm_id,client_id,name,group_name,nature) values (:i,:f,:c,'Rent','Indirect Expenses','expense')",
              i=ids["ledA1b"], f=ids["firmA"], c=ids["A1"])
        c.run("insert into accounting_vouchers(id,firm_id,client_id,voucher_type,voucher_no,voucher_date,fy_label,total_amount) "
              "values (:i,:f,:c,'Journal','J1','2025-04-10','2025-26',100)", i=ids["vA1"], f=ids["firmA"], c=ids["A1"])
        c.run("insert into accounting_voucher_entries(id,firm_id,client_id,voucher_id,line_no,ledger_id,dr_cr,amount) values "
              "(:i,:f,:c,:v,1,:l,'Dr',100)", i=U(), f=ids["firmA"], c=ids["A1"], v=ids["vA1"], l=ids["ledA1b"])
        c.run("insert into accounting_voucher_entries(id,firm_id,client_id,voucher_id,line_no,ledger_id,dr_cr,amount) values "
              "(:i,:f,:c,:v,2,:l,'Cr',90)", i=U(), f=ids["firmA"], c=ids["A1"], v=ids["vA1"], l=ids["ledA1"])
        c.run("insert into audit_logs(id,firm_id,user_id,action,entity_type) values (:i,:f,:u,'x','y')", i=U(), f=ids["firmA"], u=ids["adminA"])

        def as_user(key, sql, **params):
            c.run("savepoint q")
            c.run("set local role authenticated")
            c.run("select set_config('request.jwt.claims', :cl, true)", cl=json.dumps({"sub": ids[key], "role": "authenticated"}))
            try:
                rows = c.run(sql, **params)
                err = None
            except Exception as exc:  # noqa: BLE001
                rows, err = None, str(exc)
                if "--debug" in sys.argv:
                    print("ERR", key, sql[:60], err[:300])
            c.run("rollback to savepoint q")
            c.run("reset role")
            return rows, err

        def names(key, table="clients"):
            rows, err = as_user(key, f"select name from {table} order by name" if table == "clients" else f"select id from {table}")
            return sorted(r[0] for r in rows) if rows is not None else err

        check("Firm A admin sees only firm A clients", names("adminA") == ["A1", "A2"], names("adminA"))
        check("Firm B admin sees only firm B clients", names("adminB") == ["B1"], names("adminB"))
        check("Unassigned accountant sees only assigned client", names("acctA") == ["A1"], names("acctA"))
        check("Client user A1 sees only own client", names("cuA1") == ["A1"], names("cuA1"))
        check("Client user B1 sees only own client", names("cuB1") == ["B1"], names("cuB1"))
        check("Super admin cannot read tenant clients", names("sa") == [], names("sa"))
        rows, _ = as_user("adminA", "select id from documents")
        check("Firm A cannot read firm B documents", rows is not None and [str(r[0]) for r in rows] == [ids["docA1"]], rows)
        rows, _ = as_user("cuA1", "select id from documents")
        check("Client A1 cannot read client B1 documents", rows is not None and [str(r[0]) for r in rows] == [ids["docA1"]], rows)
        rows, _ = as_user("adminB", "select id from accounting_vouchers")
        check("Firm B cannot read firm A vouchers", rows == [], rows)
        rows, _ = as_user("adminB", "update clients set name = 'hacked' where id = :i returning id", i=ids["A1"])
        check("Firm B cannot update firm A client", rows == [], rows)
        rows, err = as_user("adminB", "insert into documents(id,firm_id,client_id,period_year,period_month,original_filename,storage_path,sha256) "
                                      "values (:i,:f,:c,2025,4,'evil.pdf','p','h')", i=U(), f=ids["firmA"], c=ids["A1"])
        check("Firm B cannot insert into firm A client", err is not None, err)
        rows, _ = as_user("cuA1", "select id from audit_logs")
        check("Client cannot read audit log", rows == [], rows)
        rows, err = as_user("adminA", "delete from audit_logs returning id")
        check("Audit log is append-only (delete removes nothing)", err is not None or rows == [], err or rows)
        rows, _ = as_user("adminA", "select id from storage.objects")
        check("Storage objects query runs under RLS", rows is not None, rows)
        # trigger checks run as owner (bypass RLS) — they guard everyone
        c.run("savepoint t")
        try:
            c.run("update accounting_vouchers set status='approved' where id = :i", i=ids["vA1"])
            check("Unbalanced voucher cannot be approved (trigger)", False, "update succeeded")
        except Exception as exc:  # noqa: BLE001
            check("Unbalanced voucher cannot be approved (trigger)", "Unbalanced" in str(exc), str(exc)[:80])
        c.run("rollback to savepoint t")
        c.run("insert into accounting_periods(id,firm_id,client_id,fy_label,year,month,status) values (:i,:f,:c,'2025-26',2025,4,'finalized')",
              i=U(), f=ids["firmA"], c=ids["A1"])
        c.run("savepoint t2")
        try:
            c.run("update accounting_vouchers set narration='edit' where id = :i", i=ids["vA1"])
            check("Finalized period blocks voucher edits (trigger)", False, "update succeeded")
        except Exception as exc:  # noqa: BLE001
            check("Finalized period blocks voucher edits (trigger)", "finalized" in str(exc), str(exc)[:80])
        c.run("rollback to savepoint t2")
    finally:
        c.run("rollback")
    left = c.run("select count(*) from user_profiles")[0][0]
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   -> {detail}"))
    print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed; rolled back (user_profiles rows now: {left})")
    if not all(ok for _, ok, _ in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
