import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db, orgs, users
from app.i18n import LANGS, TEXT
from app.main import app
from app.scoring import (ScoreError, check_set, court_moves, court_rotation, court_table,
                         next_courts, tournament_results)

# The schema before sql/predeployment/0001_users.sql: db.SCHEMA is the starting point.
BEFORE_ACCOUNTS = db.SCHEMA
NAMES = ["Ana", "Bea", "Carlos", "Diego", "Elena", "Fer", "Gabi", "Hugo"]
APP_DIR = Path(__file__).parent.parent / "app"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client using the English UI (most assertions below check English texts),
    logged in as the admin of organization 1, "Club" (user "admin", password "secreto")."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr("app.main.time.sleep", lambda s: None)  # skip the wrong-password delay
    with TestClient(app) as c:
        with db.connect() as conn:
            orgs.create_org(conn, "Club", "admin", "secreto")
        c.cookies.set("lang", "en")
        assert c.post("/login", data={"username": "admin", "password": "secreto"}).status_code == 200
        yield c


def add_matchday(tournament_id, played_on):
    """A matchday with no courts yet (the app itself only saves one with its courts)."""
    with db.connect() as conn:
        number = conn.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM matchdays "
                              "WHERE tournament_id = ?", (tournament_id,)).fetchone()[0]
        conn.execute("INSERT INTO matchdays (tournament_id, number, played_on) VALUES (?, ?, ?)",
                     (tournament_id, number, played_on))


@pytest.fixture
def league(client):
    """Players 1-8, tournament 1 and its matchday 1 (no courts yet)."""
    for name in NAMES:
        client.post("/players", data={"name": name})
    client.post("/tournaments", data={"name": "Liga Amigos", "held_on": "2026-10-23"})
    add_matchday(1, "2026-10-23")
    return client


def set_form(players, a, b, court=1, matchday_id=1):
    return {"matchday_id": matchday_id, "court": court,
            "a1": players[0], "a2": players[1], "b1": players[2], "b2": players[3],
            "team_a_games": a, "team_b_games": b}


# The three sets of one court, each player partnering the other three once:
# Ana +3 (2 sets won), Bea +1 (2), Carlos +5 (2), Diego -9 (0).
ROTATION = [((1, 2, 3, 4), 6, 4), ((1, 3, 2, 4), 6, 2), ((1, 4, 2, 3), 3, 6)]


def row(players, a, b, court=1):
    r = {"court": court, "team_a_games": a, "team_b_games": b, "winner": check_set(a, b)}
    for key, pid in zip(("a1", "a2", "b1", "b2"), players):
        r[key + "_id"], r[key] = pid, NAMES[pid - 1]
    return r


def standing_points(html, name):
    """A player's points in a standings table (the name cell may also hold medals)."""
    return int(re.search(rf">{name}</a>(?:(?!</td>).)*</td>\s*<td class=\"pts\">(-?\d+)<",
                         html, re.S).group(1))


@pytest.mark.parametrize("a,b,winner", [(6, 4, "A"), (7, 6, "A"), (4, 6, "B"),
                                        (3, 1, "A"), (2, 5, "B"), (9, 8, "A"),
                                        (4, 4, None), (0, 0, None)])
def test_check_set_accepts_any_score(a, b, winner):
    assert check_set(a, b) == winner


@pytest.mark.parametrize("a,b", [(-1, 6), (6, -2)])
def test_check_set_rejects_negative_games(a, b):
    with pytest.raises(ScoreError):
        check_set(a, b)


def test_places_per_court_at_the_end_of_the_matchday():
    # Sets won 2, 2, 2, 0: the three ties go by games difference (Carlos +5, Ana +3,
    # Bea +1). Places 9 / 6 / 4 / 3, plus 1 per set won.
    rows = court_table([row(*s) for s in ROTATION], position={}, places=True)
    assert [(r["name"], r["diff"], r["sets_won"], r["place"], r["points"]) for r in rows] == [
        ("Carlos", 5, 2, 1, 9 + 2), ("Ana", 3, 2, 2, 6 + 2), ("Bea", 1, 2, 3, 4 + 2),
        ("Diego", -9, 0, 4, 3)]


def test_unfinished_court_only_counts_sets_won():
    sets = [row(*s) for s in ROTATION[:2]] + [
        {**row(*ROTATION[2]), "team_a_games": None, "team_b_games": None, "winner": None}]
    rows = court_table(sets, position={}, places=True)
    assert all(r["place"] is None for r in rows)
    assert {r["name"]: r["points"] for r in rows} == {"Ana": 2, "Bea": 1, "Carlos": 1, "Diego": 0}


def test_tied_set_gives_no_one_a_set():
    rows = court_table([row((1, 2, 3, 4), 4, 4)], position={}, places=True)
    assert all(r["sets_won"] == 0 and r["diff"] == 0 for r in rows)
    assert sorted(r["points"] for r in rows) == [3, 4, 6, 9]


def test_short_and_tied_sets_can_be_saved(league):
    assert league.post("/matches", data=set_form((1, 2, 3, 4), 3, 1)).status_code == 200
    r = league.post("/matches", data=set_form((1, 3, 2, 4), 4, 4))
    assert r.status_code == 200 and "4-4" in r.text


def test_ties_go_by_difference_then_league_position():
    sets = [row((1, 2, 3, 4), 6, 4), row((3, 4, 1, 2), 6, 4)]  # everyone 1 won, diff 0
    rows = court_table(sets, position={4: 1, 3: 2, 1: 3, 2: 4}, places=True)
    assert [(r["name"], r["points"]) for r in rows] == [
        ("Diego", 9 + 1), ("Carlos", 6 + 1), ("Ana", 4 + 1), ("Bea", 3 + 1)]


def test_first_matchday_ties_are_drawn():
    sets = [row((1, 2, 3, 4), 6, 4), row((3, 4, 1, 2), 6, 4)]  # a complete tie, no ranking
    draws = {tuple(r["name"] for r in court_table(sets, {}, places=True, seed=f"1-{n}"))
             for n in range(20)}
    assert len(draws) > 1  # different courts / matchdays draw differently...
    same = [court_table(sets, {}, places=True, seed="7-1") for _ in range(3)]
    assert len({tuple(r["name"] for r in rows) for rows in same}) == 1  # ...but stay put


def test_absent_player_is_last_and_scores_zero_in_the_liga():
    rows = court_table([row(*s) for s in ROTATION], position={}, absent={3}, places=True)
    assert [(r["name"], r["points"]) for r in rows] == [
        ("Ana", 9 + 2), ("Bea", 6 + 2), ("Diego", 4), ("Carlos", 0)]


def test_games_scoring_adds_each_pairs_games():
    # Americano, Mexicano and Manual: Ana 6+6+3, Bea 6+2+6, Carlos 4+6+6, Diego 4+2+3.
    rows = court_table([row(*s) for s in ROTATION], position={})
    assert [(r["name"], r["points"]) for r in rows] == [
        ("Carlos", 16), ("Ana", 15), ("Bea", 14), ("Diego", 9)]


def test_tournament_results_add_up_matchdays():
    md1 = {"number": 1, "sets": [row(*s) for s in ROTATION]}
    md2 = {"number": 2, "sets": [row(*s) for s in ROTATION]}
    results, standings = tournament_results([md1, md2], places=True)
    assert [(r["position"], r["name"], r["points"]) for r in standings] == [
        (1, "Carlos", 22), (2, "Ana", 16), (3, "Bea", 12), (4, "Diego", 6)]
    assert standings[0]["by_matchday"] == {1: 11, 2: 11}
    assert standings[0]["played"] == 2
    assert list(results[0]["courts"]) == [1]


def test_equal_points_share_a_standings_position():
    # Games scoring: Ana & Bea beat Carlos & Diego 3-0 -> 3, 3, 0, 0.
    _, standings = tournament_results([{"number": 1, "sets": [row((1, 2, 3, 4), 3, 0)]}])
    assert [(r["position"], r["points"]) for r in standings] == [(1, 3), (1, 3), (3, 0), (3, 0)]


def test_league_position_orders_ties_on_the_next_matchday():
    # After matchday 1 Diego leads Carlos; on matchday 2 they tie on sets and difference,
    # so Diego, higher in the ranking, takes the better place.
    md1 = {"number": 1, "sets": [row((4, 1, 3, 2), 6, 0)]}
    md2 = {"number": 2, "sets": [row((1, 2, 3, 4), 6, 4), row((3, 4, 1, 2), 6, 4)]}
    results, _ = tournament_results([md1, md2], places=True)
    names = [r["name"] for r in results[1]["courts"][1]]
    assert names.index("Diego") < names.index("Carlos")


def test_court_moves():
    top = court_table([row(*s) for s in ROTATION], position={}, places=True)
    bottom = court_table([row(tuple(p + 4 for p in s[0]), s[1], s[2], court=2)
                          for s in ROTATION], position={}, places=True)
    moves = court_moves({1: top, 2: bottom}, count=1)
    assert moves[0] == {"court": 1, "up": [], "up_to": None, "down": ["Diego"], "down_to": 2}
    assert moves[1] == {"court": 2, "up": ["Gabi"], "up_to": 1, "down": [], "down_to": None}

    two = court_moves({1: top, 2: bottom}, count=2)
    assert two[0]["down"] == ["Bea", "Diego"] and two[1]["up"] == ["Gabi", "Elena"]


def test_full_matchday_flow(league):
    for players, a, b in ROTATION:
        r = league.post("/matches", data=set_form(players, a, b))
        assert r.status_code == 200
    page = league.get("/matchdays/1").text
    assert "Court 1" in page and 'aria-label="6-4"' in page and "+5" in page

    standings = league.get("/tournaments/1").text
    assert standing_points(standings, "Carlos") == 11
    assert standing_points(standings, "Diego") == 3

    home = league.get("/").text
    assert "Liga Amigos" in home and home.index("Carlos") < home.index("Diego")

    # Edit the third set so Ana & Diego win it 6-3 instead of losing 3-6: Ana wins all 3.
    league.post("/matches/3", data=set_form((1, 4, 2, 3), 6, 3))
    assert standing_points(league.get("/tournaments/1").text, "Ana") == 9 + 3

    r = league.post("/matches/3/delete")
    assert r.status_code == 200 and "2 of 3 sets recorded" in r.text

    profile = league.get("/players/1").text
    assert "Liga Amigos" in profile and "M1" in profile


def test_filter_sets(league):
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4))
    league.post("/matches", data=set_form((5, 6, 7, 8), 6, 4, court=2))
    assert league.get("/matches?player=1").text.count('class="match"') == 1
    assert league.get("/matches?player=&tournament=1").text.count('class="match"') == 2


@pytest.mark.parametrize("data,message", [
    (set_form((1, 1, 3, 4), 6, 4), "four different players"),
    (set_form((1, 2, 3, 4), 6, -1), "Games can't be negative"),
    (set_form((1, 2, 3, 4), 6, 4, matchday_id=99), "Pick a matchday"),
])
def test_rejects_bad_set(league, data, message):
    r = league.post("/matches", data=data)
    assert r.status_code == 400 and message in r.text


