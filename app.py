from flask import Flask, jsonify, request, redirect, session, render_template,abort
from oauth import get_github_login_url, fetch_github_user, get_github_token
from utils import calculate_leaderboard, fetch_user_repos, load_filter_list, update_leaderboard
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
    SOCname = request.form['name']
    
    github_user = session.get('temp_user')
    token = session.get('temp_token')
    
    logging.debug(f"Received: email={email}, phone={phone}, user={github_user}, token={token}")
    
    if 'mgits' not in email:
        return jsonify({'error': f"Invalid email. Received: email={email}, phone={phone}, user={github_user}, token={token}"})
    
    try:
        ensure_db_connection()
        if not github_user or not token:
            raise Exception("Missing GitHub user or token in session.")
        
        db.save_user_to_db(github_user, email, phone, token,SOCname)
        
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

@app.route('/dashboard')
def dashboard():
    github_user = session.get('github_id') 
    if not github_user:
        return redirect('/login')  

    try:
        user = db.client.execute(
            "SELECT * FROM users WHERE github_id = ?",
            (github_user,)
        ).fetchone()

        if not user:
            return jsonify({'error': 'User not found'}), 404
    
        # Fetch repos directly from pull requests table
        pr_repos = db.client.execute("""
        SELECT DISTINCT repo_name FROM pull_requests WHERE github_login = ?
        """, (github_user,)).fetchall()

        # Fetch allowed repos from filter.txt
        allowed_repos = load_filter_list()
        allowed_repo_names = {repo.split('/')[-1] for repo in allowed_repos}

        # Filter PR repos based on allowed repos
        filtered_repos = [
            {'repo_name': repo[0]}
            for repo in pr_repos
            if repo[0].split('/')[-1] in allowed_repo_names
        ]

        user_prs = db.client.execute("""
        SELECT repo_name, status, pr_id
        FROM pull_requests
        WHERE github_login = ?
        """, (github_user,)).fetchall()

        pr_list = [
            {
                'repo_name': pr[0],
                'status': pr[1],
                'pr_id': pr[2]
            }
            for pr in user_prs
        ]

        user_data = {
            'SOCid': user[0],
            'username': user[1],
            'email': user[3],
            'contributed_repos': filtered_repos,
            'pull_requests': pr_list
        }

        return jsonify({'user': user_data})

    except Exception as e:
        logging.error(f"Failed to fetch dashboard: {str(e)}")
        return jsonify({'error': 'Failed to load dashboard'}), 500

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

@app.route('/webhook', methods=['POST'])
def github_webhook():
    payload = request.json
    event = request.headers.get('X-GitHub-Event', '')

    if not payload or 'pull_request' not in payload:
        abort(400)

    pr = payload['pull_request']
    action = payload.get('action')

    if action in ['opened', 'synchronize', 'closed']:
        repo = payload['repository']['full_name']
        github_login = pr['user']['login']
        pr_id = pr['id']
        commits = pr['commits']
        additions = pr['additions']
        deletions = pr['deletions']
        status = 'merged' if pr.get('merged', False) else pr['state']

        ensure_db_connection()
        db.client.execute("""
        INSERT INTO pull_requests (pr_id, repo_name, github_login, total_commits, total_lines, status)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(pr_id) DO UPDATE SET
        total_commits = excluded.total_commits,
        total_lines = excluded.total_lines,
        status = excluded.status
        """, (pr_id, repo, github_login, commits, additions - deletions, status))

        db.client.commit()
        update_leaderboard(db.client)

    return jsonify({'status': 'ok'})

@app.route('/api/user/<github_id>/prs')
def user_prs(github_id):
    limit = request.args.get('limit', 10)
    offset = request.args.get('offset', 0)
    user_prs = db.client.execute("""
    SELECT pr_id, repo_name, total_commits, total_lines, status
    FROM pull_requests
    WHERE github_login = ?
    LIMIT ? OFFSET ?
    """, (github_id, limit, offset)).fetchall()

    if not user_prs:
        return jsonify({'message': 'No PRs found'}), 404

    pr_list = [{'pr_id': pr[0], 'repo': pr[1], 'commits': pr[2], 'lines': pr[3], 'status': pr[4]} for pr in user_prs]
    return jsonify({'prs': pr_list})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
