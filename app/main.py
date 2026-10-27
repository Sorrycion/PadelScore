"""PadelScore web app."""
import hashlib
import time
import unicodedata
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

import markdown
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auth, db, rounds
from .auth import LoginRequired, require_editor
from .i18n import COOKIE, LANGS, get_lang, i18n_context, translator
from .scoring import (ROUND_MODES, SCORING, ScoreError, check_set, court_moves,
                      court_rotation, is_played, next_courts)

BASE = Path(__file__).parent
DOCS = BASE.parent / "docs"
# The rules page: one section per rule type with written rules (code, file).
RULES = [("liga_amigos", DOCS / "REGLAMENTO.md"), ("americano", DOCS / "AMERICANO.md"),
         ("mexicano", DOCS / "MEXICANO.md"), ("manual", DOCS / "MANUAL.md")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="PadelScore", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates",
                            context_processors=[i18n_context, auth.auth_context])
EDIT = [Depends(require_editor)]  # routes that change data need the club password
MANUAL = "manual"  # rule type whose sets are all made by hand
templates.env.filters["pick_player"] = lambda p: {"id": p["id"], "name": p["name"]}
templates.env.globals.update(
    ROUND_MODES=ROUND_MODES, MANUAL=MANUAL,
    RULE_ICONS={"liga_amigos": "🏅", "americano": "🇺🇸", "mexicano": "🇲🇽", "manual": "✍️"},
    # Changes whenever the stylesheet does, so phones don't keep an old cached copy.
    css_version=hashlib.sha256(b"".join(
        f.read_bytes() for f in sorted((BASE / "static").iterdir()))).hexdigest()[:10],
)


@app.exception_handler(LoginRequired)
def login_required(request: Request, exc: LoginRequired):
    return redirect(f"/login?next={quote(exc.next_url, safe='/')}")


def safe_next(url: str) -> str:
    """Only redirect within this site."""
    if not url.startswith("/") or url.startswith(("//", "/\\")):
        return "/"
    return url


def opt_int(value: str | None) -> int | None:
    """Query-string ids from filter forms arrive as '' when nothing is chosen."""
    try:
        return int(value) if value else None
    except ValueError:
        return None


def opt_games(value: str) -> int | None:
    """Games from a form: '' means the set is not played yet."""
    return int(value) if value.strip() else None


def parse_date(value: str) -> str | None:
    """A form date as ISO 'YYYY-MM-DD', or None if it is not a real date."""
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def here(request: Request) -> str:
    """This page's path and query, to come back to after logging in."""
    return request.url.path + (f"?{request.url.query}" if request.url.query else "")


def redirect(url: str):
    return RedirectResponse(url, status_code=303)


# --- Queries -------------------------------------------------------------------

def all_players(conn):
    return conn.execute("SELECT * FROM players ORDER BY name").fetchall()


def all_rule_types(conn):
    return conn.execute("SELECT * FROM rule_types ORDER BY id").fetchall()


