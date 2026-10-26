import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.i18n import LANGS, TEXT
from app.main import app
from app.scoring import (ScoreError, check_set, court_moves, court_rotation, court_table,
                         next_courts, set_points, tournament_results)

NAMES = ["Ana", "Bea", "Carlos", "Diego", "Elena", "Fer", "Gabi", "Hugo"]
APP_DIR = Path(__file__).parent.parent / "app"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client using the English UI (most assertions below check English texts).
    No club password is set, so editing is open (as on a developer's machine)."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("PADELSCORE_EDIT_PASSWORD", raising=False)
    with TestClient(app) as c:
        c.cookies.set("lang", "en")
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
# Ana +3 (2 sets), Bea +1 (2), Carlos +5 (2), Diego -9 (0).
ROTATION = [((1, 2, 3, 4), 6, 4), ((1, 3, 2, 4), 6, 2), ((1, 4, 2, 3), 3, 6)]


def row(players, a, b, court=1):
    r = {"court": court, "team_a_games": a, "team_b_games": b, "winner": check_set(a, b)}
    for key, pid in zip(("a1", "a2", "b1", "b2"), players):
        r[key + "_id"], r[key] = pid, NAMES[pid - 1]
    return r


def standing_points(html, name):
    return int(re.search(rf">{name}</a></td>\s*<td class=\"pts\">(\d+)<", html).group(1))


@pytest.mark.parametrize("a,b,winner", [(6, 4, "A"), (7, 6, "A"), (4, 6, "B"),
                                        (3, 1, "A"), (2, 5, "B"), (9, 8, "A"),
                                        (4, 4, None), (0, 0, None)])
def test_check_set_accepts_any_score(a, b, winner):
    assert check_set(a, b) == winner


@pytest.mark.parametrize("a,b", [(-1, 6), (6, -2)])
def test_check_set_rejects_negative_games(a, b):
    with pytest.raises(ScoreError):
        check_set(a, b)


def test_set_points():
    assert set_points("A") == (9 + 1, 6)  # winners share 1st + 1 for the set; losers 2nd
    assert set_points("B") == (6, 9 + 1)
    assert set_points(None) == (9, 9)     # tied set: all four share 1st, no set won


def test_tied_set_gives_no_one_a_set():
    rows = court_table([row((1, 2, 3, 4), 4, 4)], position={})
    assert all(r["sets_won"] == 0 and r["diff"] == 0 and r["points"] == 9 for r in rows)


def test_short_and_tied_sets_can_be_saved(league):
    assert league.post("/matches", data=set_form((1, 2, 3, 4), 3, 1)).status_code == 200
    r = league.post("/matches", data=set_form((1, 3, 2, 4), 4, 4))
    assert r.status_code == 200 and "4-4" in r.text


def test_points_are_added_up_per_set():
    # Ana, Bea and Carlos each win 2 of their 3 sets: 10 + 10 + 6 = 26. Diego loses all
    # three: 6 * 3 = 18. Equal points are listed by games difference.
    rows = court_table([row(*s) for s in ROTATION], position={})
    assert [(r["name"], r["diff"], r["sets_won"], r["points"]) for r in rows] == [
        ("Carlos", 5, 2, 26), ("Ana", 3, 2, 26), ("Bea", 1, 2, 26), ("Diego", -9, 0, 18)]


def test_margin_and_court_do_not_change_points():
    sets = [row((1, 2, 3, 4), 3, 0, court=1), row((5, 6, 7, 8), 7, 6, court=4)]
    _, standings = tournament_results([{"number": 1, "sets": sets}])
    points = {r["name"]: r["points"] for r in standings}
    assert points == {"Ana": 10, "Bea": 10, "Elena": 10, "Fer": 10,
                      "Carlos": 6, "Diego": 6, "Gabi": 6, "Hugo": 6}


def test_ties_are_ordered_by_league_position_without_changing_points():
    sets = [row((1, 2, 3, 4), 6, 4), row((3, 4, 1, 2), 6, 4)]  # everyone 1 won, 1 lost
    rows = court_table(sets, position={4: 1, 3: 2})
    assert [r["name"] for r in rows][:2] == ["Diego", "Carlos"]  # order for court changes
    assert {r["points"] for r in rows} == {10 + 6}


def test_tournament_results_add_up_matchdays():
    md1 = {"number": 1, "sets": [row(*s) for s in ROTATION]}
    md2 = {"number": 2, "sets": [row(*s) for s in ROTATION]}
    results, standings = tournament_results([md1, md2])
    assert [(r["position"], r["name"], r["points"]) for r in standings] == [
        (1, "Ana", 52), (1, "Bea", 52), (1, "Carlos", 52), (4, "Diego", 36)]
    assert standings[0]["by_matchday"] == {1: 26, 2: 26}
    assert standings[0]["played"] == 2
    assert list(results[0]["courts"]) == [1]


def test_equal_points_share_a_standings_position():
    # Matchday 1: Ana & Bea beat Carlos & Diego 3-0 -> Ana 10, Bea 10, Carlos 6, Diego 6.
    _, standings = tournament_results([{"number": 1, "sets": [row((1, 2, 3, 4), 3, 0)]}])
    assert [(r["position"], r["points"]) for r in standings] == [(1, 10), (1, 10), (3, 6), (3, 6)]


def test_league_position_orders_ties_on_the_next_matchday():
    # After matchday 1 Diego leads Carlos; on matchday 2 everyone has the same result
    # and Diego, higher in the ranking, is listed first (court changes use this order).
    md1 = {"number": 1, "sets": [row((4, 1, 3, 2), 6, 0)]}
    md2 = {"number": 2, "sets": [row((1, 2, 3, 4), 6, 4), row((3, 4, 1, 2), 6, 4)]}
    results, _ = tournament_results([md1, md2])
    names = [r["name"] for r in results[1]["courts"][1]]
    assert names.index("Diego") < names.index("Carlos")
    assert {r["points"] for r in results[1]["courts"][1]} == {10 + 6}


def test_court_moves():
    top = court_table([row(*s) for s in ROTATION], position={})
    bottom = court_table([row(tuple(p + 4 for p in s[0]), s[1], s[2], court=2)
                          for s in ROTATION], position={})
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
    assert "Court 1" in page and "6-4" in page and "+5" in page

    standings = league.get("/tournaments/1").text
    assert standing_points(standings, "Carlos") == 26
    assert standing_points(standings, "Diego") == 18

    home = league.get("/").text
    assert "Liga Amigos" in home and home.index("Carlos") < home.index("Diego")

    # Edit the third set so Ana & Diego win it 6-3 instead of losing 3-6: Ana wins all 3.
    league.post("/matches/3", data=set_form((1, 4, 2, 3), 6, 3))
    assert standing_points(league.get("/tournaments/1").text, "Ana") == 30

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
    assert league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4, court=1)).status_code == 200
    assert league.post("/matches", data=set_form((1, 6, 7, 8), 6, 4, court=2)).status_code == 200
    # Ana is 1st on both courts: (9 + 1) twice, in one matchday.
    standings = league.get("/tournaments/1").text
    assert standing_points(standings, "Ana") == 20
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


