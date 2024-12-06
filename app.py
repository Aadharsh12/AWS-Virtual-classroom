from flask import Flask, render_template, request, redirect, url_for, session, flash
import boto3
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# AWS Configuration
s3_client = boto3.client(
    's3',
    aws_access_key_id='AKIAXYKJQQ3OH5Z3I47H',  # Fetch from environment variables
    aws_secret_access_key='n4uMwrq/odi+Yi0cVUjpnmZy+EqXeNtjRU8yAwQM',  # Fetch from environment variables
    region_name='ap-south-1'  # e.g., 'us-east-1', 'ap-south-1', etc.
)
bucket_name = 'virtual-classroom-bucket'  # Replace with your bucket name

# RDS (MySQL) Configuration
db = pymysql.connect(
    host='virtual-classroom-db.czki2k6c89z0.ap-south-1.rds.amazonaws.com',
    user='admin',
    password='Admin1234',
    database='virtual_classroom'
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        role = 'student'  # Default role for new users is 'student'
        
        # Check if username already exists
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash("Username already exists. Please choose another.", "danger")
            return redirect(url_for('register'))
        
        cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, password, role))
        db.commit()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user[2], password):  # Assuming password is in the 2nd column
            session['user'] = user[1]  # Store username in session (user[1] is the username)
            session['role'] = user[3]  # Store user role in session
            flash('Login successful!', 'success')
            # Redirect to dashboard based on role
            if session['role'] == 'admin':
                return redirect(url_for('index'))
            else:
                return redirect(url_for('index'))
        else:
            session['error_message'] = 'Invalid username or password'  # Set the error message in session
            return redirect(url_for('login'))  # Redirect back to the login page

    # If it's a GET request or the login fails
    return render_template('login.html')




@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    # Fetch courses from the database
    cursor = db.cursor()
    cursor.execute("SELECT name, file_key, description FROM courses1")
    courses = cursor.fetchall()

    # Generate presigned URLs for each course
    courses_with_urls = [
        {
            'name': course[0],
            'file_url': s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': course[1]},
                ExpiresIn=3600
            ),
            'description': course[2]
        }
        for course in courses
    ]

    return render_template('dashboard.html', courses=courses_with_urls)

@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    flash("You have been logged out.", "info")  # Optional message
    return redirect(url_for('login'))  # Redirect to the login page


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user' not in session or session['role'] != 'admin':
        flash('You must be an admin to access this page.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        file = request.files['file']
        course_name = request.form['course_name']
        description = request.form['description']
        file_key = f"courses/{course_name}/{file.filename}"

        # Upload to S3
        s3_client.upload_fileobj(file, bucket_name, file_key)

        # Insert course metadata into database
        cursor = db.cursor()
        cursor.execute("INSERT INTO courses1 (name, file_key, description) VALUES (%s, %s, %s)", (course_name, file_key, description))
        db.commit()
        flash('File uploaded successfully!', 'success')
        return redirect(url_for('admin'))

    # Fetch all courses
    cursor = db.cursor()
    cursor.execute("SELECT name, file_key, description FROM courses1")
    courses = cursor.fetchall()

    # Generate presigned URLs for each course
    courses_with_urls = [
        {
            'name': course[0],
            'file_url': s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': course[1]},
                ExpiresIn=3600
            ),
            'description': course[2]
        }
        for course in courses
    ]

    return render_template('admin.html', courses=courses_with_urls)


@app.route('/courses')
def courses():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor()
    cursor.execute("SELECT name, file_key, description FROM courses1")
    courses = cursor.fetchall()
    return render_template('course.html', courses=courses)

@app.route('/download/<path:file_key>')
def download(file_key):
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': file_key},
        ExpiresIn=3600  # Link expires in 1 hour
    )
    return redirect(url)

if __name__ == "__main__":
    app.run(debug=True)
