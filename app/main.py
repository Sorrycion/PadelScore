"""PadelScore web app."""
import hashlib
import hmac
import os
import random
import re
import secrets
import threading
import time
import unicodedata
from collections import Counter
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

import markdown
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import (auth, charts, countries, db, formats, mailer, medals, migrate, orgs, report,
               rounds, stats, users)
from .auth import LoginRequired, require_editor, require_super
from .i18n import COOKIE, LANGS, get_lang, i18n_context, translator
from .scoring import (AMISTOSOS, DAY_ROUNDS, DRAWN, LADDER, ONE_MATCH, RETAS, REY, ROUND_MODES,
                      SCORING, ScoreError, check_set, court_moves, court_rotation,
                      is_played, next_courts)

BASE = Path(__file__).parent
DOCS = BASE.parent / "docs"
# The rules page: one section per rule type with written rules (code, file).
RULES = [("liga_amigos", DOCS / "REGLAMENTO.md"), ("americano", DOCS / "AMERICANO.md"),
         ("mexicano", DOCS / "MEXICANO.md"), ("manual", DOCS / "MANUAL.md"),
         ("retas", DOCS / "RETAS.md"), ("rey_cancha", DOCS / "REY_CANCHA.md"),
         ("escalafon", DOCS / "ESCALAFON.md"), ("amistosos", DOCS / "AMISTOSOS.md")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="PadelScore", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

# Pages that work before entering an organization (and "/" itself: the login, or the
# account's tournaments in every organization).
OPEN_PATHS = ("/enter", "/login", "/logout", "/static", "/lang", "/rules", "/orgs", "/me",
              "/health", "/signup", "/join", "/sw.js", "/r/", "/install",
              "/tasks/", "/unsubscribe/", "/invite/", "/claim/")
def league_today():
    """Today where the league plays: UTC plus LEAGUE_UTC_OFFSET hours (app setting; Mexico
    City is -6 all year since 2022). The server runs on UTC, which is already tomorrow
    from 18:00 in Mexico: "hoy juegas" and the new jornada's date must not jump ahead."""
    offset = float(os.environ.get("LEAGUE_UTC_OFFSET", "-6"))
    return (datetime.now(timezone.utc) + timedelta(hours=offset)).date()


# The commit being served: the deploy pipeline writes it to app/VERSION ("dev" locally).
VERSION = (BASE / "VERSION").read_text().strip() if (BASE / "VERSION").exists() else "dev"


SECTION_LINK = re.compile(rb'((?:href|action)=")(/(?:%s)(?=[/"?#]))'
                          % "|".join(orgs.SECTIONS).encode())


def in_section(path):
    """Whether a path is a page of one organization (/tournaments/4, /players...)."""
    return path.lstrip("/").split("/", 1)[0].split("?", 1)[0] in orgs.SECTIONS


def keep_inside(send, prefix, cookie=None):
    """Wrap an ASGI `send` so the response stays inside /<slug>: redirects and the HTML's
    links (href, form action) to an organization's pages get the prefix. `cookie`: a
    Set-Cookie header to add (the organization this browser now views)."""
    held = {}

    async def wrapped(message):
        if message["type"] == "http.response.start":
            headers = [(k, prefix + v if k.lower() == b"location" and v.startswith(b"/")
                        and in_section(v.decode("latin-1")) else v) for k, v in message["headers"]]
            if cookie:
                headers.append((b"set-cookie", cookie))
            message = {**message, "headers": headers}
            if not dict(headers).get(b"content-type", b"").startswith(b"text/html"):
                return await send(message)
            held["start"], held["body"] = message, []
            return None
        if message["type"] == "http.response.body" and "start" in held:
            held["body"].append(message.get("body", b""))
            if message.get("more_body"):
                return None
            body = SECTION_LINK.sub(rb"\1" + prefix + rb"\2", b"".join(held["body"]))
            start = held["start"]
            headers = [(k, v) for k, v in start["headers"] if k.lower() != b"content-length"]
            await send({**start, "headers": headers + [(b"content-length", str(len(body)).encode())]})
            return await send({"type": "http.response.body", "body": body})
        return await send(message)
    return wrapped


class OrganizationGate:
    """Every request works inside one organization: its queries only see that
    organization's rows (db.ORG).

    - **/<slug>/...** (e.g. /nene/tournaments/4): the organization of the URL. The path
      goes on without the prefix (/tournaments/4), the browser now views that organization
      (org cookie), and every link and redirect of the answer keeps the prefix
      (keep_inside), so browsing stays filtered to it. /<slug> alone is its standings.
    - Otherwise the one this browser entered (auth.py). A GET of one of its pages without
      the prefix (an old link) goes to /<slug>/... .
    Without an organization, pages other than OPEN_PATHS send the browser to choose one."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].startswith("/static"):
            return await self.app(scope, receive, send)
        first, _, rest = scope["path"].lstrip("/").partition("/")
        by_url = auth.org_from_slug(first) if first and first not in orgs.RESERVED else None
        request = Request(scope)
        cookie_org = auth.org_from_cookie(request)
        if by_url and not auth.can_open(request, by_url):  # someone else's 🏠 Mi pádel
            target = "/" if auth.current_user(request) else \
                f"/login?next={quote(scope['path'], safe='/')}"
            return await redirect(target)(scope, receive, send)
        if cookie_org and not auth.can_open(request, cookie_org):
            cookie_org = None
        org = by_url or cookie_org
        if by_url:
            scope["path"] = "/" + rest if rest else "/standings"
            scope["raw_path"] = scope["path"].encode()
            request = Request(scope)
            cookie = None
            if not cookie_org or cookie_org["id"] != by_url["id"]:
                cookie = (f"{auth.ORG_COOKIE}={auth.org_cookie(by_url)}; Path=/; "
                          f"Max-Age={auth.COOKIE_MAX_AGE}; HttpOnly; SameSite=lax"
                          + ("; Secure" if auth.is_https(request) else "")).encode()
            send = keep_inside(send, f"/{by_url['slug']}".encode(), cookie)
        elif org and scope["method"] == "GET" and in_section(scope["path"]):
            query = scope.get("query_string", b"").decode()
            return await redirect(f"/{org['slug']}{scope['path']}"
                                  + (f"?{query}" if query else ""))(scope, receive, send)
        scope.setdefault("state", {})["org"] = org
        if org is None and scope["path"] != "/" and not scope["path"].startswith(OPEN_PATHS):
            target = "/orgs" if auth.is_super(request) else \
                "/enter" + (f"?next={quote(here(request), safe='/')}" if scope["method"] == "GET" else "")
            return await redirect(target)(scope, receive, send)
        token = db.ORG.set(org["id"] if org else None)
        try:
            await self.app(scope, receive, send)
        finally:
            db.ORG.reset(token)


app.add_middleware(OrganizationGate)
templates = Jinja2Templates(directory=BASE / "templates",
                            context_processors=[i18n_context, auth.auth_context])
EDIT = [Depends(require_editor)]  # routes that change data need the organization's admin


def require_club_editor(request: Request):
    """An admin of a club: a 🏠 Mi pádel has no accounts, emails, courts or new
    tournaments pages (its owner must not manage their friends' accounts)."""
    require_editor(request)
    org = auth.current_org(request)
    if org["owner_id"] is not None and not auth.is_super(request):
        raise HTTPException(404, "Not in Mi pádel")


CLUB = [Depends(require_club_editor)]
SUPER = [Depends(require_super)]  # managing organizations needs a super admin
MANUAL = "manual"  # rule type whose sets are all made by hand
templates.env.filters["pick_player"] = lambda p: {"id": p["id"], "name": p["name"]}
templates.env.filters["phone"] = lambda u: countries.phone_display(u["phone_country"], u["phone"])
templates.env.filters["phone_link"] = lambda u: countries.phone_link(u["phone_country"], u["phone"])
templates.env.globals.update(
    ROUND_MODES=ROUND_MODES, MANUAL=MANUAL, RETAS=RETAS, REY=REY, LADDER=LADDER,
    AMISTOSOS=AMISTOSOS,
    DAY_ROUNDS=DAY_ROUNDS, DRAWN=DRAWN,
    ROLE_KEYS={"super": "role_super", "org_admin": "role_org_admin", "player": "role_player"},
    TIER_KEYS={1: "tier_bronze", 2: "tier_silver", 3: "tier_gold"},
    RULE_ICONS={"liga_amigos": "🏅", "americano": "🇺🇸", "mexicano": "🇲🇽", "manual": "✍️",
                "retas": "🔄", "rey_cancha": "👑", "escalafon": "🪜", "amistosos": "🤝"},
    COUNTRIES=countries.COUNTRIES, DEFAULT_COUNTRY=countries.DEFAULT,
    EMAIL_KIND_KEYS={"recap": "email_kind_recap", "reminder": "email_kind_reminder",
                     "test-recap": "email_kind_test_recap",
                     "test-reminder": "email_kind_test_reminder", "test": "email_kind_test",
                     "summary": "email_kind_summary"},
    EMAIL_STATUS_KEYS={"sent": "email_status_sent", "failed": "email_status_failed",
                       "throttled": "email_status_throttled"},
    chance_of=lambda m: chance_of(m),  # defined below
    # Changes whenever the stylesheet does, so phones don't keep an old cached copy.
    css_version=hashlib.sha256(b"".join(
        f.read_bytes() for f in sorted((BASE / "static").rglob("*")) if f.is_file())).hexdigest()[:10],
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


def org_id():
    """The organization of this request (see OrganizationGate)."""
    return db.ORG.get()


def cookie_options(request):
    return {"max_age": auth.COOKIE_MAX_AGE, "httponly": True, "samesite": "lax",
            "secure": auth.is_https(request)}


# --- Queries -------------------------------------------------------------------

def all_players(conn):
    return conn.execute("SELECT * FROM players WHERE organization_id = ? ORDER BY name",
                        (org_id(),)).fetchall()


def all_rule_types(conn):
    return conn.execute("SELECT * FROM rule_types ORDER BY id").fetchall()


def get_tournament(conn, tournament_id):
    """A tournament with its rule type's name and code, or 404."""
    row = conn.execute(
        "SELECT t.*, r.name AS rule_type, r.code AS rule_code "
        "FROM tournaments t JOIN rule_types r ON r.id = t.rule_type_id "
        "WHERE t.id = ? AND t.organization_id = ?",
        (tournament_id, org_id()),
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
        WHERE t.organization_id = ?
        GROUP BY t.id
        ORDER BY t.held_on DESC, t.id DESC
        """, (org_id(),)
    )]


def all_matchdays(conn, tournament_id=None):
    return conn.execute(
        """
        SELECT d.*, t.name AS tournament, r.code AS rule_code
        FROM matchdays d
        JOIN tournaments t ON t.id = d.tournament_id
        JOIN rule_types r ON r.id = t.rule_type_id
        WHERE (? IS NULL OR d.tournament_id = ?) AND t.organization_id = ?
        ORDER BY d.played_on DESC, t.name, d.number DESC
        """, (tournament_id, tournament_id, org_id())
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
    return next((p["id"] for p in all_players(conn)
                 if p["id"] != exclude and name_key(p["name"]) == key), None)


def player_id(conn, name):
    """The id of the player with this name, adding them if there is none."""
    name = clean_name(name)
    found = find_player(conn, name)
    if found:
        return found
    return conn.execute("INSERT INTO players (organization_id, name) VALUES (?, ?)",
                        (org_id(), name)).lastrowid


def players_for(conn, tournament_id):
    """Players to pick from in a tournament: its list, or everyone when it has none."""
    return tournament_players(conn, tournament_id) or all_players(conn)


# How each table's rows belong to an organization (the `?` is its id).
ORG_SCOPE = {
    "players": "organization_id = ?",
    "tournaments": "organization_id = ?",
    "matchdays": "tournament_id IN (SELECT id FROM tournaments WHERE organization_id = ?)",
    "matches": "matchday_id IN (SELECT d.id FROM matchdays d JOIN tournaments t "
               "ON t.id = d.tournament_id WHERE t.organization_id = ?)",
}


def get_or_404(conn, table, row_id):
    """A row of this organization, or 404."""
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ? AND {ORG_SCOPE[table]}",
                       (row_id, org_id())).fetchone()
    if row is None:
        raise HTTPException(404, f"{table[:-1].capitalize()} not found")
    return row


def set_rows(conn, tournament_id=None, matchday_id=None, player_id=None, limit=None):
    """Sets (rows of `matches`) with player, matchday and tournament names."""
    sql = """
        SELECT m.id, m.matchday_id, d.number AS matchday, d.played_on,
               d.tournament_id, t.name AS tournament, r.code AS rule_code, m.court,
               m.team_a_games, m.team_b_games, m.winner, m.round, m.sets_detail,
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
    where, params = ["t.organization_id = ?"], [org_id()]
    if tournament_id is not None:
        where.append("d.tournament_id = ?")
        params.append(tournament_id)
    if matchday_id is not None:
        where.append("m.matchday_id = ?")
        params.append(matchday_id)
    if player_id is not None:
        where.append("? IN (m.a1, m.a2, m.b1, m.b2)")
        params.append(player_id)
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
    code = get_tournament(conn, tournament_id)["rule_code"]
    results, standings = SCORING[code]([
        {"id": d["id"], "number": d["number"], "played_on": d["played_on"],
         "sets": sets.get(d["id"], []), "absent": absent.get(d["id"], set())}
        for d in matchdays
    ])
    if code == LADDER:  # the ladder's positions, not the points, order an Escalafón
        place = {p: row["position"] for row in ladder_state(conn, tournament_id)
                 for p in row["players"]}
        last = len(place) + 1
        standings = sorted(standings, key=lambda r: (place.get(r["id"], last), r["name"].lower()))
        for r in standings:
            r["position"] = place.get(r["id"], last)
    return results, standings


# --- Escalafón: the ladder ------------------------------------------------------------------

def ladder_state(conn, tournament_id):
    """An Escalafón's active pairs, top first: id, position, players (ids), name,
    matches won and lost, the pending reto it is in (matchday id) and the pairs it may
    challenge (formats.targets). Each reto is a matchday whose set has the challenger
    as pair A and the challenged as pair B."""
    pairs = conn.execute(
        "SELECT lp.*, p1.name AS name1, p2.name AS name2 FROM ladder_pairs lp "
        "JOIN players p1 ON p1.id = lp.player1_id JOIN players p2 ON p2.id = lp.player2_id "
        "WHERE lp.tournament_id = ? ORDER BY lp.seed, lp.id", (tournament_id,)).fetchall()
    by_players = {frozenset((p["player1_id"], p["player2_id"])): p["id"] for p in pairs}
    retos, busy = [], {}
    record = {p["id"]: [0, 0] for p in pairs}
    for s in reversed(set_rows(conn, tournament_id=tournament_id)):  # oldest first
        challenger = by_players.get(formats.pair(s, "A"))
        challenged = by_players.get(formats.pair(s, "B"))
        if challenger is None or challenged is None:
            continue
        if not is_played(s):
            busy[challenger] = busy[challenged] = s["matchday_id"]
            continue
        retos.append((challenger, challenged, s["winner"] == "A"))
        won, lost = (challenger, challenged) if s["winner"] == "A" else (challenged, challenger)
        record[won][0] += 1
        record[lost][1] += 1
    order = formats.ladder([p["id"] for p in pairs if p["active"]], retos)
    info = {p["id"]: p for p in pairs}
    return [{"id": pid, "position": n,
             "players": (info[pid]["player1_id"], info[pid]["player2_id"]),
             "name": f"{info[pid]['name1']} / {info[pid]['name2']}",
             "won": record[pid][0], "lost": record[pid][1], "busy": busy.get(pid),
             "targets": formats.targets(order, pid, busy)}
            for n, pid in enumerate(order, 1)]


def matchday_on(conn, tournament_id, day):
    """The tournament's jornada on this date (the latest, if several), or a new one."""
    row = conn.execute("SELECT id FROM matchdays WHERE tournament_id = ? AND played_on = ? "
                       "ORDER BY number DESC LIMIT 1", (tournament_id, day)).fetchone()
    if row:
        return row["id"]
    return conn.execute(
        "INSERT INTO matchdays (tournament_id, number, played_on) VALUES (?, ?, ?)",
        (tournament_id, next_number(conn, tournament_id), day)).lastrowid


def next_court(conn, matchday_id):
    return conn.execute("SELECT COALESCE(MAX(court), 0) + 1 FROM matches WHERE matchday_id = ?",
                        (matchday_id,)).fetchone()[0]


def my_player_id(request, conn):
    """The logged-in account's player in this organization, or None."""
    user = auth.current_user(request)
    row = user and conn.execute("SELECT id FROM players WHERE user_id = ? AND "
                                "organization_id = ?", (user["id"], org_id())).fetchone()
    return row["id"] if row else None


def ladder_tournament(conn, tournament_id):
    tournament = get_tournament(conn, tournament_id)
    if tournament["rule_code"] != LADDER:
        raise HTTPException(404, "Not an Escalafón")
    return tournament


@app.post("/tournaments/{tournament_id}/pairs", dependencies=EDIT)
def add_ladder_pair(tournament_id: int, player1: str = Form(""), player2: str = Form("")):
    """Add a pair to the Escalafón, last on the ladder. Its players join the tournament."""
    ids = [opt_int(player1), opt_int(player2)]
    with db.connect() as conn:
        ladder_tournament(conn, tournament_id)
        known = {p["id"] for p in all_players(conn)}
        taken = {p for row in ladder_state(conn, tournament_id) for p in row["players"]}
        if None in ids or ids[0] == ids[1] or not set(ids) <= known or set(ids) & taken:
            return redirect(f"/tournaments/{tournament_id}?error=err_pair_invalid#ladder")
        seed = conn.execute("SELECT COALESCE(MAX(seed), 0) + 1 FROM ladder_pairs "
                            "WHERE tournament_id = ?", (tournament_id,)).fetchone()[0]
        conn.execute("INSERT INTO ladder_pairs (tournament_id, player1_id, player2_id, seed) "
                     "VALUES (?, ?, ?, ?)", (tournament_id, *ids, seed))
        conn.executemany("INSERT OR IGNORE INTO tournament_players (tournament_id, player_id) "
                         "VALUES (?, ?)", [(tournament_id, p) for p in ids])
    return redirect(f"/tournaments/{tournament_id}#ladder")


@app.post("/tournaments/{tournament_id}/pairs/draw", dependencies=EDIT)
def draw_ladder(tournament_id: int):
    """The starting draw: the pairs' positions at random. Only before the first reto."""
    with db.connect() as conn:
        ladder_tournament(conn, tournament_id)
        if set_rows(conn, tournament_id=tournament_id, limit=1):
            return redirect(f"/tournaments/{tournament_id}?error=err_ladder_started#ladder")
        ids = [r[0] for r in conn.execute("SELECT id FROM ladder_pairs WHERE tournament_id = ?",
                                          (tournament_id,))]
        random.shuffle(ids)
        for n, pid in enumerate(ids, 1):
            conn.execute("UPDATE ladder_pairs SET seed = ? WHERE id = ?", (n, pid))
    return redirect(f"/tournaments/{tournament_id}#ladder")


@app.post("/tournaments/{tournament_id}/pairs/{pair_id}/leave", dependencies=EDIT)
def leave_ladder(tournament_id: int, pair_id: int):
    """A pair leaves the Escalafón: the pairs below it move up a place. Its played retos
    stay; it can't leave with a reto still to play."""
    with db.connect() as conn:
        ladder_tournament(conn, tournament_id)
        row = next((r for r in ladder_state(conn, tournament_id) if r["id"] == pair_id), None)
        if row is None:
            raise HTTPException(404, "Pair not found")
        if row["busy"]:
            return redirect(f"/tournaments/{tournament_id}?error=err_pair_busy#ladder")
        conn.execute("UPDATE ladder_pairs SET active = 0 WHERE id = ?", (pair_id,))
    return redirect(f"/tournaments/{tournament_id}#ladder")


@app.post("/tournaments/{tournament_id}/retos")
def create_reto(request: Request, tournament_id: int, challenger: int = Form(...),
                challenged: int = Form(...), played_on: str = Form("")):
    """⚔️ A pair challenges a pair above it (formats.targets), on the date picked: the
    reto joins the tournament's jornada of that date, on its next court, or a new jornada
    if there is none that day. Admins, or a player of the challenging pair."""
    with db.connect() as conn:
        ladder_tournament(conn, tournament_id)
        rows = {r["id"]: r for r in ladder_state(conn, tournament_id)}
        mine = rows.get(challenger)
        if not auth.is_editor(request) and (
                mine is None or my_player_id(request, conn) not in mine["players"]):
            raise LoginRequired(f"/tournaments/{tournament_id}")
        if mine is None or challenged not in mine["targets"]:
            return redirect(f"/tournaments/{tournament_id}?error=err_reto_invalid#ladder")
        matchday_id = matchday_on(conn, tournament_id,
                                  parse_date(played_on) or league_today().isoformat())
        court = next_court(conn, matchday_id)
        (a1, a2), (b1, b2) = mine["players"], rows[challenged]["players"]
        match_id = conn.execute(
            "INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, round) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)", (matchday_id, court, a1, a2, b1, b2)).lastrowid
    return redirect(f"/matchdays/{matchday_id}#set-{match_id}")


@app.post("/matches/{match_id}/sets")
def save_sets(request: Request, match_id: int, a1: str = Form(""), b1: str = Form(""),
              a2: str = Form(""), b2: str = Form(""), a3: str = Form(""), b3: str = Form("")):
    """An Escalafón match's result, best of 3 sets (formats.best_of_three): editors and
    the players of the match. All empty clears it."""
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        auth.require_set_scorer(request, tournament_of(conn, match["matchday_id"]), match)
        edit = f"/matches/{match_id}/edit"
        try:
            games = [(opt_games(a), opt_games(b)) for a, b in ((a1, b1), (a2, b2), (a3, b3))]
        except ValueError:
            return redirect(f"{edit}?error=err_best_of_three")
        if any((a is None) != (b is None) for a, b in games):
            return redirect(f"{edit}?error=err_best_of_three")
        played = [(a, b) for a, b in games if a is not None]
        if not played:
            conn.execute("UPDATE matches SET team_a_games = NULL, team_b_games = NULL, "
                         "winner = NULL, sets_detail = NULL WHERE id = ?", (match_id,))
            return redirect(f"/matchdays/{match['matchday_id']}")
        try:
            won_a, won_b = formats.best_of_three(played)
        except ValueError:
            return redirect(f"{edit}?error=err_best_of_three")
        conn.execute("UPDATE matches SET team_a_games = ?, team_b_games = ?, winner = ?, "
                     "sets_detail = ? WHERE id = ?",
                     (won_a, won_b, "A" if won_a > won_b else "B", formats.sets_text(played),
                      match_id))
    return redirect(f"/matchdays/{match['matchday_id']}#set-{match_id}")


# --- 🤝 Amistosos: friendly games, one tournament per organization -------------------------

def friendlies_tournament(conn, create=False):
    """This organization's Amistosos tournament (None if it has none yet and not
    `create`). It is made with the first friendly; its player password is random (nobody
    joins it by password: every player of the organization is in it)."""
    row = conn.execute(
        "SELECT t.id FROM tournaments t JOIN rule_types r ON r.id = t.rule_type_id "
        "WHERE r.code = ? AND t.organization_id = ? ORDER BY t.id LIMIT 1",
        (AMISTOSOS, org_id())).fetchone()
    if row:
        return get_tournament(conn, row["id"])
    if not create:
        return None
    rule = conn.execute("SELECT id FROM rule_types WHERE code = ?", (AMISTOSOS,)).fetchone()
    tournament_id = conn.execute(
        "INSERT INTO tournaments (name, held_on, rule_type_id, player_password, "
        "organization_id) VALUES (?, ?, ?, ?, ?)",
        ("Amistosos", league_today().isoformat(), rule["id"], secrets.token_urlsafe(16),
         org_id())).lastrowid
    return get_tournament(conn, tournament_id)


def can_add_friendly(request, conn):
    """Admins, and accounts with a player in this organization."""
    return auth.is_editor(request) or my_player_id(request, conn) is not None


@app.get("/friendlies", response_class=HTMLResponse)
def friendlies_page(request: Request):
    """🤝 Amistosos: its tournament page, or (before the first friendly) how it works."""
    with db.connect() as conn:
        tournament = friendlies_tournament(conn)
        if tournament:
            return redirect(f"/tournaments/{tournament['id']}")
        org = auth.current_org(request)
        return templates.TemplateResponse(request, "friendlies.html", {
            "can_add": can_add_friendly(request, conn),
            "invite": invite_share(request, org) if org["owner_id"] else None})


def friendly_form(request, conn, form, error=None, status_code=200):
    return templates.TemplateResponse(request, "friendly_form.html", {
        "form": form, "error": error,
        "players_json": [{"id": p["id"], "name": p["name"]} for p in all_players(conn)],
        "tournament": friendlies_tournament(conn)}, status_code=status_code)


@app.get("/friendlies/new", response_class=HTMLResponse)
def new_friendly_page(request: Request, date: str = ""):
    """🤝 A friendly: date, the two pairs (a new name creates the player) and the games.
    A player's own name comes first."""
    with db.connect() as conn:
        if not can_add_friendly(request, conn):
            raise LoginRequired(here(request))
        mine = my_player_id(request, conn)
        me = conn.execute("SELECT name FROM players WHERE id = ?", (mine,)).fetchone() if mine else None
        return friendly_form(request, conn, {
            "played_on": parse_date(date) or league_today().isoformat(),
            "a1": me["name"] if me else ""})


@app.post("/friendlies")
def add_friendly(request: Request, played_on: str = Form(""), a1: str = Form(""),
                 a2: str = Form(""), b1: str = Form(""), b2: str = Form(""),
                 team_a_games: str = Form(""), team_b_games: str = Form("")):
    """Save a friendly in the jornada of its date (made if there is none), on its next
    court. Players who don't exist yet are created. A player must be one of the four."""
    form = {"played_on": played_on, "a1": a1, "a2": a2, "b1": b1, "b2": b2,
            "team_a_games": team_a_games, "team_b_games": team_b_games}
    with db.connect() as conn:
        if not can_add_friendly(request, conn):
            raise LoginRequired("/friendlies")
        _ = translator(get_lang(request))
        names = [clean_name(n) for n in (a1, a2, b1, b2)]
        day = parse_date(played_on)
        keys = {name_key(n) for n in names}
        error = None
        if day is None:
            error = "err_invalid_date"
        elif not all(names) or len(keys) != 4:
            error = "err_four_players"
        else:
            try:
                games = opt_games(team_a_games), opt_games(team_b_games)
                if (games[0] is None) != (games[1] is None):
                    error = "err_both_games"
                winner = check_set(*games) if games[0] is not None else None
            except (ValueError, ScoreError):
                error = "err_set"
        mine = my_player_id(request, conn)
        if not error and not auth.is_editor(request):
            me = conn.execute("SELECT name FROM players WHERE id = ?", (mine,)).fetchone()
            if name_key(me["name"]) not in keys:
                error = "err_friendly_not_in"
        if error:
            return friendly_form(request, conn, form, error=_(error), status_code=400)
        new = [n for n in names if find_player(conn, n) is None]
        ids = [player_id(conn, n) for n in names]
        user = auth.current_user(request)
        if new and user:  # 👥 the account's friends without an account (/me)
            conn.execute(f"UPDATE players SET created_by = ? WHERE organization_id = ? AND "
                         f"name IN ({', '.join('?' * len(new))})", (user["id"], org_id(), *new))
        tournament = friendlies_tournament(conn, create=True)
        matchday_id = matchday_on(conn, tournament["id"], day)
        match_id = conn.execute(
            "INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, team_a_games, "
            "team_b_games, winner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (matchday_id, next_court(conn, matchday_id), *ids, *games, winner)).lastrowid
    return redirect(f"/matchdays/{matchday_id}#set-{match_id}")


# --- Retas and Rey de la cancha: the rounds of a jornada -------------------------------------

def by_round(sets):
    """{round: its sets, by court} of a jornada, rounds in order (round 1 when unset)."""
    out = {}
    for s in sorted(sets, key=lambda s: (s["round"] or 1, s["court"], s["id"])):
        out.setdefault(s["round"] or 1, []).append(s)
    return dict(sorted(out.items()))


def day_table(md):
    """Everyone's jornada (Retas, Rey): points, games difference, sets won and played,
    best first; a player on several courts adds them up."""
    rows = {}
    for court_rows in md["courts"].values():
        for r in court_rows:
            t = rows.setdefault(r["id"], {"id": r["id"], "name": r["name"], "points": 0,
                                          "diff": 0, "sets_won": 0, "sets": 0})
            for k in ("points", "diff", "sets_won", "sets"):
                t[k] += r[k]
    return sorted(rows.values(), key=lambda r: (-r["points"], -r["diff"], r["name"].lower()))


def names_of(conn):
    return {p["id"]: p["name"] for p in all_players(conn)}


def retas_next(conn, matchday_id):
    """(round number, {court: [4 ids]}) of the next Retas round, or (None, error key)."""
    rounds_ = by_round(set_rows(conn, matchday_id=matchday_id))
    if not rounds_:
        return None, "err_round_pending"
    last = max(rounds_)
    if not all(is_played(s) for s in rounds_[last]):
        return None, "err_round_pending"
    try:
        return last + 1, formats.retas_move(rounds_[last])
    except ValueError as tie:
        return None, ("err_retas_tie", tie.args[0])


def retas_options(conn, matchday_id, number, courts):
    """Each court of the next round with its 3 possible pairings: names, whether a pair
    already played together this jornada (a warning, still allowed) and the app's draw."""
    names, used = names_of(conn), formats.played_pairs(set_rows(conn, matchday_id=matchday_id))
    out = []
    for court, four in sorted(courts.items()):
        options = []
        for i, (a, b) in enumerate(formats.pairings(four)):
            options.append({"index": i, "a": " / ".join(names[p] for p in a),
                            "b": " / ".join(names[p] for p in b),
                            "repeat": frozenset(a) in used or frozenset(b) in used})
        out.append({"court": court, "players": [names[p] for p in four], "options": options,
                    "drawn": formats.draw_pairing(four, matchday_id * 1000 + number * 10 + court)})
    return out


@app.get("/matchdays/{matchday_id}/next-round", response_class=HTMLResponse)
def next_round_page(request: Request, matchday_id: int):
    """🔄 Retas: the next round. Winners moved up and losers down; on each court the
    pairs are the app's draw or what the players chose on court."""
    with db.connect() as conn:
        tournament = tournament_of(conn, matchday_id)
        auth.require_scorer(request, tournament)
        number, courts = retas_next(conn, matchday_id)
        if number is None:
            key, *n = courts if isinstance(courts, tuple) else (courts,)
            return redirect(f"/matchdays/{matchday_id}?error={key}" + (f"&n={n[0]}" if n else ""))
        return templates.TemplateResponse(request, "next_round.html", {
            "tournament": tournament, "matchday": get_or_404(conn, "matchdays", matchday_id),
            "number": number, "courts": retas_options(conn, matchday_id, number, courts)})


@app.post("/matchdays/{matchday_id}/next-round")
async def save_next_round(request: Request, matchday_id: int):
    form = await request.form()
    with db.connect() as conn:
        tournament = tournament_of(conn, matchday_id)
        auth.require_scorer(request, tournament)
        number, courts = retas_next(conn, matchday_id)
        if number is None:
            return redirect(f"/matchdays/{matchday_id}")
        for court, four in sorted(courts.items()):
            choice = opt_int(form.get(f"court-{court}", ""))
            if choice not in (0, 1, 2):
                choice = formats.draw_pairing(four, matchday_id * 1000 + number * 10 + court)
            (a1, a2), (b1, b2) = formats.pairings(four)[choice]
            conn.execute("INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, round) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (matchday_id, court, a1, a2, b1, b2,
                                                          number))
    return redirect(f"/matchdays/{matchday_id}#round-{number}")


def rey_pairs(conn, matchday_id):
    return [(r["player1_id"], r["player2_id"]) for r in conn.execute(
        "SELECT * FROM queue_pairs WHERE matchday_id = ? ORDER BY slot", (matchday_id,))]


def rey_state(conn, matchday_id, sets=None):
    """👑 Rey de la cancha now: names of the king, the challenger and the line, and
    whether the next match can start (every match so far played)."""
    sets = sets if sets is not None else set_rows(conn, matchday_id=matchday_id)
    played = [s for rnd in by_round(sets).values() for s in rnd if is_played(s)]
    king, challenger, line = formats.king_line(rey_pairs(conn, matchday_id), played)
    names = names_of(conn)
    label = lambda p: p and " / ".join(names[i] for i in sorted(p))  # noqa: E731
    return {"king": label(king), "challenger": label(challenger),
            "line": [label(p) for p in line], "pairs": (king, challenger),
            "can_next": bool(sets) and all(is_played(s) for s in sets) and challenger}


@app.post("/matchdays/{matchday_id}/next-match")
def next_match(request: Request, matchday_id: int):
    """▶️ Rey de la cancha: the next match, the king against the next pair in line."""
    with db.connect() as conn:
        auth.require_scorer(request, tournament_of(conn, matchday_id))
        sets = set_rows(conn, matchday_id=matchday_id)
        state = rey_state(conn, matchday_id, sets)
        if not state["can_next"]:
            return redirect(f"/matchdays/{matchday_id}?error=err_round_pending")
        (a1, a2), (b1, b2) = (sorted(p) for p in state["pairs"])
        number = max((s["round"] or 1 for s in sets), default=0) + 1
        conn.execute("INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, round) "
                     "VALUES (?, 1, ?, ?, ?, ?, ?)", (matchday_id, a1, a2, b1, b2, number))
    return redirect(f"/matchdays/{matchday_id}#round-{number}")


def read_pairs(form):
    """[(id, id), ...] from the pair-<n> selects of the Rey de la cancha form, in order;
    rows left empty are skipped. Raises ValueError for a half-filled row."""
    numbered = sorted((int(k[5:]), form.getlist(k)) for k in form
                      if k.startswith("pair-") and k[5:].isdigit())
    pairs = []
    for _n, values in numbered:
        ids = [opt_int(v) for v in values]
        if not any(ids):
            continue
        if len(ids) != 2 or None in ids or ids[0] == ids[1]:
            raise ValueError
        pairs.append(tuple(ids))
    return pairs


def render_pairs(request, conn, tournament, pairs, played_on, number, error=None, status_code=200):
    return templates.TemplateResponse(request, "pairs.html", {
        "tournament": tournament, "pairs": pairs + [(None, None)] * 2, "played_on": played_on,
        "number": number, "players": players_for(conn, tournament["id"]), "error": error,
        "redraw": f"?played_on={played_on}&seed={random.randrange(10 ** 6)}"},
        status_code=status_code)


def draw_pairs(players, seed):
    """Pairs at random for a Rey de la cancha jornada (an odd player out is left over)."""
    ids = [p["id"] for p in players]
    random.Random(seed).shuffle(ids)
    return [tuple(ids[i:i + 2]) for i in range(0, len(ids) - 1, 2)]


# --- Pages -------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, error: str | None = None):
    """The start page. Logged in (an account, or a guest with tournament passwords):
    every tournament they play or run, and the sets still to play, by date. Otherwise
    the login."""
    user = auth.current_user(request)
    with db.connect() as conn:
        tournaments, upcoming, latest = (account_home(conn, user) if user
                                         else guest_home(request, conn))
        personal = orgs.personal_of(conn, user["id"]) if user else None
    if not user and not tournaments:
        # The club this browser remembers (org cookie): its tournaments, below everything.
        club = auth.current_org(request)
        with db.connect() as conn:
            remembered = all_tournaments(conn) if club and club["owner_id"] is None else []
        return templates.TemplateResponse(request, "login.html", {
            "next": "/", "home": True, "landing": True,
            "club": club if remembered else None, "club_tournaments": remembered})
    return templates.TemplateResponse(request, "home.html", {
        "tournaments": tournaments, "upcoming": upcoming, "account": user, "error": error,
        "latest": latest, "personal": personal,
        "invite": invite_share(request, personal) if personal else None})


def home_tournament(t, org, role, me=None):
    return {**t, "org_id": org["id"], "org_name": org["name"], "roles": {role}, "me": me}


def by_date(tournaments, upcoming):
    """Tournaments still going first (newest first), then ended; sets oldest date first."""
    tournaments = sorted(tournaments, key=lambda t: (t["held_on"], t["id"]), reverse=True)
    tournaments.sort(key=lambda t: bool(t["ended"]))
    upcoming.sort(key=lambda s: (s["played_on"], s["tournament"], s["matchday"], s["court"]))
    return tournaments, upcoming


def account_home(conn, user):
    """(tournaments, sets to play) of an account, across organizations: the tournaments
    its players play (with position and points) and, for admins, those they run. Other
    people's friendlies aren't shown: no 🏠 Mi pádel but one's own, and a club's
    🤝 Amistosos only if the account plays in it (its players' part, below)."""
    found, upcoming, latest = {}, [], []
    if user["role"] == "super":
        admin_of = conn.execute("SELECT * FROM organizations WHERE owner_id IS NULL "
                                "ORDER BY name").fetchall()
    elif user["role"] == "org_admin":
        admin_of = conn.execute("SELECT * FROM organizations WHERE id = ?",
                                (user["organization_id"],)).fetchall()
    else:
        admin_of = []
    for org in admin_of:
        for t in in_org(org["id"], lambda: all_tournaments(conn)):
            if t["rule_code"] != AMISTOSOS:
                found[t["id"]] = home_tournament(t, org, "admin")
    for player in my_players(conn, user["id"]):
        org = {"id": player["organization_id"], "name": player["org_name"]}
        summary = my_summary(conn, player)
        for t in summary["tournaments"]:
            if t["id"] in found:
                found[t["id"]]["roles"].add("player")
                found[t["id"]]["me"] = t["me"]
            else:
                found[t["id"]] = home_tournament(t, org, "player", t["me"])
        upcoming += [{**s, "org_name": org["name"], "org_slug": player["org_slug"]}
                     for s in summary["pending"]]
        latest += [{**s, "org_name": org["name"], "player_id": player["id"]}
                   for s in summary["recent"][:1]]
    tournaments, upcoming = by_date(list(found.values()), upcoming)
    latest = max(latest, key=lambda s: (s["played_on"], s["matchday"]), default=None)
    return tournaments, upcoming, latest


def guest_home(request, conn):
    """(tournaments, sets to play) of a guest: the tournaments whose player password this
    browser logged in with, and all their sets still to play."""
    ids = [int(name.split("_", 1)[1]) for name in auth.player_cookies(request)
           if name.split("_", 1)[1].isdigit()]
    tournaments, upcoming = [], []
    for t in conn.execute(
            f"SELECT t.*, o.name AS org_name FROM tournaments t JOIN organizations o "
            f"ON o.id = t.organization_id WHERE t.id IN ({', '.join('?' * len(ids))})", ids):
        if not auth.is_guest_player(request, t):
            continue
        org = {"id": t["organization_id"], "name": t["org_name"]}
        def work(t=t):
            row = next(r for r in all_tournaments(conn) if r["id"] == t["id"])
            return row, [s for s in set_rows(conn, tournament_id=t["id"])
                         if s["team_a_games"] is None]
        row, pending = in_org(org["id"], work)
        pending = in_org(org["id"], lambda: [{**s, "chance": chance_of(s)} for s in pending])
        tournaments.append(home_tournament(row, org, "guest"))
        upcoming += [{**s, "org_name": org["name"]} for s in pending]
    return (*by_date(tournaments, upcoming), None)


@app.get("/standings", response_class=HTMLResponse)
def standings_page(request: Request, tournament: str | None = None):
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
            "player_medals": tournament_medals(conn, latest["id"], standings, get_lang(request))
                             if latest else {},
            "usernames": account_usernames(conn),
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


def search_orgs(conn, query, limit=20):
    """Clubs whose name contains `query` (case, accents and spacing don't count; 2
    letters at least). A 🏠 Mi pádel is never found: it's private."""
    key = name_key(query)
    if len(key) < 2:
        return []
    found = [o for o in conn.execute("SELECT o.name, (SELECT COUNT(*) FROM tournaments t WHERE "
                                     "t.organization_id = o.id) AS tournaments FROM "
                                     "organizations o WHERE o.owner_id IS NULL ORDER BY o.name")
             if key in name_key(o["name"])]
    return found[:limit]


@app.get("/enter", response_class=HTMLResponse)
def enter_page(request: Request, next: str = "/", q: str = ""):
    """🔍 Find an organization by (part of) its name: nothing is listed until you search,
    so a visitor sees no organization they didn't look for."""
    with db.connect() as conn:
        return templates.TemplateResponse(request, "enter.html", {
            "next": safe_next(next), "q": q.strip(), "orgs": search_orgs(conn, q)})


@app.post("/enter")
def enter(request: Request, name: str = Form(""), next: str = Form("/")):
    with db.connect() as conn:
        org = auth.find_org(conn, name)
        if org is not None and not auth.can_open(request, org):
            org = None  # someone else's 🏠 Mi pádel: as if it didn't exist
        if org is None:
            time.sleep(1)  # slow down guessing
            return templates.TemplateResponse(request, "enter.html", {
                "next": safe_next(next), "q": name, "error": "err_unknown_org",
                "orgs": search_orgs(conn, name),
            }, status_code=404)
    return enter_org(request, org, safe_next(next))


def enter_mine(request, conn, user, response, always=False):
    """The browser views the account's 🏠 Mi pádel: always after signing up (a new
    account has no club yet); after logging in, only if it views no organization (a club
    being looked at, e.g. to join one of its tournaments, stays)."""
    if not always and auth.current_org(request):
        return response
    mine = orgs.personal_of(conn, user["id"])
    if mine:
        response.set_cookie(auth.ORG_COOKIE, auth.org_cookie(mine), **cookie_options(request))
    return response


def enter_org(request, org, next_url="/"):
    """Remember this organization in the browser and go to `next_url` (inside its URLs,
    /<slug>/..., when it's one of its pages)."""
    response = redirect(f"/{org['slug']}{next_url}" if in_section(next_url) else next_url)
    response.set_cookie(auth.ORG_COOKIE, auth.org_cookie(org), **cookie_options(request))
    return response


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    if auth.is_editor(request):
        return redirect(safe_next(next))
    return templates.TemplateResponse(request, "login.html", {"next": safe_next(next)})


@app.post("/login")
def login(request: Request, username: str = Form(""), password: str = Form(""),
          next: str = Form("/"), role: str = Form("")):
    """The login page has two sections (`role`):
    - "account": a username or email and password. Everyone lands on the home page (their
      tournaments and sets to play), or `next`; an organization admin also enters their
      organization.
    - "player": a tournament's player password, which logs in its guest players (one
      cookie per tournament whose password it is) in the organization being viewed, or
      in the one of that tournament if none is.
    Without a role (older forms), a username means an account and none a player."""
    cookie = cookie_options(request)
    if role not in ("account", "player"):
        role = "account" if username.strip() else "player"
    failed = templates.TemplateResponse(request, "login.html", {
        "next": safe_next(next), "username": username if role == "account" else "",
        "error": "err_wrong_password", "role": role,
    }, status_code=401)
    with db.connect() as conn:
        if role == "account":
            user = password and users.login(conn, username, password)
            if not user:
                time.sleep(1)  # slow down password guessing
                return failed
            current = auth.current_org(request)
            wanted = safe_next(next) if next not in ("", "/") else None
            if user["role"] == "org_admin":
                org = conn.execute("SELECT * FROM organizations WHERE id = ?",
                                   (user["organization_id"],)).fetchone()
                response = enter_org(request, org, wanted if current
                                     and current["id"] == org["id"] and wanted else "/")
            else:
                response = redirect(wanted or "/")
                if user["role"] == "player":
                    orgs.create_personal(conn, user["id"])  # older accounts get theirs now
                    enter_mine(request, conn, user, response)
            response.set_cookie(auth.USER_COOKIE, auth.user_cookie(user), **cookie)
            return response
        current = auth.current_org(request)
        matches = [t for t in conn.execute(
            "SELECT * FROM tournaments WHERE player_password IS NOT NULL "
            "AND organization_id IS NOT NULL ORDER BY id DESC")
            if auth.player_password_matches(password, t)
            and (current is None or t["organization_id"] == current["id"])]
        if not password or not matches:
            time.sleep(1)
            return failed
        org = current or conn.execute("SELECT * FROM organizations WHERE id = ?",
                                      (matches[0]["organization_id"],)).fetchone()
    matches = [t for t in matches if t["organization_id"] == org["id"]]
    target = (safe_next(next) if current and next not in ("", "/")
              else f"/tournaments/{matches[0]['id']}")
    if not auth.current_user(request):  # offer to make an account, or carry on as a guest
        target = f"/welcome?t={matches[0]['id']}&next={quote(target, safe='/')}"
    response = enter_org(request, org, target)
    for t in matches:
        response.set_cookie(auth.PLAYER_COOKIE.format(t["id"]), auth.player_token(t), **cookie)
    return response


@app.post("/logout")
def logout(request: Request):
    response = redirect("/")
    for name in [auth.USER_COOKIE, *auth.OLD_COOKIES, *auth.player_cookies(request)]:
        response.delete_cookie(name)
    return response


@app.get("/orgs", response_class=HTMLResponse, dependencies=SUPER)
def orgs_page(request: Request, error: str | None = None, mail: str | None = None):
    """Super admins: every organization with its admin's user and password, to enter
    one, change its admin or create a new one."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT o.id, o.name, o.slug, u.username AS admin_user, "
            "u.password_plain AS admin_password_plain, "
            "(SELECT COUNT(*) FROM tournaments t WHERE t.organization_id = o.id) AS tournaments, "
            "(SELECT COUNT(*) FROM players p WHERE p.organization_id = o.id) AS players "
            "FROM organizations o LEFT JOIN users u ON u.id = (SELECT MIN(id) FROM users "
            "WHERE role = 'org_admin' AND organization_id = o.id) ORDER BY o.name").fetchall()
        return templates.TemplateResponse(request, "orgs.html", {
        "orgs": rows, "error": error, "mail_sent": mail == "sent",
        "mail_enabled": mailer.enabled(),
        # Accounts that may become a new organization's admin: the player accounts.
        "accounts": admin_candidates(conn)})


def admin_candidates(conn):
    return conn.execute(
        "SELECT id, username, COALESCE(display_name, first_name, username) AS name "
        "FROM users WHERE role = 'player' "
        "ORDER BY LOWER(COALESCE(display_name, first_name, username))").fetchall()


@app.post("/orgs", dependencies=SUPER)
def add_org(name: str = Form(""), admin_account: str = Form(""), admin_user: str = Form(""),
            admin_password: str = Form("")):
    """⭐ Create an organization. Its admin: an existing player account (admin_account)
    or a new account (admin_user + admin_password)."""
    account = opt_int(admin_account)
    with db.connect() as conn:
        if not " ".join(name.split()) or account is None and not (
                admin_user.strip() and admin_password):
            return redirect("/orgs?error=err_org_fields")
        if auth.find_org(conn, name):
            return redirect("/orgs?error=err_org_exists")
        if account is None and (users.find_login(conn, admin_user) or "@" in admin_user):
            return redirect("/orgs?error=err_admin_user_exists")
        try:
            orgs.create_org(conn, name, admin_user, admin_password, user_id=account)
        except users.UserError as e:
            return redirect(f"/orgs?error={e.args[0]}")
    return redirect("/orgs")


@app.post("/orgs/{org}/enter", dependencies=SUPER)
def super_enter(request: Request, org: int):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org,)).fetchone()
    if row is None:
        raise HTTPException(404, "Organization not found")
    return enter_org(request, row)


@app.post("/orgs/{org}/admin", dependencies=SUPER)
def super_set_admin(org: int, admin_user: str = Form(""), admin_password: str = Form("")):
    """Super admins: change an organization's admin user and (if typed) password."""
    with db.connect() as conn:
        if not conn.execute("SELECT 1 FROM organizations WHERE id = ?", (org,)).fetchone():
            raise HTTPException(404, "Organization not found")
        if not admin_user.strip():
            return redirect("/orgs?error=err_org_fields")
        try:
            orgs.update_admin(conn, org, admin_user, admin_password)
        except ValueError:
            return redirect("/orgs?error=err_admin_user_exists")
    return redirect("/orgs")


# --- From guest to account, and the profile -----------------------------------------

def tournament_people(conn, tournament_id):
    """Everyone who plays in a tournament: its list and the players of its sets."""
    return conn.execute(
        "SELECT p.* FROM players p WHERE p.id IN (SELECT player_id FROM tournament_players "
        "WHERE tournament_id = ?) OR EXISTS (SELECT 1 FROM matches m JOIN matchdays d "
        "ON d.id = m.matchday_id WHERE d.tournament_id = ? AND p.id IN (m.a1, m.a2, m.b1, m.b2)) "
        "ORDER BY p.name", (tournament_id, tournament_id)).fetchall()


def guest_tournament(request, conn, tournament_id):
    """The tournament whose password this browser logged in with, or LoginRequired:
    only its players may claim one of its players."""
    tournament = get_tournament(conn, tournament_id)
    if not auth.is_guest_player(request, tournament):
        raise LoginRequired(here(request) if request.method == "GET" else "/")
    return tournament


def free_people(conn, tournament_id):
    """The tournament's players that no account has claimed yet."""
    return [p for p in tournament_people(conn, tournament_id) if p["user_id"] is None]


def take_display_name(conn, player, name):
    """Give a claimed player the account's display name, if no one else has it."""
    name = clean_name(name or "")
    if name and name != player["name"] and not find_player(conn, name, exclude=player["id"]):
        conn.execute("UPDATE players SET name = ? WHERE id = ?", (name, player["id"]))


@app.get("/welcome", response_class=HTMLResponse)
def welcome_page(request: Request, t: int, next: str = "/", error: str | None = None,
                 confirm: int | None = None):
    """After a tournament's player password (its invitation). An account picks who it is
    in the tournament: its player of this organization, one of the tournament's free
    players, or a new one. Without an account: make one, or carry on as a guest."""
    user = auth.current_user(request)
    with db.connect() as conn:
        tournament = guest_tournament(request, conn, t)
        return templates.TemplateResponse(request, "welcome.html", {
            "tournament": tournament, "next": safe_next(next), "error": error,
            "free": free_people(conn, t),
            "mine": linked_player(conn, user["id"]) if user else None,
            "playing": bool(user) and auth.account_plays(user, tournament),
            # a free player the account picked while having its own here: confirm joining
            "confirm": {p["id"]: p for p in free_people(conn, t)}.get(confirm),
        })


@app.post("/welcome/link")
def welcome_link(request: Request, t: int = Form(...), player_id: str = Form(""),
                 merge: str = Form("")):
    """A logged-in account joins a tournament it has the password of, as:
    - its own player of this organization (`player_id` is that player): added to the
      tournament's list;
    - one of the tournament's free players: claimed. If the account already has a player
      here, that asks to confirm first, then (`merge`) folds it into the account's
      player (see users.merge_players);
    - "new": a new player named after the account's display name, added to the list."""
    user = auth.current_user(request)
    if user is None:
        raise LoginRequired(f"/welcome?t={t}")
    with db.connect() as conn:
        guest_tournament(request, conn, t)
        mine = linked_player(conn, user["id"])
        add = "INSERT OR IGNORE INTO tournament_players (tournament_id, player_id) VALUES (?, ?)"
        if player_id == "new" and not mine:
            name = clean_name(user["display_name"] or user["username"])
            if find_player(conn, name):
                return redirect(f"/welcome?t={t}&error=err_player_exists")
            new_id = conn.execute("INSERT INTO players (organization_id, name) VALUES (?, ?)",
                                  (org_id(), name)).lastrowid
            conn.execute(add, (t, new_id))
            users.link_player(conn, user["id"], new_id)
            return redirect("/")
        if mine and player_id == str(mine["id"]) and not merge:
            conn.execute(add, (t, mine["id"]))
            return redirect("/")
        player_id = opt_int(player_id)
        player = next((p for p in free_people(conn, t) if p["id"] == player_id), None)
        if player is None:
            return redirect(f"/welcome?t={t}&error=err_player_claimed")
        if mine and not merge:  # that player and the account's become one: ask first
            return redirect(f"/welcome?t={t}&confirm={player_id}")
        try:
            kept = users.link_player(conn, user["id"], player_id, merge=bool(merge))
        except users.UserError as e:
            return redirect(f"/welcome?t={t}&error={e}")
        if kept == player_id:
            take_display_name(conn, player, user["display_name"])
    return redirect("/")


@app.post("/join")
def join_tournament(request: Request, password: str = Form("")):
    """An account types a tournament's player password (its invitation) from the home
    page: the browser gets that tournament's player cookie and enters its organization,
    and /welcome asks who the account is in it."""
    user = auth.current_user(request)
    if user is None:
        raise LoginRequired("/")
    with db.connect() as conn:
        found = [t for t in conn.execute(
            "SELECT * FROM tournaments WHERE player_password IS NOT NULL "
            "AND organization_id IS NOT NULL ORDER BY id DESC")
            if auth.player_password_matches(password, t)]
        if not password or not found:
            time.sleep(1)  # slow down guessing
            return redirect("/?error=err_wrong_password#join")
        tournament = found[0]
        org = conn.execute("SELECT * FROM organizations WHERE id = ?",
                           (tournament["organization_id"],)).fetchone()
    response = enter_org(request, org,
                         f"/welcome?t={tournament['id']}&next=/tournaments/{tournament['id']}")
    response.set_cookie(auth.PLAYER_COOKIE.format(tournament["id"]),
                        auth.player_token(tournament), **cookie_options(request))
    return response


def signup_form(request, conn, tournament, form=None, error=None, status_code=200, next=""):
    return templates.TemplateResponse(request, "signup.html", {
        "tournament": tournament,
        "free": free_people(conn, tournament["id"]) if tournament else [],
        "form": form or {}, "error": error, "next": next}, status_code=status_code)


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, t: int | None = None, next: str = ""):
    """Make an account. From a tournament (`t`, after its password) it also claims who
    you are in it; on its own, you join tournaments later from the home page. `next`:
    where to go after (an invitation to a 🏠 Mi pádel)."""
    with db.connect() as conn:
        return signup_form(request, conn, guest_tournament(request, conn, t) if t else None,
                           next=safe_next(next) if next else "")


@app.post("/signup")
def signup(request: Request, t: str = Form(""), who: str = Form(""),
           first_name: str = Form(""), last_name: str = Form(""),
           display_name: str = Form(""), username: str = Form(""), email: str = Form(""),
           phone_country: str = Form(""), phone: str = Form(""),
           password: str = Form(""), password2: str = Form(""),
           next_url: str = Form("", alias="next")):
    """Make a player account. From a tournament (`t`), also claim one of its players, or
    a new player ("new") who joins it; the display name becomes the player's name, so
    the tables show it. Without `t`, just the account: it joins tournaments later with
    their passwords (/join)."""
    form = {"who": who, "first_name": first_name, "last_name": last_name,
            "display_name": display_name, "username": username, "email": email,
            "phone_country": phone_country, "phone": phone}
    t = opt_int(t)
    with db.connect() as conn:
        tournament = guest_tournament(request, conn, t) if t else None
        claimed = next((p for p in free_people(conn, t) if str(p["id"]) == who),
                       None) if tournament else None
        display = clean_name(display_name)
        error = None
        if tournament and who != "new" and claimed is None:
            error = "err_choose_player"
        elif not display:
            error = "err_display_required"
        elif tournament and find_player(conn, display,
                                        exclude=claimed["id"] if claimed else None):
            error = "err_player_exists"
        elif len(password) < users.MIN_PASSWORD:
            error = "err_password_short"
        elif password != password2:
            error = "err_passwords_differ"
        if error is None:
            try:
                user_id = users.create_user(conn, "player", username, password, email=email,
                                            first_name=first_name, last_name=last_name,
                                            display_name=display, phone=phone,
                                            phone_country=phone_country)
            except users.UserError as e:
                error = str(e)
        if error:
            return signup_form(request, conn, tournament, form, error, 400,
                               next=safe_next(next_url) if next_url else "")
        orgs.create_personal(conn, user_id)  # 🏠 Mi pádel, with the account
        if not tournament:
            pid = None
        elif claimed:
            take_display_name(conn, claimed, display)
            pid = claimed["id"]
        else:
            pid = player_id(conn, display)
            conn.execute("INSERT OR IGNORE INTO tournament_players (tournament_id, player_id) "
                         "VALUES (?, ?)", (t, pid))
        if pid:
            users.link_player(conn, user_id, pid)
        user = users.get(conn, user_id)
    response = redirect(safe_next(next_url) if next_url else "/me" if tournament else "/")
    response.set_cookie(auth.USER_COOKIE, auth.user_cookie(user), **cookie_options(request))
    if not tournament:  # from a tournament, the browser already views its club
        with db.connect() as conn:
            enter_mine(request, conn, user, response, always=True)
    return response


# --- 👥 Friends without an account: claim links ------------------------------------------------

def claim_share(request, org, player):
    _ = translator(get_lang(request))
    scheme = "https" if auth.is_https(request) else "http"
    url = (f"{scheme}://{request.url.netloc}/claim/{player['id']}/"
           f"{auth.claim_token(org, player['id'])}")
    text = f"{_('claim_message', name=player['name'])}\n{url}"
    return {"url": url, "whatsapp": "https://wa.me/?text=" + quote(text, safe="")}


def my_unclaimed(request, conn, user):
    """👥 Players this account created in friendlies that no account has claimed yet,
    each with its claim link."""
    rows = conn.execute(
        "SELECT p.*, o.name AS org_name, o.secret, o.id AS org_id, o.owner_id, "
        "(SELECT COUNT(*) FROM matches m WHERE p.id IN (m.a1, m.a2, m.b1, m.b2)) AS sets "
        "FROM players p JOIN organizations o ON o.id = p.organization_id "
        "WHERE p.created_by = ? AND p.user_id IS NULL ORDER BY p.name", (user["id"],)).fetchall()
    return [{"player": r, "share": claim_share(request, {"id": r["org_id"], "secret": r["secret"]}, r)}
            for r in rows]


def claimed_player(conn, player_id, token):
    row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    org = row and conn.execute("SELECT * FROM organizations WHERE id = ?",
                               (row["organization_id"],)).fetchone()
    if not org or not hmac.compare_digest(token, auth.claim_token(org, player_id)):
        raise HTTPException(404, "Invitation not found")
    return row, org


@app.get("/claim/{player_id}/{token}", response_class=HTMLResponse)
def claim_page(request: Request, player_id: int, token: str, error: str | None = None):
    """A friend's link to a player made for them in friendlies: make an account (or log
    in) and say "that's me" to keep its games."""
    with db.connect() as conn:
        player, org = claimed_player(conn, player_id, token)
        creator = users.get(conn, player["created_by"]) if player["created_by"] else None
        sets = conn.execute("SELECT COUNT(*) FROM matches WHERE ? IN (a1, a2, b1, b2)",
                            (player_id,)).fetchone()[0]
    return templates.TemplateResponse(request, "claim.html", {
        "player": player, "org": org, "creator": creator, "sets": sets, "error": error,
        "account": auth.current_user(request), "here": f"/claim/{player_id}/{token}"})


@app.post("/claim/{player_id}/{token}")
def claim(request: Request, player_id: int, token: str):
    """The logged-in account becomes this player. If it already has a player in that
    organization, the two are joined (users.merge_players)."""
    user = auth.current_user(request)
    if user is None:
        raise LoginRequired(f"/claim/{player_id}/{token}")
    with db.connect() as conn:
        player, org = claimed_player(conn, player_id, token)
        if player["user_id"] not in (None, user["id"]):
            return redirect(f"/claim/{player_id}/{token}?error=err_player_claimed")
        try:
            users.link_player(conn, user["id"], player_id, merge=True)
        except users.UserError as e:
            return redirect(f"/claim/{player_id}/{token}?error={e}")
    return enter_org(request, org, "/friendlies")


# --- 🏠 Mi pádel: invitations ---------------------------------------------------------------

def invite_url(request, org):
    scheme = "https" if auth.is_https(request) else "http"
    return f"{scheme}://{request.url.netloc}/invite/{org['invite_code']}"


def invite_share(request, org):
    """The invitation link of a 🏠 Mi pádel and its WhatsApp message."""
    _ = translator(get_lang(request))
    url = invite_url(request, org)
    text = f"{_('invite_message')}\n{url}"
    return {"url": url, "whatsapp": "https://wa.me/?text=" + quote(text, safe="")}


def invited_org(conn, code):
    org = conn.execute("SELECT * FROM organizations WHERE invite_code = ? AND owner_id IS NOT "
                       "NULL", (code,)).fetchone()
    if org is None:
        raise HTTPException(404, "Invitation not found")
    return org


@app.get("/invite/{code}", response_class=HTMLResponse)
def invite_page(request: Request, code: str):
    """A friend's invitation to their 🏠 Mi pádel: make an account (or log in), then say
    who you are among its players (or be new)."""
    user = auth.current_user(request)
    with db.connect() as conn:
        org = invited_org(conn, code)
        owner = users.get(conn, org["owner_id"])
        if user and conn.execute("SELECT 1 FROM players WHERE organization_id = ? AND "
                                 "user_id = ?", (org["id"], user["id"])).fetchone():
            return enter_org(request, org, "/friendlies")  # already in
        free = conn.execute("SELECT * FROM players WHERE organization_id = ? AND user_id IS "
                            "NULL ORDER BY name", (org["id"],)).fetchall()
    return templates.TemplateResponse(request, "invite.html", {
        "invite": org, "owner": owner, "account": user, "free": free, "code": code})


@app.post("/invite/{code}")
def accept_invite(request: Request, code: str, player_id: str = Form("")):
    """Join a 🏠 Mi pádel as one of its unclaimed players, or as a new one ("new")."""
    user = auth.current_user(request)
    if user is None:
        raise LoginRequired(f"/invite/{code}")
    with db.connect() as conn:
        org = invited_org(conn, code)
        mine = conn.execute("SELECT id FROM players WHERE organization_id = ? AND user_id = ?",
                            (org["id"], user["id"])).fetchone()
        if not mine:
            if player_id == "new":
                name = base = clean_name(user["display_name"] or user["username"])
                n = 2
                while in_org(org["id"], lambda: find_player(conn, name)):
                    name, n = f"{base} {n}", n + 1
                conn.execute("INSERT INTO players (organization_id, name, user_id) "
                             "VALUES (?, ?, ?)", (org["id"], name, user["id"]))
            else:
                player = conn.execute("SELECT * FROM players WHERE id = ? AND organization_id "
                                      "= ? AND user_id IS NULL",
                                      (opt_int(player_id), org["id"])).fetchone()
                if player is None:
                    return redirect(f"/invite/{code}")
                users.link_player(conn, user["id"], player["id"])
    return enter_org(request, org, "/friendlies")


def my_players(conn, user_id):
    """The account's players, one per organization, with their organization."""
    return conn.execute(
        "SELECT p.*, o.name AS org_name, o.slug AS org_slug, o.owner_id AS org_owner "
        "FROM players p JOIN organizations o "
        "ON o.id = p.organization_id WHERE p.user_id = ? ORDER BY o.name", (user_id,)).fetchall()


def in_org(organization_id, work):
    """Run `work()` with this organization's queries (db.ORG), whatever the browser's."""
    token = db.ORG.set(organization_id)
    try:
        return work()
    finally:
        db.ORG.reset(token)


def my_summary(conn, player):
    """A player's tournaments (position, points), pending sets, latest sets, totals
    and medals."""
    def work():
        sets = set_rows(conn, player_id=player["id"])
        ids = {s["tournament_id"] for s in sets} | {r[0] for r in conn.execute(
            "SELECT tournament_id FROM tournament_players WHERE player_id = ?", (player["id"],))}
        friendlies = friendlies_tournament(conn)
        if friendlies:  # every player of the organization is in it
            ids.add(friendlies["id"])
        tournaments = []
        for t in all_tournaments(conn):
            if t["id"] in ids:
                _, standings = load_results(conn, t["id"])
                me = next((r for r in standings if r["id"] == player["id"]), None)
                tournaments.append({**t, "me": me})
        played = [s for s in sets if is_played(s)]
        return {"player": player, "tournaments": tournaments,
                "pending": [{**s, "chance": chance_of(s)} for s in sets
                            if s["team_a_games"] is None],
                "recent": [s for s in sets if s["team_a_games"] is not None][:5],
                "totals": stats.totals(played, player["id"]),
                "friendlies": [s for s in played if s["rule_code"] == AMISTOSOS],
                "medals": player_awards(conn, player["id"])}
    return in_org(player["organization_id"], work)


def career(conn, summaries, lang):
    """The account's numbers over all its players, in every organization: one person."""
    totals = {k: sum(s["totals"][k] for s in summaries) for k in ("played", "won", "lost")}
    totals["win_pct"] = round(100 * totals["won"] / totals["played"]) if totals["played"] else 0
    totals["orgs"] = len(summaries)
    totals["tournaments"] = sum(len(s["tournaments"]) for s in summaries)
    won = {}
    for s in summaries:
        for code, m in s["medals"].items():
            got = won.setdefault(code, {"count": 0, "tier": None})
            got["count"] += m.get("count") or 1
            if m.get("tier") and (got["tier"] or 0) < m["tier"]:
                got["tier"] = m["tier"]
    totals["medals"] = [{**m, **won[m["code"]]} for m in medal_types(conn, lang)
                        if m["code"] in won]
    return totals


@app.get("/me", response_class=HTMLResponse)
def me_page(request: Request, error: str | None = None, saved: str | None = None):
    """The logged-in account's profile: its details, and for each of its players the
    tournaments, the sets still to play and the latest ones."""
    user = auth.current_user(request)
    if user is None:
        raise LoginRequired("/me")
    with db.connect() as conn:
        summaries = [my_summary(conn, p) for p in my_players(conn, user["id"])]
        totals = career(conn, summaries, get_lang(request))
        unclaimed = my_unclaimed(request, conn, user)
    return templates.TemplateResponse(request, "me.html", {
        "account": user, "summaries": summaries, "career": totals,
        "friendlies": my_friendlies(summaries), "unclaimed": unclaimed,
        "error": error, "saved": saved})


def my_friendlies(summaries):
    """🤝 The account's friendlies in every organization: totals, each organization's
    record and the latest ones (newest first)."""
    orgs_ = []
    for s in summaries:
        if s["friendlies"]:
            orgs_.append({"name": s["player"]["org_name"],
                          "totals": stats.totals(s["friendlies"], s["player"]["id"])})
    played = sorted((dict(m, org_name=s["player"]["org_name"]) for s in summaries
                     for m in s["friendlies"]),
                    key=lambda m: (m["played_on"], m["matchday"], m["court"]), reverse=True)
    totals = {k: sum(o["totals"][k] for o in orgs_) for k in ("played", "won", "lost")}
    totals["win_pct"] = round(100 * totals["won"] / totals["played"]) if totals["played"] else 0
    return {"totals": totals, "orgs": orgs_, "recent": played[:5]}


@app.post("/me")
def update_me(request: Request, username: str = Form(""), email: str = Form(""),
              first_name: str = Form(""), last_name: str = Form(""),
              display_name: str = Form(""), phone_country: str = Form(""),
              phone: str = Form(""), email_recaps: str = Form(""),
              email_reminders: str = Form("")):
    """Change your own details. A new display name renames your players too (if no one
    else in their organization has it)."""
    user = auth.current_user(request)
    if user is None:
        raise LoginRequired("/me")
    display = clean_name(display_name)
    with db.connect() as conn:
        mine = my_players(conn, user["id"])
        if display and any(in_org(p["organization_id"],
                                  lambda: find_player(conn, display, exclude=p["id"]))
                           for p in mine):
            return redirect("/me?error=err_player_exists")
        try:
            users.update_user(conn, user["id"], username=username, email=email,
                              first_name=first_name, last_name=last_name, display_name=display,
                              phone_country=phone_country, phone=phone)
        except users.UserError as e:
            return redirect(f"/me?error={e}")
        conn.execute("UPDATE users SET email_recaps = ?, email_reminders = ? WHERE id = ?",
                     (1 if email_recaps else 0, 1 if email_reminders else 0, user["id"]))
        for p in mine:
            in_org(p["organization_id"], lambda: take_display_name(conn, p, display))
    return redirect("/me?saved=1")


@app.post("/me/password")
def change_my_password(request: Request, current: str = Form(""), password: str = Form(""),
                       password2: str = Form("")):
    user = auth.current_user(request)
    if user is None:
        raise LoginRequired("/me")
    if not users.check_password(current, user["password"]):
        time.sleep(1)
        return redirect("/me?error=err_wrong_password#password")
    if len(password) < users.MIN_PASSWORD:
        return redirect("/me?error=err_password_short#password")
    if password != password2:
        return redirect("/me?error=err_passwords_differ#password")
    with db.connect() as conn:
        users.set_password(conn, user["id"], password)
        user = users.get(conn, user["id"])
    response = redirect("/me?saved=1")  # the new password changes this browser's cookie too
    response.set_cookie(auth.USER_COOKIE, auth.user_cookie(user), **cookie_options(request))
    return response


# --- Accounts (admins) ------------------------------------------------------------

def managed_users(conn, request):
    """The accounts this admin may manage: all for a super admin; for an organization
    admin, its organization's admins and the accounts of its players."""
    if auth.is_super(request):
        return conn.execute("SELECT * FROM users ORDER BY role, username").fetchall()
    return conn.execute(
        "SELECT * FROM users WHERE role != 'super' AND ((role = 'org_admin' AND "
        "organization_id = ?) OR id IN (SELECT user_id FROM players WHERE organization_id = ?)) "
        "ORDER BY role, username",
        (org_id(), org_id())).fetchall()


def managed_user(conn, request, user_id):
    user = next((u for u in managed_users(conn, request) if u["id"] == user_id), None)
    if user is None:
        raise HTTPException(404, "Account not found")
    return user


def linked_player(conn, user_id):
    """The account's player in this organization, or None."""
    return conn.execute("SELECT * FROM players WHERE user_id = ? AND organization_id = ?",
                        (user_id, org_id())).fetchone()


@app.get("/users", response_class=HTMLResponse, dependencies=CLUB)
def users_page(request: Request, error: str | None = None, mail: str | None = None):
    with db.connect() as conn:
        rows = [{**u, "player": linked_player(conn, u["id"])}
                for u in managed_users(conn, request)]
    return templates.TemplateResponse(request, "users.html", {
        "accounts": rows, "error": error, "mail_sent": mail == "sent",
        "mail_enabled": mailer.enabled()})


@app.post("/users/{user_id}/test-email", dependencies=CLUB)
def account_test_email(request: Request, user_id: int):
    """📧 Probar email on 🔑 Cuentas: email this account, now, the recap of its player's
    latest jornada in this organization (or, without one, a plain test message). Not
    recorded, so the morning email still goes."""
    with db.connect() as conn:
        user = managed_user(conn, request, user_id)
        if not user["email"]:
            return redirect("/users?error=err_no_player_email")
        if not mailer.enabled():
            return redirect("/users?error=err_mail_off")
        player = linked_player(conn, user_id)
        latest = player and conn.execute(
            "SELECT d.id FROM matchdays d JOIN tournaments t ON t.id = d.tournament_id "
            "JOIN matches m ON m.matchday_id = d.id WHERE t.organization_id = ? "
            "AND ? IN (m.a1, m.a2, m.b1, m.b2) AND m.team_a_games IS NOT NULL "
            "ORDER BY d.played_on DESC, d.number DESC LIMIT 1",
            (org_id(), player["id"])).fetchone()
        recap = latest and jornada_recap(conn, latest["id"], player["id"], "es")
        if recap:
            ok = deliver(conn, user, "test-recap", *recap_email(
                request, auth.current_org(request), recap, user, email_extras(conn, recap)),
                org=org_id(), matchday_id=latest["id"])
        else:
            _ = translator("es")
            ok = deliver(conn, user, "test", str(_("test_email_subject")),
                         str(_("test_email_body")), f"<p>{_('test_email_body')}</p>", org=org_id())
    return redirect("/users?mail=sent" if ok else f"/users?error={mail_error()}")


@app.get("/users/{user_id}", response_class=HTMLResponse, dependencies=CLUB)
def user_page(request: Request, user_id: int, error: str | None = None):
    with db.connect() as conn:
        account = managed_user(conn, request, user_id)
        return templates.TemplateResponse(request, "user_edit.html", {
            "account": account, "player": linked_player(conn, user_id),
            "free_players": conn.execute(
                "SELECT * FROM players WHERE organization_id = ? AND user_id IS NULL "
                "ORDER BY name", (org_id(),)).fetchall(),
            "organizations": conn.execute("SELECT * FROM organizations ORDER BY name").fetchall(),
            "error": error,
        })


def user_action(request, user_id, change):
    """Run `change(conn, account)` on an account this admin manages and go back to its
    page, with the error if it was refused."""
    with db.connect() as conn:
        account = managed_user(conn, request, user_id)
        try:
            change(conn, account)
        except users.UserError as e:
            return redirect(f"/users/{user_id}?error={e}")
    return redirect(f"/users/{user_id}")


@app.post("/users/{user_id}", dependencies=CLUB)
def update_user(request: Request, user_id: int, username: str = Form(""),
                email: str = Form(""), first_name: str = Form(""), last_name: str = Form(""),
                display_name: str = Form(""), phone_country: str = Form(""),
                phone: str = Form("")):
    return user_action(request, user_id, lambda conn, u: users.update_user(
        conn, u["id"], username=username, email=email, first_name=first_name,
        last_name=last_name, display_name=display_name, phone_country=phone_country,
        phone=phone))


@app.post("/users/{user_id}/password", dependencies=CLUB)
def reset_user_password(request: Request, user_id: int, password: str = Form("")):
    return user_action(request, user_id,
                       lambda conn, u: users.set_password(conn, u["id"], password))


@app.post("/users/{user_id}/role", dependencies=SUPER)
def set_user_role(request: Request, user_id: int, role: str = Form(""),
                  organization_id: str = Form("")):
    def change(conn, u):
        if u["id"] == auth.current_user(request)["id"]:
            raise users.UserError("err_own_role")  # don't lock yourself out
        users.set_role(conn, u["id"], role, opt_int(organization_id))
    return user_action(request, user_id, change)


@app.post("/users/{user_id}/link", dependencies=CLUB)
def link_user_player(request: Request, user_id: int, player_id: int = Form(...),
                     merge: str = Form("")):
    """Link a free player to the account, or with `merge` fold a duplicate into the
    account's player in this organization."""
    def change(conn, u):
        get_or_404(conn, "players", player_id)
        users.link_player(conn, u["id"], player_id, merge=bool(merge))
    return user_action(request, user_id, change)


@app.post("/users/{user_id}/unlink", dependencies=CLUB)
def unlink_user_player(request: Request, user_id: int):
    def change(conn, u):
        player = linked_player(conn, u["id"])
        if player:
            users.unlink_player(conn, player["id"])
    return user_action(request, user_id, change)


@app.get("/install", response_class=HTMLResponse)
def install_page(request: Request, os: str = "android"):
    """📲 Install the app, in tabs: Android (the first one; a button) and iPhone (drawn
    steps). See install.html."""
    return templates.TemplateResponse(request, "install.html", {
        "os": "iphone" if os == "iphone" else "android"})


@app.get("/sw.js")
def service_worker():
    """The installed app's service worker (app/static/sw.js). It's served from the root
    so it covers the whole site, and never cached, so a new version takes over soon."""
    return FileResponse(BASE / "static" / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health():
    """For the deploy pipeline: which commit is live, and the database changes applied."""
    with db.connect() as conn:
        return {"version": VERSION, "migrations": sorted(migrate.applied(conn))}


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
            "rule_types": [r for r in all_rule_types(conn) if r["code"] != AMISTOSOS],
            "friendlies": friendlies_tournament(conn),
            "players": all_players(conn),
            "players_json": [{"id": p["id"], "name": p["name"]} for p in all_players(conn)],
            "today": league_today().isoformat(),
        })


@app.post("/tournaments", dependencies=CLUB)
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
        if not rule or rule["code"] == AMISTOSOS:  # Amistosos comes by itself
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
            "player_password, organization_id) VALUES (?, ?, ?, ?, ?, ?)",
            (name, held_on, rule_type_id, target, password, org_id())).lastrowid
        conn.executemany("INSERT INTO tournament_players (tournament_id, player_id) "
                         "VALUES (?, ?)", [(tournament_id, p) for p in players])
    return redirect(f"/tournaments/{tournament_id}")


@app.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
def tournament_page(request: Request, tournament_id: int, error: str | None = None,
                    mail: str | None = None):
    with db.connect() as conn:
        tournament = get_tournament(conn, tournament_id)
        results, standings = load_results(conn, tournament_id)
        return templates.TemplateResponse(request, "tournament.html", {
            "tournament": tournament,
            "results": results,
            "standings": standings,
            "player_medals": tournament_medals(conn, tournament_id, standings, get_lang(request)),
            "usernames": account_usernames(conn),
            "participants": tournament_players(conn, tournament_id),
            "players": all_players(conn),
            # admins can email these players their recap, to try it (📧 in the list)
            "emailable": {r[0] for r in conn.execute(
                "SELECT p.id FROM players p JOIN users u ON u.id = p.user_id "
                "WHERE p.organization_id = ? AND u.email IS NOT NULL", (org_id(),))},
            "mail_sent": mail == "sent",
            "today": league_today().isoformat(),
            "error": error,
            **summary_card(request, conn, last_played(results)),
            "ladder": ladder_state(conn, tournament_id) if tournament["rule_code"] == LADDER
                      else None,
            "my_player_id": my_player_id(request, conn),
            "ladder_started": bool(set_rows(conn, tournament_id=tournament_id, limit=1)),
            "can_add_friendly": can_add_friendly(request, conn),
            "invite": invite_share(request, auth.current_org(request))
                      if auth.current_org(request)["owner_id"] else None,
        })


@app.get("/tournaments/{tournament_id}/summary", response_class=HTMLResponse)
def tournament_summary(request: Request, tournament_id: int):
    """🏁 Resumen del torneo: the podium, the season's highlights and the medals won in
    the tournament. Final once it has ended; "so far" while it's going."""
    lang = get_lang(request)
    with db.connect() as conn:
        tournament = get_tournament(conn, tournament_id)
        results, standings = load_results(conn, tournament_id)
        sets = [s for s in reversed(set_rows(conn, tournament_id=tournament_id))
                if is_played(s)]
        won = tournament_medals(conn, tournament_id, standings, lang)
        catalog = medal_types(conn, lang)
    holders = {}
    for row in standings:
        for medal in won.get(row["id"], []):
            holders.setdefault(medal["code"], []).append(row)
    return templates.TemplateResponse(request, "season.html", {
        "tournament": tournament, "standings": standings,
        "podium": [r for r in standings if r["position"] <= 3],
        "matchdays": len(results),
        "hl": stats.season(results, standings, sets, tournament["rule_code"] == "liga_amigos"),
        "medals": [{**m, "holders": holders[m["code"]]} for m in catalog if m["code"] in holders],
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


def in_tournament(conn, tournament_id, pid):
    """Whether the player is in the tournament's list or has a set in it."""
    return conn.execute(
        "SELECT 1 FROM tournament_players WHERE tournament_id = ? AND player_id = ? "
        "UNION SELECT 1 FROM matches m JOIN matchdays d ON d.id = m.matchday_id "
        "WHERE d.tournament_id = ? AND ? IN (m.a1, m.a2, m.b1, m.b2)",
        (tournament_id, pid, tournament_id, pid)).fetchone() is not None


@app.get("/tournaments/{tournament_id}/players/{pid}/replace", response_class=HTMLResponse,
         dependencies=EDIT)
def replace_player_page(request: Request, tournament_id: int, pid: int,
                        next: str = "", error: str | None = None):
    """Choose who replaces a player (e.g. from a matchday's court table)."""
    with db.connect() as conn:
        tournament = get_tournament(conn, tournament_id)
        player = get_or_404(conn, "players", pid)
        if not in_tournament(conn, tournament_id, pid):
            raise HTTPException(404, "Player not in this tournament")
        members = {p["id"] for p in tournament_players(conn, tournament_id)}
        return templates.TemplateResponse(request, "replace_player.html", {
            "tournament": tournament, "player": player, "error": error,
            "next": safe_next(next or f"/tournaments/{tournament_id}"),
            "candidates": [{"id": p["id"], "name": p["name"]} for p in all_players(conn)
                           if p["id"] != pid and p["id"] not in members],
        })


@app.post("/tournaments/{tournament_id}/players/replace", dependencies=EDIT)
def replace_tournament_player(tournament_id: int, old_id: int = Form(0),
                              player_name: str = Form(""), create: str = Form(""),
                              points: str = Form("keep"), next: str = Form("")):
    """Put another player (found by name, or new with `create`) in place of one of the
    tournament: in its list and in its sets not played yet. `points` says what happens
    to the sets already played in this tournament:
    - "keep": they, and their points, stay with the player who leaves; the new one
      starts from zero;
    - "move": they go to the new player too (with the absences), who takes the
      leaving player's whole place in the tournament: points, history and medals.
    With `next` (the replace page), errors go back to that page and success goes to
    `next`."""
    name = clean_name(player_name)
    back = f"/tournaments/{tournament_id}"
    done = f"{back}#players"
    if next:
        done = safe_next(next)
        back = f"{back}/players/{old_id}/replace?{urlencode({'next': done})}"

    def fail(error):
        sep = "&" if "?" in back else "?"
        return redirect(f"{back}{sep}error={error}" + ("" if next else "#replace"))

    with db.connect() as conn:
        get_or_404(conn, "tournaments", tournament_id)
        if not old_id or not in_tournament(conn, tournament_id, old_id):
            return fail("err_choose_leaving")
        new_id = find_player(conn, name)
        if new_id is None and not (create and name):
            return fail("err_unknown_player")
        if new_id == old_id:
            return fail("err_replace_same")
        move = points == "move"
        pending = (("" if move else "team_a_games IS NULL AND ") +
                   "matchday_id IN (SELECT id FROM matchdays WHERE tournament_id = ?)")
        if new_id and conn.execute(
                f"SELECT 1 FROM matches WHERE {pending} AND ? IN (a1, a2, b1, b2) "
                "AND ? IN (a1, a2, b1, b2)", (tournament_id, old_id, new_id)).fetchone():
            return fail("err_replace_conflict_all" if move else "err_replace_conflict")
        new_id = new_id or player_id(conn, name)
        for col in ("a1", "a2", "b1", "b2"):
            conn.execute(f"UPDATE matches SET {col} = ? WHERE {col} = ? AND {pending}",
                         (new_id, old_id, tournament_id))
        if move:  # the absences of those matchdays too: the points follow the sets
            days = "matchday_id IN (SELECT id FROM matchdays WHERE tournament_id = ?)"
            conn.execute(f"INSERT OR IGNORE INTO absences (matchday_id, player_id) "
                         f"SELECT matchday_id, ? FROM absences WHERE player_id = ? AND {days}",
                         (new_id, old_id, tournament_id))
            conn.execute(f"DELETE FROM absences WHERE player_id = ? AND {days}",
                         (old_id, tournament_id))
        conn.execute("DELETE FROM tournament_players WHERE tournament_id = ? AND player_id = ?",
                     (tournament_id, old_id))
        conn.execute("INSERT OR IGNORE INTO tournament_players (tournament_id, player_id) "
                     "VALUES (?, ?)", (tournament_id, new_id))
        for col in ("player1_id", "player2_id"):  # an Escalafón pair keeps its place
            conn.execute(f"UPDATE ladder_pairs SET {col} = ? WHERE {col} = ? AND "
                         "tournament_id = ? AND active = 1", (new_id, old_id, tournament_id))
    return redirect(done)


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
                  error: str | None = None, summary: str | None = None, n: str = ""):
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
        code = tournament["rule_code"]
        return templates.TemplateResponse(request, "matchday.html", {
            "tournament": tournament,
            "matchday": result,
            "results": results,
            "sets": sets,
            # Retas / Rey de la cancha: the jornada by rounds, its table, what comes next.
            "rounds": by_round(sets) if code in DAY_ROUNDS else {},
            "day_table": day_table(result) if code in DAY_ROUNDS else [],
            "rey": rey_state(conn, matchday_id, sets) if code == REY else None,
            "next_round_ready": code == RETAS and bool(sets) and all(is_played(s) for s in sets),
            "error_n": n,
            "resting": resting,
            "moves": court_moves(result["courts"], move),
            "move": move,
            "error": error,
            # Only the latest matchday offers to start the next one, a week later.
            "next_number": results[-1]["number"] + 1 if results[-1]["id"] == matchday_id else None,
            "next_date": (date.fromisoformat(matchday["played_on"]) + timedelta(days=7)).isoformat(),
            "in_matchday": True,
            "recap_players": md_players(result),
            "scorer": auth.can_score(request, tournament),
            "can_add_friendly": code == AMISTOSOS and can_add_friendly(request, conn),
            # The sets this browser may score: all for the admin, a player's own.
            "scorable": {s["id"] for s in sets if auth.can_score_set(
                request, tournament, {k: s[k + "_id"] for k in ("a1", "a2", "b1", "b2")})},
            **summary_card(request, conn, result if last_played([result]) else None,
                           queued=summary == "queued"),
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
        conn.execute("DELETE FROM sent_emails WHERE matchday_id = ?", (matchday_id,))
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
    if code in ONE_MATCH:
        return [(tuple(players[:2]), tuple(players[2:]))]
    return court_rotation(players)


def same_court(old, new, code):
    """Whether a court keeps its sets: the same four players (the same pairs in an
    Americano / Mexicano round)."""
    if old is None:
        return False
    if code in ONE_MATCH:
        return {frozenset(old[:2]), frozenset(old[2:])} == {frozenset(new[:2]), frozenset(new[2:])}
    return set(old) == set(new)


def add_court_sets(conn, matchday_id, court, players, code):
    """The court's sets, pending. Its players also go on the tournament's list (if it
    keeps one), so whoever plays a jornada can be chosen for the next one, even a
    player whose place on the list someone else took while they were absent."""
    for (a1, a2), (b1, b2) in court_sets(players, code):
        conn.execute(
            "INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, round) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (matchday_id, court, a1, a2, b1, b2, 1 if code == RETAS else None))
    tournament_id = conn.execute("SELECT tournament_id FROM matchdays WHERE id = ?",
                                 (matchday_id,)).fetchone()[0]
    if conn.execute("SELECT 1 FROM tournament_players WHERE tournament_id = ?",
                    (tournament_id,)).fetchone():
        conn.executemany("INSERT OR IGNORE INTO tournament_players (tournament_id, player_id) "
                         "VALUES (?, ?)", [(tournament_id, p) for p in players])


def draw_round(conn, tournament, number, courts=None, rest=()):
    """The suggested courts of an Americano / Mexicano round: (courts, resting ids).
    courts: how many courts are available; rest: players who asked to rest."""
    players = [p["id"] for p in tournament_players(conn, tournament["id"])]
    results, standings = load_results(conn, tournament["id"])
    history = [[ids for _, ids in sorted(courts_of(md["sets"])[0].items()) if ids]
               for md in results if md["number"] < number and md["sets"]]
    seed = tournament["id"] * 1000 + number  # the same suggestion on every reload
    if tournament["rule_code"] == RETAS:
        return formats.draw_courts(players, seed, courts, rest)
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
    or to change the courts of an existing one. The players to choose from are the
    tournament's list plus anyone already placed on a court, e.g. a player the
    suggestion moves down after being absent, whose place on the list someone else
    took: otherwise their select would come up empty."""
    listed = players_for(conn, tournament["id"])
    known = {p["id"] for p in listed}
    placed = {p for ids in courts for p in ids if p and p not in known}
    choices = sorted([*listed, *(p for p in all_players(conn) if p["id"] in placed)],
                     key=lambda p: p["name"].lower())
    return templates.TemplateResponse(request, "courts.html", {
        "tournament": tournament, "matchday": matchday, "courts": courts,
        "number": matchday["number"] if matchday else number,
        "played_on": played_on, "players": choices,
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
                      rest: list[int] = Query([]), seed: str | None = None):
    """Draft of the next matchday: choose how many players change court, then review
    the courts. Nothing is saved here."""
    with db.connect() as conn:
        tournament = get_tournament(conn, tournament_id)
        played_on = parse_date(played_on or league_today().isoformat())
        if played_on is None:
            return redirect(f"/tournaments/{tournament_id}?error=err_invalid_date")
        number = next_number(conn, tournament_id)
        if tournament["rule_code"] == MANUAL:  # only the date: sets are added by hand
            return render_courts(request, conn, tournament, [], number=number,
                                 played_on=played_on, move=1)
        if tournament["rule_code"] == LADDER:  # retos come from the ladder
            return redirect(f"/tournaments/{tournament_id}#ladder")
        if tournament["rule_code"] == REY:  # the line of pairs
            pairs = draw_pairs(players_for(conn, tournament_id),
                               opt_int(seed) or tournament_id * 1000 + number)
            return render_pairs(request, conn, tournament, pairs, played_on, number)
        if tournament["rule_code"] in DRAWN:
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
        if tournament["rule_code"] == LADDER:
            return redirect(f"/tournaments/{tournament_id}#ladder")
        if tournament["rule_code"] == REY:
            return add_rey_matchday(request, conn, tournament, form, played_on, number, _)
        manual = tournament["rule_code"] == MANUAL
        chosen, error = ([], None) if manual else check_courts(conn, courts, _)
        if played_on is None:
            error = _("err_invalid_date")
        if error:
            return render_courts(
                request, conn, tournament, courts, number=number,
                played_on=form.get("played_on", ""), move=opt_int(form.get("move")),
                previous=None if tournament["rule_code"] in DRAWN
                else previous_matchday(conn, tournament_id, number),
                error=error, status_code=400)
        matchday_id = conn.execute(
            "INSERT INTO matchdays (tournament_id, number, played_on) VALUES (?, ?, ?)",
            (tournament_id, number, played_on),
        ).lastrowid
        for n, ids in enumerate(chosen, 1):
            add_court_sets(conn, matchday_id, n, ids, tournament["rule_code"])
    return redirect(f"/matchdays/{matchday_id}")


def add_rey_matchday(request, conn, tournament, form, played_on, number, _):
    """Save a Rey de la cancha jornada: its line of pairs and the first match (the first
    two pairs). Every player once; at least two pairs."""
    try:
        pairs = read_pairs(form)
    except ValueError:
        pairs = None
    known = {p["id"] for p in all_players(conn)}
    flat = [p for pair_ in pairs or [] for p in pair_]
    if not pairs or len(pairs) < 2 or len(set(flat)) != len(flat) or not set(flat) <= known \
            or played_on is None:
        return render_pairs(request, conn, tournament, pairs or [], form.get("played_on", ""),
                            number, error=_("err_invalid_date") if played_on is None
                            else _("err_rey_pairs"), status_code=400)
    matchday_id = conn.execute(
        "INSERT INTO matchdays (tournament_id, number, played_on) VALUES (?, ?, ?)",
        (tournament["id"], number, played_on)).lastrowid
    conn.executemany("INSERT INTO queue_pairs (matchday_id, slot, player1_id, player2_id) "
                     "VALUES (?, ?, ?, ?)", [(matchday_id, n, *p) for n, p in enumerate(pairs, 1)])
    (a1, a2), (b1, b2) = pairs[0], pairs[1]
    conn.execute("INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, round) "
                 "VALUES (?, 1, ?, ?, ?, ?, 1)", (matchday_id, a1, a2, b1, b2))
    conn.executemany("INSERT OR IGNORE INTO tournament_players (tournament_id, player_id) "
                     "VALUES (?, ?)", [(tournament["id"], p) for p in flat])
    return redirect(f"/matchdays/{matchday_id}")


@app.get("/courts", dependencies=CLUB)
def latest_courts():
    """The '+ Courts' button: the courts of the latest matchday."""
    with db.connect() as conn:
        latest = conn.execute(
            "SELECT d.id FROM matchdays d JOIN tournaments t ON t.id = d.tournament_id "
            "WHERE t.organization_id = ? ORDER BY d.played_on DESC, d.number DESC, d.id DESC "
            "LIMIT 1", (org_id(),)).fetchone()
    return redirect(f"/matchdays/{latest['id']}/courts" if latest else "/tournaments")


@app.get("/matchdays/{matchday_id}/courts", response_class=HTMLResponse, dependencies=EDIT)
def courts_page(request: Request, matchday_id: int, move: str | None = None,
                courts: str | None = None, rest: list[int] = Query([])):
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        tournament = get_tournament(conn, matchday["tournament_id"])
        if tournament["rule_code"] == MANUAL:  # no courts to assign: add sets by hand
            return redirect(f"/matches/new?matchday={matchday_id}")
        md_sets = set_rows(conn, matchday_id=matchday_id)
        if tournament["rule_code"] in (REY, LADDER) or any((s["round"] or 1) > 1 for s in md_sets):
            # the line, a reto, or rounds after the first: change players set by set
            return redirect(f"/matchdays/{matchday_id}")
        players, _ = courts_of(md_sets)
        if players:
            assigned = [ids or [None] * 4 for _, ids in sorted(players.items())]
            return render_courts(request, conn, tournament, assigned, matchday=matchday)
        if tournament["rule_code"] in DRAWN:
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
        player_id(conn, name)
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


def player_tournaments(conn, player_id, sets, cache=None):
    """The tournaments the player has sets in: position, totals, and their row on each
    matchday (court, points...), in playing order. `cache` (a dict) keeps each
    tournament's results for the next player."""
    tournament_ids = {s["tournament_id"] for s in sets}
    tournaments = []
    cache = {} if cache is None else cache
    for t in cache.get("tournaments") or cache.setdefault("tournaments", all_tournaments(conn)):
        if t["id"] not in tournament_ids:
            continue
        if t["id"] not in cache:
            cache[t["id"]] = load_results(conn, t["id"])
        results, standings = cache[t["id"]]
        me = next((r for r in standings if r["id"] == player_id), None)
        history = []
        for md in results:
            entry = {"id": md["id"], "number": md["number"], "played_on": md["played_on"]}
            for court, rows in md["courts"].items():
                for r in rows:
                    if r["id"] == player_id and r["sets"]:
                        history.append({**entry, "court": court, **r})
        tournaments.append({"id": t["id"], "name": t["name"], "rule_code": t["rule_code"],
                            "ended": t["ended"], "position": me and me["position"],
                            "total": me, "players": len(standings), "matchdays": t["matchdays"],
                            "last_position": max((r["position"] for r in standings), default=None),
                            "history": history})
    return tournaments


@app.get("/players/{player_id}", response_class=HTMLResponse)
def player_page(request: Request, player_id: int, error: str | None = None):
    with db.connect() as conn:
        player = get_or_404(conn, "players", player_id)
        sets = set_rows(conn, player_id=player_id)
        tournaments = player_tournaments(conn, player_id, sets)

    partners = Counter()
    for s in filter(is_played, sets):
        for team in (("a1", "a2"), ("b1", "b2")):
            ids = [s[k + "_id"] for k in team]
            if player_id in ids:
                other = team[1] if ids[0] == player_id else team[0]
                partners[(s[other + "_id"], s[other])] += 1

    account = None
    if player["user_id"] and auth.is_editor(request):
        with db.connect() as conn:
            account = users.get(conn, player["user_id"])
    return templates.TemplateResponse(request, "player.html", {
        "player": player, "account": account,
        "tournaments": tournaments,
        "partners": [{"id": pid, "name": name, "count": n}
                     for (pid, name), n in partners.most_common()],
        "matches": sets,
        "error": error,
    })


@app.get("/players/{player_id}/stats", response_class=HTMLResponse)
def player_stats_page(request: Request, player_id: int, only: str = ""):
    """The player's dashboard: totals, form, streaks, partners and rivals, with charts.
    only=friendlies: the 🤝 Amistosos alone."""
    _ = translator(get_lang(request))
    friendlies_only = only == "friendlies"
    with db.connect() as conn:
        player = get_or_404(conn, "players", player_id)
        sets = set_rows(conn, player_id=player_id)
        has_friendlies = any(s["rule_code"] == AMISTOSOS for s in sets)
        if friendlies_only:
            sets = [s for s in sets if s["rule_code"] == AMISTOSOS]
        tournaments = player_tournaments(conn, player_id, sets)
    played = [s for s in reversed(sets) if is_played(s)]  # oldest first
    board = stats.dashboard(played, player_id)
    t = board["totals"]
    results = {"W": str(_("won")), "L": str(_("lost")), "T": str(_("tied"))}
    points_charts = []
    for tour in tournaments:
        total, values = 0, []
        for h in tour["history"]:
            total += h["points"]
            values.append(total)
        if len(values) > 1 and tour["rule_code"] != AMISTOSOS:  # friendlies: win % says it
            points_charts.append({"tournament": tour, "chart": charts.line_chart(
                values, f"{tour['name']}: {_('cumulative_points')}",
                labels=[str(_("matchday_short", n=h["number"])) for h in tour["history"]])})
    partners = [p for p in board["partners"] if p["played"]][:8]
    return templates.TemplateResponse(request, "player_stats.html", {
        "player": player, "board": board, "tournaments": tournaments,
        "friendlies_only": friendlies_only, "has_friendlies": has_friendlies,
        "points_charts": points_charts,
        "donut": charts.donut([(results["W"], t["won"], charts.COLORS["W"]),
                               (results["L"], t["lost"], charts.COLORS["L"]),
                               (results["T"], t["tied"], charts.COLORS["T"])],
                              _("sets_won_lost"), center=f"{t['win_pct']}%"),
        "strip": charts.streak_strip(board["form"], _("form"), results),
        "rolling": charts.line_chart(board["rolling"], _("rolling_win_pct"), suffix="%", top=100,
                                     labels=[str(i + 1) for i in range(len(board["rolling"]))]),
        "months": charts.bar_chart([(m, n) for m, n in board["months"]][-12:], _("sets_per_month")),
        "partner_bars": charts.bar_chart([(p["name"], p["played"]) for p in partners],
                                         _("partners")),
        "partner_wins": charts.bar_chart(
            [(p["name"], p["won"]) for p in sorted(partners, key=lambda p: -p["won"]) if p["won"]],
            _("wins_with"), color="var(--up)"),
    })


@app.get("/players/{player_id}/vs", response_class=HTMLResponse)
def head_to_head_page(request: Request, player_id: int, other: str | None = None):
    """⚔️ Cara a cara: the player against any other player of the organization (sets won
    and lost against them, games, and as partners). Without `other`, their main rival."""
    _ = translator(get_lang(request))
    with db.connect() as conn:
        player = get_or_404(conn, "players", player_id)
        played = [s for s in reversed(set_rows(conn, player_id=player_id)) if is_played(s)]
        people = {p["id"]: p for p in all_players(conn) if p["id"] != player_id}
        rates = org_rates(conn)
    met = Counter(i for s in played for i in (s["a1_id"], s["a2_id"], s["b1_id"], s["b2_id"])
                  if i != player_id)
    choices = sorted((p for p in people.values() if met[p["id"]]),
                     key=lambda p: (-met[p["id"]], p["name"].lower()))
    rival = stats.highlights(played, player_id)["rival"]
    chosen = opt_int(other)
    if chosen not in people:
        chosen = rival["id"] if rival else None
    h2h = stats.head_to_head(played, player_id, chosen) if chosen else None
    results = {"W": str(_("won")), "L": str(_("lost")), "T": str(_("tied"))}
    return templates.TemplateResponse(request, "head_to_head.html", {
        "player": player, "other": people.get(chosen), "choices": choices, "h2h": h2h,
        "strip": charts.streak_strip(h2h["form"], _("h2h_results"), results) if h2h else "",
        "chance": round(100 * stats.win_probability(rates, (player_id,), (chosen,)))
                  if chosen else None,
    })


def ranking_upto(standings, number):
    """{player id: position} counting matchdays 1..number (equal points share a
    position), for the players who had played by then."""
    points = {r["id"]: sum(p for n, p in r["by_matchday"].items() if n <= number)
              for r in standings if any(n <= number for n in r["by_matchday"])}
    return {pid: 1 + sum(1 for other in points.values() if other > p)
            for pid, p in points.items()}


def jornada_recap(conn, matchday_id, player_id, lang):
    """A player's jornada: their court (place, points, sets), their sets, the ranking
    after it and how it moved, the court of the next jornada, and the medals won that
    day. None if they didn't play it."""
    matchday = get_or_404(conn, "matchdays", matchday_id)
    tournament = get_tournament(conn, matchday["tournament_id"])
    results, standings = load_results(conn, tournament["id"])
    md = next(r for r in results if r["id"] == matchday_id)
    mine = [(court, r) for court, rows in md["courts"].items() for r in rows
            if r["id"] == player_id and r["sets"]]
    if not mine:
        return None
    court, row = mine[0]
    sets = set_rows(conn, matchday_id=matchday_id, player_id=player_id)
    played = [s for s in reversed(sets) if is_played(s)]
    after = ranking_upto(standings, md["number"]).get(player_id)
    before = ranking_upto(standings, md["number"] - 1).get(player_id)
    upcoming = next((r for r in results if r["number"] == md["number"] + 1), None)
    next_court = next((c for c, rows in upcoming["courts"].items() for r in rows
                       if r["id"] == player_id), None) if upcoming else None
    # Medals of that day only: its sets, and the tournament's row for that matchday.
    day = [{**t, "ended": False, "matchdays": 0,
            "history": [h for h in t["history"] if h["id"] == matchday_id]}
           for t in player_tournaments(conn, player_id, played) if t["id"] == tournament["id"]]
    won = medals.awards(played, player_id, day)
    return {"tournament": tournament, "matchday": md, "player": get_or_404(conn, "players", player_id),
            "court": court, "row": row, "sets": sets, "players": len(md_players(md)),
            "position": after, "moved": before - after if before and after else None,
            "next_court": next_court, "standings": standings,
            "medals": [{**m, **won[m["code"]]} for m in medal_types(conn, lang)
                       if m["code"] in won]}


def md_players(md):
    """{player id: name} of everyone on a matchday's courts, by name."""
    rows = {r["id"]: r["name"] for rows in md["courts"].values() for r in rows}
    return dict(sorted(rows.items(), key=lambda kv: kv[1].lower()))


def recap_share(request, org, recap):
    """The recap's public link (/r/...) and its WhatsApp message."""
    _ = translator(get_lang(request))
    md, pid = recap["matchday"], recap["player"]["id"]
    scheme = "https" if auth.is_https(request) else "http"
    url = (f"{scheme}://{request.url.netloc}/r/{org['id']}/{md['id']}/{pid}/"
           f"{auth.recap_token(org, md['id'], pid)}")
    row = recap["row"]
    lines = [_("recap_share_head", name=recap["player"]["name"],
               tournament=recap["tournament"]["name"], n=md["number"])]
    if row["absent"]:
        lines.append(_("recap_share_absent"))
    else:
        lines.append(_("recap_share_court", place=row["place"] or "–", court=recap["court"],
                       points=row["points"], won=row["sets_won"], sets=row["sets"]))
    if recap["position"]:
        moved = recap["moved"]
        arrow = f" ▲{moved}" if moved and moved > 0 else f" ▼{-moved}" if moved else ""
        lines.append(_("recap_share_rank", n=recap["position"]) + arrow)
    if recap["medals"]:
        lines.append("🏅 " + ", ".join(m["name"] for m in recap["medals"]))
    text = "\n".join(str(line) for line in lines) + f"\n{url}"
    return {"url": url, "text": text, "whatsapp": "https://wa.me/?text=" + quote(text, safe="")}


def email_extras(conn, recap):
    """What the recap email adds to the recap: the player's tournament (totals, best
    streak, form, points per jornada) and their medals in it. Charts are HTML (bars and
    squares) and medals their emoji: email apps don't show SVG."""
    t, pid = recap["tournament"], recap["player"]["id"]
    sets = [s for s in reversed(set_rows(conn, tournament_id=t["id"], player_id=pid))
            if is_played(s)]
    me = next((r for r in recap["standings"] if r["id"] == pid), None)
    days = sorted(me["by_matchday"].items()) if me else []
    top = max((pts for _, pts in days), default=0) or 1
    today = {m["code"] for m in recap["medals"]}
    won = tournament_medals(conn, t["id"], recap["standings"], "es").get(pid, [])
    return {"totals": stats.totals(sets, pid), "streak": stats.streaks(sets, pid),
            "form": [stats.outcome(s, pid) for s in sets][-12:],
            "bars": [{"number": n, "points": pts, "width": max(round(100 * pts / top), 2)}
                     for n, pts in days],
            "medals": [{**m, "icon": medals.ICONS.get(m["code"], "🏅"), "new": m["code"] in today}
                       for m in won]}


def site_base(request):
    """https://<host> of this request (Azure's front end speaks HTTPS for us)."""
    return f"{'https' if auth.is_https(request) else 'http'}://{request.url.netloc}"


def unsubscribe_url(request, user, kind):
    """An email's signed unsubscribe link; `kind` is "recaps" or "reminders"."""
    return f"{site_base(request)}/unsubscribe/{user['id']}/{auth.unsubscribe_token(user)}?kind={kind}"


def require_task_token(request):
    """The daily tasks only exist for a caller with the X-Task-Token header equal to the
    TASKS_TOKEN app setting (GitHub Actions)."""
    token = os.environ.get("TASKS_TOKEN", "")
    if not token or not hmac.compare_digest(request.headers.get("x-task-token", ""), token):
        raise HTTPException(404, "Not found")


def recap_email(request, org, recap, user, extras=None):
    """(subject, plain text, HTML) of a jornada recap email, in Spanish (the league's
    language; accounts have no language of their own yet). `extras`: email_extras()."""
    _ = translator("es")
    share = recap_share(request, org, recap)
    unsubscribe = unsubscribe_url(request, user, "recaps")
    subject = str(_("recap_email_subject", n=recap["matchday"]["number"],
                    tournament=recap["tournament"]["name"]))
    text = (f"{share['text']}\n\n{_('recap_email_whatsapp')}: {share['whatsapp']}\n\n"
            f"{_('recap_email_unsubscribe')}: {unsubscribe}")
    html = templates.env.get_template("email_recap.html").render(
        _=_, recap=recap, share=share, unsubscribe=unsubscribe, org_name=org["name"],
        x=extras or {"totals": None, "streak": None, "form": [], "bars": [], "medals": []})
    return subject, text, html


def recaps_due(conn):
    """(matchday, player, account, organization) for every account to email the recap
    of a jornada played in the last 3 days (up to yesterday). Only accounts with an email
    AND a player (the jornada's players joined to their account); recaps on; all its
    sets of that jornada played; not emailed yet."""
    today = league_today()
    return conn.execute(
        """
        SELECT DISTINCT d.id AS matchday_id, p.id AS player_id, u.id AS user_id,
               t.organization_id
        FROM matchdays d
        JOIN tournaments t ON t.id = d.tournament_id
        JOIN matches m ON m.matchday_id = d.id
        JOIN players p ON p.id IN (m.a1, m.a2, m.b1, m.b2)
        JOIN users u ON u.id = p.user_id
        WHERE d.played_on BETWEEN ? AND ? AND u.email IS NOT NULL AND u.email_recaps = 1
          AND NOT EXISTS (SELECT 1 FROM sent_emails s WHERE s.kind = 'recap'
                          AND s.user_id = u.id AND s.matchday_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM matches x WHERE x.matchday_id = d.id
                          AND p.id IN (x.a1, x.a2, x.b1, x.b2) AND x.team_a_games IS NULL)
        ORDER BY d.id, u.id
        """, ((today - timedelta(days=3)).isoformat(),
              (today - timedelta(days=1)).isoformat())).fetchall()


def deliver(conn, user, kind, subject, text, html, org=None, matchday_id=None,
            attachments=None):
    """Send one email to an account (mailer.send) and log the attempt, sent or not, in
    email_log (📬 Emails). `kind`: one of EMAIL_KINDS."""
    ok = mailer.send(user["email"], user["display_name"] or user["username"], subject, text,
                     html, *([attachments] if attachments else []))
    status = "sent" if ok else ("throttled" if mailer.last_status == mailer.THROTTLED else "failed")
    conn.execute(
        "INSERT INTO email_log (day, organization_id, user_id, address, kind, matchday_id, "
        "subject, status, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (league_today().isoformat(), org, user["id"], user["email"], kind, matchday_id,
         str(subject), status, None if ok else mailer.last_error))
    conn.commit()
    return ok


def mail_error():
    """The error key for a failed email: Azure's sending limit, or anything else."""
    return "err_mail_throttled" if mailer.last_status == mailer.THROTTLED else "err_mail_failed"


def build_due_email(request, conn, kind, org, due, user, cache):
    """(subject, text, HTML[, attachments]) of a due reminder, jornada summary or recap
    (inside its organization), or None when there's nothing to say any more. `cache`:
    what one run builds once (the summary's PDF)."""
    if kind == "reminder":
        data = reminder_data(conn, due["matchday_id"], due["player_id"])
        return data and reminder_email(request, org, data, user)
    if kind == "summary":  # the same PDF for everyone: built once per run
        key = ("summary", due["matchday_id"])
        if key not in cache:
            data = jornada_summary(conn, due["matchday_id"], "es")
            cache[key] = (data, report.build(data, translator("es")))
        return summary_email(request, org, *cache[key], user)
    recap = jornada_recap(conn, due["matchday_id"], due["player_id"], "es")
    return recap and recap_email(request, org, recap, user, email_extras(conn, recap))


DUE = {"reminder": lambda conn: reminders_due(conn), "recap": lambda conn: recaps_due(conn),
       "summary": lambda conn: summaries_due(conn)}  # each kind's due emails
SENDING = threading.Lock()  # one batch at a time (the hourly job, an admin's 📄 send)


def send_due(request, kinds):
    """Send the due emails of these kinds ("reminder", "summary", "recap"), at most
    mailer.per_run() of them, mailer.pause() seconds apart, for Azure's limits. If Azure
    answers 429 (over its limit) it stops: nothing more is marked sent, and the next
    hourly run carries on. Returns the counts."""
    out = {"sent": 0, "failed": 0, "left": 0, "throttled": False}
    budget, cache = mailer.per_run(), {}
    with SENDING, db.connect() as conn:
        for kind in kinds:
            for due in DUE[kind](conn):
                if out["throttled"] or out["sent"] + out["failed"] >= budget:
                    out["left"] += 1
                    continue
                org = conn.execute("SELECT * FROM organizations WHERE id = ?",
                                   (due["organization_id"],)).fetchone()
                user = users.get(conn, due["user_id"])
                email = in_org(org["id"], lambda: build_due_email(request, conn, kind, org,
                                                                  due, user, cache))
                if email is None:
                    continue
                if out["sent"] + out["failed"]:
                    time.sleep(mailer.pause())
                if deliver(conn, user, kind, *email[:3], org=org["id"],
                           matchday_id=due["matchday_id"], attachments=email[3:] and email[3]):
                    conn.execute("INSERT INTO sent_emails (kind, user_id, matchday_id) "
                                 "VALUES (?, ?, ?)", (kind, user["id"], due["matchday_id"]))
                    conn.commit()  # each one counts, even if a later one fails
                    out["sent"] += 1
                else:
                    out["failed"] += 1
                    out["throttled"] = mailer.last_status == mailer.THROTTLED
    return out


EMAIL_KINDS = ("recap", "reminder", "summary", "test-recap", "test-reminder", "test")
EMAIL_STATUSES = ("sent", "failed", "throttled")


def local_time(sent_at):
    """'HH:MM' in the league's time zone, from email_log.sent_at (UTC)."""
    when = datetime.fromisoformat(sent_at) + timedelta(
        hours=float(os.environ.get("LEAGUE_UTC_OFFSET", "-6")))
    return when.strftime("%H:%M")


@app.get("/emails", response_class=HTMLResponse, dependencies=CLUB)
def emails_page(request: Request, day: str | None = None, status: str = "", kind: str = ""):
    """📬 Emails (admins): every email this organization's accounts got (or didn't) on one
    league day, with how it went; filtered by status and kind."""
    day = parse_date(day or "") or league_today().isoformat()
    status = status if status in EMAIL_STATUSES else ""
    kind = kind if kind in EMAIL_KINDS else ""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT e.*, u.username, u.display_name FROM email_log e "
            "LEFT JOIN users u ON u.id = e.user_id WHERE e.organization_id = ? AND e.day = ? "
            "AND (? = '' OR e.status = ?) AND (? = '' OR e.kind = ?) ORDER BY e.id DESC",
            (org_id(), day, status, status, kind, kind)).fetchall()
        counts = dict(conn.execute(
            "SELECT status, COUNT(*) FROM email_log WHERE organization_id = ? AND day = ? "
            "GROUP BY status", (org_id(), day)).fetchall())
    shown = date.fromisoformat(day)
    return templates.TemplateResponse(request, "emails.html", {
        "rows": [{**r, "time": local_time(r["sent_at"])} for r in rows], "day": day,
        "status": status, "kind": kind, "counts": counts,
        "prev_day": (shown - timedelta(days=1)).isoformat(),
        "next_day": (shown + timedelta(days=1)).isoformat()})


@app.post("/tasks/send-emails")
def send_emails(request: Request):
    """Called every hour, all day (from 00:00 Mexico), by GitHub Actions
    (.github/workflows/daily-emails.yml): today's game-day reminders first, then the recaps
    of the last days' jornadas, as many as Azure's hourly limit allows (send_due); the
    next hours carry on until all are sent. The header X-Task-Token must
    match the app setting TASKS_TOKEN; otherwise it doesn't exist."""
    require_task_token(request)
    if not mailer.enabled():
        return {"enabled": False, "sent": 0, "failed": 0}
    return {"enabled": True, **send_due(request, ("reminder", "summary", "recap"))}


@app.post("/tasks/send-recaps")
def send_recaps(request: Request):
    """Only the recaps (send_due); the hourly job uses /tasks/send-emails."""
    require_task_token(request)
    if not mailer.enabled():
        return {"enabled": False, "sent": 0, "failed": 0}
    return {"enabled": True, **send_due(request, ("recap",))}


def org_rates(conn):
    """Everyone's record in this organization (stats.player_rates of its played sets)."""
    return stats.player_rates([s for s in set_rows(conn) if is_played(s)])


RATES = ContextVar("rates", default=None)  # this request's {organization id: records}


def chance_of(m):
    """The % chance that pair A wins this set while it's pending (None once played), for
    every place that shows a set. Each organization's records (org_rates) are worked
    out once per request. A set that already carries a "chance" (built inside another
    organization, e.g. the home page's next sets) keeps it."""
    if is_played(m):
        return None
    if "chance" in m.keys():
        return m["chance"]
    cache = RATES.get()
    if cache is None:
        cache = {}
        RATES.set(cache)
    if org_id() not in cache:
        with db.connect() as conn:
            cache[org_id()] = org_rates(conn)
    return round(100 * stats.win_probability(cache[org_id()], (m["a1_id"], m["a2_id"]),
                                             (m["b1_id"], m["b2_id"])))


def plays(s, pid):
    return pid in (s["a1_id"], s["a2_id"], s["b1_id"], s["b2_id"])


# --- 📄 Jornada summary (PDF) ---------------------------------------------------------

SET_MEDAL_KEYS = {  # stats.set_highlights code: (name, how) text keys
    "renido": ("set_medal_renido", "set_medal_renido_how"),
    "parejo": ("set_medal_parejo", "set_medal_parejo_how"),
    "aplastante": ("set_medal_aplastante", "set_medal_aplastante_how"),
    "sorpresa": ("set_medal_sorpresa", "set_medal_sorpresa_how"),
    "cantado": ("set_medal_cantado", "set_medal_cantado_how"),
}


def last_played(results):
    """The latest matchday of these with a played set, or None."""
    return next((md for md in reversed(results)
                 if any(is_played(s) for s in md.get("sets", []))), None)


def by_court(sets, rates):
    """[(court, its sets with "chance": % pair A wins, from these records)]."""
    courts = {}
    for s in sorted(sets, key=lambda s: (s["court"], s["id"])):
        chance = round(100 * stats.win_probability(rates, (s["a1_id"], s["a2_id"]),
                                                   (s["b1_id"], s["b2_id"])))
        courts.setdefault(s["court"], []).append({**s, "chance": chance})
    return list(courts.items())


def jornada_summary(conn, matchday_id, lang):
    """What the 📄 jornada summary (report.build) shows, inside the organization: the
    ranking after the jornada (points, that day's, places moved, medals in the
    tournament), its sets by court with the chance each pair had before the jornada, the
    set medals (stats.set_highlights), everyone's points jornada by jornada, and the next
    jornada's sets with their chances now, if it has any."""
    _ = translator(lang)
    matchday = get_or_404(conn, "matchdays", matchday_id)
    tournament = get_tournament(conn, matchday["tournament_id"])
    results, standings = load_results(conn, tournament["id"])
    md = next(r for r in results if r["id"] == matchday_id)
    n, round_mode = md["number"], tournament["rule_code"] in ROUND_MODES
    label_key = "round_n" if round_mode else "matchday_n"
    after, before = ranking_upto(standings, n), ranking_upto(standings, n - 1)
    if tournament["rule_code"] == LADDER:  # the ladder, not the points, gives positions
        after = {r["id"]: r["position"] for r in standings}
        before = {}
    won = tournament_medals(conn, tournament["id"], standings, lang)
    names = {m["code"]: m["name"] for m in medal_types(conn, lang)}
    ranking = sorted((
        {"id": r["id"], "name": r["name"], "position": after[r["id"]],
         "points": sum(p for k, p in r["by_matchday"].items() if k <= n),
         "today": r["by_matchday"].get(n),
         "moved": before[r["id"]] - after[r["id"]] if r["id"] in before else None,
         "medals": [m["code"] for m in won.get(r["id"], [])]}
        for r in standings if r["id"] in after), key=lambda r: (r["position"], r["name"].lower()))
    shown = {code for r in ranking for code in r["medals"]}
    # Each pair's chance as it was before this jornada: the records of the earlier sets.
    earlier = [s for s in set_rows(conn) if is_played(s) and (
        s["played_on"] < matchday["played_on"]
        or (s["tournament_id"] == tournament["id"] and s["matchday"] < n))]
    rates_before = stats.player_rates(earlier)
    sets = set_rows(conn, matchday_id=matchday_id)
    highlights = []
    for hl in stats.set_highlights([s for s in sets if is_played(s)], rates_before):
        s, name, how = hl["set"], *SET_MEDAL_KEYS[hl["code"]]
        a, b = s["team_a_games"], s["team_b_games"]
        highlights.append({**hl, "name": str(_(name)), "how": str(_(
            how, n=hl["chance"], games=a + b, gap=abs(a - b)))})
    numbers = [d["number"] for d in results if d["number"] <= n]
    ranks = {k: ranking_upto(standings, k) for k in numbers}
    evolution = []
    for r in ranking:
        days = next(row for row in standings if row["id"] == r["id"])["by_matchday"]
        total, values = 0, [0]  # from 0 at the start: a line even after one jornada
        for k in numbers:
            total += days.get(k, 0)
            values.append(total)
        evolution.append({"name": r["name"], "position": r["position"], "values": values,
                          # the position after each jornada (None before their first)
                          "positions": [ranks[k].get(r["id"]) for k in numbers]})
    upcoming = next((d for d in results if d["number"] == n + 1), None)
    upcoming_sets = set_rows(conn, matchday_id=upcoming["id"]) if upcoming else []
    org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id(),)).fetchone()
    short = lambda k: str(_("round_short" if round_mode else "matchday_short", n=k))  # noqa: E731
    return {
        "org": org["name"], "org_slug": org["slug"], "tournament": tournament,
        "matchday": md, "label": str(_(label_key, n=n)), "short": short(n),
        "signed": tournament["rule_code"] == "manual",
        "ranking": ranking,
        "legend": [(code, names[code]) for code in names if code in shown],
        "highlights": highlights,
        "courts": by_court(sets, rates_before),
        "evolution": {"numbers": numbers, "players": evolution,
                      "labels": [str(_("pdf_start"))] + [short(k) for k in numbers]},
        "next": upcoming_sets and {
            "label": str(_(label_key, n=n + 1)), "played_on": upcoming["played_on"],
            "courts": by_court(upcoming_sets, org_rates(conn))},
    }


def summary_file_name(data):
    """e.g. liga-de-otono-j3.pdf"""
    return f"{orgs.slugify(data['tournament']['name'])}-{orgs.slugify(data['short'])}.pdf"


def summary_pdf(data, lang):
    return Response(report.build(data, translator(lang)), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{summary_file_name(data)}"'})


@app.get("/matchdays/{matchday_id}/summary.pdf")
def jornada_summary_pdf(request: Request, matchday_id: int):
    """📄 The jornada summary as a PDF, for whoever can see the jornada (to keep or share)."""
    lang = get_lang(request)
    with db.connect() as conn:
        data = jornada_summary(conn, matchday_id, lang)
    return summary_pdf(data, lang)


# Before /r/{org}/{jornada}/{player}/{token} (the recap), which would take "summary".
@app.get("/r/{org_id}/{matchday_id}/summary/{token}")
def shared_summary_pdf(request: Request, org_id: int, matchday_id: int, token: str):
    """The summary PDF's public link, as sent on WhatsApp: it opens without entering the
    organization (the token proves the link came from the app)."""
    lang = get_lang(request)
    with db.connect() as conn:
        org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
        if org is None or not hmac.compare_digest(token, auth.summary_token(org, matchday_id)):
            raise HTTPException(404, "Not found")
        data = in_org(org_id, lambda: jornada_summary(conn, matchday_id, lang))
    return summary_pdf(data, lang)


def summary_whatsapp(request, conn, md, tournament):
    """The 📲 WhatsApp message of a jornada summary: its title and the PDF's public link
    (phones that can share files send the PDF itself, with this text)."""
    _ = translator(get_lang(request))
    org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id(),)).fetchone()
    url = f"{site_base(request)}/r/{org['id']}/{md['id']}/summary/{auth.summary_token(org, md['id'])}"
    label = _("round_n" if tournament["rule_code"] in ROUND_MODES else "matchday_n", n=md["number"])
    text = str(_("pdf_whatsapp_text", label=label, tournament=tournament["name"]))
    return {"pdf_text": text, "pdf_url": url,
            "pdf_whatsapp": "https://wa.me/?text=" + quote(f"{text}\n{url}", safe="")}


