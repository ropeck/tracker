from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from scripts.auth import ALLOWED_USER, get_current_user, router


@pytest.fixture()
def app_with_session() -> FastAPI:
    from starlette.middleware.sessions import SessionMiddleware

    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret",  # noqa: S106
    )  # noqa: S106
    app.include_router(router)
    return app


@pytest.mark.asyncio()
@patch("scripts.auth.oauth.google.authorize_redirect", new_callable=AsyncMock)
async def test_login_redirect(mock_redirect, app_with_session) -> None:
    from httpx import ASGITransport, AsyncClient

    # ✅ Fix: return a real response object
    mock_redirect.return_value = RedirectResponse(url="/auth")

    transport = ASGITransport(app=app_with_session)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/login")

    assert response.status_code in {307, 302}
    assert response.headers["location"] == "/auth"
    mock_redirect.assert_awaited_once()


@pytest.mark.asyncio()
@patch(
    "scripts.auth.oauth.google.authorize_access_token", new_callable=AsyncMock
)
@patch("scripts.auth.oauth.google.userinfo", new_callable=AsyncMock)
async def test_auth_success(
    mock_userinfo, mock_token, app_with_session
) -> None:
    mock_token.return_value = {
        "access_token": "abc123",
        "userinfo": {"email": ALLOWED_USER},
    }
    mock_userinfo.return_value = {"email": ALLOWED_USER}

    transport = ASGITransport(app=app_with_session)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    res = await client.get("/auth", follow_redirects=False)
    assert res.status_code == 302  # noqa: PLR2004
    assert res.headers["location"] == "/"
    await client.aclose()


@pytest.mark.asyncio()
@patch(
    "scripts.auth.oauth.google.authorize_access_token", new_callable=AsyncMock
)
@patch("scripts.auth.oauth.google.userinfo", new_callable=AsyncMock)
async def test_auth_rejects_invalid_user(
    mock_userinfo, mock_token, app_with_session
) -> None:
    mock_token.return_value = {"userinfo": {"email": "not@allowed.com"}}
    mock_userinfo.return_value = {"email": "not@allowed.com"}

    transport = ASGITransport(app=app_with_session)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    res = await client.get("/auth", follow_redirects=False)
    assert res.status_code == 302  # noqa: PLR2004
    assert res.headers["location"] == "/unauthorized"
    await client.aclose()


def test_logout_clears_session(app_with_session) -> None:
    with TestClient(app_with_session) as client:
        client.cookies.set("session", "mock")
        res = client.get("/logout", follow_redirects=False)
        assert res.status_code == 302  # noqa: PLR2004
        assert res.headers["location"] == "/"


def test_get_current_user_with_nologin(monkeypatch) -> None:
    monkeypatch.setenv("NOLOGIN", "1")
    request = MagicMock()
    result = get_current_user(request)
    assert result["email"] == ALLOWED_USER


def test_get_current_user_with_session() -> None:
    request = MagicMock()
    request.session = {"user": {"email": "fogcat5@gmail.com"}}
    result = get_current_user(request)
    assert result["email"] == ALLOWED_USER
