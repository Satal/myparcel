"""Tests for sign-in through Authelia (OIDC code + PKCE)."""

from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import ASGITransport, AsyncClient

from myparcel.api import auth
from myparcel.config import settings
from myparcel.main import app


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "auth_username", "sam")
    monkeypatch.setattr(settings, "auth_password", "correct horse")
    monkeypatch.setattr(settings, "sso_issuer", "https://auth.example.test")
    monkeypatch.setattr(settings, "sso_internal_url", "http://authelia:9091")
    monkeypatch.setattr(settings, "sso_client_secret", "s3cret")
    monkeypatch.setattr(settings, "sso_users", "sam")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def fake_authelia(monkeypatch, username="sam", calls=None):
    async def fetch(code, verifier, redirect_uri):
        if calls is not None:
            calls.append((code, verifier, redirect_uri))
        return username

    monkeypatch.setattr(auth, "fetch_username", fetch)


async def start(client, next="/"):
    response = await client.get(f"/auth/sso?next={next}")
    assert response.status_code == 303
    location = urlsplit(response.headers["location"])
    return location, parse_qs(location.query)


async def test_login_page_goes_to_sso(client):
    response = await client.get("/login?next=/parcel/1")
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/sso?next=/parcel/1"


async def test_local_shows_break_glass_form(client):
    response = await client.get("/login?local")
    assert response.status_code == 200
    assert 'name="password"' in response.text
    assert "Sign in with Jenkins Group" in response.text


async def test_redirect_to_authelia_with_pkce(client):
    location, query = await start(client)
    assert f"{location.scheme}://{location.netloc}{location.path}" == "https://auth.example.test/api/oidc/authorization"
    assert query["client_id"] == ["myparcel"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["http://test/auth/sso/callback"]


async def test_callback_signs_in_allowed_user(client, monkeypatch):
    calls = []
    fake_authelia(monkeypatch, calls=calls)
    _, query = await start(client, next="/api/carriers")
    response = await client.get(f"/auth/sso/callback?code=abc&state={query['state'][0]}")
    assert response.status_code == 303
    assert response.headers["location"] == "/api/carriers"
    assert calls[0][0] == "abc"
    assert (await client.get("/api/carriers")).status_code == 200


async def test_callback_rejects_bad_state(client, monkeypatch):
    fake_authelia(monkeypatch)
    await start(client)
    response = await client.get("/auth/sso/callback?code=abc&state=forged")
    assert response.status_code == 401
    assert (await client.get("/api/carriers")).status_code == 401


async def test_callback_rejects_unlisted_user(client, monkeypatch):
    fake_authelia(monkeypatch, username="mallory")
    _, query = await start(client)
    response = await client.get(f"/auth/sso/callback?code=abc&state={query['state'][0]}")
    assert response.status_code == 401
    assert "not allowed" in response.text
    assert (await client.get("/api/carriers")).status_code == 401


async def test_state_is_single_use(client, monkeypatch):
    fake_authelia(monkeypatch)
    _, query = await start(client)
    state = query["state"][0]
    await client.get(f"/auth/sso/callback?code=abc&state={state}")
    await client.post("/logout")
    response = await client.get(f"/auth/sso/callback?code=abc&state={state}")
    assert response.status_code == 401


async def test_sso_routes_404_when_off(client, monkeypatch):
    monkeypatch.setattr(settings, "sso_client_secret", None)
    assert (await client.get("/auth/sso")).status_code == 404
    assert (await client.get("/login")).status_code == 200