def test_player_can_play_on_two_courts_and_points_add_up(league):
    for players, a, b, court in [((1, 2, 3, 4), 6, 4, 1), ((1, 3, 2, 4), 6, 2, 1),
                                 ((1, 6, 7, 8), 6, 4, 2), ((1, 7, 6, 8), 6, 1, 2)]:
        assert league.post("/matches", data=set_form(players, a, b, court=court)).status_code == 200
    # Ana is 1st on both courts with 2 sets won each: (9 + 2) twice, in one matchday.
    standings = league.get("/tournaments/1").text
    assert standing_points(standings, "Ana") == 22
    profile = league.get("/players/1").text
    assert "1 matchday played" in profile


@pytest.mark.parametrize("held_on", ["", "not a date", "2026-02-30", "23/10/2026"])
def test_tournament_date_must_be_valid(client, held_on):
    r = client.post("/tournaments", data={"name": "Torneo X", "held_on": held_on})
    assert "Enter a valid date" in r.text and "Torneo X" not in r.text


@pytest.mark.parametrize("played_on", ["", "next friday", "2026-02-30"])
def test_matchday_date_must_be_valid(league, played_on):
    data = {"played_on": played_on, "court-1": ["1", "2", "3", "4"]}
    r = league.post("/tournaments/1/matchdays", data=data)
    assert r.status_code == 400 and "Enter a valid date" in r.text
    if played_on:
        r = league.get("/tournaments/1/matchdays/new", params={"played_on": played_on})
        assert "Enter a valid date" in r.text
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM matchdays").fetchone()[0] == 1


@pytest.mark.parametrize("sql", [
    "INSERT INTO tournaments (name, held_on) VALUES ('X', '2026-13-01')",
    "INSERT INTO matchdays (tournament_id, number, played_on) VALUES (1, 9, 'soon')",
])
def test_database_rejects_invalid_dates(league, sql):
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        with db.connect() as conn:
            conn.execute(sql)


def test_rules_page(client):
    r = client.get("/rules")
    assert r.status_code == 200
    assert "Reglamento Liga Amigos" in r.text and "<table>" in r.text
    for section in ("liga_amigos", "americano", "mexicano", "manual"):
        assert f'id="{section}"' in r.text
    assert "Reglamento Manual individual" in r.text


def test_missing_pages_return_404(league):
    for url in ["/tournaments/99", "/matchdays/99", "/players/99", "/matches/99/edit"]:
        assert league.get(url).status_code == 404


def test_spanish_is_the_default_language(league):
    league.cookies.delete("lang")
    home = league.get("/").text
    assert '<html lang="es">' in home and "Clasificación" in home and "Jornada 1" in home
    r = league.post("/matches", data=set_form((1, 1, 3, 4), 6, 4))
    assert "Elige cuatro jugadores diferentes." in r.text
    r = league.post("/tournaments", data={"name": "X", "held_on": "mañana"})
    assert "Ingresa una fecha válida." in r.text


def test_switch_language(league):
    league.cookies.delete("lang")
    r = league.get("/lang/en?next=/tournaments/1")
    assert r.status_code == 200 and str(r.url).endswith("/tournaments/1")
    assert "Matchdays" in r.text and '<html lang="en">' in r.text
    r = league.get("/lang/es?next=/matches%3Fplayer%3D1")
    assert str(r.url).endswith("/matches?player=1") and "Todos los torneos" in r.text


@pytest.mark.parametrize("next_url", ["https://evil.example", "//evil.example", "/\\evil.example"])
def test_language_switch_only_redirects_within_the_site(client, next_url):
    r = client.get("/lang/es", params={"next": next_url}, follow_redirects=False)
    assert r.headers["location"] == "/"


def test_knowledge_base_is_linked():
    """Every process page is in the index, and every skill is in CLAUDE.md (see the
    "Every PR documents itself" rule)."""
    root = Path(__file__).resolve().parent.parent
    index = (root / "docs/processes/README.md").read_text(encoding="utf-8")
    pages = [p.name for p in (root / "docs/processes").glob("*.md") if p.name != "README.md"]
    assert pages and all(f"({name})" in index for name in pages), pages
    guide = (root / "CLAUDE.md").read_text(encoding="utf-8")
    skills = [p.name for p in (root / ".claude/skills").iterdir() if p.is_dir()]
    assert skills and all(f"`{name}`" in guide for name in skills), skills
    for name in skills:
        assert (root / ".claude/skills" / name / "SKILL.md").exists(), name
    assert "Docs and memory" in (root / ".github/pull_request_template.md").read_text(
        encoding="utf-8")


def test_every_text_has_both_languages_and_every_key_exists():
    for key, entry in TEXT.items():
        assert set(entry) == set(LANGS), key
        assert all(isinstance(v, type(entry["es"])) for v in entry.values()), key
    sources = [p.read_text(encoding="utf-8") for p in (APP_DIR / "templates").glob("*.html")]
    sources.append((APP_DIR / "main.py").read_text(encoding="utf-8"))
    used = {k for s in sources for k in re.findall(r"""_\(\s*["'](\w+)["']""", s)}
    used |= set(re.findall(r"error=(err_\w+)", sources[-1]))
    assert used and not used - set(TEXT), used - set(TEXT)


def test_values_are_escaped_in_translated_texts(league):
    from app.i18n import translator
    assert str(translator("en")("position_n", n="<b>1</b>")) == "Position &lt;b&gt;1&lt;/b&gt;"
    league.post("/players", data={"name": "<b>Zed</b>"})
    league.post("/matches", data=set_form((9, 2, 3, 4), 6, 4))
    page = league.get("/matchdays/1").text
    assert "&lt;b&gt;Zed&lt;/b&gt;" in page and "<b>Zed</b>" not in page


def test_new_set_form_selects_the_latest_matchday(league):
    add_matchday(1, "2026-10-30")  # matchday 2
    add_matchday(1, "2026-10-16")  # 3, but older
    form = league.get("/matches/new").text
    assert re.search(r'<option value="2" selected>[^<]*Matchday 2', form)
    assert form.count(" selected>") == 1
    # A link naming a matchday still wins.
    assert re.search(r'<option value="1" selected>', league.get("/matches/new?matchday=1").text)


# --- Club password ---------------------------------------------------------------

@pytest.fixture
def locked(league):
    """The league, seen by a browser that entered the organization but isn't logged in."""
    league.cookies.delete("user")
    return league


def test_viewing_needs_no_password(locked):
    for url in ["/", "/tournaments", "/tournaments/1", "/matchdays/1", "/players", "/matches", "/rules"]:
        assert locked.get(url).status_code == 200, url
    page = locked.get("/tournaments").text
    assert "Add tournament" not in page and 'href="/courts"' not in page and "Log in</a>" in page


@pytest.mark.parametrize("method,url,data", [
    ("post", "/players", {"name": "Zed"}),
    ("post", "/tournaments", {"name": "Otra", "held_on": "2026-11-01"}),
    ("post", "/tournaments/1/matchdays", {"played_on": "2026-11-01", "court-1": ["1", "2", "3", "4"]}),
    ("get", "/tournaments/1/matchdays/new", None),
    ("post", "/matches", set_form((1, 2, 3, 4), 6, 4)),
    ("get", "/matches/new", None),
    ("get", "/matchdays/1/courts", None),
    ("post", "/matchdays/1/courts", {"court-1": ["1", "2", "3", "4"]}),
    ("post", "/players/1", {"name": "Zed"}),
    ("post", "/players/1/delete", {"confirm": "1"}),
])
def test_changes_need_the_password(locked, method, url, data):
    r = getattr(locked, method)(url, data=data, follow_redirects=False) if data else \
        getattr(locked, method)(url, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == len(NAMES)
        assert conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM matchdays").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 0


def test_login_page_remembers_where_to_go(locked):
    r = locked.get("/matches/new?matchday=1")
    assert "Log in to edit" in r.text and 'value="/matches/new?matchday=1"' in r.text


def test_wrong_password_is_rejected(locked):
    r = locked.post("/login", data={"password": "nope", "next": "/"})
    assert r.status_code == 401 and "Wrong password." in r.text
    assert locked.post("/players", data={"name": "Zed"}, follow_redirects=False).status_code == 303


def test_login_then_edit_then_logout(locked):
    r = locked.post("/login", data={"username": "admin", "password": "secreto", "next": "/players"})
    assert r.status_code == 200 and str(r.url).endswith("/players") and "Add player" in r.text
    assert "Zed" in locked.post("/players", data={"name": "Zed"}).text
    assert locked.post("/matches", data=set_form((1, 2, 3, 4), 6, 4)).status_code == 200
    assert "Log out</button>" in locked.get("/").text

    locked.post("/logout")
    r = locked.post("/players", data={"name": "Yan"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")


def test_changing_the_password_logs_everyone_out(locked, monkeypatch):
    locked.post("/login", data={"username": "admin", "password": "secreto", "next": "/"})
    with db.connect() as conn:
        orgs.set_password(conn, "admin", "nuevo")
    assert locked.post("/players", data={"name": "Zed"}, follow_redirects=False).status_code == 303


def test_login_only_redirects_within_the_site(locked):
    r = locked.post("/login", data={"username": "admin", "password": "secreto", "next": "https://evil.example"},
                    follow_redirects=False)
    assert r.headers["location"] == "/"


def test_database_folder_is_created(tmp_path, monkeypatch):
    path = tmp_path / "data" / "nested" / "padelscore.db"
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    assert path.exists()


def test_stylesheet_link_works_behind_https(client):
    # Azure's front end talks plain HTTP to the app; an absolute http:// link would be
    # blocked by browsers on the https:// site.
    page = client.get("/", headers={"x-forwarded-proto": "https"}).text
    link = re.search(r'<link rel="stylesheet" href="(/static/style\.css\?v=\w+)">', page)
    assert link and client.get(link.group(1)).status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_delete_tournament_removes_its_matchdays_and_sets(league):
    league.post("/tournaments", data={"name": "Otra liga", "held_on": "2026-11-01"})  # id 2
    add_matchday(2, "2026-11-01")                                                   # matchday 2
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4, matchday_id=1))
    league.post("/matches", data=set_form((5, 6, 7, 8), 6, 4, matchday_id=2))

    assert "Delete tournament" in league.get("/tournaments/1").text
    r = league.post("/tournaments/1/delete")
    assert r.status_code == 200 and str(r.url).endswith("/tournaments")
    assert "Liga Amigos" not in r.text and "Otra liga" in r.text
    assert league.get("/tournaments/1").status_code == 404
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM matchdays").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == len(NAMES)
    assert league.post("/tournaments/99/delete").status_code == 404


def test_delete_tournament_needs_the_password(locked):
    assert "Delete tournament" not in locked.get("/tournaments/1").text
    r = locked.post("/tournaments/1/delete", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert locked.get("/tournaments/1").status_code == 200


# --- Courts and pending sets -------------------------------------------------------

def courts_form(*courts):
    return {f"court-{n}": [str(p) for p in ids] for n, ids in enumerate(courts, 1)}


def pending_count():
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM matches WHERE team_a_games IS NULL").fetchone()[0]


def court_count(page):
    """Courts on the courts screen (the hidden template for a new court is left out)."""
    return page.split('<template')[0].count('<fieldset class="court-pick">')


def selected(html):
    return set(re.findall(r'<option value="(\d+)" selected>', html))


def test_court_rotation_gives_everyone_each_partner_once():
    sets = court_rotation((1, 2, 3, 4))
    pairs = [frozenset(team) for teams in sets for team in teams]
    assert len(sets) == 3 and len(set(pairs)) == 6  # all 6 possible pairs, once each


def test_next_courts_moves_one_up_and_one_down():
    courts = {1: [{"id": i} for i in (1, 2, 3, 4)], 2: [{"id": i} for i in (5, 6, 7, 8)]}
    new = next_courts(courts, 1)
    assert sorted(new[1]) == [1, 2, 3, 5] and sorted(new[2]) == [4, 6, 7, 8]


def matchday_count():
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM matchdays").fetchone()[0]


def test_new_matchday_is_saved_only_with_its_courts(client):
    for name in NAMES:
        client.post("/players", data={"name": name})
    client.post("/tournaments", data={"name": "Liga Amigos", "held_on": "2026-10-23"})
    # The tournament page's button opens a draft; nothing is saved yet.
    page = client.get("/tournaments/1").text
    assert 'action="/tournaments/1/matchdays/new"' in page
    r = client.get("/tournaments/1/matchdays/new", params={"played_on": "2026-10-23"})
    assert "New matchday 1" in r.text and "isn't saved yet" in r.text
    assert court_count(r.text) == 2  # 8 players: 2 empty courts; no question on matchday 1
    assert "How many players" not in r.text and matchday_count() == 0

    data = {"played_on": "2026-10-23", **courts_form((1, 2, 3, 4), (5, 6, 7, 8))}
    r = client.post("/tournaments/1/matchdays", data=data)
    assert r.status_code == 200 and str(r.url).endswith("/matchdays/1")
    assert matchday_count() == 1 and pending_count() == 6
    assert client.get("/courts", follow_redirects=False).headers["location"] == "/matchdays/1/courts"


def test_new_matchday_with_bad_courts_is_not_saved(league):
    data = {"played_on": "2026-10-30", **courts_form((1, 2, 3, 4), (4, 5, 6, 7))}
    r = league.post("/tournaments/1/matchdays", data=data)
    assert r.status_code == 400 and "Diego is on more than one court" in r.text
    assert 'value="2026-10-30"' in r.text and court_count(r.text) == 2  # the draft is kept
    assert matchday_count() == 1 and pending_count() == 0


def test_assigning_courts_creates_three_pending_sets_each(league):
    r = league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 4), (5, 6, 7, 8)))
    assert r.status_code == 200 and str(r.url).endswith("/matchdays/1")
    assert pending_count() == 6 and r.text.count('class="score-form"') == 6
    with db.connect() as conn:
        rows = conn.execute("SELECT a1, a2, b1, b2 FROM matches WHERE court = 1 ORDER BY id").fetchall()
    assert [((r[0], r[1]), (r[2], r[3])) for r in rows] == court_rotation((1, 2, 3, 4))
    # Pending sets give no points, so nobody is in the standings yet.
    assert "No results in this tournament yet" in league.get("/tournaments/1").text

    r = league.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "4"})
    assert "6-4" in r.text and pending_count() == 5
    assert standing_points(league.get("/tournaments/1").text, "Ana") == 1  # 1 set won so far
    assert "Pending" in league.get("/matches").text  # only a label on other pages


