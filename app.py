from flask import Flask, render_template, request, redirect, url_for
from flask_pymongo import PyMongo
from datetime import datetime
import os
import random
import string
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# MongoDB configuration
app.config['MONGO_URI'] = f"mongodb+srv://{os.environ.get('MONGO_USER')}:{os.environ.get('MONGO_PASS')}@url-short-python.br0gv.mongodb.net/{os.environ.get('MONGO_DB')}?retryWrites=true&w=majority"
mongo = PyMongo(app)

# Function to generate a random 4-character string
def generate_random_string(length=4):
    characters = string.ascii_letters  # Contains both lowercase and uppercase letters
    return ''.join(random.choice(characters) for _ in range(length))

# Root route to display the form for shortening URLs
@app.route('/')
def index():
    # Count the total number of shortened URLs
    total_urls = mongo.db.urls.count_documents({})
    return render_template('index.html', total_urls=total_urls)

# Route to shorten the URL
@app.route('/shorten', methods=['POST'])
def shorten_url():
    original_url = request.form['url']
    
    # Check if the original URL already exists
    existing_url = mongo.db.urls.find_one({'original_url': original_url})
    if existing_url:
        # If it exists, return the existing short URL
        short_url = request.host_url + existing_url['short_hash']
        return render_template('shortened.html', short_url=short_url, message="This URL has already been shortened.")

    # Generate a unique 4-character string for the URL
    while True:
        random_string = generate_random_string()
        # Check if this short code already exists
        if not mongo.db.urls.find_one({'short_hash': random_string}):
            break

    short_url = request.host_url + random_string

    # Store the mapping in MongoDB with a timestamp
    mongo.db.urls.insert_one({
        'short_hash': random_string,
        'original_url': original_url,
        'created_at': datetime.utcnow()  # Store the current timestamp in UTC
    })

    return render_template('shortened.html', short_url=short_url)

# Route to display all shortened URLs
@app.route('/display')
def display_urls():
    # Retrieve all shortened URLs to display
    urls = mongo.db.urls.find()
    total_urls = mongo.db.urls.count_documents({})
    return render_template('display.html', urls=urls, total_urls=total_urls)

# Route to redirect to the original URL
@app.route('/<short_hash>')
def redirect_url(short_hash):
    url_entry = mongo.db.urls.find_one({'short_hash': short_hash})
    if url_entry:
        return redirect(url_entry['original_url'])
    else:
        return "URL not found!", 404

# Route to delete a shortened URL
@app.route('/delete/<short_hash>', methods=['POST'])
def delete_url(short_hash):
    mongo.db.urls.delete_one({'short_hash': short_hash})
    return redirect(url_for('display_urls'))

if __name__ == '__main__':
    app.run(debug=True)
