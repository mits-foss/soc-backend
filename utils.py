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

def fetch_user_repos(username, client):
    max_attempts = 3
    attempts = 0
    token = client.execute(f"SELECT key FROM users WHERE github_id = {username.github_id}").fetchall()

    if not token:
        logging.warning("No tokens available. Redirecting to refresh login.")
        return None  # Return None if no tokens (instead of redirect)

    while attempts < max_attempts:
        url = f"https://api.github.com/users/{username}/repos"
        headers = {'Authorization': f'token {token}'}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()  # Return JSON list of repos

        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                logging.error(f"Token {token} is unauthorized. Removing...")
            elif response.status_code == 403:
                logging.warning(f"Token {token} exceeded rate limit. Rotating...")
            else:
                raise e
        attempts += 1

    raise Exception("Failed to fetch repos. All tokens invalid or rate-limited.")
