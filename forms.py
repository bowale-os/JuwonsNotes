from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, URL, Length, Optional
from flask_wtf.file import FileField, FileAllowed

class LoginForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SeriesForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired(), Length(max=50)])
    submit = SubmitField('Create Series')

class PostForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired(), Length(max=25)])
    content = TextAreaField('Post Content', validators=[DataRequired()])
    pic = FileField('Add Image File', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Please upload images only.'), Optional()])
    image_url = StringField('Or Add Image URL', validators=[Optional(), URL("Please add a valid URL.")])
    series_id = SelectField('Series ID', coerce=str, validators=[DataRequired('Every post should have a Series')])

    def validate(self, extra_validators=None):
        if not super().validate:
            return False
        
        if not self.pic.data and not self.image_url.data:
            self.image_url.errors.append('Please add an image file or a valid URL.')
            return False
        return True