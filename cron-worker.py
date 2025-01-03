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

    logging.info("Cron worker started...")

    while RUNNING:
        try:
            # Reconnect to DB if connection is lost
            if client is None or client.isolation_level is None:
                client = connect_db()
                client.execute("SELECT 1").fetchone()  # Test DB connection
                logging.info("Reconnected to database.")

            logging.info(f"Running PR fetch at {datetime.datetime.now()}")

            pr_count = fetch_filtered_prs(client)

            update_leaderboard(client)

            logging.info(f"Updated {pr_count} PRs and refreshed leaderboard.")

        except Exception as e:
            logging.error(f"Error during cron job execution: {str(e)}")
            time.sleep(60)  # Wait before retrying to avoid rapid-fire failures

        time.sleep(45 * 60)  # Sleep for 45 minutes before the next run

    logging.info("Cron worker exiting...")

if __name__ == "__main__":
    cron_worker()
