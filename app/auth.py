"""Shared club password for editing; viewing stays open to everyone.

The password comes from the PADELSCORE_EDIT_PASSWORD environment variable (an App
Service setting in production). When it is not set, as on a developer's machine,
editing is open. Logging in stores a cookie holding an HMAC of the password, so
changing the password logs every browser out.

A tournament can also have a player password. It is stored as typed so the club's
editors can look it up and share it. Players who log in with it may enter set results
in that tournament, and create sets in a manual one; nothing else. Their cookie, one
per tournament, is an HMAC of that password, so a new password logs them out.
"""
import hashlib
import hmac
import os

from fastapi import Request

PASSWORD_ENV = "PADELSCORE_EDIT_PASSWORD"
COOKIE = "editor"
COOKIE_MAX_AGE = 180 * 24 * 3600  # stay logged in for about 6 months
PLAYER_COOKIE = "player_{}"       # per tournament id


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


def player_password_matches(given: str, tournament) -> bool:
    password = tournament["player_password"]
    return bool(password) and hmac.compare_digest(given.encode(), password.encode())


def player_token(tournament) -> str:
    return hmac.new(tournament["player_password"].encode(),
                    f"player:{tournament['id']}".encode(), hashlib.sha256).hexdigest()


def is_player(request: Request, tournament) -> bool:
    """Logged in with this tournament's player password."""
    if not tournament["player_password"]:
        return False
    cookie = request.cookies.get(PLAYER_COOKIE.format(tournament["id"]), "")
    return hmac.compare_digest(cookie, player_token(tournament))


def can_score(request: Request, tournament) -> bool:
    """May enter results in this tournament: an editor, or one of its players."""
    return is_editor(request) or is_player(request, tournament)


def is_https(request: Request) -> bool:
    # Behind Azure's front end the app itself sees plain HTTP.
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


def require_editor(request: Request):
    """Route dependency for every page or action that changes data."""
    if not is_editor(request):
        here = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise LoginRequired(here if request.method == "GET" else "/")


def require_scorer(request: Request, tournament):
    if not can_score(request, tournament):
        raise LoginRequired("/")


def player_cookies(request: Request) -> list[str]:
    return [name for name in request.cookies if name.startswith(PLAYER_COOKIE.format(""))]


def auth_context(request: Request) -> dict:
    """Jinja context processor: whether this browser may edit, to show or hide controls."""
    editor = is_editor(request)
    return {"editor": editor, "login_enabled": edit_password() is not None,
            "logged_in": (editor and edit_password() is not None) or bool(player_cookies(request))}