def test_score_needs_both_teams(league):
    league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 4)))
    r = league.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": ""})
    assert "Enter both teams" in r.text and pending_count() == 3
    r = league.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "-1"})
    assert "can't be negative" in r.text and pending_count() == 3


def test_saving_courts_again_keeps_unchanged_courts(league):
    league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 4), (5, 6, 7, 8)))
    league.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "4"})
    # The same four players on each court (in another order): nothing changes.
    r = league.post("/matchdays/1/courts", data=courts_form((4, 3, 2, 1), (8, 7, 6, 5)))
    assert r.status_code == 200 and pending_count() == 5
    with db.connect() as conn:
        assert conn.execute("SELECT team_a_games FROM matches WHERE id = 1").fetchone()[0] == 6
    # Court 2 has no results, so it can go.
    r = league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 4)))
    assert r.status_code == 200 and pending_count() == 2
    # Court 1 has a result: its players can't change.
    r = league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 5)))
    assert r.status_code == 400 and "Court 1 already has results" in r.text
    # The screen shows what is saved.
    page = league.get("/matchdays/1/courts").text
    assert court_count(page) == 1 and "creates its sets again" in page
    assert selected(page.split('<template')[0]) == {"1", "2", "3", "4"}


def test_changed_court_gets_new_sets(league):
    league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 4), (5, 6, 7, 8)))
    league.post("/players", data={"name": "Ivan"})
    league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 4), (5, 6, 7, 9)))
    with db.connect() as conn:
        players = {p for r in conn.execute("SELECT a1, a2, b1, b2 FROM matches WHERE court = 2")
                   for p in r}
    assert players == {5, 6, 7, 9} and pending_count() == 6


@pytest.mark.parametrize("courts,message", [
    (((1, 2, 3, 4), (4, 5, 6, 7)), "Diego is on more than one court"),
    (((1, 2, 3, ""),), "Court 1: pick 4 different players"),
    (((1, 2, 3, 3),), "Court 1: pick 4 different players"),
    (((1, 2, 3, 99),), "Court 1: pick 4 different players"),
    ((("", "", "", ""),), "Add at least one court"),
])
def test_rejects_bad_courts(league, courts, message):
    r = league.post("/matchdays/1/courts", data=courts_form(*courts))
    assert r.status_code == 400 and message in r.text and pending_count() == 0


def test_empty_courts_are_left_out(league):
    r = league.post("/matchdays/1/courts", data=courts_form(("", "", "", ""), (5, 6, 7, 8)))
    assert r.status_code == 200
    with db.connect() as conn:
        assert {r[0] for r in conn.execute("SELECT court FROM matches")} == {1}


def test_next_matchday_suggests_courts_after_moves(league):
    league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 4), (5, 6, 7, 8)))
    for match_id in range(1, 7):  # the ROTATION results on both courts
        a, b = ROTATION[(match_id - 1) % 3][1:]
        league.post(f"/matches/{match_id}/score", data={"team_a_games": a, "team_b_games": b})
    # Court order after matchday 1: Carlos, Ana, Bea, Diego and Gabi, Elena, Fer, Hugo.
    new = "/tournaments/1/matchdays/new"
    page = league.get(new, params={"played_on": "2026-10-30"}).text
    assert "How many players move up and down" in page and court_count(page) == 0

    def suggested(move):
        page = league.get(new, params={"played_on": "2026-10-30", "move": move}).text
        assert "Suggested from matchday 1" in page and 'value="2026-10-30"' in page
        return [selected(c) for c in page.split("<template")[0]
                .split('<fieldset class="court-pick">')[1:]]

    # One moves: Diego down, Gabi up. The best of court 1 and the last of court 2 stay.
    assert suggested(1) == [{"1", "2", "3", "7"}, {"4", "5", "6", "8"}]
    # Two move: Bea and Diego down, Gabi and Elena up.
    assert suggested(2) == [{"1", "3", "5", "7"}, {"2", "4", "6", "8"}]
    assert matchday_count() == 1  # still only a draft


def test_set_form_can_save_a_pending_set(league):
    r = league.post("/matches", data=set_form((1, 2, 3, 4), "", ""))
    assert r.status_code == 200 and pending_count() == 1
    r = league.post("/matches", data=set_form((1, 2, 3, 4), "6", ""))
    assert r.status_code == 400 and "Enter both teams" in r.text


def test_rename_player(league):
    r = league.post("/players/1", data={"name": "  Anita "})
    assert r.status_code == 200 and "<h1>Anita</h1>" in r.text
    assert "That player already exists" in league.post("/players/1", data={"name": "bea"}).text
    assert "Name is required" in league.post("/players/1", data={"name": " "}).text


def test_delete_player_only_without_sets(league):
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4))
    assert "Can't delete" in league.post("/players/1/delete").text
    r = league.post("/players/8/delete")
    assert str(r.url).endswith("/players") and "Hugo" not in r.text
    assert league.get("/players/8").status_code == 404


def test_old_database_is_upgraded_for_pending_sets(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "old.db"
    old = (BEFORE_ACCOUNTS.replace("team_a_games INTEGER,", "team_a_games INTEGER NOT NULL,")
                    .replace("team_b_games INTEGER,", "team_b_games INTEGER NOT NULL,"))
    assert old.count("NOT NULL,") > db.SCHEMA.count("NOT NULL,")
    conn = sqlite3.connect(path)
    conn.executescript(old + """
        INSERT INTO players (name) VALUES ('A'), ('B'), ('C'), ('D');
        INSERT INTO tournaments (name, held_on) VALUES ('T', '2026-10-01');
        INSERT INTO matchdays (tournament_id, number, played_on) VALUES (1, 1, '2026-10-01');
        INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, team_a_games, team_b_games, winner)
            VALUES (1, 1, 1, 2, 3, 4, 6, 3, 'A');
    """)
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    db.init_db()  # a second start leaves it alone
    with db.connect() as conn:
        assert tuple(conn.execute("SELECT team_a_games, team_b_games, winner FROM matches")
                     .fetchone()) == (6, 3, "A")
        conn.execute("INSERT INTO matches (matchday_id, court, a1, a2, b1, b2) "
                     "VALUES (1, 1, 1, 3, 2, 4)")
        with pytest.raises(sqlite3.IntegrityError):  # both games or neither
            conn.execute("INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, team_a_games) "
                         "VALUES (1, 1, 1, 4, 2, 3, 6)")


def test_next_courts_keeps_court_1_winners_and_last_court_losers():
    courts = {c: [{"id": c * 10 + i} for i in range(4)] for c in (1, 2, 3)}
    new = next_courts(courts, 2)
    assert {10, 11} <= set(new[1]) and {32, 33} <= set(new[3])  # they stay
    assert sorted(new[2]) == sorted([12, 13, 30, 31])


def test_delete_matchday_removes_its_sets_and_renumbers(league):
    add_matchday(1, "2026-10-30")  # matchday 2 (id 2)
    add_matchday(1, "2026-11-06")  # matchday 3 (id 3)
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4, matchday_id=1))
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4, matchday_id=2))
    assert "Delete matchday" in league.get("/matchdays/2").text

    r = league.post("/matchdays/2/delete")
    assert r.status_code == 200 and str(r.url).endswith("/tournaments/1")
    assert league.get("/matchdays/2").status_code == 404
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1
        numbers = conn.execute("SELECT id, number FROM matchdays ORDER BY number").fetchall()
    assert [tuple(n) for n in numbers] == [(1, 1), (3, 2)]
    assert standing_points(league.get("/tournaments/1").text, "Ana") == 10
    assert league.post("/matchdays/99/delete").status_code == 404


