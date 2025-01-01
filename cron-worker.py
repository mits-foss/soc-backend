import time
from db import connect_db
from utils import fetch_filtered_prs, update_leaderboard
import logging
logging.basicConfig(level=logging.DEBUG)

def cron_worker():
    client = connect_db()
    logging.info("Cron worker started...")
    while True:
        fetch_filtered_prs(client)
        update_leaderboard(client)
        logging.info("Updated PRs and leaderboard.")
        time.sleep(45 * 60)
