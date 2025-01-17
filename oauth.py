import requests
import os
from dotenv import load_dotenv
import logging
import time
load_dotenv()

CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:5000/callback')


def fetch_github_user(token=None) :
    max_attempts=3
    attempts =0
    while attempts<max_attempts:
        headers= {'Authorization': f'token {token}'}   #Auth headers, to be used in request, geenrally used in axios, can include cookies for extra auth, remember if https

        try:
            response = requests.get("https://api.github.com/user", headers=headers)
            response.raise_for_status()  # Raises exception for 4xx or 5xx responses
            return response.json()  # Return GitHub user info
        
        except requests.exceptions.HTTPError as e:
            # Handle rate limit (403) by rotating the token
            if response.status_code == 403:
                logging.error(f"Token {token} hit rate limit. Rotating...")
                token = None  # Force token refresh
            else:
                # Log the error and re-raise it for higher-level handling
                logging.error(f"Failed to fetch GitHub user: {response.text}")
                raise e
        
        attempts += 1
        time.sleep(min(60 * attempts, 300))  # Exponential backoff (up to 5 mins)

    
    # Raise exception if no valid tokens are left after attempts
    raise Exception("All available tokens hit the rate limit.")

def get_github_token(code):
    response = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'redirect_uri': REDIRECT_URI,
        },
        headers={'Accept': 'application/json'},
    )

    # Handle potential non-JSON responses gracefully
    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        logging.error(f"Non-JSON response from GitHub: {response.text}")
        raise Exception("Failed to retrieve access token: GitHub returned non-JSON response")

    # Handle OAuth error case
    if 'access_token' not in data:
        error_message = data.get('error_description', data.get('error', 'Unknown error during token exchange'))
        logging.error(f"GitHub token exchange failed: {data}")
        raise Exception(f"Failed to retrieve access token from GitHub: {error_message}")
    
    return data['access_token']
