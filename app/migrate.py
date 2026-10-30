"""Pre-deployment database changes: the SQL files in sql/predeployment.

Each file (0001_name.sql, 0002_name.sql, ...) runs once, in name order, inside a
transaction; schema_migrations records the ones applied. They run on every database,
new ones included: db.SCHEMA is the database before the first file.

The deploy pipeline runs this against the live database before the new code goes
live (it only needs the standard library):

    python -m app.migrate            apply what's pending (= what the app does on start)
    python -m app.migrate --status   list applied and pending files

New schema changes: add the next numbered file there (never edit an applied one).
"""
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent / "sql" / "predeployment"


def files():
    return sorted(FOLDER.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def _table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                 "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))")


def applied(conn):
    """The files already applied (reading only: no table yet means none)."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'schema_migrations'").fetchone():
        return set()
    return {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}


def apply(conn, log=print):
    """Run the pending files in order. A failing file is rolled back and stops the run."""
    _table(conn)
    done = applied(conn)
    pending = [f for f in files() if f.stem not in done]
    conn.commit()
    for f in pending:
        log(f"applying {f.name}")
        try:
            conn.executescript("BEGIN;\n" + f.read_text(encoding="utf-8") +
                               f"\n;INSERT INTO schema_migrations (version) VALUES ('{f.stem}');"
                               "\nCOMMIT;")
        except Exception:
            conn.rollback()
            raise
    return [f.stem for f in pending]


def main(args):
    from . import db
    if args == ["--status"]:
        with db.connect() as conn:
            done = applied(conn)
            for f in files():
                print(("applied " if f.stem in done else "PENDING ") + f.name)
        return 0
    if args:
        print(__doc__)
        return 2
    db.init_db(log=print)
    print("database up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
