from flask import Flask, jsonify, request, redirect, session
from oauth import get_github_login_url, fetch_github_user, get_github_token
from utils import calculate_leaderboard, fetch_user_repos
import db
import logging
import os
from dotenv import load_dotenv
from db import client


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretWOOOOOOOOOOOO')

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
        github_user = fetch_github_user(db.client, token)
        db.save_user_to_db(github_user, token)
        
        db.client.execute("""
        INSERT INTO api_keys (key)
        VALUES (?)
        ON CONFLICT(key) DO NOTHING
        """, (token,))
        db.client.commit()

        session['user_id'] = github_user['id']
        return jsonify({'message': 'Login successful', 'user': github_user})
    
    except Exception as e:
        logging.error(f"OAuth callback error: {str(e)}")
        return redirect('/login')  # Retry OAuth flow

@app.route('/refresh_login')
def refresh_login():
    session.clear()
    return redirect(get_github_login_url())
@app.route('/dashboard')
def dashboard():
    users = db.get_all_users()
    leaderboard = calculate_leaderboard(db.client)
    
    for user in users:
        repos = fetch_user_repos(user['username'], db.client)
        if repos is None:
            return redirect('/refresh_login')  # Perform redirect if no tokens
        
        user['repos'] = [
            {
                'repo_name': repo['name'],
                'last_commit': repo['updated_at']
            }
            for repo in repos
        ]

    return jsonify({'users': users, 'leaderboard': leaderboard})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)