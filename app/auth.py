"""Shared club password for editing; viewing stays open to everyone.

The password comes from the PADELSCORE_EDIT_PASSWORD environment variable (an App
Service setting in production). When it is not set, as on a developer's machine,
editing is open. Logging in stores a cookie holding an HMAC of the password, so
changing the password logs every browser out.
"""
import hashlib
import hmac
import os

from fastapi import Request

PASSWORD_ENV = "PADELSCORE_EDIT_PASSWORD"
COOKIE = "editor"
COOKIE_MAX_AGE = 180 * 24 * 3600  # stay logged in for about 6 months


class LoginRequired(Exception):
    """Raised by `require_editor`; the app turns it into a redirect to /login."""

    def __init__(self, next_url: str):
        self.next_url = next_url


def edit_password() -> str | None:
    return os.environ.get(PASSWORD_ENV) or None


def editor_token(password: str) -> str:
    return hmac.new(password.encode(), b"padelscore-editor", hashlib.sha256).hexdigest()


def password_matches(given: str) -> bool:
    password = edit_password()
    return password is not None and hmac.compare_digest(given.encode(), password.encode())


def is_editor(request: Request) -> bool:
    password = edit_password()
    if password is None:
        return True
    return hmac.compare_digest(request.cookies.get(COOKIE, ""), editor_token(password))


def is_https(request: Request) -> bool:
    # Behind Azure's front end the app itself sees plain HTTP.
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


def require_editor(request: Request):
    """Route dependency for every page or action that changes data."""
    if not is_editor(request):
        here = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise LoginRequired(here if request.method == "GET" else "/")


def auth_context(request: Request) -> dict:
    """Jinja context processor: whether this browser may edit, to show or hide controls."""
    return {"editor": is_editor(request), "login_enabled": edit_password() is not None}
