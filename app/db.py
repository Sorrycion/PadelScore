"""SQLite storage for players, tournaments, matchdays and matches (one row per set)."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("PADELSCORE_DB", "padelscore.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    -- SQLite has no real date type: store ISO 'YYYY-MM-DD' and reject anything else.
    held_on DATE NOT NULL CHECK (held_on IS date(held_on))
);

-- A matchday (jornada) of a tournament: one day of play.
CREATE TABLE IF NOT EXISTS matchdays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
    number INTEGER NOT NULL,
    played_on DATE NOT NULL CHECK (played_on IS date(played_on)),
    UNIQUE (tournament_id, number)
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