def test_delete_matchday_needs_the_password(locked):
    assert "Delete matchday" not in locked.get("/matchdays/1").text
    r = locked.post("/matchdays/1/delete", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert matchday_count() == 1


# --- Rule types ----------------------------------------------------------------------

def test_tournaments_have_a_rule_type(league):
    page = league.get("/tournaments").text
    assert re.search(r'<option value="1" data-code="liga_amigos" selected>[^<]*Liga de amigos score</option>', page)
    assert "Liga de amigos score" in league.get("/tournaments/1").text
    r = league.post("/tournaments", data={"name": "Otra", "held_on": "2026-11-01",
                                          "rule_type_id": "99"})
    assert "Pick a rules type" in r.text and "Otra" not in r.text
    league.post("/tournaments", data={"name": "Otra", "held_on": "2026-11-01", "rule_type_id": "1"})
    with db.connect() as conn:
        assert [r[0] for r in conn.execute("SELECT rule_type_id FROM tournaments")] == [1, 1]


def test_old_tournaments_get_the_liga_de_amigos_rule_type(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE tournaments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            held_on DATE NOT NULL CHECK (held_on IS date(held_on)));
        INSERT INTO tournaments (name, held_on) VALUES ('Vieja', '2026-10-01');
    """)
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    db.init_db()
    with db.connect() as conn:
        row = conn.execute("SELECT t.name, r.name FROM tournaments t "
                           "JOIN rule_types r ON r.id = t.rule_type_id").fetchone()
        assert tuple(row) == ("Vieja", "Liga de amigos score")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


# --- Absences --------------------------------------------------------------------------

def test_absent_player_scores_zero_and_goes_last():
    sets = [row(p, a, b) for p, a, b in ROTATION]
    rows = court_table(sets, position={}, absent={3})
    carlos = next(r for r in rows if r["id"] == 3)
    assert rows[-1] is carlos and carlos["absent"]
    assert (carlos["points"], carlos["diff"], carlos["sets_won"], carlos["sets"]) == (0, 0, 0, 3)
    # Everyone else scores their pairs' games as usual.
    assert {r["id"]: r["points"] for r in rows if not r["absent"]} == {1: 15, 2: 14, 4: 9}


def test_mark_player_absent_on_a_matchday(league):
    for players, a, b in ROTATION:
        league.post("/matches", data=set_form(players, a, b))
    assert standing_points(league.get("/tournaments/1").text, "Carlos") == 11

    r = league.post("/matchdays/1/absent/3")
    assert r.status_code == 200 and "🚫 Absent<" in r.text and "Mark present" in r.text
    assert standing_points(league.get("/tournaments/1").text, "Carlos") == 0
    # Carlos goes last; Ana (2 sets, +3) is now 1st on the court: 9 + 2.
    assert standing_points(league.get("/tournaments/1").text, "Ana") == 11
    profile = league.get("/players/3").text
    assert "🚫 Absent<" in profile and "0 matchdays played" in profile
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 3  # same sets

    league.post("/matchdays/1/absent/3")  # present again
    assert standing_points(league.get("/tournaments/1").text, "Carlos") == 11
    assert league.post("/matchdays/1/absent/8").status_code == 404  # Hugo isn't playing


def test_deleting_a_matchday_removes_its_absences(league):
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4))
    league.post("/matchdays/1/absent/1")
    league.post("/matchdays/1/delete")
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM absences").fetchone()[0] == 0


def test_marking_absent_needs_the_password(locked):
    r = locked.post("/matchdays/1/absent/1", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")


def test_latest_matchday_offers_the_next_one(league):
    league.post("/matchdays/1/courts", data=courts_form((1, 2, 3, 4), (5, 6, 7, 8)))
    for match_id in range(1, 7):
        league.post(f"/matches/{match_id}/score", data={"team_a_games": "6", "team_b_games": "0"})
    page = league.get("/matchdays/1?move=2").text
    assert "New matchday 2" in page and 'value="2026-10-30"' in page
    assert '<input type="hidden" name="move" value="2">' in page
    # The button opens the draft with those moves; nothing is saved yet.
    r = league.get("/tournaments/1/matchdays/new", params={"move": "2", "played_on": "2026-10-30"})
    assert "Suggested from matchday 1" in r.text and matchday_count() == 1
    # An older matchday doesn't offer it.
    add_matchday(1, "2026-10-30")
    assert "New matchday" not in league.get("/matchdays/1").text


# --- Americano, Mexicano and manual tournaments -------------------------------------

from collections import Counter

from app import rounds


def play_rounds(make_round, players, count):
    history = []
    for n in range(count):
        courts, resting = make_round(players, history, n)
        playing = [p for c in courts for p in c]
        assert sorted(playing + resting) == sorted(players)  # everyone plays or rests once
        history.append(courts)
    return history


def test_americano_rotates_partners():
    history = play_rounds(rounds.americano_round, list(range(1, 9)), 7)
    partners = Counter(frozenset(pair) for courts in history for c in courts
                       for pair in (c[:2], c[2:]))
    assert all(len(courts) == 2 for courts in history)
    assert max(partners.values()) <= 2 and len(partners) >= 24  # of the 28 possible pairs
    first_three = Counter(frozenset(pair) for courts in history[:3] for c in courts
                          for pair in (c[:2], c[2:]))
    assert max(first_three.values()) == 1  # no repeated partner early on


def test_rests_rotate_before_anyone_rests_twice():
    players = list(range(1, 10))  # 9 players, 2 courts: one rests each round
    history = play_rounds(rounds.americano_round, players, 9)
    assert set(rounds.rests(players, history).values()) == {1}


def test_mexicano_pairs_by_ranking():
    players = list(range(1, 10))
    ranking = [3, 1, 4, 5, 9, 2, 6, 8, 7]  # best first
    # Round 1: 9 rested. Now the lowest ranked of the others rests; then 1st+3rd vs
    # 2nd+4th on court 1, 5th+7th vs 6th+8th on court 2.
    courts, resting = rounds.mexicano_round(players, [[[1, 2, 3, 4], [5, 6, 7, 8]]], ranking, seed=1)
    assert resting == [7]
    assert courts == [[3, 4, 1, 5], [9, 6, 2, 8]]
    # Round 1 is a draw: every player plays or rests.
    courts, resting = rounds.mexicano_round(players, [], [], seed=1)
    assert len(courts) == 2 and len(resting) == 1


def new_tournament(client, rule_type_id, players=(), points=24, name="Copa"):
    data = {"name": name, "held_on": "2026-11-01", "rule_type_id": str(rule_type_id),
            "points_per_match": str(points), "players": [str(p) for p in players]}
    return client.post("/tournaments", data=data)


def test_americano_needs_four_players(league):
    r = new_tournament(league, 2, players=(1, 2, 3))
    assert "Pick at least 4 players" in r.text
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0] == 1


def test_americano_round_flow(league):
    league.post("/players", data={"name": "Zed"})
    r = new_tournament(league, 2, players=range(1, 10))  # 9 players: one rests
    assert str(r.url).endswith("/tournaments/2") and "Americano" in r.text and "24</strong> 🎯" in r.text
    page = league.get("/tournaments/2/matchdays/new", params={"played_on": "2026-11-01"}).text
    assert "New round 1" in page and "How many players" not in page and "Resting" in page
    court_1, court_2 = page.split("<template")[0].split('<fieldset class="court-pick">')[1:3]
    picks = [re.findall(r'<option value="(\d+)" selected>', c) for c in (court_1, court_2)]
    assert all(len(p) == 4 for p in picks)

    data = {"played_on": "2026-11-01", **courts_form(*picks)}
    r = league.post("/tournaments/2/matchdays", data=data)
    assert str(r.url).endswith("/matchdays/2") and "Round 1" in r.text and "🛋️" in r.text
    with db.connect() as conn:
        sets = conn.execute("SELECT id, a1, a2, b1, b2 FROM matches ORDER BY id").fetchall()
    assert len(sets) == 2  # one match per court, first two against last two
    assert [list(s)[1:] for s in sets] == [[int(p) for p in pick] for pick in picks]

    league.post(f"/matches/{sets[0]['id']}/score", data={"team_a_games": "14", "team_b_games": "10"})
    standings = league.get("/tournaments/2").text
    a1 = NAMES[sets[0]["a1"] - 1] if sets[0]["a1"] <= 8 else "Zed"
    b1 = NAMES[sets[0]["b1"] - 1] if sets[0]["b1"] <= 8 else "Zed"
    assert standing_points(standings, a1) == 14 and standing_points(standings, b1) == 10


def test_mexicano_second_round_follows_the_ranking(league):
    new_tournament(league, 3, players=range(1, 9))
    data = {"played_on": "2026-11-01", **courts_form((1, 2, 3, 4), (5, 6, 7, 8))}
    league.post("/tournaments/2/matchdays", data=data)
    league.post("/matches/1/score", data={"team_a_games": "15", "team_b_games": "9"})   # Ana, Bea 15
    league.post("/matches/2/score", data={"team_a_games": "12", "team_b_games": "12"})  # all 12
    page = league.get("/tournaments/2/matchdays/new", params={"played_on": "2026-11-01"}).text
    court_1 = page.split("<template")[0].split('<fieldset class="court-pick">')[1]
    # Ranking: Ana, Bea (15), then Elena, Fer, Gabi, Hugo (12): court 1 is Ana+Elena vs Bea+Fer.
    assert re.findall(r'<option value="(\d+)" selected>', court_1) == ["1", "5", "2", "6"]


def test_manual_tournament_sets_are_made_by_hand(league):
    new_tournament(league, 4)
    page = league.get("/tournaments/2/matchdays/new", params={"played_on": "2026-11-01"}).text
    assert "court-pick" not in page and "add each set" in page
    r = league.post("/tournaments/2/matchdays", data={"played_on": "2026-11-01"})
    assert str(r.url).endswith("/matchdays/2") and "Record the first one" in r.text
    assert league.get("/matchdays/2/courts", follow_redirects=False).headers["location"] == \
        "/matches/new?matchday=2"
    league.post("/matches", data=set_form((1, 5, 2, 6), 6, 3, court=3, matchday_id=2))
    standings = league.get("/tournaments/2").text
    assert standing_points(standings, "Ana") == 3 and standing_points(standings, "Bea") == -3
    league.post("/matches", data=set_form((1, 5, 2, 6), 2, 6, court=3, matchday_id=2))
    standings = league.get("/tournaments/2").text
    assert standing_points(standings, "Ana") == -1 and standing_points(standings, "Bea") == 1


def test_filter_sets_by_matchday(league):
    add_matchday(1, "2026-10-30")
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4, matchday_id=1))
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 2, matchday_id=2))
    page = league.get("/matches?matchday=2").text
    assert page.count('class="match"') == 1 and 'aria-label="6-2"' in page
    assert '<option value="2" selected>' in page
    # A matchday of another tournament is ignored.
    assert league.get("/matches?tournament=1&matchday=99").text.count('class="match"') == 2


def test_players_can_ask_to_rest_and_courts_can_be_fewer():
    players = list(range(1, 10))
    courts, resting = rounds.americano_round(players, [], seed=3, rest=[4, 7])
    assert {4, 7} <= set(resting) and len(resting) == 5 and len(courts) == 1  # 7 left: one court, 3 more rest
    courts, resting = rounds.americano_round(players, [], seed=3, courts=1)
    assert len(courts) == 1 and len(resting) == 5
    # Mexicano: whoever asked rests; the other rest goes to the lowest ranked.
    history = [[[1, 2, 3, 4], [5, 6, 7, 8]]]  # 9 rested in round 1
    courts, resting = rounds.mexicano_round(players, history, list(range(1, 10)), seed=1, rest=[2])
    assert resting == [2] and [p for c in courts for p in c] == [1, 4, 3, 5, 6, 8, 7, 9]


def test_round_draft_with_rests_and_courts(league):
    new_tournament(league, 2, players=range(1, 9))
    page = league.get("/tournaments/2/matchdays/new",
                      params={"played_on": "2026-11-01", "rest": ["1", "2"]}).text
    assert "Who rests this round" in page and court_count(page) == 1
    assert "Resting" in page and "🛋️ Ana" in page and "🛋️ Bea" in page
    assert 'name="rest" value="1" checked' in page
    page = league.get("/tournaments/2/matchdays/new",
                      params={"played_on": "2026-11-01", "courts": "1"}).text
    assert court_count(page) == 1 and page.count("🛋️ ") >= 4


# --- Tournament players and the player password ---------------------------------------

def test_tournament_players_can_be_added_and_removed(league):
    r = new_tournament(league, 1, players=(1, 2, 3, 4), name="Liga 2")
    assert "👤 Ana" in r.text and "👤 Elena" not in r.text
    league.post("/tournaments/2/players", data={"player_name": "elena "})  # Elena replaces Ana
    r = league.post("/tournaments/2/players", data={"player_name": "Nadie"})
    assert "There's no player with that name" in r.text
    league.post("/tournaments/2/players/1/remove")
    with db.connect() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT player_id FROM tournament_players WHERE tournament_id = 2 ORDER BY player_id")]
    assert ids == [2, 3, 4, 5]
    # The courts screen offers only the tournament's players.
    page = league.get("/tournaments/2/matchdays/new", params={"played_on": "2026-11-01"}).text
    assert ">Elena</option>" in page and ">Ana</option>" not in page and court_count(page) == 1


def test_removed_player_keeps_results(league):
    new_tournament(league, 4, players=(1, 2, 3, 4), name="Manual")  # tournament 2
    league.post("/tournaments/2/matchdays", data={"played_on": "2026-11-01"})
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 3, matchday_id=2))
    league.post("/tournaments/2/players/1/remove")
    assert standing_points(league.get("/tournaments/2").text, "Ana") == 3


@pytest.fixture
def with_players(locked):
    """The locked league; tournament 1 has players' password 'jugamos' and two sets."""
    from app import auth
    with db.connect() as conn:
        conn.execute("UPDATE tournaments SET player_password = 'jugamos' WHERE id = 1")
        for a1, a2, b1, b2 in ((1, 2, 3, 4), (1, 3, 2, 4)):
            conn.execute("INSERT INTO matches (matchday_id, court, a1, a2, b1, b2) "
                         "VALUES (1, 1, ?, ?, ?, ?)", (a1, a2, b1, b2))
    return locked


def test_player_password_lets_players_enter_results_only(with_players):
    c = with_players
    assert c.post("/login", data={"password": "nope", "next": "/"}).status_code == 401
    r = c.post("/login", data={"password": "jugamos", "next": "/"})
    assert str(r.url).endswith("/tournaments/1") and "Log out" in r.text
    assert "player_1" in c.cookies

    page = c.get("/matchdays/1").text
    assert page.count('class="score-form"') == 2 and "Logged in as a player" in page
    assert "Delete" not in page and "Assign courts" not in page
    r = c.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "4"})
    assert 'value="6"' in r.text  # entered, and still editable to correct it
    c.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "2"})
    with db.connect() as conn:
        assert tuple(conn.execute("SELECT team_a_games, team_b_games FROM matches WHERE id = 1")
                     .fetchone()) == (6, 2)

    # Nothing else: no deleting, no new sets in a Liga, no courts, no tournaments.
    for method, url, data in [("post", "/matches/1/delete", {"x": "1"}),
                              ("get", "/matches/new", None),
                              ("post", "/matches", set_form((5, 6, 7, 8), 6, 4)),
                              ("get", "/matches/1/edit", None),
                              ("get", "/matchdays/1/courts", None),
                              ("post", "/tournaments/1/players/1/remove", {"x": "1"}),
                              ("post", "/tournaments/1/player-password", {"password": ""}),
                              ("post", "/players", {"name": "Zed"})]:
        r = getattr(c, method)(url, data=data, follow_redirects=False) if data else \
            getattr(c, method)(url, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/login"), url
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 2

    c.post("/logout")
    assert "player_1" not in c.cookies
    assert c.post("/matches/2/score", data={"team_a_games": "1", "team_b_games": "0"},
                  follow_redirects=False).status_code == 303


def test_players_of_one_tournament_cannot_score_another(with_players):
    from app import auth
    with db.connect() as conn:
        conn.execute("INSERT INTO tournaments (name, held_on, player_password, organization_id) "
                     "VALUES ('Otra', '2026-11-01', 'otra', 1)")
    with_players.post("/login", data={"password": "otra", "next": "/"})
    r = with_players.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "4"},
                          follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")