SUMMARY_AUDIENCE = """
    FROM matchdays d
    JOIN tournaments t ON t.id = d.tournament_id
    JOIN players p ON p.organization_id = t.organization_id
    JOIN users u ON u.id = p.user_id
    WHERE u.email IS NOT NULL AND u.email_recaps = 1
      AND (p.id IN (SELECT player_id FROM tournament_players WHERE tournament_id = t.id)
           OR EXISTS (SELECT 1 FROM matches x JOIN matchdays y ON y.id = x.matchday_id
                      WHERE y.tournament_id = t.id AND p.id IN (x.a1, x.a2, x.b1, x.b2)))
"""  # who gets a jornada's summary: accounts with an email and a player in its tournament


def summaries_due(conn):
    """(matchday, player, account, organization) for every account still to get a jornada
    summary an admin asked to send in the last 3 days (SUMMARY_AUDIENCE)."""
    return conn.execute(
        "SELECT DISTINCT d.id AS matchday_id, p.id AS player_id, u.id AS user_id, "
        "t.organization_id " + SUMMARY_AUDIENCE.replace(
            "FROM matchdays d", "FROM summary_requests r JOIN matchdays d ON d.id = r.matchday_id")
        + " AND r.requested_at >= datetime('now', '-3 days') AND NOT EXISTS (SELECT 1 "
        "FROM sent_emails s WHERE s.kind = 'summary' AND s.user_id = u.id "
        "AND s.matchday_id = d.id) ORDER BY r.requested_at, u.id").fetchall()


