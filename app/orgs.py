"""Organizations: create them, with their admin account (users.py).

Everything (players, tournaments and what hangs from them) belongs to an organization.
Its admin is a users row with role org_admin. `secret` signs the cookie of browsers
that entered the organization (auth.py).

This module only needs the standard library, so it also runs where the app's
dependencies aren't installed (e.g. Azure's Kudu console):

    python -m app.orgs create "Name" "admin user" "admin password"
    python -m app.orgs password "user" "new password"     (any account)
    python -m app.orgs superadmin "user" "password"       (creates one, or changes its password)

The first organization created adopts every player and tournament that has none
(those from before organizations existed).
"""
import re
import secrets
import sys
import unicodedata

from . import db, users
from .users import check_password, hash_password  # noqa: F401 (used by older callers)


# The app's own first path segments: an organization's slug can't be one of them.
SECTIONS = ("standings", "tournaments", "players", "matchdays", "matches", "medals",
            "courts", "users", "emails", "friendlies")  # pages of one organization: /<slug>/<section>/...
RESERVED = {"static", "enter", "login", "logout", "lang", "rules", "orgs", "me", "health",
            "signup", "join", "sw.js", "r", "install", "tasks", "unsubscribe", "welcome",
            *SECTIONS}


def slugify(name):
    """An organization's name for its URLs: lowercase ASCII letters and digits, dashes
    between words ("Liga Nené" -> "liga-nene")."""
    plain = unicodedata.normalize("NFD", name.casefold())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "org"
    return f"{slug}-org" if slug in RESERVED else slug


def unique_slug(conn, name, org_id=None):
    """slugify(name), with -2, -3... if another organization already has it."""
    base = slug = slugify(name)
    n = 2
    while conn.execute("SELECT 1 FROM organizations WHERE slug = ? AND id IS NOT ?",
                       (slug, org_id)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def create_org(conn, name, admin_user="", password="", user_id=None):
    """Add an organization and return its id. Its admin is a new account (admin_user +
    password) or, with `user_id`, an existing player account, which becomes its admin
    (keeping its password and its players; an account administers one organization).
    The first one adopts the players and tournaments that have no organization yet."""
    name, admin_user = " ".join(name.split()), (admin_user or "").strip()
    account = users.get(conn, user_id) if user_id is not None else None
    if user_id is not None and (account is None or account["role"] != "player"):
        raise users.UserError("err_admin_account")
    if not name or not account and not (admin_user and password):
        raise ValueError("Name, admin user and password are required.")
    if account:
        admin_user, hashed, plain = account["username"], account["password"], None
    else:
        users.check_fields(conn, users.clean({"username": admin_user}))
        hashed, plain = hash_password(password), password
    first = conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 0
    org_id = conn.execute(
        "INSERT INTO organizations (name, admin_user, admin_password, admin_password_plain, "
        "secret, slug) VALUES (?, ?, ?, ?, ?, ?)",
        (name, admin_user, hashed, plain, secrets.token_hex(32),
         unique_slug(conn, name))).lastrowid
    if account:
        users.set_role(conn, user_id, "org_admin", org_id)
    else:
        user_id = users.create_user(conn, "org_admin", admin_user, password,
                                    organization_id=org_id)
    users.sync_org(conn, user_id)
    if first:
        for table in ("players", "tournaments"):
            conn.execute(f"UPDATE {table} SET organization_id = ? WHERE organization_id IS NULL",
                         (org_id,))
    return org_id


def set_password(conn, username, password):
    """Change an account's password (it must log in again)."""
    user = users.find_login(conn, username)
    if user is None:
        raise ValueError(f"No account has the user {username!r}.")
    users.set_password(conn, user["id"], password)


def update_admin(conn, org_id, admin_user, password=""):
    """Change an organization's admin user, and its password unless `password` is empty.
    Raises ValueError (users.UserError) if the user is empty or taken."""
    admin = users.org_admin(conn, org_id)
    users.update_user(conn, admin["id"], username=admin_user)
    if password:
        users.set_password(conn, admin["id"], password)


def set_superadmin(conn, username, password):
    """Add a super admin, or change the password of an existing one."""
    user = users.find_login(conn, username)
    if user is None:
        users.create_user(conn, "super", username, password)
    elif user["role"] != "super":
        raise ValueError(f"{username!r} is an account that isn't a super admin.")
    else:
        users.set_password(conn, user["id"], password)


def main(args):
    db.init_db()
    with db.connect() as conn:
        if len(args) == 4 and args[0] == "create":
            org_id = create_org(conn, *args[1:])
            print(f"Organization {args[1]!r} created (id {org_id}).")
        elif len(args) == 3 and args[0] == "password":
            set_password(conn, *args[1:])
            print("Password changed.")
        elif len(args) == 3 and args[0] == "superadmin":
            set_superadmin(conn, *args[1:])
            print(f"Super admin {args[1]!r} saved.")
        else:
            print(__doc__)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
