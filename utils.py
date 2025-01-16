import random
import requests
import logging
from flask import redirect
import datetime
import time

from configs.globals import CRON_TOKEN

logging.basicConfig(level=logging.DEBUG)


def calculate_leaderboard(client):
    pr_list = client.execute("""
    SELECT id, repo_name, github_user
    FROM pull_requests
    JOIN users ON pull_requests.id = users.id
    GROUP BY users.name
    ORDER BY pr_count DESC;
    """)
    return list(pr_list)

def fetch_user_repos(username, client):
    try:
        return list(
            client.execute("""
            SELECT repo_name 
            FROM pull_requests
            WHERE github_user = ?""",(username,))
        )
    except Exception as e:
         logging.error(f"Error updating leaderboard: {str(e)}")

def update_leaderboard(client):
    try:
        cursor = client.cursor()

        # Ensure all users exist in leaderboard (initialize with 0s)
        cursor.execute("""
        INSERT OR IGNORE INTO leaderboard (user_id, total_prs, total_commits, total_lines, points)
        SELECT id, 0, 0, 0, 0 FROM users
        """)

        # Update leaderboard with filtered PRs and status points
        cursor.execute("""
        INSERT INTO leaderboard (user_id, total_prs, total_commits, total_lines, points)
        SELECT users.id,
       COUNT(DISTINCT pull_requests.repo_name), 
       SUM(pull_requests.total_commits),
       SUM(pull_requests.total_lines),
       SUM(CASE WHEN pull_requests.status = 'merged' THEN 10 ELSE 5 END)
        FROM users
        JOIN pull_requests ON users.github_id = pull_requests.github_login
        WHERE pull_requests.pr_id IN (
            SELECT MAX(pr_id)
            FROM pull_requests
            GROUP BY repo_name, github_login
        )
        GROUP BY users.id


        ON CONFLICT(user_id) DO UPDATE SET
        total_prs = excluded.total_prs,
        total_commits = excluded.total_commits,
        total_lines = excluded.total_lines,
        points = excluded.points;
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
            status = pr.get('state', 'open')

            user_exists = client.execute(
                "SELECT 1 FROM users WHERE github_id = ?",
                (github_login,)
            ).fetchone()

            if not user_exists:
                logging.warning(f"User {github_login} not found. Skipping PR {pr['id']}.")
                continue

            # Check for existing PR from the same repo and user
            existing_pr = client.execute(
                "SELECT pr_id FROM pull_requests WHERE pr_id = ?",
                (pr['id'],)
            ).fetchone()

            if existing_pr:
                logging.debug(f"Updating existing PR {existing_pr[0]}")
                client.execute("""
                UPDATE pull_requests
                SET total_commits = ?, total_lines = ?, status = ?
                WHERE pr_id = ?
                """, (total_commits, total_lines, status, existing_pr[0]))
            else:
                logging.info(f"Inserting new PR {pr['id']}")
                client.execute("""
                INSERT INTO pull_requests (pr_id, repo_name, github_login, total_commits, total_lines, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    pr['id'],
                    repo,
                    github_login,
                    total_commits,
                    total_lines,
                    status
                ))
                pr_count += 1

    client.commit()
    logging.info(f"Fetched {pr_count} new PRs.")
    return pr_count

def fetch_recent_prs(repo, client):
    token = CRON_TOKEN
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

def fetch_pr_details(repo, pr_id, client, token):

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