def summary_card(request, conn, md, queued=False):
    """The 📄 card's context for a matchday with played sets (None: no card): its
    WhatsApp message and, for admins, who would get it by email and how many did."""
    if md is None:
        return {"pdf_md": None}
    tournament = conn.execute("SELECT t.*, r.code AS rule_code FROM matchdays d "
                              "JOIN tournaments t ON t.id = d.tournament_id "
                              "JOIN rule_types r ON r.id = t.rule_type_id WHERE d.id = ?",
                              (md["id"],)).fetchone()
    out = {"pdf_md": md, "pdf_queued": queued, **summary_whatsapp(request, conn, md, tournament)}
    if auth.is_editor(request):
        out["pdf_to"] = conn.execute("SELECT COUNT(DISTINCT u.id) " + SUMMARY_AUDIENCE
                                     + " AND d.id = ?", (md["id"],)).fetchone()[0]
        out["pdf_sent"] = conn.execute(
            "SELECT COUNT(*) FROM sent_emails WHERE kind = 'summary' AND matchday_id = ?",
            (md["id"],)).fetchone()[0]
        out["pdf_asked"] = conn.execute("SELECT requested_at FROM summary_requests "
                                        "WHERE matchday_id = ?", (md["id"],)).fetchone()
    return out


def summary_email(request, org, data, pdf, user):
    """(subject, text, HTML, attachments) of the jornada summary email: a few lines and
    the PDF attached. In Spanish, like the other emails."""
    _ = translator("es")
    t = data["tournament"]
    link = f"{site_base(request)}/{org['slug']}/tournaments/{t['id']}"
    unsubscribe = unsubscribe_url(request, user, "recaps")
    subject = str(_("summary_email_subject", label=data["label"], tournament=t["name"]))
    leader = data["ranking"][0] if data["ranking"] else None
    lines = [str(_("summary_email_intro", label=data["label"], tournament=t["name"]))]
    if leader:
        lines.append(str(_("summary_email_leader", name=leader["name"], points=leader["points"])))
    lines += [f"{medals.SET_ICONS[h['code']]} {h['name']}: {h['how']}" for h in data["highlights"]]
    text = "\n".join(lines) + f"\n\n{link}\n\n{_('recap_email_unsubscribe')}: {unsubscribe}"
    html = templates.env.get_template("email_summary.html").render(
        _=_, data=data, lines=lines, link=link, unsubscribe=unsubscribe, org_name=org["name"],
        name=user["display_name"] or user["username"])
    return subject, text, html, [(summary_file_name(data), "application/pdf", pdf)]


