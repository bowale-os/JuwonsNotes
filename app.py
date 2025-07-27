from datetime import datetime, timezone
from flask import Flask, render_template, url_for, jsonify, redirect, request, flash, session
from forms import LoginForm, PostForm, SeriesForm
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from functools import wraps
import uuid  
import os
from firebasesetup import initialize_firebase_admin
from google.cloud import firestore 

firebase = initialize_firebase_admin()
firestore_db = firebase["firestore"]
storage_bucket = firebase["storage"]

load_dotenv(override=True, verbose=True)
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notes.db'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# app.config['UPLOAD_FOLDER'] = 'static/uploads'
predef_username = os.getenv('USERNAME')
predef_password = os.getenv('PASSWORD')
print("Loaded USERNAME:", predef_username)
print("Loaded PASSWORD:", predef_password)


def login_required(route_f):
    @wraps(route_f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            flash("You need to log in in order to access that page.", 'warning')
            return redirect(url_for('login'))
        return route_f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        name = form.name.data
        password = form.password.data

        if name == predef_username and password == predef_password:
            session['logged_in'] = True
            session['username'] = name
            flash("✅ You are logged in!", "success")
            return redirect(url_for('admin_suite'))
        else:
            flash("❌ Invalid credentials. Try again.", "danger")
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash("You are logged out")
    return redirect(url_for('login'))


# Routes
@app.route('/')
def home():
    posts_docs = (
    firestore_db.collection('posts')
    .order_by('published_at', direction=firestore.Query.DESCENDING)
    .stream()
)
    posts = []
    for doc in posts_docs:
        post_data = doc.to_dict()
        post_data['id'] = doc.id

        series_id = post_data.get('series_id')
        if series_id:
            series_doc = firestore_db.collection('series').document(series_id).get()
            if series_doc.exists:
                series_title = series_doc.to_dict().get('title', "Unknown Series")
            post_data['series'] = series_title
        else:
            return "Unavailable at this time",404
        post_data['days_ago'] = (datetime.now(timezone.utc) - post_data['published_at']).days
        posts.append(post_data)
    
    series_docs = firestore_db.collection('series').stream()
    series = []
    for doc in series_docs:
        series_data = doc.to_dict()
        series_data['id'] = doc.id
        series_data['post_amount'] = len([p for p in posts if p.get('series_id') == doc.id])


        last_three_posts = sorted(
            [p for p in posts if p.get('series_id') == doc.id],
            key=lambda x: x.get('published_at', ''),  # sort by published_at field
            reverse=True  # latest first
        )[:3]
        
        series_data['post_imgs'] = [p.get('image') for p in last_three_posts]

        series.append(series_data)

    return render_template('index.html', posts=posts, series=series)

@app.route('/view/<post_id>')
def view_post(post_id):
    post_ref = firestore_db.collection('posts').document(post_id)
    post_doc = post_ref.get()
    post = post_doc.to_dict()
    post['id'] = post_doc.id
    return render_template('view-post.html', post=post, name=predef_username)

@app.route('/series/<series_id>')
def view_series(series_id):
    series_ref = firestore_db.collection('series').document(series_id)
    series_doc = series_ref.get()

    if not series_doc.exists:
        return "Series not found", 404
    
    series = series_doc.to_dict()
    series['id'] = series_doc.id

    posts_query = firestore_db.collection('posts').where('series_id', '==', series['id'])
    posts_docs = posts_query.stream()

    posts = []
    for doc in posts_docs:
        post = doc.to_dict()
        post['id'] = doc.id
        posts.append(post)

    return render_template('view-series.html', series=series, posts=posts)

@app.route('/admin/suite')
@login_required
def admin_suite():
    posts_docs = firestore_db.collection('posts').stream()
    posts = []
    for doc in posts_docs:
        post_data = doc.to_dict()
        post_data['id'] = doc.id
        posts.append(post_data)
    return render_template('admin/admin-suite.html', posts=posts)

@app.route('/admin/create-post', methods=['GET','POST'])
@login_required
def create_post():
    form = PostForm()

    #choices look like : 'ID - Title'
    series_ref = firestore_db.collection('series')
    series_docs = series_ref.stream()
    series_choices = [(doc.id, doc.to_dict().get('title', '')) for doc in series_docs]
    form.series_id.choices = series_choices

    if form.validate_on_submit():
        if form.pic.data:
            filename = secure_filename(form.pic.data.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"

            blob = storage_bucket.blob(f'uploads/{unique_filename}')
            blob.upload_from_file(form.pic.data.stream, content_type=form.pic.data.content_type)
            blob.make_public()

            image_url = blob.public_url
        else:
            image_url = form.image_url.data

        now_utc = datetime.now(timezone.utc)
        post_data= {
            "title": form.title.data,
            "description": form.description.data,
            "content": form.content.data,
            "image": image_url,
            "series_id": form.series_id.data,
            "published_at": now_utc,
            "updated_at": now_utc,
        }

        try:
            write_result, doc_ref  = firestore_db.collection('posts').add(post_data)

            # update series timestamp
            firestore_db.collection('series').document(form.series_id.data).update({
                "updated_at": now_utc
                })
            
            
        except Exception as e:
            flash("Error saving post. Please try again.", "danger")
            print(f"Error saving post: {e}")
            return render_template('admin/create-post.html', form=form)


        flash("Post created successfully!", "success")
        print(f"Post saved successfully! Post ID: {doc_ref.id}")
        return redirect(url_for('view_post', post_id=doc_ref.id))
        
    return render_template('admin/create-post.html', form=form)


@app.route('/admin/create-series', methods=['GET','POST'])
@login_required
def create_series():
    form = SeriesForm()
    utc_now = datetime.now(timezone.utc)
    if form.validate_on_submit():

        series_data = {
            'title': form.title.data,
            'description': form.description.data,
            'start_date': utc_now,
            'updated_at': utc_now
            }
        
        try:
            write_result, series_ref = firestore_db.collection('series').add(series_data)
            
        except Exception as e:
            flash(f"Error saving post", 'error')
            print(f"Error saving post: {e}")
            return render_template('admin/create-series.html', form=form)

        # Redirect to series detail or post creation page with series preselected
        flash(f"Series '{series_data['title']}' created successfully!", "success")
        print(f"Post saved successfully! Post ID: {series_ref.id}")
        return redirect(url_for('create_post', series_id=series_ref.id))
        
    return render_template('admin/create-series.html', form=form)

# Uncomment and finish this when needed
# @app.route('/episode/<int:episode_id>')
# def read_episode(episode_id):
#     pass

if __name__ == '__main__':
    print("Application starting...")  # Debug line
    app.run(debug=True, port=5000)
    print("Application stopped") 
