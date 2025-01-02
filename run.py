from db import connect_db
from utils import fetch_filtered_prs, calculate_leaderboard,update_leaderboard
import os
if __name__ == "__main__":
    client = connect_db()

    print("Running manual PR fetch...")
    pr_count = fetch_filtered_prs(client)
    
    print(f"\nFetched {pr_count} PRs.\n")
    update_leaderboard(client)
    print("Leaderboard Results:")
    leaderboard = calculate_leaderboard(client) 
    for entry in leaderboard:
        print(f"{entry[0]} - {entry[1]} PRs")