@app.post("/matchdays/{matchday_id}/summary/send", dependencies=EDIT)
def send_jornada_summary(request: Request, matchday_id: int, background: BackgroundTasks):
    """📧 An admin sends the jornada summary to the tournament's players: it's queued
    (summary_requests) and a first batch goes right after this answer; the hourly email
    job sends the rest within Azure's limits (send_due)."""
    with db.connect() as conn:
        get_or_404(conn, "matchdays", matchday_id)
        if not mailer.enabled():
            return redirect(f"/matchdays/{matchday_id}?error=err_mail_off#summary")
        user = auth.current_user(request)
        conn.execute(
            "INSERT INTO summary_requests (matchday_id, requested_by) VALUES (?, ?) "
            "ON CONFLICT (matchday_id) DO UPDATE SET requested_at = datetime('now'), "
            "requested_by = excluded.requested_by", (matchday_id, user and user["id"]))
    background.add_task(send_due, request, ("summary",))
    return redirect(f"/matchdays/{matchday_id}?summary=queued#summary")


def reminder_data(conn, matchday_id, player_id):
    """What a game-day reminder says (run inside the organization): the player's court,
    position and points before the jornada, their tournament so far, and each of their
    sets that day with partner, rivals, the chance of winning (stats.win_probability on
    every played set of the organization) and their record against each rival. None if
    they have no sets that day."""
    matchday = get_or_404(conn, "matchdays", matchday_id)
    sets = sorted(set_rows(conn, matchday_id=matchday_id, player_id=player_id),
                  key=lambda s: (s["court"], s["id"]))
    if not sets:
        return None
    tournament = get_tournament(conn, matchday["tournament_id"])
    _, standings = load_results(conn, tournament["id"])
    me = next((r for r in standings if r["id"] == player_id), None)
    before = matchday["number"] - 1
    history = [s for s in reversed(set_rows(conn)) if is_played(s)]  # oldest first
    mine = [s for s in history if plays(s, player_id)]
    in_tournament = [s for s in mine if s["tournament_id"] == tournament["id"]]
    rates = stats.player_rates(history)
    rows = []
    for s in sets:
        partner_id, partner_name = stats.partner(s, player_id)
        rivals = stats.opponents(s, player_id)
        chance = stats.win_probability(rates, (player_id, partner_id), [i for i, _ in rivals])
        rows.append({"set": s, "partner": partner_name, "rivals": rivals,
                     "chance": round(100 * chance), "played": is_played(s),
                     "h2h": [{"name": name, **stats.head_to_head(mine, player_id, i)["against"]}
                             for i, name in rivals]})
    return {"tournament": tournament, "matchday": matchday,
            "player": get_or_404(conn, "players", player_id), "court": sets[0]["court"],
            "position": ranking_upto(standings, before).get(player_id),
            "points": sum(p for n, p in me["by_matchday"].items() if n <= before) if me else 0,
            "totals": stats.totals(in_tournament, player_id),
            "streak": stats.streaks(in_tournament, player_id), "sets": rows}


