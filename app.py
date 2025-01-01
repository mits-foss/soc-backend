from flask import Flask, jsonify, request, redirect, session, render_template
from oauth import get_github_login_url, fetch_github_user, get_github_token
from utils import calculate_leaderboard, random_api_key, fetch_user_repos
import db
import logging
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretWOOOOOOOOOOOO')

logging.basicConfig(level=logging.DEBUG)

# Ensure DB connection is valid
def ensure_db_connection():
    if not isinstance(db.client, db.sqlite3.Connection):
        db.client = db.connect_db()

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
        
        session['temp_user'] = github_user
        session['temp_token'] = token

        ensure_db_connection()  # Make sure DB is connected
        db.client.execute("""
            INSERT INTO api_keys (key)
            VALUES (?)
            ON CONFLICT(key) DO NOTHING
        """, (token,))
        db.client.commit()

        # Render form for email and phone input
        return render_template('email_phone_form.html', github_user=github_user)
    
    except Exception as e:
        logging.error(f"OAuth callback error: {str(e)}")
        return redirect('/login')

@app.route('/submit_user', methods=['POST'])
def submit_user():
    email = request.form['email']
    phone = request.form['phone']
    github_user = session.get('temp_user')
    token = session.get('temp_token')

    if 'mgits' not in email:
        return jsonify({'error': 'Only MGITS users are allowed'})

    ensure_db_connection()
    db.save_user_to_db(github_user, email, phone, token)
    
    session.pop('temp_user')
    session.pop('temp_token')

    return redirect('/dashboard')

@app.route('/refresh_login')
def refresh_login():
    session.clear()
    ensure_db_connection()
    db.client.execute("DELETE FROM api_keys WHERE key NOT IN (SELECT token FROM users)")
    db.client.commit()
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

@app.route('/token_status')
def token_status():
    ensure_db_connection()
    tokens = db.client.execute("SELECT key FROM api_keys").fetchall()
    return jsonify({'active_tokens': tokens})

@app.route('/random_api_key')
def api_key():
    ensure_db_connection()
    key = random_api_key(db.client)
    return jsonify({'api_key': key})

@app.route('/leaderboard')
def leaderboard():
    ensure_db_connection()
    leaderboard_data = db.client.execute("""
    SELECT users.name, leaderboard.total_prs
    FROM leaderboard
    JOIN users ON leaderboard.user_id = users.id
    ORDER BY leaderboard.total_prs DESC
    """).fetchall()

    return jsonify({'leaderboard': leaderboard_data})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
