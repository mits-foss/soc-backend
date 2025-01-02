import random
import requests
import logging
from flask import redirect
import datetime
import time
logging.basicConfig(level=logging.DEBUG)


def calculate_leaderboard(client):
    pr_list = client.execute("""
    SELECT pr_id, repo_name, github_login
    FROM pull_requests
    """).fetchall()
    
    leaderboard = {}
    for pr in pr_list:
        pr_id, repo, github_login = pr
        pr_details = fetch_pr_details(repo, pr_id, client)
        
        if not pr_details:
            continue
        
        # Map github_login to user_id
        user_id_row = client.execute("SELECT id FROM users WHERE github_id = ?", (github_login,)).fetchone()
        if not user_id_row:
            continue

        user_id = user_id_row[0]
        
        if user_id not in leaderboard:
            leaderboard[user_id] = {
                'total_prs': 0,
                'total_commits': 0,
                'total_lines': 0
            }
        
        leaderboard[user_id]['total_prs'] += 1
        leaderboard[user_id]['total_commits'] += pr_details['commits']
        leaderboard[user_id]['total_lines'] += pr_details['additions'] - pr_details['deletions']
    
    result = []
    for user_id, stats in leaderboard.items():
        user_name = client.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()[0]
        result.append((user_name, stats['total_prs'], stats['total_commits'], stats['total_lines']))

    result.sort(key=lambda x: x[1], reverse=True)
    return result


def random_api_key(client):
    res = client.execute("SELECT key FROM api_keys")
    res=list(res)
    if not res:
        raise Exception("No API keys available. Please log in users to add tokens.")
    return random.choice(res)[0]
    
def remove_invalid_key(client, key):
    logging.warning(f"Removing token {key} from db due to invalidity.")
    client.execute("DELETE FROM api_keys WHERE key = ?", (key,))
    client.commit()

def fetch_user_repos(username, client):
    tokens = client.execute("SELECT key FROM api_keys").fetchall()

    if not tokens:
        logging.warning("No tokens available. Redirecting to refresh login.")
        return None

    random.shuffle(tokens)  # Shuffle tokens for random access
    for token in tokens:
        url = f"https://api.github.com/users/{username}/repos"
        headers = {'Authorization': f'token {token[0]}'}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if response.status_code in [401, 403]:  # Unauthorized or rate-limited
                logging.error(f"Token {token[0]} failed (status {response.status_code}). Removing...")
                remove_invalid_key(client, token[0])
            else:
                logging.error(f"Failed to fetch repos for {username}: {e}")
                raise e

    raise Exception("All tokens failed or rate-limited.")

def update_leaderboard(client):
    try:
        cursor = client.cursor()
        
        # Ensure all users exist in leaderboard (initialize with 0s)
        cursor.execute("""
        INSERT OR IGNORE INTO leaderboard (user_id, total_prs, total_commits, total_lines)
        SELECT id, 0, 0, 0 FROM users
        """)
        
        cursor.execute("""
        INSERT INTO leaderboard (user_id, total_prs, total_commits, total_lines)
        SELECT users.id, COUNT(pull_requests.pr_id), SUM(pull_requests.total_commits), SUM(pull_requests.total_lines)
        FROM users
        JOIN pull_requests ON users.github_id = pull_requests.github_login
        GROUP BY users.id
        ON CONFLICT(user_id) DO UPDATE SET
        total_prs = leaderboard.total_prs + excluded.total_prs,
        total_commits = leaderboard.total_commits + excluded.total_commits,
        total_lines = leaderboard.total_lines + excluded.total_lines;
        """)
        
        logging.debug("Leaderboard updated.")
        client.commit()
        cursor.close()
        
    except Exception as e:
        logging.error(f"Error updating leaderboard: {str(e)}")


def load_filter_list():
    with open('filter.txt', 'r') as f:
        return [line.strip() for line in f if line.strip()]

