"""Who sees and changes what.

Everything belongs to an organization (see orgs.py). Visitors first enter one by its
name; a cookie remembers it, signed with the organization's secret, and from then on
they see its tournaments. Viewing needs nothing more.

Accounts (users.py) log in with their username or email and password. The account
cookie is an HMAC (with the account's secret) of the stored password hash, so
changing the password logs the account out everywhere.
- A super admin is admin in every organization and manages organizations (/orgs).
- An organization admin may change everything in their organization.
- A player account may enter results in the tournaments its players play in.

A tournament also has a player password. It is stored as typed so the admin can look
it up and share it. Guests who log in with it may enter set results in that
tournament, and create sets in a manual one; nothing else. Their cookie, one per
tournament, is an HMAC of that password, so a new password logs them out.
"""
import hashlib
import hmac

from fastapi import Request

from . import db, users
from .db import default_player_password  # noqa: F401 (used by the app and tests)

ORG_COOKIE = "org"
USER_COOKIE = "user"
OLD_COOKIES = ("editor", "super")  # before accounts; logging out clears them
COOKIE_MAX_AGE = 180 * 24 * 3600   # stay logged in for about 6 months
PLAYER_COOKIE = "player_{}"        # per tournament id


class LoginRequired(Exception):
    """Raised by `require_editor`; the app turns it into a redirect to /login."""

    def __init__(self, next_url: str):
        self.next_url = next_url


def _sign(row, message: str) -> str:
    return hmac.new(row["secret"].encode(), message.encode(), hashlib.sha256).hexdigest()


# --- The organization being viewed --------------------------------------------------

def org_cookie(org) -> str:
    return f"{org['id']}.{_sign(org, 'org:%d' % org['id'])}"


def org_from_cookie(request: Request):
    """The organization this browser entered, or None."""
    org_id, _, token = request.cookies.get(ORG_COOKIE, "").partition(".")
    if not org_id.isdigit():
        return None
    with db.connect() as conn:
        org = conn.execute("SELECT * FROM organizations WHERE id = ?", (int(org_id),)).fetchone()
    return org if org and hmac.compare_digest(token, _sign(org, f"org:{org['id']}")) else None


def current_org(request: Request):
    """The organization of this request (set by the app's middleware)."""
    return request.scope.get("state", {}).get("org")


def find_org(conn, name: str):
    return conn.execute("SELECT * FROM organizations WHERE name = ?",
                        (" ".join(name.split()),)).fetchone()


# --- Accounts --------------------------------------------------------------------------

def user_cookie(user) -> str:
    return f"{user['id']}.{_sign(user, 'user:%d:%s' % (user['id'], user['password']))}"


def current_user(request: Request):
    """The account logged in on this browser, or None (cached for the request)."""
    cached = request.scope.setdefault("state", {})
    if "user" not in cached:
        user_id, _, token = request.cookies.get(USER_COOKIE, "").partition(".")
        user = None
        if user_id.isdigit():
            with db.connect() as conn:
                user = users.get(conn, int(user_id))
        cached["user"] = user if user and hmac.compare_digest(
            user_cookie(user), f"{user_id}.{token}") else None
    return cached["user"]


def is_super(request: Request) -> bool:
    user = current_user(request)
    return bool(user) and user["role"] == "super"


def is_editor(request: Request) -> bool:
    """Admin of the organization being viewed: its own admin, or a super admin."""
    org, user = current_org(request), current_user(request)
    if org is None or user is None:
        return False
    return user["role"] == "super" or (
        user["role"] == "org_admin" and user["organization_id"] == org["id"])


def require_super(request: Request):
    if not is_super(request):
        raise LoginRequired(request.url.path if request.method == "GET" else "/orgs")


# --- Players of a tournament ------------------------------------------------------------

def player_password_matches(given: str, tournament) -> bool:
    password = tournament["player_password"]
    return bool(password) and hmac.compare_digest(given.encode(), password.encode())


def player_token(tournament) -> str:
    return hmac.new(tournament["player_password"].encode(),
                    f"player:{tournament['id']}".encode(), hashlib.sha256).hexdigest()


def is_guest_player(request: Request, tournament) -> bool:
    """Logged in with this tournament's player password."""
    if not tournament["player_password"]:
        return False
    cookie = request.cookies.get(PLAYER_COOKIE.format(tournament["id"]), "")
    return hmac.compare_digest(cookie, player_token(tournament))


def account_plays(user, tournament) -> bool:
    """The account's player is in the tournament (its list or one of its sets)."""
    with db.connect() as conn:
        return conn.execute(
            "SELECT 1 FROM players p WHERE p.user_id = ? AND p.organization_id = ? AND ("
            " EXISTS (SELECT 1 FROM tournament_players tp WHERE tp.tournament_id = ? "
            "         AND tp.player_id = p.id)"
            " OR EXISTS (SELECT 1 FROM matches m JOIN matchdays d ON d.id = m.matchday_id "
            "            WHERE d.tournament_id = ? AND p.id IN (m.a1, m.a2, m.b1, m.b2)))",
            (user["id"], tournament["organization_id"], tournament["id"],
             tournament["id"])).fetchone() is not None


def is_player(request: Request, tournament) -> bool:
    """A player of this tournament: a guest with its password, or an account of one."""
    user = current_user(request)
    return is_guest_player(request, tournament) or bool(user) and account_plays(user, tournament)


def can_score(request: Request, tournament) -> bool:
    """May enter results in this tournament: the admin, or one of its players."""
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
    """Jinja context processor: the organization, the account, and whether this browser
    may edit."""
    user = current_user(request)
    editor, superadmin = is_editor(request), is_super(request)
    return {"editor": editor, "superadmin": superadmin, "org": current_org(request),
            "user": user, "login_enabled": True,
            "logged_in": bool(user) or bool(player_cookies(request))}
