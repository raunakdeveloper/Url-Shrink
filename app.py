from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
from flask_session import Session
from datetime import datetime
import os
import random
import string
from dotenv import load_dotenv
import bcrypt
import smtplib
from email.mime.text import MIMEText

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# MongoDB configuration
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
mongo = PyMongo(app)

# Session config
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# OTP generation and email configuration
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp):
    message_body = f"""
    Hi there,

    Your One-Time Password (OTP) for the bLink Shortener application is: **{otp}**.

    Please enter this OTP to complete your registration process. Once registered, you can log in with your email and password.

    Note: This OTP is valid for a limited time and should not be shared with anyone.

    Thank you,
    bLink Shortener Team
    """
    
    msg = MIMEText(message_body)
    msg['Subject'] = 'bLink Shortener Registration OTP Code'
    msg['From'] = os.getenv('OTP_EMAIL')
    msg['To'] = email
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(os.getenv('OTP_EMAIL'), os.getenv('OTP_EMAIL_PASSWORD'))
        server.sendmail(msg['From'], [email], msg.as_string())

# Routes for authentication
@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('index')) 
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        existing_user = mongo.db.loginUsers.find_one({'email': email})  # Updated collection name
        if existing_user:
            flash("Email already registered!")
            return redirect(url_for('register'))

        otp = generate_otp()
        send_otp_email(email, otp)
        session['pending_user'] = {
            'username': username,
            'email': email,
            'password': bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()),
            'otp': otp
        }
        
        return redirect(url_for('verify_otp'))
    return render_template('register.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'pending_user' not in session:
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        input_otp = request.form['otp']
        if input_otp == session['pending_user']['otp']:
            user_data = session.pop('pending_user')
            mongo.db.loginUsers.insert_one({  # Updated collection name
                'username': user_data['username'],
                'email': user_data['email'],
                'password': user_data['password'],
                'urls': []
            })
            flash("Registration successful! Please login.")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP! Please try again.")
    
    return render_template('verify_otp.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None  # Initialize the error variable
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = mongo.db.loginUsers.find_one({'email': email})  # Updated collection name

        # Check if the email exists
        if user is None:
            error = "This email is not registered. Please check or register."
        elif not bcrypt.checkpw(password.encode('utf-8'), user['password']):
            error = "Invalid password! Please try again."
        else:
            session['user'] = {'username': user['username'], 'email': user['email']}
            return redirect(url_for('index'))

    # Render the login template with the error variable
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("You have been logged out.")
    return redirect(url_for('home'))

# URL Shortener and Dashboard
def generate_random_string(length=4):
    characters = string.ascii_letters
    return ''.join(random.choice(characters) for _ in range(length))

@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('home'))
    total_urls = mongo.db.urls.count_documents({'user_email': session['user']['email']})
    return render_template('index.html', total_urls=total_urls)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('home'))
    urls = list(mongo.db.urls.find({'user_email': session['user']['email']}))
    total_urls = len(urls)
    return render_template('dashboard.html', urls=urls, user=session['user'], total_urls=total_urls)

@app.route('/shorten', methods=['POST'])
def shorten_url():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    original_url = request.form['url']
    existing_url = mongo.db.urls.find_one({'original_url': original_url, 'user_email': session['user']['email']})
    if existing_url:
        short_url = request.host_url + existing_url['short_hash']
        return render_template('shortened.html', short_url=short_url, message="This URL has already been shortened.")
    
    while True:
        random_string = generate_random_string()
        if not mongo.db.urls.find_one({'short_hash': random_string}):
            break

    short_url = request.host_url + random_string
    mongo.db.urls.insert_one({
        'user_email': session['user']['email'],
        'short_hash': random_string,
        'original_url': original_url,
        'created_at': datetime.utcnow()
    })
    
    return render_template('shortened.html', short_url=short_url)

@app.route('/<short_hash>')
def redirect_url(short_hash):
    url_entry = mongo.db.urls.find_one({'short_hash': short_hash})
    if url_entry:
        return redirect(url_entry['original_url'])
    else:
        return "URL not found!", 404

@app.route('/delete/<short_hash>', methods=['POST'])
def delete_url(short_hash):
    if 'user' not in session:
        return redirect(url_for('home'))

    mongo.db.urls.delete_one({'short_hash': short_hash, 'user_email': session['user']['email']})
    flash("URL deleted successfully!")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