def reminder_email(request, org, data, user):
    """(subject, plain text, HTML) of a game-day reminder, in Spanish."""
    _ = translator("es")
    md, t = data["matchday"], data["tournament"]
    subject = str(_("reminder_subject", tournament=t["name"], n=md["number"], court=data["court"]))
    lines = [subject]
    if data["position"]:
        lines.append(str(_("reminder_position", n=data["position"], points=data["points"])))
    for i, row in enumerate(data["sets"], 1):
        rivals = " / ".join(name for _, name in row["rivals"])
        lines.append(f"{i}. {_('reminder_with', name=row['partner'])} vs {rivals}: "
                     f"{_('reminder_chance', n=row['chance'])}")
    link = f"{site_base(request)}/{org['slug']}/matchdays/{md['id']}"
    unsubscribe = unsubscribe_url(request, user, "reminders")
    text = "\n".join(lines) + f"\n\n{link}\n\n{_('recap_email_unsubscribe')}: {unsubscribe}"
    html = templates.env.get_template("email_reminder.html").render(
        _=_, d=data, org_name=org["name"], link=link, unsubscribe=unsubscribe)
    return subject, text, html


def reminders_due(conn):
    """(matchday, player, account, organization) for every account that plays a jornada
    today: an email and a player, reminders on, a set of that day still to play, and not
    reminded yet."""
    return conn.execute(
        """
        SELECT DISTINCT d.id AS matchday_id, p.id AS player_id, u.id AS user_id,
               t.organization_id
        FROM matchdays d
        JOIN tournaments t ON t.id = d.tournament_id
        JOIN matches m ON m.matchday_id = d.id AND m.team_a_games IS NULL
        JOIN players p ON p.id IN (m.a1, m.a2, m.b1, m.b2)
        JOIN users u ON u.id = p.user_id
        WHERE d.played_on = ? AND u.email IS NOT NULL AND u.email_reminders = 1
          AND NOT EXISTS (SELECT 1 FROM sent_emails s WHERE s.kind = 'reminder'
                          AND s.user_id = u.id AND s.matchday_id = d.id)
        ORDER BY d.id, u.id
        """, (league_today().isoformat(),)).fetchall()


