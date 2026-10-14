"""Tests for the web UI login."""

import pytest
from httpx import ASGITransport, AsyncClient

from myparcel.api import auth
from myparcel.config import settings
from myparcel.main import app


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "auth_username", "sam")
    monkeypatch.setattr(settings, "auth_password", "correct horse")

    async def no_sleep(_):
        pass

    monkeypatch.setattr(auth.asyncio, "sleep", no_sleep)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def login(client, password="correct horse", next="/"):
    return await client.post(
        "/login", data={"username": "sam", "password": password, "next": next}
    )


async def test_anonymous_page_redirects_to_login(client):
    response = await client.get("/parcel/1?x=1")
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/parcel/1%3Fx%3D1"


async def test_anonymous_api_gets_401(client):
    response = await client.get("/api/carriers")
    assert response.status_code == 401


async def test_health_and_static_need_no_login(client):
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/static/css/style.css")).status_code == 200


async def test_wrong_password_is_rejected(client):
    response = await login(client, password="wrong")
    assert response.status_code == 401
    assert "Wrong username or password" in response.text
    assert (await client.get("/api/carriers")).status_code == 401


async def test_login_then_logout(client):
    response = await login(client, next="/api/carriers")
    assert response.status_code == 303
    assert response.headers["location"] == "/api/carriers"
    assert (await client.get("/api/carriers")).status_code == 200

    await client.post("/logout")
    assert (await client.get("/api/carriers")).status_code == 401


@pytest.mark.parametrize("target", ["//evil.example", "https://evil.example", ""])
async def test_login_does_not_redirect_off_site(client, target):
    response = await login(client, next=target)
    assert response.headers["location"] == "/"


async def test_no_login_when_credentials_unset(monkeypatch):
    monkeypatch.setattr(settings, "auth_password", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/carriers")).status_code == 200
