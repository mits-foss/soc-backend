import os
import sqlite3
import logging
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('SQLITE_DB_PATH', './app.db')

def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

client = connect_db()

def setup_database():
    logging.debug("Setting up database.")
    client.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        github_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
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
    logging.debug("Database setup complete.")

def save_user_to_db(github_user, token):
    client.execute("""
    INSERT OR IGNORE INTO users (github_id, name, email, token)
    VALUES (?, ?, ?, ?)
    """, (github_user['id'], github_user['login'], github_user.get('email', ''), token))
    
    client.execute("""
    INSERT INTO api_keys (key)
    VALUES (?)
    ON CONFLICT(key) DO UPDATE SET key=excluded.key
    """, (token,))
    
    client.commit()


def get_all_users():
    res = client.execute("SELECT * FROM users")
    return list(res)
