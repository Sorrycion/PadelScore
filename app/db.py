"""SQLite storage for organizations, players, tournaments, matchdays and matches (one
row per set). Players and tournaments belong to an organization; the rest hangs from
a tournament."""
import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar

DB_PATH = os.environ.get("PADELSCORE_DB", "padelscore.db")

# The organization of the request being served (set by the app for each request);
# the app's queries only see that organization's rows.
ORG = ContextVar("org", default=None)

SCHEMA = """
-- A club or group of friends. Its admin logs in with admin_user and the password
-- (a hash, see orgs.py); `secret` signs its cookies.
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    admin_user TEXT NOT NULL UNIQUE COLLATE NOCASE,
    admin_password TEXT NOT NULL,
    secret TEXT NOT NULL
);

-- May create organizations and is admin in all of them (see auth.py).
CREATE TABLE IF NOT EXISTS superadmins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password TEXT NOT NULL,
    secret TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER REFERENCES organizations(id),
    name TEXT NOT NULL,
    UNIQUE (organization_id, name)
);

-- How a tournament is scored. `code` picks the scoring in the app (scoring.SCORING).
CREATE TABLE IF NOT EXISTS rule_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE
);
INSERT OR IGNORE INTO rule_types (id, code, name) VALUES
    (1, 'liga_amigos', 'Liga de amigos score'),
    (2, 'americano', 'Americano'),
    (3, 'mexicano', 'Mexicano'),
    (4, 'manual', 'Manual individual');

CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    -- SQLite has no real date type: store ISO 'YYYY-MM-DD' and reject anything else.
    held_on DATE NOT NULL CHECK (held_on IS date(held_on)),
    rule_type_id INTEGER NOT NULL DEFAULT 1 REFERENCES rule_types(id),
    -- Americano / Mexicano: the points a match is played to (16, 21, 24, 32...).
    points_per_match INTEGER CHECK (points_per_match IS NULL OR points_per_match > 0),
    -- Players who log in with this password may enter results (see auth.py). Editors
    -- can see it, to share it with the players.
    player_password TEXT,
    -- 1 once an editor marks the tournament as ended: it moves to "Past tournaments".
    ended INTEGER NOT NULL DEFAULT 0 CHECK (ended IN (0, 1)),
    organization_id INTEGER REFERENCES organizations(id)
);

-- Who plays an Americano or Mexicano tournament (the rounds are drawn among them).
CREATE TABLE IF NOT EXISTS tournament_players (
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    PRIMARY KEY (tournament_id, player_id)
);

-- A matchday (jornada) of a tournament: one day of play.
CREATE TABLE IF NOT EXISTS matchdays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
    number INTEGER NOT NULL,
    played_on DATE NOT NULL CHECK (played_on IS date(played_on)),
    UNIQUE (tournament_id, number)
);

-- A player who misses a matchday: a substitute plays their sets, and they score 0.
CREATE TABLE IF NOT EXISTS absences (
    matchday_id INTEGER NOT NULL REFERENCES matchdays(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    PRIMARY KEY (matchday_id, player_id)
);

-- One set, played on a court during a matchday. Its games stay NULL until it is played.
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matchday_id INTEGER NOT NULL REFERENCES matchdays(id),
    court INTEGER NOT NULL CHECK (court >= 1),
    a1 INTEGER NOT NULL REFERENCES players(id),
    a2 INTEGER NOT NULL REFERENCES players(id),
    b1 INTEGER NOT NULL REFERENCES players(id),
    b2 INTEGER NOT NULL REFERENCES players(id),
    team_a_games INTEGER,
    team_b_games INTEGER,
    winner TEXT CHECK (winner IN ('A', 'B')),   -- NULL for a tied or pending set
    CHECK ((team_a_games IS NULL) = (team_b_games IS NULL))
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    # On Azure the database lives in a folder that may not exist yet (/home/data).
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        allow_pending_sets(conn)
        add_rule_types(conn)
        add_organizations(conn)
        # Every tournament has a player password; older ones get the default.
        for t in conn.execute("SELECT id, name FROM tournaments WHERE player_password IS NULL "
                              "OR player_password = ''").fetchall():
            conn.execute("UPDATE tournaments SET player_password = ? WHERE id = ?",
                         (default_player_password(t["name"]), t["id"]))


def default_player_password(tournament_name):
    """A tournament's default player password: its name in lowercase, words joined by
    underscores ("Liga de la Amistad" -> "liga_de_la_amistad")."""
    return "_".join(tournament_name.lower().split())


def add_organizations(conn):
    """Databases made before organizations: players get an organization_id (and names
    are unique per organization, so the table is rebuilt with the same ids), and
    tournaments get one too. They stay NULL until the first organization adopts them
    (orgs.create_org)."""
    if "organization_id" not in {r["name"] for r in conn.execute("PRAGMA table_info(players)")}:
        create = SCHEMA[SCHEMA.index("CREATE TABLE IF NOT EXISTS players"):]
        create = create[:create.index(");") + 2].replace("IF NOT EXISTS players", "players_new")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")  # matches etc. point at players
        conn.executescript(f"""
            BEGIN;
            {create}
            INSERT INTO players_new (id, name) SELECT id, name FROM players;
            DROP TABLE players;
            ALTER TABLE players_new RENAME TO players;
            COMMIT;
        """)
        conn.execute("PRAGMA foreign_keys = ON")
    if "organization_id" not in {r["name"] for r in conn.execute("PRAGMA table_info(tournaments)")}:
        conn.execute("ALTER TABLE tournaments ADD COLUMN "
                     "organization_id INTEGER REFERENCES organizations(id)")


def add_rule_types(conn):
    """Databases made before rule types: every tournament gets rule type 1 (Liga de
    amigos score), the rules it was played with. Also adds points_per_match, the
    player password and the ended flag."""
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(tournaments)")}
    if "rule_type_id" not in columns:
        # SQLite only adds a column with REFERENCES and a non-NULL default while
        # foreign keys are off.
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("ALTER TABLE tournaments ADD COLUMN "
                     "rule_type_id INTEGER NOT NULL DEFAULT 1 REFERENCES rule_types(id)")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
    if "player_password" not in columns:
        conn.execute("ALTER TABLE tournaments ADD COLUMN player_password TEXT")
    if "ended" not in columns:
        conn.execute("ALTER TABLE tournaments ADD COLUMN "
                     "ended INTEGER NOT NULL DEFAULT 0 CHECK (ended IN (0, 1))")
    if "points_per_match" not in columns:
        conn.execute("ALTER TABLE tournaments ADD COLUMN points_per_match INTEGER "
                     "CHECK (points_per_match IS NULL OR points_per_match > 0)")


def allow_pending_sets(conn):
    """Databases made before sets could be pending have NOT NULL games: rebuild the
    matches table (same columns, same rows) so a set can wait for its result."""
    notnull = {r["name"]: r["notnull"] for r in conn.execute("PRAGMA table_info(matches)")}
    if not notnull["team_a_games"]:
        return
    create = SCHEMA[SCHEMA.index("CREATE TABLE IF NOT EXISTS matches"):]
    conn.executescript(f"""
        BEGIN;
        ALTER TABLE matches RENAME TO matches_old;
        {create}
        INSERT INTO matches SELECT * FROM matches_old;
        DROP TABLE matches_old;
        COMMIT;
    """)
