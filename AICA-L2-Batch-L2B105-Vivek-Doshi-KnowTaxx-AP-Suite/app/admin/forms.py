from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, SelectMultipleField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError

from ..clients.forms import strip
from ..models import ROLES
from ..utils import password_problem


class UserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(3, 64)], filters=[strip])
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)], filters=[strip])
    email = StringField("Email", validators=[Optional(), Email(check_deliverability=False)], filters=[strip])
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    role = SelectField("Role", choices=[(r, r.replace("_", " ").title()) for r in ROLES])
    client_ids = SelectMultipleField("Assigned clients", coerce=int,
                                     description="Used by accountant and field staff roles. Admins and managers see all clients.")
    temp_password = PasswordField("Temporary password", validators=[Optional()],
                                  description="The user must change it at first login. Leave blank on edit to keep the current password.")
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save user")

    def validate_temp_password(self, field):
        if field.data:
            problem = password_problem(field.data)
            if problem:
                raise ValidationError(problem)


class EmailConfigForm(FlaskForm):
    client_id = SelectField("Client", coerce=int, validators=[DataRequired()])
    imap_server = StringField("IMAP server", validators=[DataRequired(), Length(max=120)], default="imap.gmail.com", filters=[strip])
    imap_port = IntegerField("IMAP port", default=993, validators=[DataRequired(), NumberRange(1, 65535)])
    email_address = StringField("Email address", validators=[DataRequired(), Email(check_deliverability=False)], filters=[strip])
    email_password = PasswordField("Password / app password", validators=[Optional()],
                                   description="Stored encrypted. For Gmail, use an App Password. Leave blank to keep the saved one.")
    poll_interval_minutes = IntegerField("Poll every (minutes)", default=5, validators=[DataRequired(), NumberRange(1, 1440)])
    is_active = BooleanField("Listener active")
    submit = SubmitField("Save settings")
