# **PullRanker**  
*A GitHub Pull Request Tracker with Leaderboards and PR Analytics*  

---

### **Table of Contents:**  
- [Overview](#overview)  
- [Features](#features)  
- [Tech Stack](#tech-stack)  
- [Setup and Installation](#setup-and-installation)  
- [Environment Variables](#environment-variables)  
- [API Endpoints](#api-endpoints)  
- [Database Schema](#database-schema)  
- [Docker Setup](#docker-setup)  
- [Contributing](#contributing)  
- [License](#license)  

---

## **Overview:**  
**PullRanker** is a Flask-based application that tracks GitHub pull requests, aggregates user contributions, and generates leaderboards based on pull request activity. It uses GitHub OAuth for user authentication and fetches data through the GitHub API to keep track of PRs and user performance.  

The system automatically rewards users with points based on their PR activities, fostering competitive collaboration among developers.  

---

## **Features:**  
- **GitHub OAuth** – Log in with your GitHub account and retrieve user information securely.  
- **Pull Request Tracking** – Monitors PRs through GitHub webhooks, storing relevant data in an SQLite database.  
- **Leaderboard** – Aggregates user contributions, points, and displays them in a ranked format.  
- **Rate Limiting with API Keys** – Rotates GitHub API keys to handle request limits and avoid rate blocks.  
- **Token Validation** – Invalid GitHub tokens are removed from the system to ensure continuous service.  
- **Dockerized** – The app can be containerized and deployed easily using Docker.  

---

## **Tech Stack:**  
- **Backend:** Flask (Python)  
- **Database:** SQLite  
- **API Integration:** GitHub API  
- **Containerization:** Docker  

---

## **Setup and Installation:**  

### **Prerequisites:**  
- Python 3.8+  
- Docker (Optional for containerization)  

### **Installation Steps:**  
# Clone the Repository
git clone https://github.com/your-username/PullRanker.git  
cd PullRanker  

# Create Virtual Environment and Install Dependencies
python -m venv env  
source env/bin/activate  # On Windows use 'env\Scripts\activate'  
pip install -r requirements.txt  

# Set Up Environment Variables
echo "GITHUB_CLIENT_ID=your_github_client_id" > .env  
echo "GITHUB_CLIENT_SECRET=your_github_client_secret" >> .env  
echo "REDIRECT_URI=http://localhost:5000/callback" >> .env  
echo "SECRET_KEY=supersecretWOOOOOOOOOOOO" >> .env  
echo "SQLITE_DB_PATH=./app.db" >> .env  

# Initialize the Database
python -c 'import db; db.setup_database()'  

# Run the Application Locally
python app.py  
# Visit http://localhost:5000/login to start the GitHub OAuth flow  

## **Environment Variables:**  

GITHUB_CLIENT_ID=your_github_client_id  
GITHUB_CLIENT_SECRET=your_github_client_secret  
REDIRECT_URI=http://localhost:5000/callback  
SECRET_KEY=supersecretWOOOOOOOOOOOO  
SQLITE_DB_PATH=./app.db  


---

## **API Endpoints:**  
/login                    [GET]    - Redirects to GitHub OAuth login  
/callback                 [GET]    - GitHub OAuth callback handler  
/submit_user              [POST]   - Submits user data (email/phone) for new users  
/dashboard                [GET]    - Fetches user-specific PR data and leaderboard  
/leaderboard              [GET]    - Retrieves the top contributors  
/random_api_key           [GET]    - Returns a random API key for rate limiting  
/token_status             [GET]    - Lists all active GitHub tokens  
/webhook                  [POST]   - Handles incoming GitHub webhooks for PRs  
/refresh-tokens           [GET]    - Runs a function that will check users table, and remove tokens that dont have any connection in API_KEYS

---

## **Database Schema:**  
-- Users Table
CREATE TABLE users (  
    id INTEGER PRIMARY KEY,  
    github_id TEXT UNIQUE NOT NULL,  
    name TEXT NOT NULL,  
    email TEXT,  
    phone_no TEXT,  
    token TEXT NOT NULL  
);  

-- API Keys Table
CREATE TABLE api_keys (  
    id INTEGER PRIMARY KEY,  
    key TEXT NOT NULL UNIQUE  
);  

-- Pull Requests Table
CREATE TABLE pull_requests (  
    pr_id INTEGER UNIQUE NOT NULL,  
    repo_name TEXT NOT NULL,  
    github_login TEXT NOT NULL,  
    total_commits INTEGER DEFAULT 0,  
    total_lines INTEGER DEFAULT 0,  
    status TEXT DEFAULT 'open',  
    PRIMARY KEY (pr_id),  
    FOREIGN KEY(github_login) REFERENCES users(github_id)  
);  

-- Leaderboard Table
CREATE TABLE leaderboard (  
    user_id INTEGER PRIMARY KEY,  
    total_prs INTEGER DEFAULT 0,  
    total_commits INTEGER DEFAULT 0,  
    total_lines INTEGER DEFAULT 0,  
    points INTEGER DEFAULT 0,  
    FOREIGN KEY(user_id) REFERENCES users(id)  
);  

## **Docker Setup:**  
# Build the Docker Image
docker build -t pullranker .  

# Run the Container
docker run -p 5000:5000 pullranker  

# Verify the Application is Running at:
http://localhost:5000/login  


### **Docker Compose Setup (Optional, with SQLite Volume Persistence):**  
version: '3.8'  
services:  
  app:  
    build: .  
    ports:  
      - "5000:5000"  
    volumes:  
      - ./app.db:/app/app.db  

# Run Docker Compose

docker-compose up -d  

## **Contributing:**  
Pull requests are welcome! Please open an issue to discuss significant changes beforehand.  

---

## **License:**  
Distributed under the MIT License. See `LICENSE` for more information.  
