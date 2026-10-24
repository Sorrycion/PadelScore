"""PadelScore web app."""
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import markdown
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .i18n import COOKIE, LANGS, get_lang, i18n_context, translator
from .scoring import ScoreError, check_set, court_moves, tournament_results

BASE = Path(__file__).parent
RULES = BASE.parent / "docs" / "REGLAMENTO.md"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="PadelScore", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates", context_processors=[i18n_context])


def opt_int(value: str | None) -> int | None:
    """Query-string ids from filter forms arrive as '' when nothing is chosen."""
    try:
        return int(value) if value else None
    except ValueError:
        return None


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
    if not next.startswith("/") or next.startswith(("//", "/\\")):
        next = "/"  # only redirect within this site
    response = redirect(next)
    if lang in LANGS:
        response.set_cookie(COOKIE, lang, max_age=365 * 24 * 3600, samesite="lax")
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


@app.post("/tournaments")
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


@app.post("/tournaments/{tournament_id}/matchdays")
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
    return redirect(f"/matchdays/{cur.lastrowid}")


@app.get("/matchdays/{matchday_id}", response_class=HTMLResponse)
def matchday_page(request: Request, matchday_id: int, move: int = 1):
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
        })


@app.get("/players", response_class=HTMLResponse)
def players_page(request: Request, error: str | None = None):
    with db.connect() as conn:
        return templates.TemplateResponse(request, "players.html", {
            "players": all_players(conn), "error": error,
        })


@app.post("/players")
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


@app.get("/players/{player_id}", response_class=HTMLResponse)
def player_page(request: Request, player_id: int):
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
                        if r["id"] == player_id:
                            history.append({**entry, "court": court, **r})
            tournaments.append({"id": t["id"], "name": t["name"],
                                "position": me and me["position"], "total": me,
                                "history": history})

    partners = Counter()
    for s in sets:
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
                    team_a_games: int = Form(...), team_b_games: int = Form(...)):
    return {"matchday_id": matchday_id, "court": court,
            "a1": a1, "a2": a2, "b1": b1, "b2": b2,
            "team_a_games": team_a_games, "team_b_games": team_b_games}


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
    try:
        return None, check_set(form["team_a_games"], form["team_b_games"])
    except ScoreError:
        return _("err_set"), None


@app.get("/matches/new", response_class=HTMLResponse)
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


@app.post("/matches")
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


@app.get("/matches/{match_id}/edit", response_class=HTMLResponse)
def edit_match_page(request: Request, match_id: int):
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        return render_match_form(request, conn, {c: match[c] for c in MATCH_COLUMNS},
                                 match_id=match_id)


@app.post("/matches/{match_id}")
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


@app.post("/matches/{match_id}/delete")
def delete_match(match_id: int):
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    return redirect(f"/matchdays/{match['matchday_id']}")
