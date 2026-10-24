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

-- One set, played on a court during a matchday.
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matchday_id INTEGER NOT NULL REFERENCES matchdays(id),
    court INTEGER NOT NULL CHECK (court >= 1),
    a1 INTEGER NOT NULL REFERENCES players(id),
    a2 INTEGER NOT NULL REFERENCES players(id),
    b1 INTEGER NOT NULL REFERENCES players(id),
    b2 INTEGER NOT NULL REFERENCES players(id),
    team_a_games INTEGER NOT NULL,
    team_b_games INTEGER NOT NULL,
    winner TEXT CHECK (winner IN ('A', 'B'))   -- NULL for a tied set
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
    with connect() as conn:
        conn.executescript(SCHEMA)
