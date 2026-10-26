"""PadelScore web app."""
import time
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import quote

import markdown
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auth, db
from .auth import LoginRequired, require_editor
from .i18n import COOKIE, LANGS, get_lang, i18n_context, translator
from .scoring import (ScoreError, check_set, court_moves, court_rotation, is_played,
                      next_courts, tournament_results)

BASE = Path(__file__).parent
RULES = BASE.parent / "docs" / "REGLAMENTO.md"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="PadelScore", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates",
                            context_processors=[i18n_context, auth.auth_context])
EDIT = [Depends(require_editor)]  # routes that change data need the club password


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


def redirect(url: str):
    return RedirectResponse(url, status_code=303)


# --- Queries -------------------------------------------------------------------

def all_players(conn):
    return conn.execute("SELECT * FROM players ORDER BY name").fetchall()


def all_tournaments(conn):
    return conn.execute(
        """
        SELECT t.*, COUNT(d.id) AS matchdays
        FROM tournaments t LEFT JOIN matchdays d ON d.tournament_id = t.id
        GROUP BY t.id
        ORDER BY t.held_on DESC, t.id DESC
        """
    ).fetchall()


def all_matchdays(conn):
    return conn.execute(
        """
        SELECT d.*, t.name AS tournament
        FROM matchdays d JOIN tournaments t ON t.id = d.tournament_id
        ORDER BY d.played_on DESC, t.name, d.number DESC
        """
    ).fetchall()


def get_or_404(conn, table, row_id):
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"{table[:-1].capitalize()} not found")
    return row