def test_missing_pages_return_404(league):
    for url in ["/tournaments/99", "/matchdays/99", "/players/99", "/matches/99/edit"]:
        assert league.get(url).status_code == 404


def test_spanish_is_the_default_language(league):
    league.cookies.clear()
    home = league.get("/").text
    assert '<html lang="es">' in home and "Clasificación" in home and "Jornada 1" in home
    r = league.post("/matches", data=set_form((1, 1, 3, 4), 6, 4))
    assert "Elige cuatro jugadores diferentes." in r.text
    r = league.post("/tournaments", data={"name": "X", "held_on": "mañana"})
    assert "Ingresa una fecha válida." in r.text


def test_switch_language(league):
    league.cookies.clear()
    r = league.get("/lang/en?next=/tournaments/1")
    assert r.status_code == 200 and str(r.url).endswith("/tournaments/1")
    assert "Matchdays" in r.text and '<html lang="en">' in r.text
    r = league.get("/lang/es?next=/matches%3Fplayer%3D1")
    assert str(r.url).endswith("/matches?player=1") and "Todos los torneos" in r.text


@pytest.mark.parametrize("next_url", ["https://evil.example", "//evil.example", "/\\evil.example"])
def test_language_switch_only_redirects_within_the_site(client, next_url):
    r = client.get("/lang/es", params={"next": next_url}, follow_redirects=False)
    assert r.headers["location"] == "/"


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
def locked(league, monkeypatch):
    """The league, with a club password set and this browser not logged in."""
    monkeypatch.setenv("PADELSCORE_EDIT_PASSWORD", "secreto")
    monkeypatch.setattr("app.main.time.sleep", lambda s: None)  # skip the wrong-password delay
    league.cookies.delete("editor")
    return league