@app.post("/tasks/send-reminders")
def send_reminders(request: Request):
    """Only today's game-day reminders (send_due); the hourly job uses /tasks/send-emails."""
    require_task_token(request)
    if not mailer.enabled():
        return {"enabled": False, "sent": 0, "failed": 0}
    return {"enabled": True, **send_due(request, ("reminder",))}


def next_jornada(conn, player_id, tournament_id=None):
    """The player's next jornada with a set still to play (the soonest), or else their
    latest one, in this organization (or that tournament): its id, or None."""
    where = ("t.organization_id = ? AND ? IN (m.a1, m.a2, m.b1, m.b2)"
             + (" AND d.tournament_id = ?" if tournament_id else ""))
    params = (org_id(), player_id) + ((tournament_id,) if tournament_id else ())
    base = ("SELECT d.id FROM matchdays d JOIN tournaments t ON t.id = d.tournament_id "
            f"JOIN matches m ON m.matchday_id = d.id WHERE {where}")
    row = (conn.execute(base + " AND m.team_a_games IS NULL ORDER BY d.played_on, d.number "
                        "LIMIT 1", params).fetchone()
           or conn.execute(base + " ORDER BY d.played_on DESC, d.number DESC LIMIT 1",
                           params).fetchone())
    return row["id"] if row else None


