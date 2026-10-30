-- Accounts: super admins and organization admins become users rows (same usernames
-- and passwords); players can be claimed by an account (players.user_id).

-- Accounts (see users.py): super admins (admin everywhere), organization admins and
-- players. Log in with username or email; password is a hash, password_plain is kept
-- for org admins only (super admins may look it up).
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL CHECK (role IN ('super', 'org_admin', 'player')),
    organization_id INTEGER REFERENCES organizations(id),
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email TEXT UNIQUE COLLATE NOCASE,
    first_name TEXT,
    last_name TEXT,
    display_name TEXT,
    password TEXT NOT NULL,
    password_plain TEXT,
    secret TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (role != 'org_admin' OR organization_id IS NOT NULL)
);

ALTER TABLE players ADD COLUMN user_id INTEGER REFERENCES users(id);
CREATE UNIQUE INDEX IF NOT EXISTS players_org_user ON players (organization_id, user_id);

INSERT INTO users (role, username, password, secret)
SELECT 'super', username, password, secret FROM superadmins ORDER BY id;

-- Usernames are unique among all accounts now: an organization admin with a super
-- admin's username gets "_<organization id>" added.
INSERT INTO users (role, organization_id, username, password, password_plain, secret)
SELECT 'org_admin', o.id,
       CASE WHEN EXISTS (SELECT 1 FROM superadmins s WHERE s.username = o.admin_user)
            THEN o.admin_user || '_' || o.id ELSE o.admin_user END,
       o.admin_password, o.admin_password_plain, lower(hex(randomblob(32)))
FROM organizations o ORDER BY o.id;
