import random
import requests
import logging
from flask import redirect
import datetime
import time


def calculate_leaderboard(client):
    res = client.execute("""
    SELECT users.name, COUNT(pull_requests.pr_id) as pr_count
    FROM pull_requests
    JOIN users ON pull_requests.user_id = users.id
    GROUP BY users.name
    ORDER BY pr_count DESC;
    """)
    return list(res)
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
    client.execute("""
    INSERT INTO leaderboard (user_id, total_prs)
    SELECT user_id, COUNT(*)
    FROM pull_requests
    GROUP BY user_id
    ON CONFLICT(user_id) DO UPDATE SET
    total_prs = excluded.total_prs
    """)
    client.commit()
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
            user_id = pr['user']['id'] if 'user' in pr else None
            title = pr.get('title', 'No Title')
            state = pr.get('state', 'open')

            existing_pr = client.execute(
                "SELECT pr_id FROM pull_requests WHERE pr_id = ?",
                (pr['id'],)
            ).fetchone()

            if existing_pr:
                logging.debug(f"PR {pr['id']} already exists. Updating...")
                client.execute("""
                UPDATE pull_requests
                SET status = ?, updated_at = ?
                WHERE pr_id = ?
                """, (state, pr['updated_at'], pr['id']))
            else:
                logging.info(f"Inserting new PR {pr['id']}")
                client.execute("""
                INSERT INTO pull_requests (pr_id, repo_name, user_id, title, status, points, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pr['id'],
                    repo,
                    user_id,
                    title,
                    state,
                    10,
                    pr['created_at'],
                    pr['updated_at']
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
    client.execute("""
    INSERT INTO pull_requests (pr_id, repo_name, user_id, title, status, points, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pr.id,
        repo,
        pr.user.id,
        pr.title,
        pr.state,
        10,  # Default points
        pr.created_at,
        pr.updated_at
    ))
    client.commit()
    logging.info(f"Inserted PR {pr.id} for repo {repo}")
