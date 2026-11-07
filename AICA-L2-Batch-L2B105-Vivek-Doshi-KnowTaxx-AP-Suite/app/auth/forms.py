from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, ValidationError

from ..utils import password_problem


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired()],
                                 description="At least 8 characters, with a letter and a digit.")
    confirm_password = PasswordField("Confirm new password",
                                     validators=[DataRequired(), EqualTo("new_password", "Passwords do not match.")])
    submit = SubmitField("Change password")

    def validate_new_password(self, field):
        problem = password_problem(field.data)
        if problem:
            raise ValidationError(problem)
        if field.data == self.current_password.data:
            raise ValidationError("The new password must differ from the current one.")