def send_test_reminder(request, conn, user, player_id, tournament_id=None):
    """Email `user`, now, the game-day reminder of next_jornada(): "sent", or the error."""
    if not user["email"]:
        return "err_no_player_email"
    if not mailer.enabled():
        return "err_mail_off"
    jornada = next_jornada(conn, player_id, tournament_id)
    data = jornada and reminder_data(conn, jornada, player_id)
    if not data:
        return "err_no_jornada_yet"
    ok = deliver(conn, user, "test-reminder",
                 *reminder_email(request, auth.current_org(request), data, user),
                 org=org_id(), matchday_id=jornada)
    return "sent" if ok else mail_error()


@app.post("/users/{user_id}/test-reminder", dependencies=CLUB)
def account_test_reminder(request: Request, user_id: int):
    """⏰ Probar recordatorio on 🔑 Cuentas: email this account, now, the game-day reminder
    of its player's next jornada (whatever its date), to try it. Not recorded, so the
    real reminder still goes on the day."""
    with db.connect() as conn:
        user = managed_user(conn, request, user_id)
        player = linked_player(conn, user_id)
        result = (send_test_reminder(request, conn, user, player["id"]) if player
                  else "err_no_jornada_yet")
    return redirect("/users?mail=sent" if result == "sent" else f"/users?error={result}")