def test_players_create_sets_in_a_manual_tournament(with_players):
    from app import auth
    with db.connect() as conn:
        conn.execute("INSERT INTO tournaments (name, held_on, rule_type_id, player_password, "
                     "organization_id) VALUES ('Manual', '2026-11-01', 4, 'manual', 1)")
        conn.executemany("INSERT INTO tournament_players (tournament_id, player_id) VALUES (2, ?)",
                         [(p,) for p in (1, 2, 3, 4, 5)])
        conn.execute("INSERT INTO matchdays (tournament_id, number, played_on) VALUES (2, 1, '2026-11-01')")
    c = with_players
    c.post("/login", data={"password": "manual", "next": "/"})
    form = c.get("/matches/new?matchday=2").text
    assert ">Elena</option>" in form and ">Fer</option>" not in form  # the tournament's players
    assert '<option value="1" ' not in form.split('name="matchday_id"')[1].split("</select>")[0]
    r = c.post("/matches", data=set_form((1, 5, 2, 3), 6, 4, court=2, matchday_id=2))
    assert r.status_code == 200 and str(r.url).endswith("/matchdays/2")
    assert c.get("/matches/3/edit").status_code == 200
    # Not in the Liga tournament, whose players' password they don't have.
    r = c.post("/matches", data=set_form((1, 2, 3, 4), 6, 4, matchday_id=1), follow_redirects=False)
    assert r.status_code == 303


def test_set_and_remove_the_player_password(league):
    r = league.post("/tournaments/1/player-password", data={"password": " jugamos "})
    assert "<code>jugamos</code>" in r.text  # admins can look it up
    assert "<code>jugamos</code>" in league.get("/tournaments").text
    r = league.post("/tournaments/1/player-password", data={"password": ""})
    assert "<code>liga_amigos</code>" in r.text  # back to the default


def test_player_password_defaults_to_the_tournament_name(league):
    from app.auth import default_player_password
    assert default_player_password("  Liga de la  Amistad ") == "liga_de_la_amistad"
    # The league fixture's tournament got it when created.
    assert "<code>liga_amigos</code>" in league.get("/tournaments/1").text
    new_tournament(league, 1, name="Copa Otoño 2026")
    with db.connect() as conn:
        assert conn.execute("SELECT player_password FROM tournaments WHERE id = 2").fetchone()[0] \
            == "copa_otoño_2026"
    # A typed one wins.
    league.post("/tournaments", data={"name": "X", "held_on": "2026-11-01", "player_password": "clave"})
    with db.connect() as conn:
        assert conn.execute("SELECT player_password FROM tournaments WHERE id = 3").fetchone()[0] == "clave"


