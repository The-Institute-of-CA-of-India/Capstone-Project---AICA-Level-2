from flask_wtf import FlaskForm
from wtforms import BooleanField, DecimalField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError

from ..models import ENTITY_TYPES
from ..utils import valid_gstin, valid_pan


def upper(value):
    return value.strip().upper() if isinstance(value, str) else value


def strip(value):
    return value.strip() if isinstance(value, str) else value


class MoneyField(DecimalField):
    """DecimalField that accepts Indian-formatted input such as 1,25,000.50."""

    def process_formdata(self, valuelist):
        if valuelist:
            valuelist = [v.replace(",", "").replace("₹", "").strip() for v in valuelist]
        super().process_formdata(valuelist)


class ClientForm(FlaskForm):
    name = StringField("Client name", validators=[DataRequired(), Length(max=200)], filters=[strip])
    entity_type = SelectField("Entity type", choices=[(e, e.upper() if e in ("llp", "aop") else e.title()) for e in ENTITY_TYPES])
    pan = StringField("PAN", validators=[Optional(), Length(max=10)], filters=[upper])
    cin = StringField("CIN", validators=[Optional(), Length(max=21)], filters=[upper])
    llpin = StringField("LLPIN", validators=[Optional(), Length(max=8)], filters=[upper])
    gstin = StringField("GSTIN", validators=[Optional(), Length(max=15)], filters=[upper])
    contact_person = StringField("Contact person", validators=[Optional(), Length(max=120)])
    contact_email = StringField("Contact email", validators=[Optional(), Email(check_deliverability=False)])
    contact_phone = StringField("Contact phone", validators=[Optional(), Length(max=20)])
    address = TextAreaField("Address", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save client")

    def validate_pan(self, field):
        if field.data and not valid_pan(field.data):
            raise ValidationError("PAN must be 5 letters, 4 digits, 1 letter (e.g. AAACA1234A).")

    def validate_gstin(self, field):
        if field.data and not valid_gstin(field.data):
            raise ValidationError("Invalid GSTIN: format or check digit is wrong.")


class CostCentreForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(max=20)], filters=[upper])
    name = StringField("Name", validators=[DataRequired(), Length(max=120)], filters=[strip])
    parent_id = SelectField("Parent", coerce=int, default=0)
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save cost centre")


class BudgetForm(FlaskForm):
    cost_centre_id = SelectField("Cost centre", coerce=int, validators=[DataRequired()])
    period_year = IntegerField("Year", validators=[DataRequired(), NumberRange(2000, 2100)])
    period_month = SelectField("Month", coerce=int, choices=[
        (m, n) for m, n in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)])
    budget_amount = MoneyField("Budget amount (₹)", validators=[DataRequired(), NumberRange(min=0)])
    gl_account = StringField("GL account", validators=[Optional(), Length(max=120)])
    notes = StringField("Notes", validators=[Optional()])
    submit = SubmitField("Save budget")