def get_tournament(conn, tournament_id):
    """A tournament with its rule type's name and code, or 404."""
    row = conn.execute(
        "SELECT t.*, r.name AS rule_type, r.code AS rule_code "
        "FROM tournaments t JOIN rule_types r ON r.id = t.rule_type_id WHERE t.id = ?",
        (tournament_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Tournament not found")
    return row


def all_tournaments(conn):
    """Tournaments, newest first, with their rule type, matchdays and players."""
    players = dict(conn.execute(
        """
        SELECT d.tournament_id, COUNT(DISTINCT p.id)
        FROM matches m
        JOIN matchdays d ON d.id = m.matchday_id
        JOIN players p ON p.id IN (m.a1, m.a2, m.b1, m.b2)
        GROUP BY d.tournament_id
        """
    ).fetchall())
    chosen = dict(conn.execute(
        "SELECT tournament_id, COUNT(*) FROM tournament_players GROUP BY tournament_id"
    ).fetchall())
    return [{**t, "players": chosen.get(t["id"]) or players.get(t["id"], 0)} for t in conn.execute(
        """
        SELECT t.*, r.name AS rule_type, r.code AS rule_code, COUNT(d.id) AS matchdays
        FROM tournaments t
        JOIN rule_types r ON r.id = t.rule_type_id
        LEFT JOIN matchdays d ON d.tournament_id = t.id
        GROUP BY t.id
        ORDER BY t.held_on DESC, t.id DESC
        """
    )]


def all_matchdays(conn, tournament_id=None):
    return conn.execute(
        """
        SELECT d.*, t.name AS tournament, r.code AS rule_code
        FROM matchdays d
        JOIN tournaments t ON t.id = d.tournament_id
        JOIN rule_types r ON r.id = t.rule_type_id
        WHERE ? IS NULL OR d.tournament_id = ?
        ORDER BY d.played_on DESC, t.name, d.number DESC
        """, (tournament_id, tournament_id)
    ).fetchall()


def tournament_players(conn, tournament_id):
    """The players of a tournament, by name (its list; may be empty)."""
    return conn.execute(
        "SELECT p.* FROM tournament_players tp JOIN players p ON p.id = tp.player_id "
        "WHERE tp.tournament_id = ? ORDER BY p.name", (tournament_id,)
    ).fetchall()


def clean_name(name):
    """A player name with single spaces between words."""
    return " ".join(name.split())


def name_key(name):
    """What makes two names the same player: case, accents and spacing don't count."""
    plain = unicodedata.normalize("NFD", clean_name(name).casefold())
    return "".join(c for c in plain if not unicodedata.combining(c))


def find_player(conn, name, exclude=None):
    """The id of the player with this name (see `name_key`), or None."""
    key = name_key(name)
    return next((p["id"] for p in conn.execute("SELECT id, name FROM players")
                 if p["id"] != exclude and name_key(p["name"]) == key), None)


def player_id(conn, name):
    """The id of the player with this name, adding them if there is none."""
    name = clean_name(name)
    found = find_player(conn, name)
    if found:
        return found
    return conn.execute("INSERT INTO players (name) VALUES (?)", (name,)).lastrowid


def players_for(conn, tournament_id):
    """Players to pick from in a tournament: its list, or everyone when it has none."""
    return tournament_players(conn, tournament_id) or all_players(conn)


def get_or_404(conn, table, row_id):
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"{table[:-1].capitalize()} not found")
    return row


def set_rows(conn, tournament_id=None, matchday_id=None, player_id=None, limit=None):
    """Sets (rows of `matches`) with player, matchday and tournament names."""
    sql = """
        SELECT m.id, m.matchday_id, d.number AS matchday, d.played_on,
               d.tournament_id, t.name AS tournament, r.code AS rule_code, m.court,
               m.team_a_games, m.team_b_games, m.winner,
               m.a1 AS a1_id, pa1.name AS a1, m.a2 AS a2_id, pa2.name AS a2,
               m.b1 AS b1_id, pb1.name AS b1, m.b2 AS b2_id, pb2.name AS b2
        FROM matches m
        JOIN matchdays d ON d.id = m.matchday_id
        JOIN tournaments t ON t.id = d.tournament_id
        JOIN rule_types r ON r.id = t.rule_type_id
        JOIN players pa1 ON pa1.id = m.a1
        JOIN players pa2 ON pa2.id = m.a2
        JOIN players pb1 ON pb1.id = m.b1
        JOIN players pb2 ON pb2.id = m.b2
    """
    where, params = [], []
    if tournament_id is not None:
        where.append("d.tournament_id = ?")
        params.append(tournament_id)
    if matchday_id is not None:
        where.append("m.matchday_id = ?")
        params.append(matchday_id)
    if player_id is not None:
        where.append("? IN (m.a1, m.a2, m.b1, m.b2)")
        params.append(player_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY d.played_on DESC, d.number DESC, m.court, m.id"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def load_results(conn, tournament_id):
    """(matchdays with their courts, standings) for one tournament."""
    matchdays = conn.execute(
        "SELECT * FROM matchdays WHERE tournament_id = ? ORDER BY number",
        (tournament_id,),
    ).fetchall()
    sets = {}
    for s in set_rows(conn, tournament_id=tournament_id):
        sets.setdefault(s["matchday_id"], []).append(s)
    absent = {}
    for a in conn.execute(
            "SELECT a.* FROM absences a JOIN matchdays d ON d.id = a.matchday_id "
            "WHERE d.tournament_id = ?", (tournament_id,)):
        absent.setdefault(a["matchday_id"], set()).add(a["player_id"])
    score = SCORING[get_tournament(conn, tournament_id)["rule_code"]]
    return score([
        {"id": d["id"], "number": d["number"], "played_on": d["played_on"],
         "sets": sets.get(d["id"], []), "absent": absent.get(d["id"], set())}
        for d in matchdays
    ])


# --- Pages -------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, tournament: str | None = None):
    """Standings of one tournament (the latest unless chosen), with a tournament picker."""
    with db.connect() as conn:
        everyone = all_tournaments(conn)
        chosen = opt_int(tournament)
        if chosen not in [t["id"] for t in everyone]:
            current = [t for t in everyone if not t["ended"]] or everyone
            chosen = current[0]["id"] if current else None
        # Tabs for the tournaments still going (and the chosen one, if it has ended).
        tournaments = [t for t in everyone if not t["ended"] or t["id"] == chosen]
        latest = chosen and get_tournament(conn, chosen)
        results, standings = load_results(conn, latest["id"]) if latest else ([], [])
        return templates.TemplateResponse(request, "index.html", {
            "tournaments": tournaments,
            "tournament": latest,
            "results": results,
            "standings": standings,
            "latest_matchday": results[-1] if results else None,
            "matches": set_rows(conn, tournament_id=latest["id"], limit=6) if latest else [],
        })


@app.get("/lang/{lang}")
def set_language(lang: str, next: str = "/"):
    """Remember the UI language in a cookie and go back to the page the user was on."""
    response = redirect(safe_next(next))
    if lang in LANGS:
        response.set_cookie(COOKIE, lang, max_age=365 * 24 * 3600, samesite="lax")
    return response


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    if auth.is_editor(request):
        return redirect(safe_next(next))
    return templates.TemplateResponse(request, "login.html", {"next": safe_next(next)})


@app.post("/login")
def login(request: Request, password: str = Form(""), next: str = Form("/")):
    """The club password logs in an editor; a tournament's player password logs in its
    players (one cookie per tournament whose password it is)."""
    cookie = {"max_age": auth.COOKIE_MAX_AGE, "httponly": True, "samesite": "lax",
              "secure": auth.is_https(request)}
    if auth.password_matches(password):
        response = redirect(safe_next(next))
        response.set_cookie(auth.COOKIE, auth.editor_token(auth.edit_password()), **cookie)
        return response
    with db.connect() as conn:
        matches = [t for t in conn.execute(
            "SELECT * FROM tournaments WHERE player_password IS NOT NULL ORDER BY id DESC")
            if auth.player_password_matches(password, t)]
    if not password or not matches:
        time.sleep(1)  # slow down password guessing
        return templates.TemplateResponse(request, "login.html", {
            "next": safe_next(next), "error": "err_wrong_password",
        }, status_code=401)
    response = redirect(safe_next(next) if next not in ("", "/")
                        else f"/tournaments/{matches[0]['id']}")
    for t in matches:
        response.set_cookie(auth.PLAYER_COOKIE.format(t["id"]), auth.player_token(t), **cookie)
    return response


@app.post("/logout")
def logout(request: Request):
    response = redirect("/")
    for name in [auth.COOKIE, *auth.player_cookies(request)]:
        response.delete_cookie(name)
    return response


@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request):
    sections = []
    for code, path in RULES:
        text = path.read_text(encoding="utf-8")
        sections.append({"code": code, "title": text.splitlines()[0].lstrip("# "),
                         "html": markdown.markdown(text, extensions=["tables"])})
    return templates.TemplateResponse(request, "rules.html", {"sections": sections})


@app.get("/tournaments", response_class=HTMLResponse)
def tournaments_page(request: Request, error: str | None = None, past: str = ""):
    """Tournaments still going, or (past=1) the ones that have ended."""
    with db.connect() as conn:
        everyone = all_tournaments(conn)
        past = past == "1"
        return templates.TemplateResponse(request, "tournaments.html", {
            "tournaments": [t for t in everyone if bool(t["ended"]) == past], "error": error,
            "past": past, "n_past": sum(1 for t in everyone if t["ended"]),
            "n_current": sum(1 for t in everyone if not t["ended"]),
            "rule_types": all_rule_types(conn),
            "players": all_players(conn),
            "players_json": [{"id": p["id"], "name": p["name"]} for p in all_players(conn)],
            "today": date.today().isoformat(),
        })


@app.post("/tournaments", dependencies=EDIT)
def add_tournament(name: str = Form(...), held_on: str = Form(""),
                   rule_type_id: str = Form("1"), points_per_match: str = Form(""),
                   players: list[int] = Form([]), new_players: list[str] = Form([]),
                   player_password: str = Form("")):
    name, held_on, rule_type_id = name.strip(), parse_date(held_on), opt_int(rule_type_id)
    if not name:
        return redirect("/tournaments?error=err_name_required")
    if held_on is None:
        return redirect("/tournaments?error=err_invalid_date")
    with db.connect() as conn:
        rule = conn.execute("SELECT * FROM rule_types WHERE id = ?", (rule_type_id,)).fetchone()
        if not rule:
            return redirect("/tournaments?error=err_rule_type")
        players = set(players) & {p["id"] for p in all_players(conn)}
        players = sorted(players | {player_id(conn, n) for n in new_players if n.strip()})
        target = None
        if rule["code"] in ROUND_MODES:  # rounds are drawn among the chosen players
            if len(players) < 4:
                return redirect("/tournaments?error=err_round_players")
            target = opt_int(points_per_match)
            if target is not None and target < 1:
                target = None
        password = player_password.strip() or auth.default_player_password(name)
        tournament_id = conn.execute(
            "INSERT INTO tournaments (name, held_on, rule_type_id, points_per_match, "
            "player_password) VALUES (?, ?, ?, ?, ?)",
            (name, held_on, rule_type_id, target,
             password)).lastrowid
        conn.executemany("INSERT INTO tournament_players (tournament_id, player_id) "
                         "VALUES (?, ?)", [(tournament_id, p) for p in players])
    return redirect(f"/tournaments/{tournament_id}")


@app.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
def tournament_page(request: Request, tournament_id: int, error: str | None = None):
    with db.connect() as conn:
        tournament = get_tournament(conn, tournament_id)
        results, standings = load_results(conn, tournament_id)
        return templates.TemplateResponse(request, "tournament.html", {
            "tournament": tournament,
            "results": results,
            "standings": standings,
            "participants": tournament_players(conn, tournament_id),
            "players": all_players(conn),
            "today": date.today().isoformat(),
            "error": error,
        })


@app.post("/tournaments/{tournament_id}/players", dependencies=EDIT)
def add_tournament_player(tournament_id: int, player_name: str = Form(""),
                          create: str = Form("")):
    """Add a player, found by name, to the tournament (e.g. to replace one who left);
    with `create`, a name that isn't a player yet becomes a new player."""
    name = clean_name(player_name)
    with db.connect() as conn:
        get_or_404(conn, "tournaments", tournament_id)
        found = find_player(conn, name)
        if found is None and not (create and name):
            return redirect(f"/tournaments/{tournament_id}?error=err_unknown_player#players")
        conn.execute("INSERT OR IGNORE INTO tournament_players (tournament_id, player_id) "
                     "VALUES (?, ?)", (tournament_id, found or player_id(conn, name)))
    return redirect(f"/tournaments/{tournament_id}#players")


@app.post("/tournaments/{tournament_id}/players/{player_id}/remove", dependencies=EDIT)
def remove_tournament_player(tournament_id: int, player_id: int):
    """Take a player out of the tournament. Their sets and points so far are kept."""
    with db.connect() as conn:
        get_or_404(conn, "tournaments", tournament_id)
        conn.execute("DELETE FROM tournament_players WHERE tournament_id = ? AND player_id = ?",
                     (tournament_id, player_id))
    return redirect(f"/tournaments/{tournament_id}#players")


@app.post("/tournaments/{tournament_id}/players/replace", dependencies=EDIT)
def replace_tournament_player(tournament_id: int, old_id: int = Form(0),
                              player_name: str = Form(""), create: str = Form("")):
    """Put another player (found by name, or new with `create`) in place of one of the
    tournament: in its list and in its sets not played yet. Sets already played, and
    their points, stay with the player who leaves."""
    name = clean_name(player_name)
    back = f"/tournaments/{tournament_id}"
    with db.connect() as conn:
        get_or_404(conn, "tournaments", tournament_id)
        if not conn.execute("SELECT 1 FROM tournament_players WHERE tournament_id = ? "
                            "AND player_id = ?", (tournament_id, old_id)).fetchone():
            return redirect(f"{back}?error=err_choose_leaving#replace")
        new_id = find_player(conn, name)
        if new_id is None and not (create and name):
            return redirect(f"{back}?error=err_unknown_player#replace")
        if new_id == old_id:
            return redirect(f"{back}?error=err_replace_same#replace")
        pending = ("team_a_games IS NULL AND matchday_id IN "
                   "(SELECT id FROM matchdays WHERE tournament_id = ?)")
        if new_id and conn.execute(
                f"SELECT 1 FROM matches WHERE {pending} AND ? IN (a1, a2, b1, b2) "
                "AND ? IN (a1, a2, b1, b2)", (tournament_id, old_id, new_id)).fetchone():
            return redirect(f"{back}?error=err_replace_conflict#replace")
        new_id = new_id or player_id(conn, name)
        for col in ("a1", "a2", "b1", "b2"):
            conn.execute(f"UPDATE matches SET {col} = ? WHERE {col} = ? AND {pending}",
                         (new_id, old_id, tournament_id))
        conn.execute("DELETE FROM tournament_players WHERE tournament_id = ? AND player_id = ?",
                     (tournament_id, old_id))
        conn.execute("INSERT OR IGNORE INTO tournament_players (tournament_id, player_id) "
                     "VALUES (?, ?)", (tournament_id, new_id))
    return redirect(f"{back}#players")


@app.post("/tournaments/{tournament_id}/ended", dependencies=EDIT)
def set_tournament_ended(tournament_id: int, ended: str = Form("1")):
    """End a tournament (it moves to Past tournaments), or reopen it with ended=0."""
    with db.connect() as conn:
        get_or_404(conn, "tournaments", tournament_id)
        conn.execute("UPDATE tournaments SET ended = ? WHERE id = ?",
                     (int(ended == "1"), tournament_id))
    return redirect(f"/tournaments/{tournament_id}")


@app.post("/tournaments/{tournament_id}/player-password", dependencies=EDIT)
def set_player_password(tournament_id: int, password: str = Form("")):
    """Change the players' password; an empty one goes back to the default (from the
    tournament's name). Players who were logged in must log in again."""
    with db.connect() as conn:
        tournament = get_or_404(conn, "tournaments", tournament_id)
        password = password.strip() or auth.default_player_password(tournament["name"])
        conn.execute("UPDATE tournaments SET player_password = ? WHERE id = ?",
                     (password, tournament_id))
    return redirect(f"/tournaments/{tournament_id}#player-password")


@app.post("/tournaments/{tournament_id}/delete", dependencies=EDIT)
def delete_tournament(tournament_id: int):
    """Delete a tournament with all its matchdays and sets; players are kept."""
    with db.connect() as conn:
        get_or_404(conn, "tournaments", tournament_id)
        for table in ("matches", "absences"):
            conn.execute(
                f"DELETE FROM {table} WHERE matchday_id IN "
                "(SELECT id FROM matchdays WHERE tournament_id = ?)", (tournament_id,))
        conn.execute("DELETE FROM matchdays WHERE tournament_id = ?", (tournament_id,))
        conn.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        conn.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
    return redirect("/tournaments")


@app.get("/matchdays/{matchday_id}", response_class=HTMLResponse)
def matchday_page(request: Request, matchday_id: int, move: int = 1,
                  error: str | None = None):
    move = 2 if move == 2 else 1
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        tournament = get_tournament(conn, matchday["tournament_id"])
        results, _ = load_results(conn, tournament["id"])
        result = next(r for r in results if r["id"] == matchday_id)
        sets = set_rows(conn, matchday_id=matchday_id)
        playing = {s[k + "_id"] for s in sets for k in ("a1", "a2", "b1", "b2")}
        resting = [p["name"] for p in tournament_players(conn, tournament["id"])
                   if p["id"] not in playing] if sets else []
        return templates.TemplateResponse(request, "matchday.html", {
            "tournament": tournament,
            "matchday": result,
            "results": results,
            "sets": sets,
            "resting": resting,
            "moves": court_moves(result["courts"], move),
            "move": move,
            "error": error,
            # Only the latest matchday offers to start the next one, a week later.
            "next_number": results[-1]["number"] + 1 if results[-1]["id"] == matchday_id else None,
            "next_date": (date.fromisoformat(matchday["played_on"]) + timedelta(days=7)).isoformat(),
            "score_inline": True,  # pending sets get their games entered right here
            "scorer": auth.can_score(request, tournament),
        })


@app.post("/matchdays/{matchday_id}/absent/{player_id}", dependencies=EDIT)
def toggle_absent(matchday_id: int, player_id: int):
    """Mark a player of this matchday absent (they score 0), or present again."""
    with db.connect() as conn:
        get_or_404(conn, "matchdays", matchday_id)
        if not any(player_id in (s["a1_id"], s["a2_id"], s["b1_id"], s["b2_id"])
                   for s in set_rows(conn, matchday_id=matchday_id)):
            raise HTTPException(404, "Player not on this matchday")
        removed = conn.execute("DELETE FROM absences WHERE matchday_id = ? AND player_id = ?",
                               (matchday_id, player_id)).rowcount
        if not removed:
            conn.execute("INSERT INTO absences (matchday_id, player_id) VALUES (?, ?)",
                         (matchday_id, player_id))
    return redirect(f"/matchdays/{matchday_id}")


@app.post("/matchdays/{matchday_id}/delete", dependencies=EDIT)
def delete_matchday(matchday_id: int):
    """Delete a matchday with its sets; the later matchdays move up a number so the
    numbering has no gaps."""
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        conn.execute("DELETE FROM matches WHERE matchday_id = ?", (matchday_id,))
        conn.execute("DELETE FROM absences WHERE matchday_id = ?", (matchday_id,))
        conn.execute("DELETE FROM matchdays WHERE id = ?", (matchday_id,))
        later = conn.execute(
            "SELECT id FROM matchdays WHERE tournament_id = ? AND number > ? ORDER BY number",
            (matchday["tournament_id"], matchday["number"]),
        ).fetchall()
        for row in later:  # in order, so each number is free when it is taken
            conn.execute("UPDATE matchdays SET number = number - 1 WHERE id = ?", (row["id"],))
    return redirect(f"/tournaments/{matchday['tournament_id']}")


# --- Courts of a matchday ---------------------------------------------------------

def courts_of(sets):
    """{court: [4 player ids]} from a matchday's sets, in the order of its first set;
    a court whose sets don't share the same four players maps to None. Also returns
    the courts that have a played set."""
    players, played = {}, set()
    for s in sets:
        ids = [s[k + "_id"] for k in ("a1", "a2", "b1", "b2")]
        if s["court"] not in players:
            players[s["court"]] = ids
        elif players[s["court"]] is not None and set(ids) != set(players[s["court"]]):
            players[s["court"]] = None
        if is_played(s):
            played.add(s["court"])
    return players, played


def next_number(conn, tournament_id):
    return conn.execute(
        "SELECT COALESCE(MAX(number), 0) + 1 FROM matchdays WHERE tournament_id = ?",
        (tournament_id,),
    ).fetchone()[0]


def previous_matchday(conn, tournament_id, number):
    """The last matchday before `number` that has courts (with its "courts"), or None."""
    results, _ = load_results(conn, tournament_id)
    before = [r for r in results if r["number"] < number and r["courts"]]
    return before[-1] if before else None


def suggest_courts(conn, tournament_id, previous, move):
    """Courts for a new matchday: the previous matchday's courts after `move` players
    of each court go up and `move` go down, or empty courts for everyone."""
    if previous:
        return [ids for _, ids in sorted(next_courts(previous["courts"], move).items())]
    return [[None] * 4 for _ in range(max(len(players_for(conn, tournament_id)) // 4, 1))]


def read_courts(form):
    """Player ids per court from the court-<n> selects, in court order."""
    numbered = sorted((int(k[6:]), form.getlist(k)) for k in form
                      if k.startswith("court-") and k[6:].isdigit())
    return [[opt_int(v) for v in values] for _, values in numbered]


def check_courts(conn, courts, _):
    """Return (courts to save, error); empty courts are left out."""
    names = {p["id"]: p["name"] for p in all_players(conn)}
    chosen = [ids for ids in courts if any(ids)]
    if not chosen:
        return None, _("err_need_court")
    seen = set()
    for n, ids in enumerate(chosen, 1):
        if len(ids) != 4 or None in ids or len(set(ids)) != 4 \
                or not all(p in names for p in ids):
            return None, _("err_court_four", n=n)
        for p in ids:
            if p in seen:
                return None, _("err_player_two_courts", name=names[p])
            seen.add(p)
    return chosen, None


def court_sets(players, code):
    """A court's sets: in the Liga three, every player partnering each of the others
    once; in an Americano / Mexicano round one match, the first two against the last two."""
    if code in ROUND_MODES:
        return [(tuple(players[:2]), tuple(players[2:]))]
    return court_rotation(players)


def same_court(old, new, code):
    """Whether a court keeps its sets: the same four players (the same pairs in an
    Americano / Mexicano round)."""
    if old is None:
        return False
    if code in ROUND_MODES:
        return {frozenset(old[:2]), frozenset(old[2:])} == {frozenset(new[:2]), frozenset(new[2:])}
    return set(old) == set(new)


def add_court_sets(conn, matchday_id, court, players, code):
    for (a1, a2), (b1, b2) in court_sets(players, code):
        conn.execute(
            "INSERT INTO matches (matchday_id, court, a1, a2, b1, b2) "
            "VALUES (?, ?, ?, ?, ?, ?)", (matchday_id, court, a1, a2, b1, b2))


def draw_round(conn, tournament, number, courts=None, rest=()):
    """The suggested courts of an Americano / Mexicano round: (courts, resting ids).
    courts: how many courts are available; rest: players who asked to rest."""
    players = [p["id"] for p in tournament_players(conn, tournament["id"])]
    results, standings = load_results(conn, tournament["id"])
    history = [[ids for _, ids in sorted(courts_of(md["sets"])[0].items()) if ids]
               for md in results if md["number"] < number and md["sets"]]
    seed = tournament["id"] * 1000 + number  # the same suggestion on every reload
    if tournament["rule_code"] == "americano":
        return rounds.americano_round(players, history, seed, courts, rest)
    return rounds.mexicano_round(players, history, [r["id"] for r in standings], seed,
                                 courts, rest)


def move_choice(previous, move):
    """`move` (1 or 2) from the query string; None means ask, which only makes sense
    when there is a previous matchday to move players from."""
    if not previous:
        return 1
    return move if move in (1, 2) else None


def move_urls(**params):
    return {n: "?" + urlencode({**params, "move": n}) for n in (1, 2)}


def render_courts(request, conn, tournament, courts, *, matchday=None, number=None,
                  played_on=None, previous=None, move=None, resting=(), asked=(),
                  court_count=None, error=None, status_code=200):
    """The courts screen: for a new matchday (nothing is saved until the form is sent)
    or to change the courts of an existing one."""
    return templates.TemplateResponse(request, "courts.html", {
        "tournament": tournament, "matchday": matchday, "courts": courts,
        "number": matchday["number"] if matchday else number,
        "played_on": played_on, "players": players_for(conn, tournament["id"]),
        "previous": previous, "move": move,
        "resting": [p["name"] for p in all_players(conn) if p["id"] in resting],
        # Americano / Mexicano: the round's settings (courts available, who asked to rest).
        "participants": tournament_players(conn, tournament["id"]),
        "asked": set(asked), "court_count": court_count or len(courts),
        "move_urls": move_urls(**({} if matchday else {"played_on": played_on})),
        "action": f"/matchdays/{matchday['id']}/courts" if matchday
                  else f"/tournaments/{tournament['id']}/matchdays",
        "has_sets": bool(matchday and set_rows(conn, matchday_id=matchday["id"], limit=1)),
        "error": error,
    }, status_code=status_code)


@app.get("/tournaments/{tournament_id}/matchdays/new", response_class=HTMLResponse,
         dependencies=EDIT)
def new_matchday_page(request: Request, tournament_id: int, played_on: str = "",
                      move: str | None = None, courts: str | None = None,
                      rest: list[int] = Query([])):
    """Draft of the next matchday: choose how many players change court, then review
    the courts. Nothing is saved here."""
    with db.connect() as conn:
        tournament = get_tournament(conn, tournament_id)
        played_on = parse_date(played_on or date.today().isoformat())
        if played_on is None:
            return redirect(f"/tournaments/{tournament_id}?error=err_invalid_date")
        number = next_number(conn, tournament_id)
        if tournament["rule_code"] == MANUAL:  # only the date: sets are added by hand
            return render_courts(request, conn, tournament, [], number=number,
                                 played_on=played_on, move=1)
        if tournament["rule_code"] in ROUND_MODES:
            drawn, resting = draw_round(conn, tournament, number, opt_int(courts), rest)
            return render_courts(request, conn, tournament, drawn, number=number,
                                 played_on=played_on, move=1, resting=resting, asked=rest)
        previous = previous_matchday(conn, tournament_id, number)
        move = move_choice(previous, opt_int(move))
        suggested = suggest_courts(conn, tournament["id"], previous, move) if move else []
        return render_courts(request, conn, tournament, suggested, number=number,
                             played_on=played_on, previous=previous, move=move)


@app.post("/tournaments/{tournament_id}/matchdays", dependencies=EDIT)
async def add_matchday(request: Request, tournament_id: int):
    """Save a new matchday together with its courts and their sets."""
    _ = translator(get_lang(request))
    form = await request.form()
    courts = read_courts(form)
    with db.connect() as conn:
        tournament = get_tournament(conn, tournament_id)
        played_on = parse_date(form.get("played_on", ""))
        number = next_number(conn, tournament_id)
        manual = tournament["rule_code"] == MANUAL
        chosen, error = ([], None) if manual else check_courts(conn, courts, _)
        if played_on is None:
            error = _("err_invalid_date")
        if error:
            return render_courts(
                request, conn, tournament, courts, number=number,
                played_on=form.get("played_on", ""), move=opt_int(form.get("move")),
                previous=None if tournament["rule_code"] in ROUND_MODES
                else previous_matchday(conn, tournament_id, number),
                error=error, status_code=400)
        matchday_id = conn.execute(
            "INSERT INTO matchdays (tournament_id, number, played_on) VALUES (?, ?, ?)",
            (tournament_id, number, played_on),
        ).lastrowid
        for n, ids in enumerate(chosen, 1):
            add_court_sets(conn, matchday_id, n, ids, tournament["rule_code"])
    return redirect(f"/matchdays/{matchday_id}")


@app.get("/courts", dependencies=EDIT)
def latest_courts():
    """The '+ Courts' button: the courts of the latest matchday."""
    with db.connect() as conn:
        latest = conn.execute(
            "SELECT id FROM matchdays ORDER BY played_on DESC, number DESC, id DESC LIMIT 1"
        ).fetchone()
    return redirect(f"/matchdays/{latest['id']}/courts" if latest else "/tournaments")


@app.get("/matchdays/{matchday_id}/courts", response_class=HTMLResponse, dependencies=EDIT)
def courts_page(request: Request, matchday_id: int, move: str | None = None,
                courts: str | None = None, rest: list[int] = Query([])):
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        tournament = get_tournament(conn, matchday["tournament_id"])
        if tournament["rule_code"] == MANUAL:  # no courts to assign: add sets by hand
            return redirect(f"/matches/new?matchday={matchday_id}")
        players, _ = courts_of(set_rows(conn, matchday_id=matchday_id))
        if players:
            assigned = [ids or [None] * 4 for _, ids in sorted(players.items())]
            return render_courts(request, conn, tournament, assigned, matchday=matchday)
        if tournament["rule_code"] in ROUND_MODES:
            drawn, resting = draw_round(conn, tournament, matchday["number"],
                                        opt_int(courts), rest)
            return render_courts(request, conn, tournament, drawn, matchday=matchday,
                                 move=1, resting=resting, asked=rest)
        previous = previous_matchday(conn, tournament["id"], matchday["number"])
        move = move_choice(previous, opt_int(move))
        suggested = suggest_courts(conn, tournament["id"], previous, move) if move else []
        return render_courts(request, conn, tournament, suggested, matchday=matchday,
                             previous=previous, move=move)


@app.post("/matchdays/{matchday_id}/courts", dependencies=EDIT)
async def save_courts(request: Request, matchday_id: int):
    """Change who plays on each court. A court with new players gets its three sets
    again; a court with the same four players keeps its sets."""
    _ = translator(get_lang(request))
    courts = read_courts(await request.form())
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        tournament = get_tournament(conn, matchday["tournament_id"])
        chosen, error = check_courts(conn, courts, _)
        existing, played = courts_of(set_rows(conn, matchday_id=matchday_id))
        code = tournament["rule_code"]
        changed = sorted(c for c in existing
                         if not chosen or c > len(chosen)
                         or not same_court(existing[c], chosen[c - 1], code))
        if not error:
            error = next((_("err_court_has_scores", n=c) for c in changed if c in played), None)
        if error:
            return render_courts(request, conn, tournament, courts, matchday=matchday,
                                 error=error, status_code=400)
        for c in changed:
            conn.execute("DELETE FROM matches WHERE matchday_id = ? AND court = ?",
                         (matchday_id, c))
        for n, ids in enumerate(chosen, 1):
            if n not in existing or n in changed:
                add_court_sets(conn, matchday_id, n, ids, code)
    return redirect(f"/matchdays/{matchday_id}")


@app.get("/players", response_class=HTMLResponse)
def players_page(request: Request, error: str | None = None):
    with db.connect() as conn:
        return templates.TemplateResponse(request, "players.html", {
            "players": all_players(conn), "error": error,
        })


@app.post("/players", dependencies=EDIT)
def add_player(name: str = Form(...)):
    name = clean_name(name)
    if not name:
        return redirect("/players?error=err_name_required")
    with db.connect() as conn:
        if find_player(conn, name):
            return redirect("/players?error=err_player_exists")
        conn.execute("INSERT INTO players (name) VALUES (?)", (name,))
    return redirect("/players")


@app.post("/players/{player_id}", dependencies=EDIT)
def rename_player(player_id: int, name: str = Form(...)):
    name = clean_name(name)
    with db.connect() as conn:
        get_or_404(conn, "players", player_id)
        if not name:
            return redirect(f"/players/{player_id}?error=err_name_required")
        if find_player(conn, name, exclude=player_id):
            return redirect(f"/players/{player_id}?error=err_player_exists")
        conn.execute("UPDATE players SET name = ? WHERE id = ?", (name, player_id))
    return redirect(f"/players/{player_id}")


@app.post("/players/{player_id}/delete", dependencies=EDIT)
def delete_player(player_id: int):
    """Delete a player who has no sets. Sets are never removed with a player: that
    would change the other three players' points."""
    with db.connect() as conn:
        get_or_404(conn, "players", player_id)
        if set_rows(conn, player_id=player_id, limit=1):
            return redirect(f"/players/{player_id}?error=err_player_has_sets")
        conn.execute("DELETE FROM absences WHERE player_id = ?", (player_id,))
        conn.execute("DELETE FROM tournament_players WHERE player_id = ?", (player_id,))
        conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
    return redirect("/players")


@app.get("/players/{player_id}", response_class=HTMLResponse)
def player_page(request: Request, player_id: int, error: str | None = None):
    with db.connect() as conn:
        player = get_or_404(conn, "players", player_id)
        sets = set_rows(conn, player_id=player_id)
        tournament_ids = {s["tournament_id"] for s in sets}
        tournaments = []
        for t in all_tournaments(conn):
            if t["id"] not in tournament_ids:
                continue
            results, standings = load_results(conn, t["id"])
            me = next((r for r in standings if r["id"] == player_id), None)
            history = []
            for md in results:
                entry = {"id": md["id"], "number": md["number"],
                         "played_on": md["played_on"]}
                for court, rows in md["courts"].items():
                    for r in rows:
                        if r["id"] == player_id and r["sets"]:
                            history.append({**entry, "court": court, **r})
            tournaments.append({"id": t["id"], "name": t["name"],
                                "position": me and me["position"], "total": me,
                                "history": history})

    partners = Counter()
    for s in filter(is_played, sets):
        for team in (("a1", "a2"), ("b1", "b2")):
            ids = [s[k + "_id"] for k in team]
            if player_id in ids:
                other = team[1] if ids[0] == player_id else team[0]
                partners[(s[other + "_id"], s[other])] += 1

    return templates.TemplateResponse(request, "player.html", {
        "player": player,
        "tournaments": tournaments,
        "partners": [{"id": pid, "name": name, "count": n}
                     for (pid, name), n in partners.most_common()],
        "matches": sets,
        "error": error,
    })


@app.get("/matches", response_class=HTMLResponse)
def matches_page(request: Request, tournament: str | None = None,
                 matchday: str | None = None, player: str | None = None):
    tournament_id, matchday_id = opt_int(tournament), opt_int(matchday)
    player_id = opt_int(player)
    with db.connect() as conn:
        matchdays = all_matchdays(conn, tournament_id)
        if matchday_id not in {d["id"] for d in matchdays}:  # e.g. after changing tournament
            matchday_id = None
        return templates.TemplateResponse(request, "matches.html", {
            "matches": set_rows(conn, tournament_id=tournament_id, matchday_id=matchday_id,
                                player_id=player_id),
            "tournaments": all_tournaments(conn),
            "matchdays": matchdays,
            "players": all_players(conn),
            "filter": {"tournament": tournament_id, "matchday": matchday_id,
                       "player": player_id},
        })


# --- Recording sets ---------------------------------------------------------------

MATCH_COLUMNS = ("matchday_id", "court", "a1", "a2", "b1", "b2",
                 "team_a_games", "team_b_games")


def match_form_data(matchday_id: int = Form(...), court: int = Form(...),
                    a1: int = Form(...), a2: int = Form(...),
                    b1: int = Form(...), b2: int = Form(...),
                    team_a_games: str = Form(""), team_b_games: str = Form("")):
    try:
        games = opt_games(team_a_games), opt_games(team_b_games)
    except ValueError:
        raise HTTPException(422, "Games must be whole numbers")
    return {"matchday_id": matchday_id, "court": court,
            "a1": a1, "a2": a2, "b1": b1, "b2": b2,
            "team_a_games": games[0], "team_b_games": games[1]}


def tournament_of(conn, matchday_id):
    matchday = get_or_404(conn, "matchdays", matchday_id)
    return get_tournament(conn, matchday["tournament_id"])


def set_matchdays(request, conn):
    """Matchdays this browser may add sets to: all for an editor; for players, those of
    manual tournaments whose player password they logged in with."""
    if auth.is_editor(request):
        return all_matchdays(conn)
    allowed = {t["id"] for t in conn.execute(
        "SELECT t.*, r.code AS rule_code FROM tournaments t "
        "JOIN rule_types r ON r.id = t.rule_type_id WHERE r.code = ?", (MANUAL,))
        if auth.is_player(request, t)}
    return [d for d in all_matchdays(conn) if d["tournament_id"] in allowed]


def require_set_maker(request, conn, *matchday_ids):
    """Editors, or players of the manual tournament(s) of these matchdays."""
    if auth.is_editor(request):
        return
    allowed = {d["id"] for d in set_matchdays(request, conn)}
    if not all(i in allowed for i in matchday_ids):
        raise LoginRequired(here(request) if request.method == "GET" else "/")


def render_match_form(request, conn, form, match_id=None, error=None,
                      status_code=200):
    matchdays = set_matchdays(request, conn)
    if auth.is_editor(request):
        players = all_players(conn)
    else:  # players pick among their tournaments' players
        tournament_ids = {d["tournament_id"] for d in matchdays}
        players = sorted({p["id"]: p for t in tournament_ids for p in players_for(conn, t)}.values(),
                         key=lambda p: p["name"].lower())
    return templates.TemplateResponse(request, "match_form.html", {
        "players": players,
        "matchdays": matchdays,
        "form": form,
        "match_id": match_id,
        "error": error,
    }, status_code=status_code)


def validate_match(conn, form, _):
    """Return (error, winner); exactly one of them is None. `_` translates the error."""
    players = [form[k] for k in ("a1", "a2", "b1", "b2")]
    if len(set(players)) != 4:
        return _("err_four_players"), None
    if not conn.execute("SELECT 1 FROM matchdays WHERE id = ?",
                        (form["matchday_id"],)).fetchone():
        return _("err_pick_matchday"), None
    if form["court"] < 1:
        return _("err_court"), None
    if form["team_a_games"] is None and form["team_b_games"] is None:
        return None, None  # pending: the result is entered later
    if form["team_a_games"] is None or form["team_b_games"] is None:
        return _("err_both_games"), None
    try:
        return None, check_set(form["team_a_games"], form["team_b_games"])
    except ScoreError:
        return _("err_set"), None


@app.get("/matches/new", response_class=HTMLResponse)
def new_match_page(request: Request, matchday: str | None = None,
                   court: str | None = None):
    with db.connect() as conn:
        allowed = set_matchdays(request, conn)
        if not allowed and not auth.is_editor(request):
            raise LoginRequired(here(request))
        matchday_id = opt_int(matchday)
        if matchday_id is not None:
            require_set_maker(request, conn, matchday_id)
        elif allowed:  # default to the latest jornada
            latest = max(allowed, key=lambda d: (d["played_on"], d["number"], d["id"]))
            matchday_id = latest["id"]
        return render_match_form(request, conn, {
            "matchday_id": matchday_id, "court": opt_int(court) or 1,
        })


@app.post("/matches")
def add_match(request: Request, form: dict = Depends(match_form_data)):
    with db.connect() as conn:
        require_set_maker(request, conn, form["matchday_id"])
        error, winner = validate_match(conn, form, translator(get_lang(request)))
        if error:
            return render_match_form(request, conn, form, error=error,
                                     status_code=400)
        conn.execute(
            f"INSERT INTO matches ({', '.join(MATCH_COLUMNS)}, winner) "
            f"VALUES ({', '.join('?' * (len(MATCH_COLUMNS) + 1))})",
            [form[c] for c in MATCH_COLUMNS] + [winner],
        )
    return redirect(f"/matchdays/{form['matchday_id']}")


@app.get("/matches/{match_id}/edit", response_class=HTMLResponse)
def edit_match_page(request: Request, match_id: int):
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        require_set_maker(request, conn, match["matchday_id"])
        return render_match_form(request, conn, {c: match[c] for c in MATCH_COLUMNS},
                                 match_id=match_id)


@app.post("/matches/{match_id}")
def update_match(request: Request, match_id: int,
                 form: dict = Depends(match_form_data)):
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        require_set_maker(request, conn, match["matchday_id"], form["matchday_id"])
        error, winner = validate_match(conn, form, translator(get_lang(request)))
        if error:
            return render_match_form(request, conn, form, match_id=match_id,
                                     error=error, status_code=400)
        conn.execute(
            f"UPDATE matches SET {', '.join(c + ' = ?' for c in MATCH_COLUMNS)}, "
            "winner = ? WHERE id = ?",
            [form[c] for c in MATCH_COLUMNS] + [winner, match_id],
        )
    return redirect(f"/matchdays/{form['matchday_id']}")


@app.post("/matches/{match_id}/delete", dependencies=EDIT)
def delete_match(match_id: int):
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    return redirect(f"/matchdays/{match['matchday_id']}")


@app.post("/matches/{match_id}/score")
def save_score(request: Request, match_id: int, team_a_games: str = Form(""),
               team_b_games: str = Form("")):
    """Enter (or clear) the games of a set from the matchday page: editors and the
    tournament's players."""
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        auth.require_scorer(request, tournament_of(conn, match["matchday_id"]))
        back = f"/matchdays/{match['matchday_id']}"
        try:
            a, b = opt_games(team_a_games), opt_games(team_b_games)
            if (a is None) != (b is None):
                return redirect(f"{back}?error=err_both_games")
            winner = check_set(a, b) if a is not None else None
        except (ValueError, ScoreError):
            return redirect(f"{back}?error=err_set")
        conn.execute("UPDATE matches SET team_a_games = ?, team_b_games = ?, winner = ? "
                     "WHERE id = ?", (a, b, winner, match_id))
    return redirect(f"{back}#set-{match_id}")
