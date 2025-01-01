import os
import sqlite3
import logging
from dotenv import load_dotenv
import requests
from utils import fetch_user_repos

load_dotenv()

DB_PATH = os.getenv('SQLITE_DB_PATH', './app.db')

def connect_db():
    logging.debug("Connecting to database...")
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# Initialize the client on module load
client = connect_db()

def setup_database():
    logging.debug("Setting up database.")
    client.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        github_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        phone_no TEXT,  
        token TEXT NOT NULL
    );
    """)
    
    client.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY,
        key TEXT NOT NULL UNIQUE
    );
    """)
    
    client.execute("""
    CREATE TABLE IF NOT EXISTS pull_requests (
        id INTEGER PRIMARY KEY,
        repo_name TEXT NOT NULL,
        user_id INTEGER,
        status TEXT,
        points INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    
    client.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        user_id INTEGER PRIMARY KEY,
        total_prs INTEGER DEFAULT 0,
        total_commits INTEGER DEFAULT 0,
        total_lines INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    logging.debug("Database setup complete.")

def save_user_to_db(github_user, email, phone, token):
    client.execute("""
    INSERT OR IGNORE INTO users (github_id, name, email, phone_no, token)
    VALUES (?, ?, ?, ?, ?)
    """, (github_user['id'], github_user['login'], email, phone, token))
    
    client.execute("""
    INSERT INTO api_keys (key)
    VALUES (?)
    ON CONFLICT(key) DO UPDATE SET key=excluded.key
    """, (token,))
    
    client.commit()

def get_all_users():
    res = client.execute("SELECT * FROM users").fetchall()
    users = []

    for row in res:
        github_username = row[2]
        try:
            repos = fetch_user_repos(github_username, client)
            repo_details = [
                {
                    'repo_name': repo['name'],
                    'last_commit': repo['updated_at']
                }
                for repo in repos
            ]
        except Exception as e:
            logging.error(f"Failed to fetch repos for {github_username}: {str(e)}")
            repo_details = [] 
        
        users.append({
            'SOCid': row[0],
            'username': github_username,
            'email': row[3],
            'repos': repo_details
        })
    return users

def validate_tokens(client):
    tokens = client.execute("SELECT key FROM api_keys").fetchall()
    for token in tokens:
        response = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token[0]}"}
        )
        if response.status_code == 401:  # Token is invalid
            logging.warning(f"Removing invalid token: {token[0]}")
            remove_invalid_key(client, token[0])
        else:
            logging.info(f"Token {token[0]} is valid.")
