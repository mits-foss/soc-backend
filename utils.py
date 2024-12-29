import random

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

def remove_invalid_key(key):
    client.execute("DELETE FROM api_keys WHERE key = ?", (key,))
    client.commit()
    logging.info(f"Token {key} removed due to rate limit.")

def fetch_user_repos(username,client):
    token = random_api_key(client)
    url = f"https://api.github.com/users/{username}/repos"
    
    headers = {'Authorization': f'token {token}'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.HTTPError as e:
        if response.status_code == 403:  # Rate limit
            logging.warning(f"Token {token} exceeded rate limit. Removing...")
            remove_invalid_key(token)
        raise e
