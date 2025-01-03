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
    logging.warning(f"db.client type before check: {type(db.client)}")
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
        ensure_db_connection()  # Ensure db.client is valid before use
        github_user = fetch_github_user(db.client, token)
        logging.debug(f"GitHub user response: {github_user}")

        # Check if the user is already logged in (based on session)
        if 'github_id' in session and session['github_id'] == github_user['login']:
            logging.info(f"User {github_user['login']} already logged in. Redirecting to dashboard.")
            return redirect('/dashboard')

        # Check if the user exists in the database
        existing_user = db.client.execute("""
        SELECT * FROM users WHERE github_id = ?
        """, (github_user['login'],)).fetchone()

        if existing_user:
            logging.info(f"User {github_user['login']} found in DB. Logging in directly.")
            session['github_id'] = github_user['login']
            session['user_id'] = existing_user[0]  # Store user ID in session
            return redirect('/dashboard')
        
        # If user not found, ask for email/phone to create new entry
        session['temp_user'] = github_user
        session['temp_token'] = token

        return render_template('email_phone_form.html', github_user=github_user)

    except Exception as e:
        logging.error(f"OAuth callback error: {str(e)}")
        return redirect('/login')  # Retry OAuth flow

@app.route('/submit_user', methods=['POST'])
def submit_user():
    email = request.form['email']
    phone = request.form['phone']
    github_user = session.get('temp_user')
    token = session.get('temp_token')
    
    logging.debug(f"Received: email={email}, phone={phone}, user={github_user}, token={token}")
    
    if 'mgits' not in email:
        return jsonify({'error': f"Invalid email. Received: email={email}, phone={phone}, user={github_user}, token={token}"})
    
    try:
        ensure_db_connection()
        if not github_user or not token:
            raise Exception("Missing GitHub user or token in session.")
        
        db.save_user_to_db(github_user, email, phone, token)
        
        db.client.execute("""
        INSERT INTO api_keys (key)
        VALUES (?)
        ON CONFLICT(key) DO NOTHING
        """, (token,))
        db.client.commit()

        # Clear temp session data
        session.pop('temp_token')

        session['user_id'] = github_user['id']
        return redirect('/dashboard')
    
    except Exception as e:
        logging.error(f"Failed to save user: {str(e)}")
        return redirect('/login')

@app.route('/refresh_login')
def refresh_login():
    session.clear()
    ensure_db_connection()
    db.client.execute("DELETE FROM api_keys WHERE key NOT IN (SELECT token FROM users)")
    db.client.commit()
    return redirect(get_github_login_url())
@app.route('/dashboard')
def dashboard():
    github_user = session.get('temp_user')
    if not github_user:
        return redirect('/login')  

    try:
        user = db.client.execute(
            "SELECT * FROM users WHERE github_id = ?",
            (github_user['login'],)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        repos = fetch_user_repos(github_user['login'], db.client)
        user_data = {
            'SOCid': user[0],
            'username': user[1],
            'email': user[3],
            'repos': [
                {
                    'repo_name': repo['name'],
                    'last_commit': repo['updated_at']
                }
                for repo in repos
            ] if repos else []
        }
        return jsonify({'user': user_data})
    except Exception as e:
        logging.error(f"Failed to fetch dashboard: {str(e)}")
        return jsonify({'error': 'Failed to load dashboard'}), 500

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
    SELECT users.name, leaderboard.total_prs,leaderboard.points
    FROM leaderboard
    JOIN users ON leaderboard.user_id = users.id
    ORDER BY leaderboard.total_prs DESC
    """).fetchall()

    return jsonify({'leaderboard': leaderboard_data})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
