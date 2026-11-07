from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import BooleanField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError

from ..clients.forms import strip, upper
from ..models import VENDOR_CATEGORIES, VENDOR_DOC_TYPES
from ..utils import IFSC_RE, UDYAM_RE, valid_gstin, valid_pan


class VendorFieldsMixin:
    trade_name = StringField("Trade name", validators=[DataRequired(), Length(max=200)], filters=[strip])
    legal_name = StringField("Legal name", validators=[Optional(), Length(max=200)], filters=[strip])
    pan = StringField("PAN", validators=[DataRequired(), Length(max=10)], filters=[upper])
    gstin = StringField("GSTIN", validators=[Optional(), Length(max=15)], filters=[upper],
                        description="Leave blank if not registered under GST.")
    category = SelectField("Category", choices=[(c, c.title()) for c in VENDOR_CATEGORIES])
    msme_registered = BooleanField("MSME registered")
    udyam_number = StringField("Udyam number", validators=[Optional(), Length(max=25)], filters=[upper],
                               description="Format: UDYAM-MH-12-1234567")
    bank_account_no = StringField("Bank account number", validators=[Optional(), Length(max=30)], filters=[strip])
    bank_ifsc = StringField("IFSC", validators=[Optional(), Length(max=11)], filters=[upper])
    bank_branch = StringField("Bank and branch", validators=[Optional(), Length(max=120)])
    contact_person = StringField("Contact person", validators=[Optional(), Length(max=120)])
    contact_email = StringField("Contact email", validators=[Optional(), Email(check_deliverability=False)], filters=[strip])
    contact_phone = StringField("Contact phone", validators=[Optional(), Length(max=20)])
    address = TextAreaField("Address", validators=[Optional()])

    def validate_pan(self, field):
        if not valid_pan(field.data):
            raise ValidationError("PAN must be 5 letters, 4 digits, 1 letter.")

    def validate_gstin(self, field):
        if field.data:
            if not valid_gstin(field.data):
                raise ValidationError("Invalid GSTIN: format or check digit is wrong.")
            if self.pan.data and field.data[2:12] != self.pan.data:
                raise ValidationError("The PAN embedded in this GSTIN does not match the PAN entered.")

    def validate_bank_ifsc(self, field):
        if field.data and not IFSC_RE.match(field.data):
            raise ValidationError("IFSC must look like HDFC0001234.")

    def validate_udyam_number(self, field):
        if field.data and not UDYAM_RE.match(field.data):
            raise ValidationError("Udyam number must look like UDYAM-MH-12-1234567.")
        if self.msme_registered.data and not field.data:
            raise ValidationError("Enter the Udyam number for an MSME vendor.")


class VendorForm(VendorFieldsMixin, FlaskForm):
    notes = TextAreaField("Internal notes", validators=[Optional()])
    confirm_duplicate = BooleanField("I have checked the possible duplicates above. Save anyway.")
    submit = SubmitField("Save vendor")


class PublicRegistrationForm(VendorFieldsMixin, FlaskForm):
    bank_account_no = StringField("Bank account number", validators=[DataRequired(), Length(max=30)], filters=[strip])
    bank_ifsc = StringField("IFSC", validators=[DataRequired(), Length(max=11)], filters=[upper])
    contact_person = StringField("Contact person", validators=[DataRequired(), Length(max=120)])
    contact_email = StringField("Contact email", validators=[DataRequired(), Email(check_deliverability=False)], filters=[strip])
    contact_phone = StringField("Contact phone", validators=[DataRequired(), Length(max=20)])
    doc_pan = FileField("PAN card copy (required)")
    doc_gst = FileField("GST certificate (required if you entered a GSTIN)")
    doc_cheque = FileField("Cancelled cheque (required)")
    doc_msme = FileField("MSME certificate (optional)")
    submit = SubmitField("Submit registration")


class VendorDocumentForm(FlaskForm):
    doc_type = SelectField("Document type", choices=[(d, d.replace("_", " ").title()) for d in VENDOR_DOC_TYPES])
    document = FileField("File (PDF, JPG or PNG)")
    submit = SubmitField("Upload")
