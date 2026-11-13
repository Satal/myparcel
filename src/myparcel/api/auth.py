"""Login for the web UI.

Two ways in, either of which turns the login on:

- Authelia SSO (OIDC authorisation code + PKCE), when SSO_ISSUER and
  SSO_CLIENT_SECRET are set. /login goes straight to Authelia; only usernames in
  SSO_USERS get in. Server-side calls go to SSO_INTERNAL_URL (authelia:9091),
  with forwarded headers so Authelia answers as the public issuer.
- A single username and password (AUTH_USERNAME, AUTH_PASSWORD). With SSO on,
  the form is only shown at /login?local, as break-glass.

The session lives in a cookie signed with SECRET_KEY.
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import secrets
from urllib.parse import quote, urlencode, urlsplit

import httpx

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from myparcel.api.templating import templates
from myparcel.config import settings

router = APIRouter()

PUBLIC_PATHS = ("/login", "/health", "/auth/sso", "/auth/sso/callback")

logger = logging.getLogger(__name__)
PUBLIC_PREFIXES = ("/static/",)


def password_enabled() -> bool:
    return bool(settings.auth_username and settings.auth_password)


def sso_enabled() -> bool:
    return bool(settings.sso_issuer and settings.sso_client_secret)


def auth_enabled() -> bool:
    return password_enabled() or sso_enabled()


def sso_allowed_users() -> set[str]:
    return {u.strip() for u in settings.sso_users.split(",") if u.strip()}


def check_credentials(username: str, password: str) -> bool:
    # Compare both in full so timing doesn't reveal which one was wrong
    user_ok = hmac.compare_digest(username.encode(), (settings.auth_username or "").encode())
    password_ok = hmac.compare_digest(password.encode(), (settings.auth_password or "").encode())
    return user_ok and password_ok


def _safe_next(target: str | None) -> str:
    """Only follow redirects back into this app."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return "/"


async def require_login(request: Request, call_next) -> Response:
    """Middleware: send anonymous visitors to the login page."""
    path = request.url.path
    if (
        not auth_enabled()
        or path in PUBLIC_PATHS
        or path.startswith(PUBLIC_PREFIXES)
        or request.session.get("user")
    ):
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    target = path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/login?next={quote(target)}", status_code=303)


def _login_page(request: Request, next: str, error: str | None = None, status_code: int = 200, **extra):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"next": _safe_next(next), "error": error, "sso": sso_enabled(),
         "password": password_enabled(), **extra},
        status_code=status_code,
    )


@router.get("/login")
async def login_form(request: Request, next: str = "/"):
    if not auth_enabled() or request.session.get("user"):
        return RedirectResponse(_safe_next(next), status_code=303)
    if sso_enabled() and "local" not in request.query_params:
        return RedirectResponse(f"/auth/sso?next={quote(_safe_next(next))}", status_code=303)
    return _login_page(request, next)


def _redirect_uri(request: Request) -> str:
    return settings.sso_redirect_uri or str(request.url_for("sso_callback"))


@router.get("/auth/sso")
async def sso_start(request: Request, next: str = "/"):
    if not sso_enabled():
        return JSONResponse({"detail": "Not found"}, status_code=404)
    state = secrets.token_urlsafe(30)
    verifier = secrets.token_urlsafe(48)
    request.session["sso"] = {"state": state, "verifier": verifier, "next": _safe_next(next)}
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({
        "response_type": "code",
        "client_id": settings.sso_client_id,
        "redirect_uri": _redirect_uri(request),
        "scope": "openid profile email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return RedirectResponse(f"{settings.sso_issuer.rstrip('/')}/api/oidc/authorization?{query}", status_code=303)


async def fetch_username(code: str, verifier: str, redirect_uri: str) -> str | None:
    """Swap the code for a token, then ask Authelia who it belongs to."""
    issuer = urlsplit(settings.sso_issuer or "")
    base = (settings.sso_internal_url or settings.sso_issuer or "").rstrip("/")
    headers = {"X-Forwarded-Proto": issuer.scheme or "https", "X-Forwarded-Host": issuer.netloc,
               "Accept": "application/json"}
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=10) as http:
        tokens = await http.post(
            "/api/oidc/token",
            auth=(settings.sso_client_id, settings.sso_client_secret or ""),
            data={"grant_type": "authorization_code", "code": code,
                  "redirect_uri": redirect_uri, "code_verifier": verifier},
        )
        access = tokens.json().get("access_token") if tokens.is_success else None
        if not isinstance(access, str):
            logger.warning("SSO token exchange failed: HTTP %s", tokens.status_code)
            return None
        info = await http.get("/api/oidc/userinfo", headers={"Authorization": f"Bearer {access}"})
        return (info.json().get("preferred_username") or None) if info.is_success else None


@router.get("/auth/sso/callback", name="sso_callback")
async def sso_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if not sso_enabled():
        return JSONResponse({"detail": "Not found"}, status_code=404)
    expected = request.session.pop("sso", None)
    if not isinstance(expected, dict) or not state or not hmac.compare_digest(expected.get("state", ""), state):
        return _sso_failed(request, "state mismatch")
    if error or not code:
        return _sso_failed(request, f"authorisation refused: {(error or 'no code')[:60]}")
    try:
        username = await fetch_username(code, expected["verifier"], _redirect_uri(request))
    except httpx.HTTPError as exc:
        return _sso_failed(request, f"Authelia unreachable: {type(exc).__name__}")
    if not username:
        return _sso_failed(request, "no username from Authelia")
    if username not in sso_allowed_users():
        return _sso_failed(request, f"'{username}' is not allowed in")
    request.session["user"] = username
    return RedirectResponse(expected.get("next", "/"), status_code=303)


def _sso_failed(request: Request, reason: str):
    logger.warning("SSO sign-in failed: %s", reason)
    return _login_page(request, "/", error=f"Single sign-on failed ({reason}). Try again.", status_code=401)


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/"),
):
    if password_enabled() and check_credentials(username, password):
        request.session["user"] = username
        return RedirectResponse(_safe_next(next), status_code=303)

    await asyncio.sleep(1)  # slow down guessing
    return _login_page(request, next, error="Wrong username or password", status_code=401, username=username)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