def test_older_tournaments_get_the_default_player_password(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE tournaments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            held_on DATE NOT NULL CHECK (held_on IS date(held_on)));
        INSERT INTO tournaments (name, held_on) VALUES ('Liga de la amistad', '2026-10-01');
    """)
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    with db.connect() as conn:
        assert conn.execute("SELECT player_password FROM tournaments").fetchone()[0] == "liga_de_la_amistad"


def test_only_admins_see_the_player_password(with_players):
    assert "jugamos" not in with_players.get("/tournaments/1").text
    assert "jugamos" not in with_players.get("/tournaments").text
    with_players.post("/login", data={"password": "jugamos", "next": "/"})  # a player
    assert "jugamos" not in with_players.get("/tournaments/1").text
    with_players.post("/login", data={"username": "admin", "password": "secreto", "next": "/"})  # the club
    assert "<code>jugamos</code>" in with_players.get("/tournaments/1").text


def test_standings_page_by_tournament(league):
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4))       # Liga Amigos
    new_tournament(league, 4, players=(5, 6, 7, 8), name="Otra copa")  # newer, no sets
    home = league.get("/").text
    assert "Standings: <a" in home and "Otra copa</a></h1>" in home   # latest by default
    assert 'href="/?tournament=1"' in home and 'href="/?tournament=2"' in home
    page = league.get("/?tournament=1").text
    assert "Liga Amigos</a></h1>" in page and standing_points(page, "Ana") == 10
    assert "Otra copa</a></h1>" in league.get("/?tournament=99").text  # unknown: the latest


def test_new_players_can_be_created_while_choosing_them(league):
    data = {"name": "Copa", "held_on": "2026-11-01", "rule_type_id": "1",
            "players": ["1", "2"], "new_players": ["Zoe", " ana "]}  # " ana " is Ana
    league.post("/tournaments", data=data)
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == len(NAMES) + 1
        names = [r[0] for r in conn.execute(
            "SELECT p.name FROM tournament_players tp JOIN players p ON p.id = tp.player_id "
            "WHERE tp.tournament_id = 2 ORDER BY p.name")]
    assert names == ["Ana", "Bea", "Zoe"]


def test_tournament_page_adds_or_creates_a_player(league):
    page = league.get("/tournaments/1").text
    assert 'class="picker add-player"' in page and '"name": "Ana"' in page
    league.post("/tournaments/1/players", data={"player_name": "Yuri", "create": "1"})
    league.post("/tournaments/1/players", data={"player_name": "bea", "create": ""})
    r = league.post("/tournaments/1/players", data={"player_name": "Nadie", "create": ""})
    assert "There's no player with that name" in r.text
    with db.connect() as conn:
        names = {r[0] for r in conn.execute(
            "SELECT p.name FROM tournament_players tp JOIN players p ON p.id = tp.player_id")}
    assert names == {"Yuri", "Bea"}


def test_player_names_cannot_repeat_ignoring_case_accents_and_spaces(league):
    for name in ("ANA", " Ána ", "Bea"):
        assert "That player already exists" in league.post("/players", data={"name": name}).text
    assert "That player already exists" in league.post("/players/2", data={"name": "ana"}).text
    league.post("/players", data={"name": "Luis   Pérez"})
    assert "That player already exists" in league.post(
        "/players", data={"name": "luis perez"}).text
    league.post("/tournaments/1/players", data={"player_name": "LUIS PEREZ", "create": "1"})
    with db.connect() as conn:
        names = [r[0] for r in conn.execute("SELECT name FROM players WHERE name LIKE 'Luis%'")]
    assert names == ["Luis Pérez"]


def test_admin_replaces_a_player_in_pending_sets_only(league):
    league.post("/tournaments/1/players", data={"player_name": "Ana"})
    league.post("/tournaments/1/players", data={"player_name": "Bea"})
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 3))  # played
    league.post("/matches", data=set_form((1, 3, 2, 4), "", ""))  # pending
    page = league.get("/tournaments/1").text
    assert 'action="/tournaments/1/players/replace"' in page
    r = league.post("/tournaments/1/players/replace",
                    data={"old_id": "1", "player_name": "Zoe", "create": "1"})
    assert r.status_code == 200
    with db.connect() as conn:
        zoe = conn.execute("SELECT id FROM players WHERE name = 'Zoe'").fetchone()[0]
        sets = conn.execute("SELECT a1, team_a_games FROM matches ORDER BY id").fetchall()
        members = {row[0] for row in conn.execute("SELECT player_id FROM tournament_players")}
    assert [tuple(s) for s in sets] == [(1, 6), (zoe, None)]
    assert members == {2, zoe}
    # Errors: nobody chosen to leave, the same player, or someone already in that set.
    for data, error in (({"old_id": "", "player_name": "Hugo"}, "Choose which player leaves"),
                        ({"old_id": "2", "player_name": "bea"}, "Choose a different player"),
                        ({"old_id": "2", "player_name": "Diego"}, "already in a pending set")):
        assert error in league.post("/tournaments/1/players/replace", data=data).text


def test_ended_tournaments_go_to_the_past_tab(league):
    league.post("/tournaments", data={"name": "Copa", "held_on": "2026-11-01"})  # id 2
    league.post("/tournaments/1/ended", data={"ended": "1"})
    current = league.get("/tournaments").text
    assert "Copa" in current and "Liga Amigos" not in current and "Past (1)" in current
    past = league.get("/tournaments?past=1").text
    assert "Liga Amigos" in past and "Copa" not in past
    assert "Reopen tournament" in league.get("/tournaments/1").text
    home = league.get("/").text
    assert "Copa" in home and "/?tournament=1" not in home
    assert "Liga Amigos" in league.get("/?tournament=1").text  # still reachable
    league.post("/tournaments/1/ended", data={"ended": "0"})
    assert "Liga Amigos" in league.get("/tournaments").text


def test_replace_a_player_from_the_matchday_court_table(league):
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 3))  # played
    league.post("/matches", data=set_form((1, 3, 2, 4), "", ""))  # pending
    link = "/tournaments/1/players/1/replace?next=/matchdays/1"
    assert link in league.get("/matchdays/1").text
    page = league.get(link).text
    assert "Replace Ana" in page and '"name": "Hugo"' in page and '"name": "Ana"' not in page
    r = league.post("/tournaments/1/players/replace", data={
        "old_id": "1", "player_name": "Diego", "next": "/matchdays/1"})
    assert "already in a pending set" in r.text and "Replace Ana" in r.text
    r = league.post("/tournaments/1/players/replace", data={
        "old_id": "1", "player_name": "Nuevo", "create": "1", "next": "/matchdays/1"})
    assert str(r.url).endswith("/matchdays/1") and "Nuevo" in r.text
    with db.connect() as conn:
        assert [r[0] for r in conn.execute("SELECT a1 FROM matches ORDER BY id")][0] == 1
    assert league.get("/tournaments/1/players/8/replace").status_code == 404  # no sets


# --- Organizations and super admins ------------------------------------------------------

def test_visitors_enter_an_organization_first(league):
    league.cookies.delete("org")
    r = league.get("/tournaments", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/enter?next=/tournaments"
    assert league.get("/rules").status_code == 200  # the rules are for everyone
    r = league.post("/enter", data={"name": "Nadie", "next": "/tournaments"})
    assert r.status_code == 404 and "no organization with that name" in r.text
    r = league.post("/enter", data={"name": "  club ", "next": "/tournaments"})
    assert str(r.url).endswith("/tournaments") and "Liga Amigos" in r.text and "🏢 Club" in r.text
    # A forged cookie is ignored.
    league.cookies.delete("org")
    league.cookies.set("org", "1.forged")
    assert league.get("/", follow_redirects=False).headers["location"].startswith("/enter")


def test_organizations_only_see_their_own_data(league):
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4))
    with db.connect() as conn:
        orgs.create_org(conn, "Otro club", "otro", "clave")
    other = league.post("/login", data={"username": "otro", "password": "clave"})
    assert "🏢 Otro club" in other.text and "Liga Amigos" not in other.text
    assert "Liga Amigos" not in league.get("/tournaments").text
    assert "Ana" not in league.get("/players").text and "Ana" not in league.get("/matches").text
    for url in ("/tournaments/1", "/matchdays/1", "/players/1", "/matches/1/edit"):
        assert league.get(url).status_code == 404, url
    assert league.post("/matches/1/score", data={"team_a_games": "0", "team_b_games": "6"}
                       ).status_code == 404
    # Its own players, even with names the other club uses; no sets with the other's players.
    league.post("/players", data={"name": "Ana"})
    league.post("/tournaments", data={"name": "Copa", "held_on": "2026-11-01"})
    with db.connect() as conn:
        conn.execute("INSERT INTO matchdays (tournament_id, number, played_on) "
                     "VALUES (2, 1, '2026-11-01')")
    r = league.post("/matches", data=set_form((1, 2, 3, 9), 6, 4, matchday_id=2))
    assert r.status_code == 400
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM players WHERE name = 'Ana'").fetchone()[0] == 2
        assert conn.execute("SELECT team_a_games FROM matches WHERE id = 1").fetchone()[0] == 6
    # The first club's admin is no admin here.
    other_org = league.cookies.get("org")
    league.post("/login", data={"username": "admin", "password": "secreto"})
    league.cookies.delete("org")
    league.cookies.set("org", other_org)
    assert league.post("/players", data={"name": "Zed"}, follow_redirects=False) \
        .headers["location"].startswith("/login")


def test_admins_log_in_with_user_and_password(locked):
    r = locked.post("/login", data={"username": "admin", "password": "nope"})
    assert r.status_code == 401 and "Wrong password." in r.text
    r = locked.post("/login", data={"username": "ADMIN", "password": "secreto", "next": "/players"})
    assert str(r.url).endswith("/players") and "Add player" in r.text


def test_super_admin_creates_and_enters_organizations(locked):
    assert locked.get("/orgs", follow_redirects=False).headers["location"].startswith("/login")
    assert locked.post("/orgs", data={"name": "X", "admin_user": "x", "admin_password": "x"},
                       follow_redirects=False).status_code == 303
    with db.connect() as conn:
        orgs.set_superadmin(conn, "julio", "super")
        assert conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 1
    locked.cookies.delete("org")
    r = locked.post("/login", data={"username": "julio", "password": "super"})
    assert str(r.url).endswith("/orgs") and "Club" in r.text
    r = locked.post("/orgs", data={"name": "Nene", "admin_user": "nene", "admin_password": "pa"})
    assert "Nene" in r.text
    assert "already" in locked.post("/orgs", data={"name": "nene", "admin_user": "y",
                                                   "admin_password": "p"}).text
    # Admin in every organization.
    r = locked.post("/orgs/1/enter")
    assert "Liga Amigos" in r.text and "Delete tournament" in locked.get("/tournaments/1").text
    assert "Zed" in locked.post("/players", data={"name": "Zed"}).text
    locked.post("/orgs/2/enter")
    assert "Liga Amigos" not in locked.get("/tournaments").text
    # Sees each admin's user and password, and can change them.
    page = locked.get("/orgs").text
    assert "<code>nene</code>" in page and "<code>pa</code>" in page
    assert "already" in locked.post("/orgs/2/admin", data={"admin_user": "admin"}).text
    locked.post("/orgs/2/admin", data={"admin_user": "nene2", "admin_password": "nueva"})
    assert "<code>nene2</code>" in locked.get("/orgs").text
    locked.post("/orgs/2/admin", data={"admin_user": "nene2", "admin_password": ""})
    assert "<code>nueva</code>" in locked.get("/orgs").text  # an empty password keeps it
    locked.post("/logout")
    r = locked.post("/login", data={"username": "nene2", "password": "nueva", "role": "account"})
    assert "🏢 Nene" in r.text


def test_login_page_has_an_account_and_a_player_section(with_players):
    with_players.cookies.delete("user")
    page = with_players.get("/login").text
    assert 'value="account"' in page and 'value="player"' in page
    # The account section doesn't take player passwords, nor the player section accounts.
    r = with_players.post("/login", data={"username": "x", "password": "jugamos", "role": "account"})
    assert r.status_code == 401
    r = with_players.post("/login", data={"username": "admin", "password": "secreto", "role": "player"})
    assert r.status_code == 401
    r = with_players.post("/login", data={"username": "admin", "password": "secreto", "role": "account"})
    assert r.status_code == 200 and "Log out" in r.text


def test_accounts_log_in_with_username_or_email(locked):
    with db.connect() as conn:
        users.create_user(conn, "player", "juli", "clave-larga", email="Juli@Example.com")
        orgs.set_superadmin(conn, "julio", "super")
    for name in ("juli", "JULI", "juli@example.com"):
        locked.cookies.delete("user")
        r = locked.post("/login", data={"username": name, "password": "clave-larga",
                                        "role": "account"}, follow_redirects=False)
        assert r.status_code == 303 and "user" in r.cookies, name
    # A player account isn't an admin.
    assert "Delete tournament" not in locked.get("/tournaments/1").text
    locked.post("/logout")
    r = locked.post("/login", data={"username": "julio", "password": "super", "role": "account"})
    assert "Delete tournament" in locked.get("/tournaments/1").text  # super: admin everywhere


def test_old_admins_become_accounts(tmp_path, monkeypatch):
    """Databases from before accounts: their super admin and organization admin log in
    as before, now as users rows (sql/predeployment/0001_users.sql)."""
    import sqlite3
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(BEFORE_ACCOUNTS)
    conn.execute("INSERT INTO superadmins (username, password, secret) VALUES (?, ?, 's')",
                 ("raiz", orgs.hash_password("clave-raiz")))
    conn.execute("INSERT INTO organizations (name, admin_user, admin_password, secret) "
                 "VALUES ('Vieja', 'raiz', ?, 's2')", (orgs.hash_password("clave-org"),))
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    db.init_db()  # a second start leaves it alone
    conn = sqlite3.connect(path)
    rows = conn.execute("SELECT role, username, organization_id FROM users ORDER BY id").fetchall()
    assert rows == [("super", "raiz", None), ("org_admin", "raiz_1", 1)]
    assert ("0001_users",) in conn.execute("SELECT version FROM schema_migrations").fetchall()
    with db.connect() as c:
        assert users.login(c, "raiz", "clave-raiz")["role"] == "super"
        assert users.login(c, "raiz_1", "clave-org")["role"] == "org_admin"


def test_a_failing_predeployment_file_changes_nothing(tmp_path, monkeypatch):
    from app import migrate
    folder = tmp_path / "sql"
    folder.mkdir()
    (folder / "0001_ok.sql").write_text("CREATE TABLE uno (x INTEGER);")
    (folder / "0002_bad.sql").write_text("CREATE TABLE dos (x INTEGER); SELECT * FROM nada;")
    monkeypatch.setattr(migrate, "FOLDER", folder)
    import sqlite3
    conn = sqlite3.connect(tmp_path / "m.db")
    with pytest.raises(sqlite3.OperationalError):
        migrate.apply(conn, log=lambda m: None)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "uno" in tables and "dos" not in tables
    assert migrate.applied(conn) == {"0001_ok"}


def test_player_password_enters_its_organization(with_players):
    with_players.cookies.delete("org")
    r = with_players.post("/login", data={"password": "jugamos", "next": "/"})
    assert str(r.url).endswith("/tournaments/1") and "🏢 Club" in r.text


def test_first_organization_adopts_existing_data(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE players (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
        CREATE TABLE tournaments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            held_on DATE NOT NULL CHECK (held_on IS date(held_on)));
        INSERT INTO players (name) VALUES ('A'), ('B'), ('C'), ('D');
        INSERT INTO tournaments (name, held_on) VALUES ('Vieja', '2026-10-01');
    """)
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    assert orgs.main(["create", "Primera", "primera", "clave-uno"]) == 0
    assert orgs.main(["create", "Otra", "otra", "x"]) == 0
    with db.connect() as conn:
        assert [r[0] for r in conn.execute("SELECT organization_id FROM players")] == [1] * 4
        assert conn.execute("SELECT organization_id FROM tournaments").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        org = conn.execute("SELECT * FROM organizations WHERE id = 1").fetchone()
        assert org["admin_password"] != "clave-uno"
        assert orgs.check_password("clave-uno", org["admin_password"])
        conn.execute("INSERT INTO players (organization_id, name) VALUES (2, 'A')")  # per org


