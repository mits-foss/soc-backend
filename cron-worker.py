import time
from db import connect_db
from utils import fetch_filtered_prs, update_leaderboard

def cron_worker():
    client = connect_db()

    while True:
        fetch_filtered_prs(client)
        update_leaderboard(client)
        logging.info("Updated PRs and leaderboard.")
        time.sleep(45 * 60)
