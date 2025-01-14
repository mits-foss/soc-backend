from flask import Flask, jsonify, request, redirect, session, render_template,abort
from flask_cors import CORS
from oauth import fetch_github_user, get_github_token
from utils import calculate_leaderboard, fetch_user_repos, load_filter_list, update_leaderboard
import db
import logging
import os
from re import match 
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True)

app.secret_key = os.getenv('SECRET_KEY', 'supersecretWOOOOOOOOOOOO')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173/finish')

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


@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Missing code parameter'}), 400
    try:
        token = get_github_token(code)
        try:
            ensure_db_connection()
            db.save_token(token)
        except Exception as e:
            return jsonify({'error': f"{e}"})
        
        github_user = fetch_github_user(token)
        logging.debug(f"GitHub user response: {github_user}")
        info = [github_user['login'],github_user['avatar_url'],github_user['html_url']]
        logging.info(info)
        return redirect(f"{FRONTEND_URL}/finish/?login={info[0]}&avatar_url={info[1]}&html_url={info[2]}")

    except Exception as e:
        logging.error(f"OAuth callback error: {str(e)}")
        return redirect(f'{FRONTEND_URL}/')  # Retry OAuth flow

@app.route('/register', methods=['POST'])
def submit_user():
    # Get data as json
    data = request.get_json()
    
    name = data.get('name')
    contact = data.get('contact')
    email = data.get('email')
    
    # Further parse user data
    user = data.get('user')
    
    github_user = str(user['login'])
    avatar = str(user['avatar'])
    link = str(user['html_url'])
    
    
    logging.debug(f"Received: email={email}, phone={contact}, name={name}, token={user}")
    
    # Checking for validity
    if len(contact) < 10:
        return jsonify({'error': f"Invalid phone number. Received the number {contact}, which is not an valid Indian mobile number"})
    
    if not match(r'^\d{2}(cs|ct|ad|me|ce|ee|ec|cy)\d{3}@mgits\.ac\.in$', email):
        return jsonify({'error': f"Invalid email. Received the email {email}, which is not an valid mgits email"})
    
    # Adding user to the database
    try:
        ensure_db_connection()
        if not github_user:
            raise Exception("Missing GitHub user or token in session.")
        logging.warning(type(avatar))
        db.save_user_to_db(github_user, name, email, contact, avatar, link)        
        
        return jsonify({'success': 'Request completed sucessfully'})
    
    except Exception as e:
        return jsonify({'error': f"{e}"})
        

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