def test_viewing_needs_no_password(locked):
    for url in ["/", "/tournaments", "/tournaments/1", "/matchdays/1", "/players", "/matches", "/rules"]:
        assert locked.get(url).status_code == 200, url
    page = locked.get("/tournaments").text
    assert "Add tournament" not in page and "+ Courts" not in page and ">Log in<" in page


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
    r = locked.post("/login", data={"password": "secreto", "next": "/players"})
    assert r.status_code == 200 and str(r.url).endswith("/players") and "Add player" in r.text
    assert "Zed" in locked.post("/players", data={"name": "Zed"}).text
    assert locked.post("/matches", data=set_form((1, 2, 3, 4), 6, 4)).status_code == 200
    assert ">Log out<" in locked.get("/").text

    locked.post("/logout")
    r = locked.post("/players", data={"name": "Yan"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")


def test_changing_the_password_logs_everyone_out(locked, monkeypatch):
    locked.post("/login", data={"password": "secreto", "next": "/"})
    monkeypatch.setenv("PADELSCORE_EDIT_PASSWORD", "nuevo")
    assert locked.post("/players", data={"name": "Zed"}, follow_redirects=False).status_code == 303


def test_login_only_redirects_within_the_site(locked):
    r = locked.post("/login", data={"password": "secreto", "next": "https://evil.example"},
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
    assert '<link rel="stylesheet" href="/static/style.css">' in page
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
    assert standing_points(league.get("/tournaments/1").text, "Ana") == 10
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
    for match_id in range(1, 7):  # team A wins every set
        league.post(f"/matches/{match_id}/score", data={"team_a_games": "6", "team_b_games": "0"})
    # Court order after matchday 1: Ana, Bea, Carlos, Diego and Elena, Fer, Gabi, Hugo.
    new = "/tournaments/1/matchdays/new"
    page = league.get(new, params={"played_on": "2026-10-30"}).text
    assert "How many players move up and down" in page and court_count(page) == 0

    def suggested(move):
        page = league.get(new, params={"played_on": "2026-10-30", "move": move}).text
        assert "Suggested from matchday 1" in page and 'value="2026-10-30"' in page
        return [selected(c) for c in page.split("<template")[0]
                .split('<fieldset class="court-pick">')[1:]]

    # One moves: Diego down, Elena up. The best of court 1 and the last of court 2 stay.
    assert suggested(1) == [{"1", "2", "3", "5"}, {"4", "6", "7", "8"}]
    # Two move: Carlos and Diego down, Elena and Fer up.
    assert suggested(2) == [{"1", "2", "5", "6"}, {"3", "4", "7", "8"}]
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
    old = (db.SCHEMA.replace("team_a_games INTEGER,", "team_a_games INTEGER NOT NULL,")
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
    assert '<option value="1" selected>Liga de amigos score</option>' in page
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
    # Everyone else scores as usual.
    assert {r["id"]: r["points"] for r in rows if not r["absent"]} == {1: 26, 2: 26, 4: 18}


def test_mark_player_absent_on_a_matchday(league):
    for players, a, b in ROTATION:
        league.post("/matches", data=set_form(players, a, b))
    assert standing_points(league.get("/tournaments/1").text, "Carlos") == 26

    r = league.post("/matchdays/1/absent/3")
    assert r.status_code == 200 and ">Absent<" in r.text and "Mark present" in r.text
    assert standing_points(league.get("/tournaments/1").text, "Carlos") == 0
    assert standing_points(league.get("/tournaments/1").text, "Ana") == 26  # unchanged
    profile = league.get("/players/3").text
    assert ">Absent<" in profile and "0 matchdays played" in profile
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 3  # same sets

    league.post("/matchdays/1/absent/3")  # present again
    assert standing_points(league.get("/tournaments/1").text, "Carlos") == 26
    assert league.post("/matchdays/1/absent/8").status_code == 404  # Hugo isn't playing


def test_deleting_a_matchday_removes_its_absences(league):
    league.post("/matches", data=set_form((1, 2, 3, 4), 6, 4))
    league.post("/matchdays/1/absent/1")
    league.post("/matchdays/1/delete")
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM absences").fetchone()[0] == 0


def test_marking_absent_needs_the_password(locked):
    locked.cookies.delete("editor")
    r = locked.post("/matchdays/1/absent/1", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
