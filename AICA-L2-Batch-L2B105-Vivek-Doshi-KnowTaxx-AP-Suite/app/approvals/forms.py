from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError

from ..clients.forms import MoneyField
from ..models import EXPENSE_CATEGORIES


class MatrixRuleForm(FlaskForm):
    min_amount = MoneyField("From amount (₹)", default=0, validators=[Optional(), NumberRange(min=0)])
    max_amount = MoneyField("To amount (₹)", validators=[Optional(), NumberRange(min=0)],
                            description="Leave blank for no upper limit.")
    expense_category = SelectField("Expense category", choices=[("", "Any category")] + [(c, c) for c in EXPENSE_CATEGORIES])
    cost_centre_id = SelectField("Cost centre", coerce=int, default=0)
    approver_id = SelectField("Approver", coerce=int, validators=[DataRequired()])
    approval_level = IntegerField("Level", default=1, validators=[DataRequired(), NumberRange(1, 5)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save rule")

    def validate_max_amount(self, field):
        if field.data is not None and field.data < (self.min_amount.data or 0):
            raise ValidationError("Must be at least the 'from' amount.")
