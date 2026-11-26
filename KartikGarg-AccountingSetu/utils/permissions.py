"""Role-based permissions. Mirrors public.has_permission() in database/migrations/002_rls.sql."""
from __future__ import annotations

ROLES = {
    "firm_admin": "Firm Admin",
    "partner": "CA / Partner",
    "accountant": "Accountant",
    "audit_staff": "Audit Staff",
    "gst_executive": "GST Executive",
    "reviewer": "Reviewer",
    "read_only": "Read-Only Staff",
}

PERMISSIONS = {
    "view": "View assigned clients' data",
    "manage_firm": "Edit firm profile, branding and settings",
    "manage_staff": "Add/edit staff and permissions",
    "manage_clients": "Create/edit clients, invite client users, assign staff",
    "view_all_clients": "Access every client of the firm (not only assigned ones)",
    "upload_documents": "Upload documents on behalf of clients",
    "review_documents": "Review and correct extracted document data, add notes",
    "approve_documents": "Approve/reject documents for accounting",
    "prepare_vouchers": "Create and edit draft vouchers, manual journals, opening balances",
    "approve_vouchers": "Approve vouchers (post to books)",
    "manage_ledgers": "Create ledgers and ledger mappings",
    "bank_reconcile": "Import bank statements, match and reconcile",
    "gst_prepare": "Prepare GST returns and GSTR-2B reconciliation",
    "gst_approve": "Approve GST return preparation data",
    "generate_reports": "Generate financial reports",
    "approve_reports": "Approve and share reports with clients",
    "export_tally": "Export vouchers to Tally",
    "finalize_period": "Finalize and lock accounting months",
    "reopen_period": "Reopen finalized months",
    "view_audit": "View audit trail",
}

_ALL = set(PERMISSIONS)

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "firm_admin": set(_ALL),
    "partner": _ALL - {"manage_firm", "manage_staff"},
    "accountant": {"view", "upload_documents", "review_documents", "approve_documents", "prepare_vouchers",
                   "manage_ledgers", "bank_reconcile", "generate_reports", "export_tally"},
    "audit_staff": {"view", "review_documents", "generate_reports", "view_audit"},
    "gst_executive": {"view", "review_documents", "gst_prepare", "generate_reports"},
    "reviewer": {"view", "review_documents", "approve_documents", "approve_vouchers", "approve_reports",
                 "generate_reports"},
    "read_only": {"view"},
}

# Client portal users get a fixed, minimal permission set on their own client only.
CLIENT_PERMISSIONS = {"view", "client_upload", "client_submit", "client_respond"}


def effective_permissions(role: str, overrides: dict | None) -> set[str]:
    perms = set(ROLE_PERMISSIONS.get(role, set()))
    overrides = overrides or {}
    perms |= {p for p in overrides.get("grant", []) if p in PERMISSIONS}
    perms -= set(overrides.get("revoke", []))
    return perms


class PermissionDenied(Exception):
    """Raised when the authenticated user is not allowed to perform an action."""


class NotFound(Exception):
    """Raised when a record does not exist *or* is outside the user's tenant scope."""
