import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.i18n import LANGS, TEXT
from app.main import app
from app.scoring import (ScoreError, check_set, court_moves, court_table, set_points,
                         tournament_results)

NAMES = ["Ana", "Bea", "Carlos", "Diego", "Elena", "Fer", "Gabi", "Hugo"]
APP_DIR = Path(__file__).parent.parent / "app"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client using the English UI (most assertions below check English texts)."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        c.cookies.set("lang", "en")
        yield c


@pytest.fixture
def league(client):
    """Players 1-8, tournament 1 and its matchday 1."""
    for name in NAMES:
        client.post("/players", data={"name": name})
    client.post("/tournaments", data={"name": "Liga Amigos", "held_on": "2026-10-23"})
    client.post("/tournaments/1/matchdays", data={"played_on": "2026-10-23"})
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
    r = client.post("/tournaments", data={"name": "Liga", "held_on": held_on})
    assert "Enter a valid date" in r.text and "Liga" not in r.text


@pytest.mark.parametrize("played_on", ["", "next friday", "2026-02-30"])
def test_matchday_date_must_be_valid(league, played_on):
    r = league.post("/tournaments/1/matchdays", data={"played_on": played_on})
    assert "Enter a valid date" in r.text and "Matchday 2<" not in r.text


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
    league.post("/tournaments/1/matchdays", data={"played_on": "2026-10-30"})  # matchday 2
    league.post("/tournaments/1/matchdays", data={"played_on": "2026-10-16"})  # 3, but older
    form = league.get("/matches/new").text
    assert re.search(r'<option value="2" selected>[^<]*Matchday 2', form)
    assert form.count(" selected>") == 1
    # A link naming a matchday still wins.
    assert re.search(r'<option value="1" selected>', league.get("/matches/new?matchday=1").text)
