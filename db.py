import os
import sqlite3
import logging
from dotenv import load_dotenv
import requests
from utils import fetch_user_repos

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

DB_PATH = os.getenv('SQLITE_DB_PATH','./app.db')

def connect_db():
    logging.debug("Connecting to database...")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    if not isinstance(conn, sqlite3.Connection):
        raise Exception("Failed to establish database connection.")
    return conn

client = connect_db()

def setup_database():
    logging.debug("Setting up database.")
    client.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        github_user TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        contact TEXT,  
        avatar TEXT,
        link TEXT 
    );
    """)
    
    client.execute("""
    CREATE TABLE IF NOT EXISTS pull_requests (
        id INTEGER PRIMARY KEY,
        repo_name TEXT NOT NULL,
        github_user TEXT NOT NULL,
        total_commits INTEGER DEFAULT 0,
        total_lines INTEGER DEFAULT 0,
        status TEXT DEFAULT 'open',
        FOREIGN KEY(github_user) REFERENCES users(github_user)
    );


    """)
    
    client.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        id INTEGER PRIMARY KEY,
        total_prs INTEGER DEFAULT 0,
        total_commits INTEGER DEFAULT 0,
        total_lines INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        FOREIGN KEY(id) REFERENCES users(id)
    );
    """)
    
    
    client.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        token TEXT
    );
    """)
    
    logging.debug("Database setup complete.")

def save_user_to_db(github_user, name, email, contact, avatar, link):
    client.execute("""
    INSERT OR REPLACE INTO users (github_user, name, email, contact, avatar, link)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (github_user, name, email, contact, avatar, link))
    
    client.commit()
def save_token(token):
    client.execute("""
    INSERT OR REPLACE INTO tokens (token)
    VALUES (?)
    """, (token,))
    
    client.commit()

def get_all_users():
    res = client.execute("SELECT * FROM users").fetchall()
    users = []

    for row in res:
        github_username = row[1]
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
    tokens = client.execute("SELECT key FROM api_keys").fetchall()[0]
    for token in tokens:
        response = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token[0]}"}
        )
        if response.status_code == 401:  
            logging.warning(f"Removing invalid token: {token[0]}")
        else:
            logging.info(f"Token {token[0]} is valid.")
