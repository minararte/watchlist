from flask import Flask, render_template, url_for, redirect, request, session, current_app, flash
from flask_wtf import FlaskForm
import uuid
from wtforms import SubmitField, IntegerField, StringField, FileField, PasswordField, TextAreaField
from wtforms.validators import  InputRequired, NumberRange, Length, EqualTo, Email
from pymongo import MongoClient
from dataclasses import dataclass, field
import os
from werkzeug.utils import secure_filename
import base64
from passlib.hash import pbkdf2_sha256
import functools
import dotenv
import os

dotenv.load_dotenv()


ALLOWED_EXTENSIONS = {'jpg', 'png', 'jpeg', 'webp', 'webm'}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
client = MongoClient (os.getenv("MONGODB_URI"))
app.db = client.movies


class movie_form(FlaskForm):
    title = StringField("Title", validators=[InputRequired()])
    director = StringField("Director", validators=[InputRequired()])
    year = IntegerField("Year", validators=[InputRequired(), NumberRange(min=1878, max=2025)])
    genre = StringField("Genre", validators=[InputRequired()])
    duration = IntegerField("Duration(Min)", validators=[InputRequired(), NumberRange(min=1, max=999)])
    coverpage = FileField('Cover Page', validators=[InputRequired()])
    synopsis = StringField('Synopsis', validators=[InputRequired()])
    embed = StringField('https://www.youtube.com/embed/<video_id>', validators=[InputRequired()])
    cast = StringField('Cast', validators=[InputRequired()])
    submit = SubmitField("Add Movie")

class register_form(FlaskForm):
    email = StringField("E-mail", validators=[InputRequired(), Email()])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=8, max=30)])
    confirm_password = PasswordField('Confirm password', validators=[InputRequired(), EqualTo("password")])
    submit = SubmitField("Register")

class login_form(FlaskForm):
    email = StringField("E-mail", validators=[InputRequired(), Email()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Login")

class comments_form(FlaskForm):
    comment = TextAreaField("Add comment:", validators=[Length(min=1, max=500), InputRequired()])
    submit = SubmitField("Send")

@dataclass
class movieObject:
    _id: str
    title: str
    director: str
    year: int
    genre: str
    duration: int
    synopsis: str
    coverpage: str
    embed: str
    cast: str
    rating: int = 0
    comments = str

@dataclass
class User:
    _id : str
    email: str
    password: str
    movies: list[str] = field(default_factory=list)

@dataclass
class Comment:
    movie_id: str
    comment: str
    _id: str
    nickname: str

def login_required(route):
    @functools.wraps(route)
    def route_wrapper(*args, **kwargs):
        if not session.get("email"):
            return redirect(url_for('login'))
        return route(*args, **kwargs)
    return route_wrapper

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    movies_data = current_app.db.movies.find({})
    movies = [movieObject(**movie) for movie in movies_data]
    return render_template('index.html',
                           email=session.get('email'),
                           title="Watchlist",
                           theme=session.get('theme'),
                           movies=movies)




@app.route("/add", methods=["GET", "POST"])
def add_movie():
    form = movie_form()
    if form.validate_on_submit():
        img = form.coverpage.data
        img = form.coverpage.data
        if img and allowed_file(img.filename):
            filename = secure_filename(img.filename)
            coverpage_bytes = img.read()
            coverpage_bytes_encoded = base64.b64encode(coverpage_bytes).decode('utf-8')
            movie = (movieObject
            (
                _id= uuid.uuid4().hex,
                title= form.title.data,
                director= form.director.data,
                year= form.year.data,
                genre= form.genre.data,
                duration= form.duration.data,
                synopsis= form.synopsis.data,
                coverpage= coverpage_bytes_encoded,
                embed = form.embed.data,
                cast = form.cast.data
                 )
        )
        current_app.db.movies.insert_one((movie.__dict__))
        return redirect(url_for('index'))
    return render_template('new_movie.html', title="Add Movie", form=form, email=session.get('email'))



@app.get("/movie/details/<string:_id>")
def movie_details(_id: str):
    comment_data = current_app.db.comments.find({"movie_id": _id})
    comments = [Comment(**comment) for comment in comment_data]
    movie_data = current_app.db.movies.find_one({"_id": _id})
    movie = movieObject(**movie_data)
    return render_template('movie_details.html', movie=movie,
                            title=movie.title,
                            email=session.get('email'),
                            form2=comments_form(),
                            comments=comments)


@app.route('/register', methods=["POST", "GET"])
def register():
    form = register_form()
    if session.get("email"):
        return redirect(url_for('index'))
    if form.validate_on_submit():
        user = User(
            _id= uuid.uuid4().hex,
            email= form.email.data,
            password= pbkdf2_sha256.hash(form.password.data)
        )
        current_app.db.users.insert_one((user.__dict__))
        return redirect(url_for('index'))

    return render_template('register.html', title="Register", form=form)

@app.route("/login", methods=["GET", "POST"])
def login():
    form = login_form()
    if form.validate_on_submit():
        user_data = current_app.db.users.find_one({"email": form.email.data})
        if not user_data:
            flash("Invalid e-mail or password")
            return redirect(url_for('login'))
        user = User(**user_data)    
        if user_data and pbkdf2_sha256.verify(form.password.data, user.password):
            session['user_id'] = user._id
            session['email'] = user.email

            return redirect(url_for('index'))
        else:
            flash("Incorrect e-mail or password.")
            return redirect(url_for('login'))
    print(session.get('email'))
    return render_template('login.html', form=form, email=session.get('email'))

@app.get('/movie/details/<string:_id>/rate')
@login_required
def rate(_id):
    rating = request.args.get("rating")
    rating_int = int(rating)
    current_app.db.movies.update_one({"_id": _id}, {"$set": {"rating": rating_int}})
    return redirect(url_for("movie_details", _id=_id))

@app.route('/movie/details/<string:_id>/comment', methods=["POST"])
@login_required
def comments(_id: str):
    movie_data = current_app.db.movies.find_one({"_id": _id})
    movie = movieObject(**movie_data)
    form2 = comments_form()
    if form2.validate_on_submit():
        comment = Comment(
            movie_id= _id,
            _id=uuid.uuid4().hex,
            comment= form2.comment.data,
            nickname= session.get('email').split('@')[0]
        )
        current_app.db.comments.insert_one(comment.__dict__)
        return redirect(url_for("movie_details", _id=_id))
    else:
        print(form2.errors)
    return redirect(url_for('movie_details', _id=_id))


@app.get('/toggle_theme')
def toggle_theme():
    current_theme = session.get('theme')
    if current_theme == 'dark':
        session['theme'] = 'light'
    else:
        session['theme'] = 'dark'
    return redirect(request.args.get("current_page"))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)
