from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from ..clients.forms import MoneyField, strip, upper
from ..models import EXPENSE_CATEGORIES
from ..utils import valid_gstin

TDS_SECTIONS = ["", "194C", "194H", "194I", "194J", "194Q", "195"]


class ReviewForm(FlaskForm):
    final_vendor_name = StringField("Vendor name", validators=[Optional(), Length(max=200)], filters=[strip])
    vendor_id = SelectField("Linked vendor", coerce=int, default=0)
    final_gstin = StringField("Vendor GSTIN", validators=[Optional(), Length(max=15)], filters=[upper])
    final_invoice_number = StringField("Invoice number", validators=[Optional(), Length(max=60)], filters=[strip])
    final_invoice_date = DateField("Invoice date", validators=[Optional()])
    due_date = DateField("Due date", validators=[Optional()])
    final_taxable_amount = MoneyField("Taxable value", places=2, validators=[Optional(), NumberRange(min=0)])
    final_cgst = MoneyField("CGST", places=2, validators=[Optional(), NumberRange(min=0)])
    final_sgst = MoneyField("SGST", places=2, validators=[Optional(), NumberRange(min=0)])
    final_igst = MoneyField("IGST", places=2, validators=[Optional(), NumberRange(min=0)])
    final_total_amount = MoneyField("Total amount", places=2, validators=[Optional(), NumberRange(min=0)])
    final_tds_section = SelectField("TDS section", choices=[(s, s or "- None -") for s in TDS_SECTIONS],
                                    validators=[Optional()], validate_choice=False)
    final_tds_rate = DecimalField("TDS rate %", places=2, validators=[Optional(), NumberRange(0, 40)])
    final_hsn_sac = StringField("HSN / SAC", validators=[Optional(), Length(max=20)])
    expense_category = SelectField("Expense category", choices=[("", "- Select -")] + [(c, c) for c in EXPENSE_CATEGORIES],
                                   validators=[Optional()])
    cost_centre_id = SelectField("Cost centre", coerce=int, default=0)
    gl_account = StringField("GL account / ledger", validators=[Optional(), Length(max=120)])
    final_description = TextAreaField("Description", validators=[Optional()])
    narration = TextAreaField("Narration", validators=[Optional()])
    save = SubmitField("Save for later")
    submit_approval = SubmitField("Submit for approval")

    def validate_final_gstin(self, field):
        if field.data and not valid_gstin(field.data):
            raise ValidationError("Invalid GSTIN: format or check digit is wrong.")


class PaymentForm(FlaskForm):
    payment_date = DateField("Payment date", validators=[DataRequired()])
    payment_reference = StringField("UTR / reference", validators=[DataRequired(), Length(max=60)], filters=[strip])
    submit = SubmitField("Mark as paid")
