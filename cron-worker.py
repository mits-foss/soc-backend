import time
from db import connect_db
from utils import fetch_filtered_prs, update_leaderboard
import logging
import datetime
import signal
import sys
# Most of this code is GPT, i no no know how to make cron, forgive me :pensive:
logging.basicConfig(level=logging.DEBUG)

RUNNING = True  # Global flag for graceful shutdown

def handle_exit(signum, frame):
    global RUNNING
    logging.info("Received termination signal. Exiting gracefully...")
    RUNNING = False

# Attach signal handlers for graceful termination
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)
def cron_worker():
    global RUNNING
    client = None
    attempts = 0

    while RUNNING:
        try:
            if client is None or client.isolation_level is None:
                client = connect_db()

            logging.info("Running PR fetch...")

            pr_count = fetch_filtered_prs(client)
            update_leaderboard(client)
            logging.info(f"Updated {pr_count} PRs")

            attempts = 0  # Reset attempts if successful

        except Exception as e:
            attempts += 1
            wait_time = min(60 * (2 ** attempts), 300)  # Exponential backoff (max 5 min)
            logging.error(f"Error in cron job: {str(e)}. Retrying in {wait_time} seconds.")
            time.sleep(wait_time)

        time.sleep(45 * 60)  # Sleep for 45 minutes before the next run

    logging.info("Cron worker exiting...")

if __name__ == "__main__":
    cron_worker()
