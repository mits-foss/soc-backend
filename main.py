from fastapi import FastAPI, HTTPException, Path
from typing import List, Annotated
import httpx 
from odmantic import Field, Model, EmbeddedModel, AIOEngine, ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import os

app = FastAPI(debug=True)

load_dotenv()
engine = AIOEngine(client=AsyncIOMotorClient(os.getenv("MONGO_URI")),database="soc")
GITHUB_CLIENT_ID = os.getenv("CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URL = os.getenv("REDIRECT_URL")


class PullRequest(EmbeddedModel):
    repo: str = Field(...)
    status: str = Field(...)

class User(Model):
    usertoken: str = Field(default="")
    name: str = Field(...)
    phone_no: int = Field(...)
    clg_mail: str = Field(...)
    avatar: str = Field(...)
    points: int = Field(default=0)
    github: str = Field(default="")
    access_token: str = Field(default="")
    prs: List[PullRequest] = Field(default_factory=list)

class WebUser():
    usertoken: str
    name: str 
    phone_no: int 
    clg_mail: str 
    github: str
    avatar: str 


@app.get("/")
async def read_root():
    user = User(usertoken=str(ObjectId()), name="Advaith",phone_no=123345456,clg_mail="advaith@glitchy.systems",github_token="lm",avatar="htts")
    await engine.save(user)


@app.post("/signup")
async def read_item(user: User):
    print(user)
    user.usertoken = str(user.id)
    await engine.save(user)
    return user.usertoken


@app.get("/user/{usertoken}")
async def get_user(usertoken: Annotated[str, Path(title="The ID of the item to get")]):
    print(usertoken)
    user = await engine.find_one(User, User.usertoken == usertoken)
    print(user)
    return jsonable_encoder(user)

@app.get("/login")
async def github_login(usertoken):
    if usertoken:
        user = engine.find_one(User, User.usertoken == usertoken)
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {user.access_token}"})
            if response.status_code == 200:
                return jsonable_encoder(user)

    return RedirectResponse(f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={REDIRECT_URL}")

@app.get("/callback")
async def github_callback(code: str):
    print(code)
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code
    }
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post("https://github.com/login/oauth/access_token", params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(data)
        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token")
    else:
        raise HTTPException(status_code=400, detail="Failed to exchange code for access token")
    
    
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {access_token}"})
        
    data = response.json()
    username = data["login"]
    avatar_url = data["avatar_url"]
    user_url = data["html_url"]
    return [access_token,username,avatar_url,user_url]
    
@app.post("/register")
async def user_register(user: User):
    if user:
        engine.save(user)