def set_rows(conn, tournament_id=None, matchday_id=None, player_id=None, limit=None):
    """Sets (rows of `matches`) with player, matchday and tournament names."""
    sql = """
        SELECT m.id, m.matchday_id, d.number AS matchday, d.played_on,
               d.tournament_id, t.name AS tournament, m.court,
               m.team_a_games, m.team_b_games, m.winner,
               m.a1 AS a1_id, pa1.name AS a1, m.a2 AS a2_id, pa2.name AS a2,
               m.b1 AS b1_id, pb1.name AS b1, m.b2 AS b2_id, pb2.name AS b2
        FROM matches m
        JOIN matchdays d ON d.id = m.matchday_id
        JOIN tournaments t ON t.id = d.tournament_id
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
    return tournament_results([
        {"id": d["id"], "number": d["number"], "played_on": d["played_on"],
         "sets": sets.get(d["id"], [])}
        for d in matchdays
    ])


# --- Pages -------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with db.connect() as conn:
        latest = conn.execute(
            "SELECT * FROM tournaments ORDER BY held_on DESC, id DESC LIMIT 1"
        ).fetchone()
        results, standings = load_results(conn, latest["id"]) if latest else ([], [])
        return templates.TemplateResponse(request, "index.html", {
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
    if not auth.password_matches(password):
        time.sleep(1)  # slow down password guessing
        return templates.TemplateResponse(request, "login.html", {
            "next": safe_next(next), "error": "err_wrong_password",
        }, status_code=401)
    response = redirect(safe_next(next))
    response.set_cookie(auth.COOKIE, auth.editor_token(auth.edit_password()),
                        max_age=auth.COOKIE_MAX_AGE, httponly=True, samesite="lax",
                        secure=auth.is_https(request))
    return response


@app.post("/logout")
def logout():
    response = redirect("/")
    response.delete_cookie(auth.COOKIE)
    return response


@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request):
    html = markdown.markdown(RULES.read_text(encoding="utf-8"), extensions=["tables"])
    return templates.TemplateResponse(request, "rules.html", {"rules": html})


@app.get("/tournaments", response_class=HTMLResponse)
def tournaments_page(request: Request, error: str | None = None):
    with db.connect() as conn:
        return templates.TemplateResponse(request, "tournaments.html", {
            "tournaments": all_tournaments(conn), "error": error,
            "today": date.today().isoformat(),
        })


@app.post("/tournaments", dependencies=EDIT)
def add_tournament(name: str = Form(...), held_on: str = Form("")):
    name, held_on = name.strip(), parse_date(held_on)
    if not name:
        return redirect("/tournaments?error=err_name_required")
    if held_on is None:
        return redirect("/tournaments?error=err_invalid_date")
    with db.connect() as conn:
        conn.execute("INSERT INTO tournaments (name, held_on) VALUES (?, ?)",
                     (name, held_on))
    return redirect("/tournaments")


@app.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
def tournament_page(request: Request, tournament_id: int, error: str | None = None):
    with db.connect() as conn:
        tournament = get_or_404(conn, "tournaments", tournament_id)
        results, standings = load_results(conn, tournament_id)
        return templates.TemplateResponse(request, "tournament.html", {
            "tournament": tournament,
            "results": results,
            "standings": standings,
            "today": date.today().isoformat(),
            "error": error,
        })


@app.post("/tournaments/{tournament_id}/delete", dependencies=EDIT)
def delete_tournament(tournament_id: int):
    """Delete a tournament with all its matchdays and sets; players are kept."""
    with db.connect() as conn:
        get_or_404(conn, "tournaments", tournament_id)
        conn.execute(
            "DELETE FROM matches WHERE matchday_id IN "
            "(SELECT id FROM matchdays WHERE tournament_id = ?)", (tournament_id,))
        conn.execute("DELETE FROM matchdays WHERE tournament_id = ?", (tournament_id,))
        conn.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
    return redirect("/tournaments")


@app.post("/tournaments/{tournament_id}/matchdays", dependencies=EDIT)
def add_matchday(tournament_id: int, played_on: str = Form("")):
    played_on = parse_date(played_on)
    with db.connect() as conn:
        get_or_404(conn, "tournaments", tournament_id)
        if played_on is None:
            return redirect(f"/tournaments/{tournament_id}?error=err_invalid_date")
        number = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM matchdays WHERE tournament_id = ?",
            (tournament_id,),
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO matchdays (tournament_id, number, played_on) VALUES (?, ?, ?)",
            (tournament_id, number, played_on),
        )
    return redirect(f"/matchdays/{cur.lastrowid}/courts")


@app.get("/matchdays/{matchday_id}", response_class=HTMLResponse)
def matchday_page(request: Request, matchday_id: int, move: int = 1,
                  error: str | None = None):
    move = 2 if move == 2 else 1
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        tournament = get_or_404(conn, "tournaments", matchday["tournament_id"])
        results, _ = load_results(conn, tournament["id"])
        result = next(r for r in results if r["id"] == matchday_id)
        return templates.TemplateResponse(request, "matchday.html", {
            "tournament": tournament,
            "matchday": result,
            "sets": set_rows(conn, matchday_id=matchday_id),
            "moves": court_moves(result["courts"], move),
            "move": move,
            "error": error,
            "score_inline": True,  # pending sets get their games entered right here
        })


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


def suggest_courts(conn, matchday):
    """Courts for a matchday with no sets yet: the previous matchday's courts after
    moving one player up and one down, or empty courts for everyone."""
    previous = conn.execute(
        "SELECT * FROM matchdays WHERE tournament_id = ? AND number < ? "
        "ORDER BY number DESC LIMIT 1",
        (matchday["tournament_id"], matchday["number"]),
    ).fetchone()
    if previous:
        results, _ = load_results(conn, matchday["tournament_id"])
        courts = next(r for r in results if r["id"] == previous["id"])["courts"]
        if courts:
            return [ids for _, ids in sorted(next_courts(courts, 1).items())], previous
    count = len(all_players(conn)) // 4
    return [[None] * 4 for _ in range(max(count, 1))], None


def render_courts(request, conn, matchday, courts, previous=None, error=None,
                  status_code=200):
    tournament = get_or_404(conn, "tournaments", matchday["tournament_id"])
    return templates.TemplateResponse(request, "courts.html", {
        "tournament": tournament, "matchday": matchday, "courts": courts,
        "players": all_players(conn), "previous": previous, "error": error,
        "has_sets": bool(set_rows(conn, matchday_id=matchday["id"], limit=1)),
    }, status_code=status_code)


@app.get("/courts", dependencies=EDIT)
def latest_courts():
    """The '+ Courts' button: assign courts on the latest matchday."""
    with db.connect() as conn:
        latest = conn.execute(
            "SELECT id FROM matchdays ORDER BY played_on DESC, number DESC, id DESC LIMIT 1"
        ).fetchone()
    return redirect(f"/matchdays/{latest['id']}/courts" if latest else "/tournaments")


@app.get("/matchdays/{matchday_id}/courts", response_class=HTMLResponse, dependencies=EDIT)
def courts_page(request: Request, matchday_id: int):
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        players, _ = courts_of(set_rows(conn, matchday_id=matchday_id))
        if players:
            courts = [ids or [None] * 4 for _, ids in sorted(players.items())]
            previous = None
        else:
            courts, previous = suggest_courts(conn, matchday)
        return render_courts(request, conn, matchday, courts, previous)


@app.post("/matchdays/{matchday_id}/courts", dependencies=EDIT)
async def save_courts(request: Request, matchday_id: int):
    """Save who plays on each court. A court with new players gets its three sets
    (every player partnering each of the others once); a court with the same four
    players keeps its sets."""
    _ = translator(get_lang(request))
    form = await request.form()
    numbered = sorted((int(k[6:]), form.getlist(k)) for k in form
                      if k.startswith("court-") and k[6:].isdigit())
    courts = [[opt_int(v) for v in values] for _, values in numbered]
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        names = {p["id"]: p["name"] for p in all_players(conn)}
        chosen = [ids for ids in courts if any(ids)]  # empty courts are left out

        def error(text):
            return render_courts(request, conn, matchday, courts, error=text,
                                 status_code=400)

        if not chosen:
            return error(_("err_need_court"))
        seen = set()
        for n, ids in enumerate(chosen, 1):
            if len(ids) != 4 or None in ids or len(set(ids)) != 4 \
                    or not all(p in names for p in ids):
                return error(_("err_court_four", n=n))
            for p in ids:
                if p in seen:
                    return error(_("err_player_two_courts", name=names[p]))
                seen.add(p)

        existing, played = courts_of(set_rows(conn, matchday_id=matchday_id))
        changed = sorted(c for c in existing
                         if c > len(chosen) or existing[c] is None
                         or set(existing[c]) != set(chosen[c - 1]))
        for c in changed:
            if c in played:
                return error(_("err_court_has_scores", n=c))
        for c in changed:
            conn.execute("DELETE FROM matches WHERE matchday_id = ? AND court = ?",
                         (matchday_id, c))
        for n, ids in enumerate(chosen, 1):
            if n in existing and n not in changed:
                continue
            for (a1, a2), (b1, b2) in court_rotation(ids):
                conn.execute(
                    "INSERT INTO matches (matchday_id, court, a1, a2, b1, b2) "
                    "VALUES (?, ?, ?, ?, ?, ?)", (matchday_id, n, a1, a2, b1, b2))
    return redirect(f"/matchdays/{matchday_id}")


@app.get("/players", response_class=HTMLResponse)
def players_page(request: Request, error: str | None = None):
    with db.connect() as conn:
        return templates.TemplateResponse(request, "players.html", {
            "players": all_players(conn), "error": error,
        })


@app.post("/players", dependencies=EDIT)
def add_player(name: str = Form(...)):
    name = name.strip()
    if not name:
        return redirect("/players?error=err_name_required")
    with db.connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM players WHERE lower(name) = lower(?)", (name,)
        ).fetchone()
        if exists:
            return redirect("/players?error=err_player_exists")
        conn.execute("INSERT INTO players (name) VALUES (?)", (name,))
    return redirect("/players")


@app.post("/players/{player_id}", dependencies=EDIT)
def rename_player(player_id: int, name: str = Form(...)):
    name = name.strip()
    with db.connect() as conn:
        get_or_404(conn, "players", player_id)
        if not name:
            return redirect(f"/players/{player_id}?error=err_name_required")
        exists = conn.execute(
            "SELECT 1 FROM players WHERE lower(name) = lower(?) AND id != ?", (name, player_id)
        ).fetchone()
        if exists:
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
                 player: str | None = None):
    tournament_id, player_id = opt_int(tournament), opt_int(player)
    with db.connect() as conn:
        return templates.TemplateResponse(request, "matches.html", {
            "matches": set_rows(conn, tournament_id=tournament_id, player_id=player_id),
            "tournaments": all_tournaments(conn),
            "players": all_players(conn),
            "filter": {"tournament": tournament_id, "player": player_id},
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


def render_match_form(request, conn, form, match_id=None, error=None,
                      status_code=200):
    return templates.TemplateResponse(request, "match_form.html", {
        "players": all_players(conn),
        "matchdays": all_matchdays(conn),
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


@app.get("/matches/new", response_class=HTMLResponse, dependencies=EDIT)
def new_match_page(request: Request, matchday: str | None = None,
                   court: str | None = None):
    with db.connect() as conn:
        matchday_id = opt_int(matchday)
        if matchday_id is None:  # default to the latest jornada
            latest = conn.execute(
                "SELECT id FROM matchdays ORDER BY played_on DESC, number DESC, id DESC LIMIT 1"
            ).fetchone()
            matchday_id = latest["id"] if latest else None
        return render_match_form(request, conn, {
            "matchday_id": matchday_id, "court": opt_int(court) or 1,
        })


@app.post("/matches", dependencies=EDIT)
def add_match(request: Request, form: dict = Depends(match_form_data)):
    with db.connect() as conn:
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


@app.get("/matches/{match_id}/edit", response_class=HTMLResponse, dependencies=EDIT)
def edit_match_page(request: Request, match_id: int):
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        return render_match_form(request, conn, {c: match[c] for c in MATCH_COLUMNS},
                                 match_id=match_id)


@app.post("/matches/{match_id}", dependencies=EDIT)
def update_match(request: Request, match_id: int,
                 form: dict = Depends(match_form_data)):
    with db.connect() as conn:
        get_or_404(conn, "matches", match_id)
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


@app.post("/matches/{match_id}/score", dependencies=EDIT)
def save_score(match_id: int, team_a_games: str = Form(""), team_b_games: str = Form("")):
    """Enter (or clear) the games of a set from the matchday page."""
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
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
