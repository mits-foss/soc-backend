from flask import Flask, jsonify, request, redirect, session
from oauth import get_github_login_url, fetch_github_user, get_github_token
from utils import calculate_leaderboard, random_api_key
import db
import logging
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecret')

logging.basicConfig(level=logging.DEBUG)

@app.before_request
def init_db():
    if not hasattr(app, 'db_initialized'):
        db.setup_database()
        app.db_initialized = True

@app.route('/login')
def login():
    return redirect(get_github_login_url())

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Missing code parameter'}), 400

    try:
        token = get_github_token(code)
        github_user = fetch_github_user(token)
        db.save_user_to_db(github_user, token)
        session['user_id'] = github_user['id']
        return jsonify({'message': 'Login successful', 'user': github_user})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/dashboard')
def dashboard():
    users = db.get_all_users()
    leaderboard = calculate_leaderboard(db.client)
    return jsonify({'users': users, 'leaderboard': leaderboard})

@app.route('/random_api_key')
def api_key():
    key = random_api_key(db.client)
    return jsonify({'api_key': key})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
