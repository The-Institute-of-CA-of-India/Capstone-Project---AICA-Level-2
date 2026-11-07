"""SQLAlchemy models for every table in the suite."""
import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utcnow():
    """Naive UTC timestamp (SQLite has no timezone type)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


Money = db.Numeric(14, 2)

ROLES = ("admin", "manager", "accountant", "approver", "field_staff")
ENTITY_TYPES = ("company", "llp", "firm", "proprietor", "trust", "aop")
VENDOR_CATEGORIES = ("goods", "services", "contractor", "professional", "other")
VENDOR_STATUSES = ("pending", "active", "blacklisted", "archived")
VENDOR_DOC_TYPES = ("pan_card", "gst_cert", "cancelled_cheque", "msme_cert", "other")
INVOICE_STATUSES = ("auto_captured", "pending_review", "reviewed", "pending_approval",
                    "approved", "rejected", "paid", "cancelled")
EXPENSE_CATEGORIES = ("Raw Materials", "Rent", "Professional Fees", "Contractor Services", "Utilities",
                      "Telecom & Internet", "IT & Software", "Travel & Conveyance", "Office Supplies",
                      "Repairs & Maintenance", "Marketing", "Freight & Logistics", "Commission", "Other")
# Statuses that count as real spend (accountant has validated the amounts)
SPEND_STATUSES = ("reviewed", "pending_approval", "approved", "paid")
# Statuses still owed to the vendor
OPEN_AP_STATUSES = ("reviewed", "pending_approval", "approved")
EDITABLE_STATUSES = ("auto_captured", "pending_review", "reviewed")


class BaseModel(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


user_clients = db.Table(
    "user_clients",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("client_id", db.Integer, db.ForeignKey("client.id"), primary_key=True),
)


class User(UserMixin, BaseModel):
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), nullable=False, default="accountant")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    must_change_password = db.Column(db.Boolean, default=True, nullable=False)
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime)
    last_login = db.Column(db.DateTime)
    clients = db.relationship("Client", secondary=user_clients, backref="assigned_users")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def sees_all_clients(self):
        return self.role in ("admin", "manager")

    def can_access_client(self, client_id):
        if self.sees_all_clients:
            return True
        return any(c.id == client_id for c in self.clients)

    def accessible_clients(self, include_archived=False):
        query = Client.query
        if not include_archived:
            query = query.filter_by(is_archived=False)
        if not self.sees_all_clients:
            ids = [c.id for c in self.clients]
            query = query.filter(Client.id.in_(ids))
        return query.order_by(Client.code).all()


class Client(BaseModel):
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    entity_type = db.Column(db.String(20), nullable=False, default="company")
    pan = db.Column(db.String(10))
    cin = db.Column(db.String(21))
    llpin = db.Column(db.String(8))
    gstin = db.Column(db.String(15))
    contact_person = db.Column(db.String(120))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    email_alias = db.Column(db.String(40), unique=True, nullable=False)
    vendor_registration_token = db.Column(db.String(36), unique=True, nullable=False,
                                          default=lambda: str(uuid.uuid4()))
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    vendors = db.relationship("Vendor", backref="client", lazy="dynamic")
    invoices = db.relationship("Invoice", backref="client", lazy="dynamic")
    cost_centres = db.relationship("CostCentre", backref="client", lazy="dynamic")


class Vendor(BaseModel):
    __table_args__ = (db.UniqueConstraint("client_id", "code", name="uq_vendor_client_code"),)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False, index=True)
    code = db.Column(db.String(10), nullable=False)
    trade_name = db.Column(db.String(200), nullable=False)
    legal_name = db.Column(db.String(200))
    pan = db.Column(db.String(10), index=True)
    gstin = db.Column(db.String(15), index=True)
    msme_registered = db.Column(db.Boolean, default=False, nullable=False)
    udyam_number = db.Column(db.String(25))
    bank_account_no = db.Column(db.String(30))
    bank_ifsc = db.Column(db.String(11))
    bank_branch = db.Column(db.String(120))
    contact_person = db.Column(db.String(120))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    category = db.Column(db.String(20), default="goods")
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    blacklist_reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    registered_by = db.Column(db.String(10), default="internal", nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    approved_at = db.Column(db.DateTime)
    documents = db.relationship("VendorDocument", backref="vendor", lazy="dynamic")
    approver = db.relationship("User", foreign_keys=[approved_by])


class VendorDocument(BaseModel):
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"), nullable=False, index=True)
    doc_type = db.Column(db.String(20), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    file_hash = db.Column(db.String(64))
    uploaded_at = db.Column(db.DateTime, default=utcnow)


class CostCentre(BaseModel):
    __table_args__ = (db.UniqueConstraint("client_id", "code", name="uq_cc_client_code"),)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("cost_centre.id"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    children = db.relationship("CostCentre", backref=db.backref("parent", remote_side="CostCentre.id"))


class Invoice(BaseModel):
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"), index=True)
    invoice_number = db.Column(db.String(60), index=True)
    invoice_date = db.Column(db.Date, index=True)
    due_date = db.Column(db.Date)
    source = db.Column(db.String(10), default="upload", nullable=False)
    source_email_subject = db.Column(db.String(300))
    source_email_from = db.Column(db.String(200))
    source_email_date = db.Column(db.String(60))
    original_filename = db.Column(db.String(255))
    original_filepath = db.Column(db.String(500))
    file_hash = db.Column(db.String(64), index=True)

    # OCR-extracted fields
    ocr_vendor_name = db.Column(db.String(200))
    ocr_gstin = db.Column(db.String(15))
    ocr_invoice_number = db.Column(db.String(60))
    ocr_invoice_date = db.Column(db.Date)
    ocr_total_amount = db.Column(Money)
    ocr_taxable_amount = db.Column(Money)
    ocr_cgst = db.Column(Money)
    ocr_sgst = db.Column(Money)
    ocr_igst = db.Column(Money)
    ocr_tds_applicable = db.Column(db.Boolean, default=False)
    ocr_tds_section = db.Column(db.String(10))
    ocr_tds_rate = db.Column(db.Numeric(5, 2))
    ocr_confidence_score = db.Column(db.Float, default=0.0)
    ocr_raw_text = db.Column(db.Text)
    ocr_field_confidence = db.Column(db.Text)  # JSON {field: 0.0-1.0}
    ocr_warnings = db.Column(db.Text)          # JSON list of strings

    # Validated / corrected fields
    final_vendor_name = db.Column(db.String(200))
    final_gstin = db.Column(db.String(15))
    final_invoice_number = db.Column(db.String(60))
    final_invoice_date = db.Column(db.Date)
    final_total_amount = db.Column(Money)
    final_taxable_amount = db.Column(Money)
    final_cgst = db.Column(Money)
    final_sgst = db.Column(Money)
    final_igst = db.Column(Money)
    final_tds_section = db.Column(db.String(10))
    final_tds_rate = db.Column(db.Numeric(5, 2))
    final_hsn_sac = db.Column(db.String(20))
    final_description = db.Column(db.Text)
    expense_category = db.Column(db.String(40), index=True)
    cost_centre_id = db.Column(db.Integer, db.ForeignKey("cost_centre.id"), index=True)
    gl_account = db.Column(db.String(120))
    narration = db.Column(db.Text)

    # Workflow
    status = db.Column(db.String(20), default="auto_captured", nullable=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_at = db.Column(db.DateTime)
    current_approver_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    current_level = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime)
    level_entered_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    approved_at = db.Column(db.DateTime)
    rejected_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    rejected_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    payment_date = db.Column(db.Date)
    payment_reference = db.Column(db.String(60))
    is_duplicate_flag = db.Column(db.Boolean, default=False, nullable=False)
    duplicate_of_id = db.Column(db.Integer, db.ForeignKey("invoice.id"))
    notes = db.Column(db.Text)
    synced_from_offline = db.Column(db.Boolean, default=False, nullable=False)

    vendor = db.relationship("Vendor", backref=db.backref("invoices", lazy="dynamic"))
    cost_centre = db.relationship("CostCentre", backref=db.backref("invoices", lazy="dynamic"))
    line_items = db.relationship("InvoiceLineItem", backref="invoice", cascade="all, delete-orphan",
                                 order_by="InvoiceLineItem.id")
    logs = db.relationship("ApprovalLog", backref="invoice", order_by="ApprovalLog.acted_at")
    uploader = db.relationship("User", foreign_keys=[uploaded_by])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    current_approver = db.relationship("User", foreign_keys=[current_approver_id])
    approver = db.relationship("User", foreign_keys=[approved_by])
    rejecter = db.relationship("User", foreign_keys=[rejected_by])
    duplicate_of = db.relationship("Invoice", remote_side="Invoice.id", foreign_keys=[duplicate_of_id])

    @property
    def amount(self):
        return self.final_total_amount if self.final_total_amount is not None else self.ocr_total_amount

    @property
    def display_vendor(self):
        if self.vendor:
            return self.vendor.trade_name
        return self.final_vendor_name or self.ocr_vendor_name or "Unknown vendor"

    @property
    def display_number(self):
        return self.final_invoice_number or self.invoice_number or self.ocr_invoice_number or "-"

    @property
    def display_date(self):
        return self.final_invoice_date or self.invoice_date or self.ocr_invoice_date

    @property
    def tds_amount(self):
        if self.final_tds_rate and self.final_taxable_amount:
            return round(float(self.final_taxable_amount) * float(self.final_tds_rate) / 100, 2)
        return 0.0


class InvoiceLineItem(BaseModel):
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False, index=True)
    description = db.Column(db.String(300))
    hsn_sac = db.Column(db.String(10))
    quantity = db.Column(db.Numeric(12, 3))
    unit_price = db.Column(Money)
    taxable_amount = db.Column(Money)
    cgst_rate = db.Column(db.Numeric(5, 2))
    cgst_amount = db.Column(Money)
    sgst_rate = db.Column(db.Numeric(5, 2))
    sgst_amount = db.Column(Money)
    igst_rate = db.Column(db.Numeric(5, 2))
    igst_amount = db.Column(Money)
    total_amount = db.Column(Money)
    cost_centre_id = db.Column(db.Integer, db.ForeignKey("cost_centre.id"))


class ApprovalMatrix(BaseModel):
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False, index=True)
    min_amount = db.Column(Money, nullable=False, default=0)
    max_amount = db.Column(Money)  # null = no upper limit
    expense_category = db.Column(db.String(40))
    cost_centre_id = db.Column(db.Integer, db.ForeignKey("cost_centre.id"))
    approver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    approval_level = db.Column(db.Integer, default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    approver = db.relationship("User")
    cost_centre = db.relationship("CostCentre")


class ApprovalLog(BaseModel):
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    actor_role = db.Column(db.String(20))
    level = db.Column(db.Integer)
    comments = db.Column(db.Text)
    acted_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    actor = db.relationship("User")


class Budget(BaseModel):
    __table_args__ = (db.UniqueConstraint("client_id", "cost_centre_id", "period_year", "period_month",
                                          name="uq_budget_period"),)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False, index=True)
    cost_centre_id = db.Column(db.Integer, db.ForeignKey("cost_centre.id"), nullable=False)
    gl_account = db.Column(db.String(120))
    category = db.Column(db.String(40))
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)
    budget_amount = db.Column(Money, nullable=False, default=0)
    notes = db.Column(db.Text)
    cost_centre = db.relationship("CostCentre")


class EmailConfig(BaseModel):
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), unique=True, nullable=False)
    imap_server = db.Column(db.String(120))
    imap_port = db.Column(db.Integer, default=993)
    email_address = db.Column(db.String(120))
    email_password_encrypted = db.Column(db.Text)
    poll_interval_minutes = db.Column(db.Integer, default=5)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    last_poll_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    client = db.relationship("Client", backref=db.backref("email_config", uselist=False))


class AuditLog(BaseModel):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    action = db.Column(db.String(20), nullable=False, index=True)
    entity_type = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    user = db.relationship("User")


class OfflineSyncQueue(BaseModel):
    client_uuid = db.Column(db.String(36), unique=True, index=True)  # makes retried syncs idempotent
    device_id = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action_type = db.Column(db.String(20), nullable=False)
    payload = db.Column(db.Text)
    created_at_device = db.Column(db.DateTime)
    synced_at = db.Column(db.DateTime)
    sync_status = db.Column(db.String(10), default="pending", nullable=False, index=True)
    conflict_details = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"))
    resolved = db.Column(db.Boolean, default=False, nullable=False)
    user = db.relationship("User")
    invoice = db.relationship("Invoice")
