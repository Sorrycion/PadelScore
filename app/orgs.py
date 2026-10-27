"""Organizations and super admins: create them and change their passwords.

Everything (players, tournaments and what hangs from them) belongs to an organization.
Its admin logs in with the organization's admin user and password. The password is
stored as a salted PBKDF2 hash; `secret` signs the organization's cookies (auth.py).

This module only needs the standard library, so it also runs where the app's
dependencies aren't installed (e.g. Azure's Kudu console):

    python -m app.orgs create "Name" "admin user" "admin password"
    python -m app.orgs password "admin user" "new password"
    python -m app.orgs superadmin "user" "password"   (creates one, or changes its password)

The first organization created adopts every player and tournament that has none
(those from before organizations existed).
"""
import hashlib
import hmac
import secrets
import sys

from . import db

ITERATIONS = 200_000


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def check_password(password, stored):
    try:
        _, iterations, salt, digest = stored.split("$")
        given = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                    int(iterations))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(given.hex(), digest)


def create_org(conn, name, admin_user, password):
    """Add an organization and return its id. The first one adopts the players and
    tournaments that have no organization yet."""
    name, admin_user = " ".join(name.split()), admin_user.strip()
    if not name or not admin_user or not password:
        raise ValueError("Name, admin user and password are required.")
    first = conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 0
    org_id = conn.execute(
        "INSERT INTO organizations (name, admin_user, admin_password, secret) "
        "VALUES (?, ?, ?, ?)",
        (name, admin_user, hash_password(password), secrets.token_hex(32))).lastrowid
    if first:
        for table in ("players", "tournaments"):
            conn.execute(f"UPDATE {table} SET organization_id = ? WHERE organization_id IS NULL",
                         (org_id,))
    return org_id


def set_password(conn, admin_user, password):
    """Change an organization's admin password (its admins must log in again)."""
    if not password:
        raise ValueError("The password can't be empty.")
    changed = conn.execute("UPDATE organizations SET admin_password = ? WHERE admin_user = ?",
                           (hash_password(password), admin_user.strip())).rowcount
    if not changed:
        raise ValueError(f"No organization has the admin user {admin_user!r}.")


def set_superadmin(conn, username, password):
    """Add a super admin, or change the password of an existing one."""
    username = username.strip()
    if not username or not password:
        raise ValueError("User and password are required.")
    if conn.execute("UPDATE superadmins SET password = ? WHERE username = ?",
                    (hash_password(password), username)).rowcount:
        return
    conn.execute("INSERT INTO superadmins (username, password, secret) VALUES (?, ?, ?)",
                 (username, hash_password(password), secrets.token_hex(32)))


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
