import random
import requests
import logging
from flask import redirect

def calculate_leaderboard(client):
    res = client.execute("""
    SELECT users.name, COUNT(pull_requests.id) as pr_count
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
    max_attempts = 3
    attempts = 0
    tokens = client.execute("SELECT key FROM api_keys").fetchall()

    if not tokens:
        logging.warning("No tokens available. Redirecting to refresh login.")
        return None  # Return None if no tokens (instead of redirect)

    while attempts < max_attempts:
        token = random.choice(tokens)[0]
        url = f"https://api.github.com/users/{username}/repos"
        headers = {'Authorization': f'token {token}'}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()  # Return JSON list of repos

        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                logging.error(f"Token {token} is unauthorized. Removing...")
                remove_invalid_key(client, token)
            elif response.status_code == 403:
                logging.warning(f"Token {token} exceeded rate limit. Rotating...")
                remove_invalid_key(client, token)
            else:
                raise e
        attempts += 1

    raise Exception("Failed to fetch repos. All tokens invalid or rate-limited.")
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
    
    for repo in repos:
        prs = fetch_recent_prs(repo, client)
        for pr in prs:
            insert_pull_request(client, pr, repo)
