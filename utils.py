import random

def calculate_leaderboard(client):
    res = client.execute("""
    SELECT users.name, COUNT(pull_requests.id) as pr_count
    FROM pull_requests
    JOIN users ON pull_requests.user_id = users.id
    GROUP BY users.name
    ORDER BY pr_count DESC;
    """).fetchall()
    return res

def random_api_key(client):
    res = client.execute("SELECT key FROM api_keys").fetchall()
    return random.choice(res)[0] if res else None