def fetch_filtered_prs(client):
    repos = load_filter_list()
    pr_count = 0
    
    for repo in repos:
        prs = fetch_recent_prs(repo, client)  
        if not prs:
            logging.info(f"No PRs found for {repo}. Skipping...")
            continue

        for pr in prs:
            github_login = pr['user']['login'] if 'user' in pr else None
            if not github_login:
                logging.warning(f"PR {pr['id']} missing user login. Skipping...")
                continue

            pr_details = fetch_pr_details(repo, pr['id'], client)
            if not pr_details:
                logging.warning(f"Skipping PR {pr['id']} - Failed to fetch details.")
                continue

            total_commits = pr_details.get('commits', 0)
            total_lines = pr_details.get('additions', 0) - pr_details.get('deletions', 0)

            user_exists = client.execute(
                "SELECT 1 FROM users WHERE github_id = ?",
                (github_login,)
            ).fetchone()

            if not user_exists:
                logging.warning(f"User {github_login} not found. Skipping PR {pr['id']}.")
                continue

            existing_pr = client.execute(
                "SELECT pr_id FROM pull_requests WHERE pr_id = ?",
                (pr['id'],)
            ).fetchone()

            if existing_pr:
                logging.debug(f"PR {pr['id']} already exists. Updating...")
                client.execute("""
                UPDATE pull_requests
                SET total_commits = ?, total_lines = ?
                WHERE pr_id = ?
                """, (total_commits, total_lines, pr['id']))
            else:
                logging.info(f"Inserting new PR {pr['id']}")
                client.execute("""
                INSERT INTO pull_requests (pr_id, repo_name, github_login, total_commits, total_lines)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    pr['id'],
                    repo,
                    github_login,
                    total_commits,
                    total_lines
                ))
                pr_count += 1

    client.commit()
    logging.info(f"Fetched {pr_count} new PRs.")
    return pr_count

def fetch_recent_prs(repo, client):
    token = random_api_key(client)
    url = f"https://api.github.com/repos/{repo}/pulls?state=open"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()  
    elif response.status_code == 403:
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            wait_time = int(retry_after)
        else:
            reset_time = int(response.headers.get('X-RateLimit-Reset', time.time()))
            wait_time = max(reset_time - int(datetime.datetime.now().timestamp()), 60)
        logging.warning(f"Rate limit hit. Sleeping for {wait_time} seconds...")
        time.sleep(wait_time + 1)
        return fetch_recent_prs(repo, client)



def insert_pull_request(client, pr, repo):
    github_login = pr['user']['login']
    pr_details = fetch_pr_details(repo, pr['id'], client)
    
    if pr_details:
        client.execute("""
        INSERT INTO pull_requests (pr_id, repo_name, github_login, total_commits, total_lines)
        VALUES (?, ?, ?, ?, ?)
        """, (
            pr['id'],
            repo,
            github_login,
            pr_details['commits'],
            pr_details['additions'] - pr_details['deletions']
        ))
        logging.info(f"Inserted PR {pr['id']} by {github_login} for {repo}")
    else:
        logging.warning(f"Skipping PR {pr['id']} due to missing details.")
    
    client.commit()

def fetch_pr_details(repo, pr_id, client):
    token = random_api_key(client)

    # Fetch all open PRs and match the pr_id manually
    url = f"https://api.github.com/repos/{repo}/pulls"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        pr_list = response.json()
        
        # Search for matching PR by ID
        matched_pr = next((pr for pr in pr_list if pr['id'] == pr_id), None)
        if not matched_pr:
            logging.warning(f"PR {pr_id} not found in the open PR list for {repo}")
            return None
        
        # Fetch detailed info using the pulls_url
        detail_url = matched_pr['url']  # This is the correct URL for the PR
        details_response = requests.get(detail_url, headers=headers)

        if details_response.status_code == 200:
            pr_details = details_response.json()
            return {
                'commits': pr_details['commits'],
                'additions': pr_details['additions'],
                'deletions': pr_details['deletions']
            }
        else:
            logging.warning(f"Failed to fetch detailed PR data: {details_response.status_code}")
            return None
    else:
        logging.error(f"Failed to fetch open PRs for {repo}: {response.status_code}")
        return None
