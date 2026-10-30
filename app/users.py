"""User accounts: super admins, organization admins and players.

Every account has a unique username and may log in with it or with its email (an
email always has "@", a username never). Passwords are stored as a salted PBKDF2
hash; an organization admin's password is also kept as typed, so super admins can
look it up (`password_plain`). `secret` signs the account's cookie (auth.py).

A player account claims players: `players.user_id`, at most one player per
organization, so the same person can play in several organizations.

This module only needs the standard library, so it also runs where the app's
dependencies aren't installed (orgs.py uses it from Azure's Kudu console).
"""
import hashlib
import hmac
import secrets

ROLES = ("super", "org_admin", "player")
ITERATIONS = 200_000
MIN_PASSWORD = 8  # for player accounts; admins' passwords are set by other admins
FIELDS = ("username", "email", "first_name", "last_name", "display_name")


class UserError(ValueError):
    """A rejected change. The message is an i18n key (e.g. "err_username_taken")."""


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


def clean(fields):
    """Strip the account fields; empty optional ones become None."""
    out = {k: " ".join((fields.get(k) or "").split()) or None for k in FIELDS if k in fields}
    if out.get("username"):
        out["username"] = out["username"].replace(" ", "")
    return out


def check_fields(conn, fields, user_id=None):
    """Raise UserError if the username or email is missing, malformed or taken."""
    username, email = fields.get("username"), fields.get("email")
    if "username" in fields and (not username or "@" in username):
        raise UserError("err_username_invalid")
    if email is not None and ("@" not in email or " " in email):
        raise UserError("err_email_invalid")
    for column, value, error in (("username", username, "err_username_taken"),
                                 ("email", email, "err_email_taken")):
        if value and conn.execute(f"SELECT 1 FROM users WHERE {column} = ? AND id IS NOT ?",
                                  (value, user_id)).fetchone():
            raise UserError(error)


def create_user(conn, role, username, password, organization_id=None, **fields):
    """Add an account and return its id."""
    if role not in ROLES:
        raise UserError("err_role")
    if not password:
        raise UserError("err_password_required")
    fields = clean({"username": username, **fields})
    check_fields(conn, fields)
    columns = ["role", "organization_id", "password", "password_plain", "secret", *fields]
    values = [role, organization_id, hash_password(password),
              password if role == "org_admin" else None, secrets.token_hex(32),
              *fields.values()]
    return conn.execute(f"INSERT INTO users ({', '.join(columns)}) "
                        f"VALUES ({', '.join('?' * len(values))})", values).lastrowid


def get(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def find_login(conn, login):
    """The account with this email (if `login` has "@") or username, or None."""
    login = login.strip()
    if not login:
        return None
    column = "email" if "@" in login else "username"
    return conn.execute(f"SELECT * FROM users WHERE {column} = ?", (login,)).fetchone()


def login(conn, name, password):
    """The account with this username or email and password, or None."""
    user = find_login(conn, name)
    return user if user and check_password(password, user["password"]) else None


def set_password(conn, user_id, password):
    """Give an account a new password (it is logged out everywhere)."""
    if not password:
        raise UserError("err_password_required")
    user = get(conn, user_id)
    conn.execute("UPDATE users SET password = ?, password_plain = ? WHERE id = ?",
                 (hash_password(password), password if user["role"] == "org_admin" else None,
                  user_id))
    sync_org(conn, user_id)


def update_user(conn, user_id, **fields):
    """Change an account's username, email or names."""
    fields = clean(fields)
    check_fields(conn, fields, user_id)
    if "email" in fields and not fields["email"] and get(conn, user_id)["role"] == "player":
        raise UserError("err_email_required")
    if fields:
        conn.execute(f"UPDATE users SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",
                     (*fields.values(), user_id))
        sync_org(conn, user_id)


def sync_org(conn, user_id):
    """Copy an organization admin's username and password to the deprecated columns of
    organizations (db.py), so they never go stale."""
    user = get(conn, user_id)
    if user["role"] == "org_admin" and org_admin(conn, user["organization_id"])["id"] == user_id:
        conn.execute("UPDATE organizations SET admin_user = ?, admin_password = ?, "
                     "admin_password_plain = ? WHERE id = ?",
                     (user["username"], user["password"], user["password_plain"],
                      user["organization_id"]))


def set_role(conn, user_id, role, organization_id=None):
    if role not in ROLES or (role == "org_admin" and organization_id is None):
        raise UserError("err_role")
    conn.execute("UPDATE users SET role = ?, organization_id = ? WHERE id = ?",
                 (role, organization_id if role == "org_admin" else None, user_id))


def link_player(conn, user_id, player_id):
    """Let the account claim a player that has none (one per organization)."""
    player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    if player is None or player["user_id"] not in (None, user_id):
        raise UserError("err_player_claimed")
    if conn.execute("SELECT 1 FROM players WHERE user_id = ? AND organization_id = ? "
                    "AND id != ?", (user_id, player["organization_id"], player_id)).fetchone():
        raise UserError("err_already_linked")
    conn.execute("UPDATE players SET user_id = ? WHERE id = ?", (user_id, player_id))


def unlink_player(conn, player_id):
    conn.execute("UPDATE players SET user_id = NULL WHERE id = ?", (player_id,))


def org_admin(conn, organization_id):
    """The (first) admin account of an organization, or None."""
    return conn.execute("SELECT * FROM users WHERE role = 'org_admin' AND organization_id = ? "
                        "ORDER BY id LIMIT 1", (organization_id,)).fetchone()
