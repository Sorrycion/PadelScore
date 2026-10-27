"""Who sees and changes what.

Everything belongs to an organization (see orgs.py). Visitors first enter one by its
name; a cookie remembers it, signed with the organization's secret, and from then on
they see its tournaments. Viewing needs nothing more.

The organization's admin logs in with its admin user and password and may change
everything in it. The admin cookie is an HMAC (with the organization's secret) of the
stored password hash, so changing the password logs every admin out.

A super admin (table superadmins, created with orgs.py) logs in the same way, with
their own user and password. They may create organizations (with their admin user and
password), enter any of them, and are admin in all of them.

A tournament also has a player password. It is stored as typed so the admin can look
it up and share it. Players who log in with it may enter set results in that
tournament, and create sets in a manual one; nothing else. Their cookie, one per
tournament, is an HMAC of that password, so a new password logs them out.
"""
import hashlib
import hmac

from fastapi import Request

from . import db, orgs
from .db import default_player_password  # noqa: F401 (used by the app and tests)

ORG_COOKIE = "org"
COOKIE = "editor"
SUPER_COOKIE = "super"
COOKIE_MAX_AGE = 180 * 24 * 3600  # stay logged in for about 6 months
PLAYER_COOKIE = "player_{}"       # per tournament id


class LoginRequired(Exception):
    """Raised by `require_editor`; the app turns it into a redirect to /login."""

    def __init__(self, next_url: str):
        self.next_url = next_url


def _sign(org, message: str) -> str:
    return hmac.new(org["secret"].encode(), message.encode(), hashlib.sha256).hexdigest()


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


# --- Admins ------------------------------------------------------------------------

def editor_token(org) -> str:
    return _sign(org, f"admin:{org['id']}:{org['admin_password']}")


def admin_login(conn, user: str, password: str):
    """The organization whose admin this is, or None."""
    org = conn.execute("SELECT * FROM organizations WHERE admin_user = ?",
                       (user.strip(),)).fetchone()
    return org if org and orgs.check_password(password, org["admin_password"]) else None


def is_editor(request: Request) -> bool:
    """Admin of the organization being viewed: its own admin, or a super admin."""
    org = current_org(request)
    if org is None:
        return False
    return is_super(request) or hmac.compare_digest(request.cookies.get(COOKIE, ""),
                                                    editor_token(org))


# --- Super admins ----------------------------------------------------------------------

def super_cookie(admin) -> str:
    return f"{admin['id']}.{_sign(admin, 'super:%d:%s' % (admin['id'], admin['password']))}"


def super_login(conn, user: str, password: str):
    """The super admin with this user and password, or None."""
    admin = conn.execute("SELECT * FROM superadmins WHERE username = ?",
                         (user.strip(),)).fetchone()
    return admin if admin and orgs.check_password(password, admin["password"]) else None


def is_super(request: Request) -> bool:
    cached = request.scope.setdefault("state", {})
    if "super" not in cached:
        admin_id, _, token = request.cookies.get(SUPER_COOKIE, "").partition(".")
        admin = None
        if admin_id.isdigit():
            with db.connect() as conn:
                admin = conn.execute("SELECT * FROM superadmins WHERE id = ?",
                                     (int(admin_id),)).fetchone()
        cached["super"] = bool(admin) and hmac.compare_digest(super_cookie(admin), f"{admin_id}.{token}")
    return cached["super"]


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


def is_player(request: Request, tournament) -> bool:
    """Logged in with this tournament's player password."""
    if not tournament["player_password"]:
        return False
    cookie = request.cookies.get(PLAYER_COOKIE.format(tournament["id"]), "")
    return hmac.compare_digest(cookie, player_token(tournament))


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
    """Jinja context processor: the organization, and whether this browser may edit."""
    editor, superadmin = is_editor(request), is_super(request)
    return {"editor": editor, "superadmin": superadmin, "org": current_org(request),
            "login_enabled": True,
            "logged_in": editor or superadmin or bool(player_cookies(request))}
