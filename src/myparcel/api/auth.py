"""Single-user login for the web UI.

Enabled when AUTH_USERNAME and AUTH_PASSWORD are both set. The session lives in a
cookie signed with SECRET_KEY.
"""

import asyncio
import hmac
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from myparcel.api.templating import templates
from myparcel.config import settings

router = APIRouter()

PUBLIC_PATHS = ("/login", "/health")
PUBLIC_PREFIXES = ("/static/",)


def auth_enabled() -> bool:
    return bool(settings.auth_username and settings.auth_password)


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


@router.get("/login")
async def login_form(request: Request, next: str = "/"):
    if not auth_enabled() or request.session.get("user"):
        return RedirectResponse(_safe_next(next), status_code=303)
    return templates.TemplateResponse(request, "login.html", {"next": _safe_next(next)})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/"),
):
    if check_credentials(username, password):
        request.session["user"] = username
        return RedirectResponse(_safe_next(next), status_code=303)

    await asyncio.sleep(1)  # slow down guessing
    return templates.TemplateResponse(
        request,
        "login.html",
        {"next": _safe_next(next), "error": "Wrong username or password", "username": username},
        status_code=401,
    )


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
