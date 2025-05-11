"""
OAuth authentication module for the inventory app.

Uses Google OAuth via Authlib to authenticate a single allowed user
(`fogcat5@gmail.com`) and manage login/logout session handling.

Routes:
- `/login`: Starts the OAuth redirect flow.
- `/auth`: Handles the OAuth callback and verifies the user.
- `/logout`: Clears the current session.
"""

import os

from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

load_dotenv()

ALLOWED_USER = "fogcat5@gmail.com"

router = APIRouter()

# Configure OAuth using Authlib with Google as the provider
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login(request: Request):
    """
    Initiates the OAuth login flow by redirecting the user to Google's
    authorization endpoint.
    """
    redirect_uri = str(request.url_for("auth")).replace("http://", "https://")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth")
async def auth(request: Request):
    """
    Handles the OAuth callback from Google, validates the user, and stores
    the user info in the session if authorized.
    """
    token = await oauth.google.authorize_access_token(request)
    print("OAuth token response:", token)

    if "userinfo" in token:
        user = token["userinfo"]
    else:
        user = await oauth.google.userinfo(token=token)
    request.session["user"] = dict(user)

    print("User info:", user)

    if user.get("email") != ALLOWED_USER:
        print(f"Access denied for: {user.get('email')}")
        return RedirectResponse("/unauthorized", status_code=302)

    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """
    Logs out the current user by removing their session data.
    """
    request.session.pop("user", None)
    return RedirectResponse(url="/", status_code=302)


def get_current_user(request: Request):
    """
    Returns the current user from the session. If the NOLOGIN environment
    variable is set, bypasses auth and returns the allowed user.
    """
    if os.getenv("NOLOGIN", None):
        return {"email": ALLOWED_USER}
    return request.session.get("user")