def test_enter_page_lists_the_top_ten_organizations(league):
    with db.connect() as conn:
        for i in range(11):
            orgs.create_org(conn, f"Org {i:02d}", f"admin{i}", "x")
    league.cookies.delete("org")
    page = league.get("/enter").text
    names = re.findall(r'class="org-pick"><span>🏢 ([^<]+)</span>', page)
    assert names[0] == "Club" and len(names) == 10  # the most tournaments first, then by name
    assert "Org 09" not in names and "Org 08" in names
    r = league.post("/enter", data={"name": "Club", "next": "/"})
    assert "Liga Amigos" in r.text


def test_admins_manage_their_players_accounts(league):
    with db.connect() as conn:
        juli = users.create_user(conn, "player", "juli", "clave-larga", email="juli@example.com")
        users.link_player(conn, juli, 1)  # Ana
        orgs.create_org(conn, "Otro club", "otro", "clave")
        stranger = users.create_user(conn, "player", "lejos", "clave-larga", email="l@example.com")
    page = league.get("/users").text
    assert "juli" in page and "lejos" not in page and "Ana" in page
    assert league.get(f"/users/{stranger}").status_code == 404  # not this organization's
    # Edit details; taken usernames and emails are refused.
    league.post(f"/users/{juli}", data={"username": "juli", "email": "nuevo@example.com",
                                        "first_name": "Juliana", "last_name": "Pérez",
                                        "display_name": "Juli"})
    assert "nuevo@example.com" in league.get(f"/users/{juli}").text
    r = league.post(f"/users/{juli}", data={"username": "admin", "email": "x@example.com"})
    assert "That username is taken" in r.text
    r = league.post(f"/users/{juli}", data={"username": "juli", "email": ""})
    assert "Players need an email" in r.text
    # A new password logs the account out and lets it in with the new one.
    other = TestClient(app)
    other.cookies.set("lang", "en")
    other.post("/login", data={"username": "juli", "password": "clave-larga", "role": "account"})
    assert other.cookies.get("user")
    league.post(f"/users/{juli}/password", data={"password": "otra-clave"})
    with db.connect() as conn:
        assert users.login(conn, "nuevo@example.com", "otra-clave")
        assert auth_user_from(other) is None
    # Unlink and link the player.
    league.post(f"/users/{juli}/unlink")
    with db.connect() as conn:
        assert conn.execute("SELECT user_id FROM players WHERE id = 1").fetchone()[0] is None
    league.post(f"/users/{juli}/link", data={"player_id": 2})
    assert "Account" in league.get("/players/2").text
    assert "Guest player" in league.get("/players/1").text
    # Only super admins change roles.
    assert league.post(f"/users/{juli}/role", data={"role": "super"},
                       follow_redirects=False).headers["location"].startswith("/login")


def auth_user_from(client):
    """The account a test client's cookie logs in, or None."""
    from app import auth
    user_id, _, token = client.cookies.get("user", "").partition(".")
    with db.connect() as conn:
        user = users.get(conn, int(user_id)) if user_id.isdigit() else None
    return user if user and auth.user_cookie(user) == f"{user_id}.{token}" else None


# --- From guest to account ------------------------------------------------------------

def test_tournament_password_offers_an_account_or_guest(with_players):
    r = with_players.post("/login", data={"password": "jugamos", "role": "player"})
    assert "/welcome?t=1" in str(r.url)
    assert "Create account" in r.text and "Continue as a guest" in r.text
    assert 'href="/tournaments/1"' in r.text  # the guest carries on as before
    # Without the tournament's password there's nothing to claim.
    with_players.cookies.delete("player_1")
    r = with_players.get("/signup?t=1", follow_redirects=False)
    assert r.headers["location"].startswith("/login")


def signup(client, **form):
    data = {"t": 1, "who": "1", "first_name": "Ana", "last_name": "López",
            "display_name": "Ana L", "username": "analo", "email": "ana@example.com",
            "password": "clave-larga", "password2": "clave-larga", **form}
    return client.post("/signup", data=data)


def test_signup_claims_a_guest_player(with_players):
    c = with_players
    c.post("/login", data={"password": "jugamos", "role": "player"})
    assert "Ana" in c.get("/signup?t=1").text
    assert "at least 8" in signup(c, password="corta", password2="corta").text
    assert "don't match" in signup(c, password2="otra-clave").text
    assert "That player already exists" in signup(c, display_name="Bea").text  # another player's name
    r = signup(c)
    assert str(r.url).endswith("/me") and "Ana L" in r.text and "Liga Amigos" in r.text
    assert "My sets to play" in r.text and "Ana L / Bea" in r.text  # a pending set
    with db.connect() as conn:
        ana = conn.execute("SELECT * FROM players WHERE id = 1").fetchone()
        assert ana["name"] == "Ana L" and ana["user_id"] is not None
    # The account scores its tournament without the tournament password.
    c.cookies.delete("player_1")
    r = c.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "4"},
               follow_redirects=False)
    assert r.status_code == 303 and not r.headers["location"].startswith("/login")
    # Nobody else can claim Ana, and the username and email are taken.
    c.post("/logout")
    c.post("/login", data={"password": "jugamos", "role": "player"})
    assert "Ana L" not in c.get("/signup?t=1").text.split("Who are you")[1].split("</select>")[0]
    r = signup(c, who="1", username="otra", email="otra@example.com", display_name="Otra")
    assert r.status_code == 400 and "Choose who you are" in r.text
    r = signup(c, who="2", username="ANALO", email="b@example.com", display_name="Bea")
    assert "That username is taken" in r.text
    r = signup(c, who="2", username="bea", email="ANA@example.com", display_name="Bea")
    assert "already an account with that email" in r.text


def test_signup_as_a_new_player_joins_the_tournament(with_players):
    c = with_players
    c.post("/login", data={"password": "jugamos", "role": "player"})
    r = signup(c, who="new", display_name="Zoe", username="zoe", email="zoe@example.com")
    assert str(r.url).endswith("/me")
    with db.connect() as conn:
        zoe = conn.execute("SELECT * FROM players WHERE name = 'Zoe'").fetchone()
        assert zoe["user_id"] and conn.execute(
            "SELECT 1 FROM tournament_players WHERE tournament_id = 1 AND player_id = ?",
            (zoe["id"],)).fetchone()


def test_an_existing_account_links_its_player(with_players):
    c = with_players
    with db.connect() as conn:
        users.create_user(conn, "player", "bea", "clave-larga", email="bea@example.com",
                          display_name="Bea B")
    c.post("/login", data={"password": "jugamos", "role": "player"})
    c.post("/login", data={"username": "bea@example.com", "password": "clave-larga",
                           "role": "account"})
    r = c.get("/welcome?t=1")
    assert "Link your player" in r.text
    r = c.post("/welcome/link", data={"t": 1, "player_id": 2})
    assert str(r.url).endswith("/me") and "Liga Amigos" in r.text
    with db.connect() as conn:
        assert conn.execute("SELECT name FROM players WHERE id = 2").fetchone()[0] == "Bea B"


def test_the_profile_edits_details_and_password(with_players):
    c = with_players
    c.post("/login", data={"password": "jugamos", "role": "player"})
    signup(c)
    r = c.post("/me", data={"username": "analo", "email": "ana@example.com",
                            "first_name": "Ana", "last_name": "López", "display_name": "Bea"})
    assert "That player already exists" in r.text  # Bea is another player's name
    r = c.post("/me", data={"username": "analo", "email": "ana@example.com",
                            "first_name": "Ana", "last_name": "López", "display_name": "Anita"})
    assert "Saved" in r.text and "👤 Anita" in r.text
    with db.connect() as conn:
        assert conn.execute("SELECT name FROM players WHERE id = 1").fetchone()[0] == "Anita"
    r = c.post("/me/password", data={"current": "nope", "password": "nueva-clave",
                                     "password2": "nueva-clave"})
    assert "Wrong password" in r.text or "wrong" in r.text.lower()
    r = c.post("/me/password", data={"current": "clave-larga", "password": "nueva-clave",
                                     "password2": "nueva-clave"})
    assert "Saved" in r.text  # still logged in, with the new cookie
    c.post("/logout")
    r = c.post("/login", data={"username": "analo", "password": "nueva-clave", "role": "account"})
    assert str(r.url).endswith("/me")


