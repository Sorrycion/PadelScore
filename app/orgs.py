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
import secrets
import sys

from . import db, users
from .users import check_password, hash_password  # noqa: F401 (used by older callers)


def create_org(conn, name, admin_user, password):
    """Add an organization with its admin account and return its id. The first one
    adopts the players and tournaments that have no organization yet."""
    name, admin_user = " ".join(name.split()), admin_user.strip()
    if not name or not admin_user or not password:
        raise ValueError("Name, admin user and password are required.")
    users.check_fields(conn, users.clean({"username": admin_user}))
    first = conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 0
    org_id = conn.execute(
        "INSERT INTO organizations (name, admin_user, admin_password, admin_password_plain, "
        "secret) VALUES (?, ?, ?, ?, ?)",
        (name, admin_user, hash_password(password), password, secrets.token_hex(32))).lastrowid
    user_id = users.create_user(conn, "org_admin", admin_user, password, organization_id=org_id)
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
