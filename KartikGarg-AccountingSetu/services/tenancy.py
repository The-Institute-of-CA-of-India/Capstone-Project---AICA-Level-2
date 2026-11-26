"""Tenant resolution and server-side authorization.

The AuthContext is built ONLY from the authenticated user id (see auth_service.build_context),
by reading membership tables. firm_id/client_id values coming from the UI are never trusted:
every service call re-checks them against the context with ``require_client`` /
``scoped_get`` before touching data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from services.db import get_db
from utils.permissions import CLIENT_PERMISSIONS, NotFound, PermissionDenied


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: str
    full_name: str
    kind: str  # 'super_admin' | 'staff' | 'client'
    firm_id: str | None = None
    firm_name: str | None = None
    firm_status: str | None = None
    staff_id: str | None = None
    role: str | None = None
    permissions: frozenset = field(default_factory=frozenset)
    client_id: str | None = None

    @property
    def is_super_admin(self) -> bool:
        return self.kind == "super_admin"

    @property
    def is_staff(self) -> bool:
        return self.kind == "staff"

    @property
    def is_client(self) -> bool:
        return self.kind == "client"

    def can(self, perm: str) -> bool:
        if self.kind == "staff" and self.firm_status != "active":
            return False
        return perm in self.permissions

    def require(self, perm: str) -> None:
        if not self.can(perm):
            raise PermissionDenied(f"You do not have permission: {perm}")

    def require_super_admin(self) -> None:
        if not self.is_super_admin:
            raise PermissionDenied("Super Admin access required")


def accessible_client_ids(ctx: AuthContext) -> list[str]:
    db = get_db()
    if ctx.is_client:
        return [ctx.client_id] if ctx.client_id else []
    if not ctx.is_staff or ctx.firm_status != "active":
        return []
    if ctx.can("view_all_clients"):
        rows = db.fetchall("select id from clients where firm_id = ?", [ctx.firm_id])
    else:
        rows = db.fetchall(
            "select a.client_id as id from client_staff_assignments a join clients c on c.id = a.client_id "
            "where a.staff_id = ? and c.firm_id = ?",
            [ctx.staff_id, ctx.firm_id],
        )
    return [r["id"] for r in rows]


def list_clients(ctx: AuthContext, include_inactive: bool = True) -> list[dict]:
    ids = accessible_client_ids(ctx)
    if not ids:
        return []
    db = get_db()
    marks = ",".join("?" for _ in ids)
    sql = f"select * from clients where id in ({marks}) and firm_id = ?"
    if not include_inactive:
        sql += " and status = 'active'"
    firm_id = ctx.firm_id
    return db.fetchall(sql + " order by name", [*ids, firm_id])


def require_client(ctx: AuthContext, client_id: str | None, perm: str = "view") -> dict:
    """Return the client row if the context may perform ``perm`` on it; else raise.

    Raises NotFound (not PermissionDenied) for out-of-scope clients so that the existence of
    another tenant's records is never revealed.
    """
    if not client_id:
        raise NotFound("Client not found")
    db = get_db()
    client = db.get("clients", client_id)
    if client is None:
        raise NotFound("Client not found")
    if ctx.is_client:
        if client_id != ctx.client_id:
            raise NotFound("Client not found")
        if perm not in CLIENT_PERMISSIONS:
            raise PermissionDenied(f"Client users cannot perform: {perm}")
        return client
    if not ctx.is_staff or client["firm_id"] != ctx.firm_id:
        raise NotFound("Client not found")
    if client_id not in accessible_client_ids(ctx):
        raise NotFound("Client not found")
    ctx.require(perm)
    return client


def scoped_get(ctx: AuthContext, table: str, row_id: str | None, perm: str = "view") -> dict:
    """Fetch a tenant-owned row (must have firm_id & client_id) and authorize it."""
    if not row_id:
        raise NotFound(f"{table} record not found")
    row = get_db().get(table, row_id)
    if row is None:
        raise NotFound(f"{table} record not found")
    client = require_client(ctx, row.get("client_id"), perm)
    if row.get("firm_id") != client["firm_id"]:
        raise NotFound(f"{table} record not found")
    return row


def require_firm(ctx: AuthContext, perm: str = "view") -> str:
    if not ctx.is_staff or not ctx.firm_id:
        raise PermissionDenied("Firm staff access required")
    ctx.require(perm)
    return ctx.firm_id
