import requests
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:5000/callback')

def get_github_login_url():
    return (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=repo,user"
    )
def fetch_github_user(token=None):
    max_attempts=3
    attempts =0
    while attempts<max_attempts:
        if not token:
            token=random_api_key(client)
        headers= {'Authorization': f'token {token}'}   #Auth headers, to be used in request, geenrally used in axios, can include cookies for extra auth, remember if https

        try:
            response = requests.get("https://api.github.com/user", headers=headers)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if response.status_code == 403:  
                logging.error(f"Token {token} hit rate limit. Rotating...")
                remove_invalid_key(token)
                token = None  
            else:
                raise e
        
        attempts += 1
    
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
    response.raise_for_status()
    return response.json()['access_token']