@app.post("/tournaments/{tournament_id}/players/{player_id}/reminder", dependencies=EDIT)
def email_player_reminder(request: Request, tournament_id: int, player_id: int):
    """⏰ in the tournament's player list (admins): email the player, now, the game-day
    reminder of their next jornada with sets to play (or, without one, their latest), to
    try it. Not recorded."""
    back = f"/tournaments/{tournament_id}"
    with db.connect() as conn:
        get_tournament(conn, tournament_id)
        get_or_404(conn, "players", player_id)
        user = conn.execute("SELECT u.* FROM users u JOIN players p ON p.user_id = u.id "
                            "WHERE p.id = ?", (player_id,)).fetchone()
        result = (send_test_reminder(request, conn, user, player_id, tournament_id) if user
                  else "err_no_player_email")
    return redirect(f"{back}?mail=sent#players" if result == "sent"
                    else f"{back}?error={result}#players")


@app.get("/unsubscribe/{user_id}/{token}", response_class=HTMLResponse)
def unsubscribe(request: Request, user_id: int, token: str, kind: str = "recaps"):
    """An email's unsubscribe link: no more emails of that kind ("recaps" or
    "reminders") for that account. /me turns them back on."""
    with db.connect() as conn:
        user = users.get(conn, user_id)
        if user is None or not hmac.compare_digest(token, auth.unsubscribe_token(user)):
            raise HTTPException(404, "Not found")
        column = "email_reminders" if kind == "reminders" else "email_recaps"
        conn.execute(f"UPDATE users SET {column} = 0 WHERE id = ?", (user_id,))
    return templates.TemplateResponse(request, "unsubscribed.html", {})


@app.post("/tournaments/{tournament_id}/players/{player_id}/email", dependencies=EDIT)
def email_player_recap(request: Request, tournament_id: int, player_id: int):
    """📧 in the tournament's player list (admins): email the player, now, the recap of
    their latest jornada in this tournament, to try the email. It isn't recorded, so the
    morning email still goes."""
    back = f"/tournaments/{tournament_id}"
    with db.connect() as conn:
        get_tournament(conn, tournament_id)
        get_or_404(conn, "players", player_id)
        user = conn.execute("SELECT u.* FROM users u JOIN players p ON p.user_id = u.id "
                            "WHERE p.id = ?", (player_id,)).fetchone()
        if user is None or not user["email"]:
            return redirect(f"{back}?error=err_no_player_email#players")
        if not mailer.enabled():
            return redirect(f"{back}?error=err_mail_off#players")
        latest = conn.execute(
            "SELECT d.id FROM matchdays d JOIN matches m ON m.matchday_id = d.id "
            "WHERE d.tournament_id = ? AND ? IN (m.a1, m.a2, m.b1, m.b2) "
            "AND m.team_a_games IS NOT NULL ORDER BY d.number DESC LIMIT 1",
            (tournament_id, player_id)).fetchone()
        recap = latest and jornada_recap(conn, latest["id"], player_id, "es")
        if not recap:
            return redirect(f"{back}?error=err_no_recap_yet#players")
        ok = deliver(conn, user, "test-recap",
                     *recap_email(request, auth.current_org(request), recap, user,
                                  email_extras(conn, recap)),
                     org=org_id(), matchday_id=latest["id"])
    return redirect(f"{back}?mail=sent#players" if ok else f"{back}?error={mail_error()}#players")


@app.post("/orgs/test-email", dependencies=SUPER)
def test_email(request: Request):
    """📧 Probar email (super admins): send a test email to your own address, to check
    the Azure setup (docs/processes/EMAIL.md)."""
    user = auth.current_user(request)
    if not user["email"]:
        return redirect("/orgs?error=err_no_email")
    if not mailer.enabled():
        return redirect("/orgs?error=err_mail_off")
    _ = translator("es")
    org = auth.current_org(request)
    with db.connect() as conn:
        ok = deliver(conn, user, "test", str(_("test_email_subject")), str(_("test_email_body")),
                     f"<p>{_('test_email_body')}</p>", org=org["id"] if org else None)
    return redirect("/orgs?mail=sent" if ok else f"/orgs?error={mail_error()}")


@app.get("/matchdays/{matchday_id}/recap", response_class=HTMLResponse)
def recap_page(request: Request, matchday_id: int, player: str | None = None):
    """📲 Mi jornada: a player's jornada, ready to share on WhatsApp. Without `player`,
    the logged-in account's player (or a list to pick from)."""
    lang = get_lang(request)
    user = auth.current_user(request)
    with db.connect() as conn:
        matchday = get_or_404(conn, "matchdays", matchday_id)
        results, _ = load_results(conn, matchday["tournament_id"])
        md = next(r for r in results if r["id"] == matchday_id)
        people = md_players(md)
        mine = linked_player(conn, user["id"]) if user else None
        chosen = opt_int(player) or (mine["id"] if mine and mine["id"] in people else None)
        recap = jornada_recap(conn, matchday_id, chosen, lang) if chosen in people else None
    return templates.TemplateResponse(request, "recap.html", {
        "recap": recap, "people": people, "chosen": chosen, "matchday": md,
        "share": recap and recap_share(request, auth.current_org(request), recap),
        "shared": False})


@app.get("/r/{org_id}/{matchday_id}/{player_id}/{token}", response_class=HTMLResponse)
def shared_recap(request: Request, org_id: int, matchday_id: int, player_id: int, token: str):
    """A recap's public link, as shared on WhatsApp: it opens without entering the
    organization (the token proves the link came from the app)."""
    with db.connect() as conn:
        org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
        if org is None or not hmac.compare_digest(token, auth.recap_token(org, matchday_id,
                                                                          player_id)):
            raise HTTPException(404, "Not found")
        recap = in_org(org_id, lambda: jornada_recap(conn, matchday_id, player_id,
                                                     get_lang(request)))
    if recap is None:
        raise HTTPException(404, "Not found")
    return templates.TemplateResponse(request, "recap.html", {
        "recap": recap, "people": {}, "chosen": player_id, "matchday": recap["matchday"],
        "share": recap_share(request, org, recap), "shared": True, "org_name": org["name"]})


def medal_types(conn, lang):
    """The medal catalog in the page's language, in display order."""
    return [{"code": m["code"], "kind": m["kind"], "name": m[f"name_{lang}"],
             "how": m[f"how_{lang}"], "image": f"/static/medals/{m['code']}.svg"}
            for m in conn.execute("SELECT * FROM medal_types ORDER BY sort")]


def player_awards(conn, player_id, cache=None):
    """The player's medals: {code: {"count", "tier", "detail"}} (medals.py)."""
    sets = set_rows(conn, player_id=player_id)
    played = [s for s in reversed(sets) if is_played(s)]
    return medals.awards(played, player_id, player_tournaments(conn, player_id, sets, cache))


def account_usernames(conn):
    """{player id: username} for this organization's players that have an account; the
    standings show them as "Display name (username)"."""
    return dict(conn.execute(
        "SELECT p.id, u.username FROM players p JOIN users u ON u.id = p.user_id "
        "WHERE p.organization_id = ?", (org_id(),)).fetchall())


def tournament_medals(conn, tournament_id, standings, lang):
    """Each player's medals won in this tournament only (its sets and matchdays), for
    the standings table: {player id: [{medal..., "count", "tier", "value"}]}."""
    catalog, cache, out = medal_types(conn, lang), {}, {}
    for row in standings:
        sets = set_rows(conn, tournament_id=tournament_id, player_id=row["id"])
        played = [s for s in reversed(sets) if is_played(s)]
        won = medals.awards(played, row["id"], player_tournaments(conn, row["id"], sets, cache))
        out[row["id"]] = [{**m, **won[m["code"]]} for m in catalog if m["code"] in won]
    return out


@app.get("/players/{player_id}/medals", response_class=HTMLResponse)
def player_medals_page(request: Request, player_id: int):
    """The player's medals: the ones won first, then the ones still to win, greyed."""
    with db.connect() as conn:
        player = get_or_404(conn, "players", player_id)
        catalog = medal_types(conn, get_lang(request))
        won = player_awards(conn, player_id)
    return templates.TemplateResponse(request, "player_medals.html", {
        "player": player, "won": [dict(m, **won[m["code"]]) for m in catalog if m["code"] in won],
        "missing": [m for m in catalog if m["code"] not in won]})


@app.get("/medals", response_class=HTMLResponse)
def medals_page(request: Request):
    """Every medal, how to win it, and who in this organization has it."""
    with db.connect() as conn:
        catalog = medal_types(conn, get_lang(request))
        cache, holders = {}, {}
        for p in all_players(conn):
            for code in player_awards(conn, p["id"], cache):
                holders.setdefault(code, []).append(p)
    return templates.TemplateResponse(request, "medals.html", {
        "catalog": catalog, "holders": holders})


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
        "JOIN rule_types r ON r.id = t.rule_type_id WHERE r.code = ? AND t.organization_id = ?",
        (MANUAL, org_id()))
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
    if not set(players) <= {p["id"] for p in all_players(conn)}:
        return _("err_four_players"), None
    if not conn.execute(f"SELECT 1 FROM matchdays WHERE id = ? AND {ORG_SCOPE['matchdays']}",
                        (form["matchday_id"], org_id())).fetchone():
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
def edit_match_page(request: Request, match_id: int, error: str | None = None):
    """Every set is changed here. Editors get the whole set, and so do the players of a
    Manual tournament for their own sets; other players, just the games of their sets."""
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        tournament = tournament_of(conn, match["matchday_id"])
        if not auth.can_score_set(request, tournament, match):
            raise LoginRequired(here(request))
        if tournament["rule_code"] == LADDER:  # a match to 2 of 3 sets
            row = next(s for s in set_rows(conn, matchday_id=match["matchday_id"])
                       if s["id"] == match_id)
            sets = formats.parse_sets(row["sets_detail"]) + [(None, None)] * 3
            return templates.TemplateResponse(request, "match_sets.html", {
                "m": row, "tournament": tournament, "sets": sets[:3], "error": error})
        if auth.is_editor(request) or match["matchday_id"] in {
                d["id"] for d in set_matchdays(request, conn)}:
            return render_match_form(request, conn, {c: match[c] for c in MATCH_COLUMNS},
                                     match_id=match_id,
                                     error=translator(get_lang(request))(error) if error else None)
        row = next(s for s in set_rows(conn, matchday_id=match["matchday_id"])
                   if s["id"] == match_id)
        return templates.TemplateResponse(request, "match_score.html", {
            "m": row, "tournament": tournament, "error": error})


@app.post("/matches/{match_id}")
def update_match(request: Request, match_id: int,
                 form: dict = Depends(match_form_data)):
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        require_set_maker(request, conn, match["matchday_id"], form["matchday_id"])
        auth.require_set_scorer(request, tournament_of(conn, match["matchday_id"]), match)
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
               team_b_games: str = Form(""), back: str = Form("")):
    """Enter (or clear) the games of a set, from its Edit page or the boxes of its card
    (jornada page; home page, back=home): editors and the set's players."""
    home = back == "home"
    with db.connect() as conn:
        match = get_or_404(conn, "matches", match_id)
        auth.require_set_scorer(request, tournament_of(conn, match["matchday_id"]), match)
        back = f"/matchdays/{match['matchday_id']}"
        edit = f"/matches/{match_id}/edit"
        try:
            a, b = opt_games(team_a_games), opt_games(team_b_games)
            if (a is None) != (b is None):
                return redirect(f"{edit}?error=err_both_games")
            winner = check_set(a, b) if a is not None else None
        except (ValueError, ScoreError):
            return redirect(f"{edit}?error=err_set")
        conn.execute("UPDATE matches SET team_a_games = ?, team_b_games = ?, winner = ? "
                     "WHERE id = ?", (a, b, winner, match_id))
    return redirect("/" if home else f"{back}#set-{match_id}")