def test_an_account_joins_its_duplicate_player(with_players):
    c = with_players
    with db.connect() as conn:  # Elena (5) is Ana entered again, with a set of her own
        conn.execute("INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, team_a_games, "
                     "team_b_games, winner) VALUES (1, 2, 5, 6, 7, 8, 6, 2, 'A')")
        conn.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (1, 5)")
    c.post("/login", data={"password": "jugamos", "role": "player"})
    signup(c)  # the account is Ana (1)
    r = c.get("/welcome?t=1")
    assert "Is this you too?" in r.text and "Elena" in r.text
    # Bea played in a set with Ana: a different person.
    r = c.post("/welcome/link", data={"t": 1, "player_id": 2, "merge": "1"})
    assert "played in the same set" in r.text
    r = c.post("/welcome/link", data={"t": 1, "player_id": 5, "merge": "1"})
    assert str(r.url).endswith("/me")
    with db.connect() as conn:
        assert conn.execute("SELECT 1 FROM players WHERE id = 5").fetchone() is None
        assert conn.execute("SELECT a1 FROM matches WHERE court = 2").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM tournament_players WHERE player_id = 1 "
                            "AND tournament_id = 1").fetchone()[0] == 1
    # Without asking to merge, a second player in the organization is refused.
    r = c.post("/welcome/link", data={"t": 1, "player_id": 6})
    assert "already has a player in this organization" in r.text


def test_an_admin_joins_duplicate_players(client, league):
    with db.connect() as conn:
        uid = users.create_user(conn, "player", "anita", "clave-larga", email="a@example.com")
        users.link_player(conn, uid, 1)
    r = client.get(f"/users/{uid}")
    assert "Is this you too?" in r.text
    r = client.post(f"/users/{uid}/link", data={"player_id": 5, "merge": "1"})
    with db.connect() as conn:
        assert conn.execute("SELECT 1 FROM players WHERE id = 5").fetchone() is None
        assert conn.execute("SELECT user_id FROM players WHERE id = 1").fetchone()[0] == uid


def test_merging_needs_the_same_organization(client, league):
    with db.connect() as conn:
        other = orgs.create_org(conn, "Otra", "otra-admin", "secreto")
        far = conn.execute("INSERT INTO players (organization_id, name) VALUES (?, 'Ana')",
                           (other,)).lastrowid
        with pytest.raises(users.UserError, match="err_merge_invalid"):
            users.merge_players(conn, 1, far)
        # One account, one player in each organization: no merge needed.
        uid = users.create_user(conn, "player", "ana", "clave-larga", email="ana@example.com")
        assert users.link_player(conn, uid, 1) == 1
        assert users.link_player(conn, uid, far) == far


def test_standings_show_display_name_and_username(with_players):
    c = with_players
    c.post("/login", data={"password": "jugamos", "role": "player"})
    signup(c)
    c.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "4"})
    assert "Ana L <span class=\"username\">(analo)</span>" in c.get("/tournaments/1").text
    assert "(analo)" in c.get("/").text
    assert "(bea)" not in c.get("/").text  # guests show just their name


def test_the_profile_adds_up_every_organization(with_players):
    c = with_players
    c.post("/login", data={"password": "jugamos", "role": "player"})
    signup(c)
    c.post("/matches/1/score", data={"team_a_games": "6", "team_b_games": "4"})
    r = c.get("/me")
    assert "All my padel" in r.text
    career = r.text.split("All my padel")[1].split("</div>\n</div>")[0]
    assert "<strong>1</strong><span>🎾 Sets</span>" in career
    assert "<strong>100%</strong>" in career


def test_phones_get_a_menu_button(client):
    r = client.get("/")
    assert 'id="menu-toggle"' in r.text and 'for="menu-toggle"' in r.text
    assert r.text.index("menu-panel") < r.text.index('class="tabbar"')


def test_the_profile_needs_an_account(client):
    client.cookies.delete("user")
    assert client.get("/me", follow_redirects=False).headers["location"].startswith("/login")


# --- Player statistics -------------------------------------------------------------------

def a_set(a1, a2, b1, b2, ga, gb, played_on="2026-10-01"):
    names = {i: f"P{i}" for i in range(1, 9)}
    return {"a1_id": a1, "a1": names[a1], "a2_id": a2, "a2": names[a2],
            "b1_id": b1, "b1": names[b1], "b2_id": b2, "b2": names[b2],
            "team_a_games": ga, "team_b_games": gb, "played_on": played_on,
            "winner": "A" if ga > gb else "B" if gb > ga else None}


def test_stats_streaks_partners_and_rivals():
    from app import stats
    sets = [a_set(1, 2, 3, 4, 6, 3), a_set(1, 2, 3, 4, 6, 4), a_set(1, 2, 5, 6, 6, 2),
            a_set(1, 3, 2, 4, 2, 6), a_set(4, 1, 2, 3, 1, 6), a_set(1, 2, 3, 4, 5, 5, "2026-11-02")]
    t = stats.totals(sets, 1)
    assert (t["played"], t["won"], t["lost"], t["tied"], t["win_pct"]) == (6, 3, 2, 1, 50)
    assert (t["games_for"], t["games_against"], t["diff"]) == (26, 26, 0)
    st = stats.streaks(sets, 1)
    assert (st["best_win"], st["worst_loss"], st["current"], st["current_len"]) == (3, 2, "T", 1)
    hl = stats.highlights(sets, 1)
    assert hl["most_partner"]["name"] == "P2" and hl["most_partner"]["played"] == 4
    assert hl["best_partner"]["name"] == "P2" and hl["best_partner"]["won"] == 3
    assert hl["worst_partner"] is None  # nobody with 3+ sets together and a loss
    assert hl["rival"]["name"] in ("P3", "P4") and hl["rival"]["faced"] == 4
    assert hl["nemesis"]["name"] in ("P2", "P3", "P4") and hl["nemesis"]["beat_me"] == 2
    assert stats.rolling_win_pct(sets, 1, window=2) == [100, 100, 100, 50, 0, 0]
    assert stats.by_month(sets) == [("2026-10", 5), ("2026-11", 1)]


def test_charts_escape_their_labels():
    from app import charts
    svg = charts.bar_chart([("<b>Ana</b>", 3)], "x")
    assert "<b>" not in svg and "&lt;b&gt;Ana&lt;/b&gt;" in svg
    assert "<svg" in charts.line_chart([1, 3, 2], "<i>", labels=["a", "b", "c"])
    assert charts.donut([("W", 0, "red")], "empty") == ""


def test_player_statistics_page(league):
    for sets in ROTATION:
        (a1, a2, b1, b2), ga, gb = sets
        league.post("/matches", data=set_form((a1, a2, b1, b2), ga, gb))
    r = league.get("/players/1/stats")
    assert r.status_code == 200 and "Statistics" in r.text and "<svg" in r.text
    assert "Most frequent partner" in r.text and "Win rate" in r.text
    assert "Statistics" in league.get("/players/1").text  # the tab on the summary
    assert "No sets played yet" in league.get("/players/8/stats").text


# --- Medals --------------------------------------------------------------------------------

def liga_set(*args, **kw):
    return {**a_set(*args, **kw), "rule_code": "liga_amigos"}


def day(md_id, court, sets_won, sets=3, place=None, absent=False):
    return {"id": md_id, "court": court, "sets": sets, "sets_won": sets_won, "place": place,
            "absent": absent}


def test_medals_are_computed_from_sets_and_tournaments():
    from app import medals
    sets = [liga_set(1, 2, 3, 4, 6, 0), liga_set(1, 3, 2, 4, 7, 6), liga_set(1, 4, 2, 3, 6, 1),
            liga_set(1, 2, 3, 4, 0, 6), {**a_set(1, 2, 3, 4, 21, 0), "rule_code": "americano"}]
    tournaments = [
        {"name": "Liga", "rule_code": "liga_amigos", "ended": 1, "position": 1,
         "last_position": 6, "players": 8, "matchdays": 3,
         "history": [day(1, 2, 3), day(2, 1, 3, place=1), day(3, 2, 0)]},
        {"name": "Abierta", "rule_code": "liga_amigos", "ended": 0, "position": 8,
         "last_position": 8, "players": 8, "matchdays": 2,
         "history": [day(4, 1, 1), day(5, 1, 0, absent=True)]},
        {"name": "Vieja", "rule_code": "manual", "ended": 1, "position": 6,
         "last_position": 6, "players": 6, "matchdays": 1, "history": [day(6, 1, 0, sets=1)]},
    ]
    got = medals.awards(sets, 1, tournaments)
    assert got["campeon"]["detail"] == ["Liga"]  # ended, 1st
    assert "subcampeon" not in got and got["farolillo"]["detail"] == ["Vieja"]  # ended, last
    assert got["asistencia"]["detail"] == ["Liga", "Vieja"]
    assert got["perfecta"]["count"] == 2 and got["jornada_negra"]["count"] == 1
    assert got["rey_pista"]["count"] == 1
    assert got["rosco"]["count"] == 1 and got["comio_rosco"]["count"] == 1  # not the 21-0
    assert got["infarto"]["count"] == 1 and got["muro"]["count"] == 2  # 6-0 and 6-1
    assert got["racha"]["tier"] == 1 and got["racha"]["value"] == 3  # 3 in a row: bronze
    assert "gafe" not in got and "veterano" not in got and "fantasma" not in got
    assert "escalador" not in got  # up once (2 -> 1), not 3 times
    assert medals.tier("veterano", 50) == 2 and medals.tier("gafe", 8) == 3


def test_medal_pages(league):
    for (a1, a2, b1, b2), ga, gb in ROTATION:
        league.post("/matches", data=set_form((a1, a2, b1, b2), ga, gb))
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 0))
    r = league.get("/players/1/medals")
    assert r.status_code == 200 and "Baker" in r.text and "Still to win" in r.text
    assert "/static/medals/rosco.svg" in r.text
    assert league.get("/static/medals/rosco.svg").status_code == 200
    r = league.get("/medals")
    assert "How to win it" in r.text and "Shame" in r.text
    assert r.text.count("medals/") >= 22  # every medal of the catalog, as an image
    assert "Ana" in r.text.split("Baker")[1].split("</tr>")[0]  # Ana holds the Baker


def test_tournament_page_shows_only_its_own_medals(league):
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 0))  # a 6-0 in tournament 1
    league.post("/tournaments", data={"name": "Copa", "held_on": "2026-11-01"})
    add_matchday(2, "2026-11-01")
    league.post("/matches", data=set_form((1, 2, 3, 4), 4, 6, matchday_id=2))
    one = league.get("/tournaments/1").text
    assert 'alt="Baker"' in one and 'alt="Ate a bagel"' in one  # in the standings table
    assert 'alt="Baker"' in league.get("/?tournament=1").text  # the home standings too
    two = league.get("/tournaments/2").text
    assert "Baker" not in two and "Ate a bagel" not in two


def test_health_reports_the_version_and_migrations(client):
    client.cookies.delete("org")  # works before entering an organization
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["version"] == "dev"
    assert {"0001_users", "0002_medals"} <= set(r.json()["migrations"])
