"""League scoring, following docs/REGLAMENTO.md.

A tournament (league) has matchdays (jornadas). On a matchday the players are split
into courts of four; each court plays three sets, every player partnering each of the
other three once.

Points are given per set, whatever the court: the two winners share 1st place (9) and
get 1 more for the set won (10 each); the two losers share 2nd place (6 each). In a
tied set all four share 1st (9 each, no set won). A player's matchday points are the
sum over their sets, and the tournament standings add up the matchdays. A set whose
games are not entered yet (pending) gives no points. A player marked absent on a
matchday keeps their place in the sets (a substitute plays for them) but scores 0:
a substitute can't earn points for the player they replace.

Americano and Mexicano tournaments are played in rounds of one match per court, to a
fixed number of points; each player scores the points their pair won (see rounds.py
for how the rounds are drawn).
"""
from functools import partial

PLACE_POINTS = (9, 6, 4, 3)
SET_WON_POINTS = 1


class ScoreError(ValueError):
    pass


def check_set(a: int, b: int) -> str | None:
    """Return the winner 'A' or 'B', or None for a tied set. Any score is allowed (a set
    may be cut short), as long as no team has negative games."""
    if a < 0 or b < 0:
        raise ScoreError("Games can't be negative.")
    if a == b:
        return None
    return "A" if a > b else "B"


def set_points(winner: str | None) -> tuple[int, int]:
    """Points for each player of team A and of team B from one set."""
    if winner is None:  # tied set: all four share 1st place
        return PLACE_POINTS[0], PLACE_POINTS[0]
    win, lose = PLACE_POINTS[0] + SET_WON_POINTS, PLACE_POINTS[1]
    return (win, lose) if winner == "A" else (lose, win)


def liga_points(m) -> tuple[int, int]:
    """Liga de amigos: points from the set's place (see set_points)."""
    return set_points(m["winner"])


def games_points(m) -> tuple[int, int]:
    """Americano / Mexicano: each player scores the points their pair won."""
    return m["team_a_games"], m["team_b_games"]


def is_played(m) -> bool:
    return m["team_a_games"] is not None


def court_rotation(players):
    """The three sets of a court of four, as ((a1, a2), (b1, b2)): every player
    partners each of the other three once."""
    p1, p2, p3, p4 = players
    return [((p1, p2), (p3, p4)), ((p1, p3), (p2, p4)), ((p1, p4), (p2, p3))]


def court_table(sets, position, absent=frozenset(), scorer=liga_points):
    """Add up each player's sets on one court on one matchday.

    sets: rows with a1_id/a1 ... b2_id/b2, team_a_games, team_b_games, winner.
    position: player id -> league position before this matchday.
    absent: ids of players absent that day; they score nothing and go last.
    scorer: a set row -> (points for each player of team A, of team B).
    Rows are ordered by points, then games difference, then league position (then
    name; the rules' coin toss on matchday 1 is done on court). The order only
    decides who changes court; it never changes anyone's points.
    Players of pending sets are listed too, with nothing added up yet.
    """
    stats = {}
    for m in sets:
        played = is_played(m)
        diff = m["team_a_games"] - m["team_b_games"] if played else 0
        pts_a, pts_b = scorer(m) if played else (0, 0)
        for side, d, pts in (("A", diff, pts_a), ("B", -diff, pts_b)):
            for key in (side.lower() + "1", side.lower() + "2"):
                r = stats.setdefault(m[key + "_id"], {
                    "id": m[key + "_id"], "name": m[key],
                    "points": 0, "diff": 0, "sets": 0, "sets_won": 0,
                    "absent": m[key + "_id"] in absent,
                })
                if not played:
                    continue
                r["sets"] += 1
                if r["absent"]:
                    continue
                r["points"] += pts
                r["diff"] += d
                r["sets_won"] += m["winner"] == side
    unranked = len(position) + 1
    return sorted(stats.values(), key=lambda r: (
        r["absent"], -r["points"], -r["diff"], position.get(r["id"], unranked), r["name"].lower()))


def _standings(rows, by_diff=False):
    """Order by points and number positions; equal points share a position (1, 1, 3).
    The Liga rules settle ties for prize positions with a sudden-death game on court;
    Americano / Mexicano (by_diff) list ties by points difference, then wins."""
    rows = sorted(rows, key=lambda r: (-r["points"], -r["diff"] if by_diff else 0,
                                       -r["sets_won"] if by_diff else 0, r["name"].lower()))
    for i, r in enumerate(rows):
        r["position"] = rows[i - 1]["position"] if i and r["points"] == rows[i - 1]["points"] else i + 1
    return rows


def tournament_results(matchdays, scorer=liga_points):
    """Score a whole tournament.

    matchdays: in playing order, each a dict with "number", "sets" (as for
    court_table, plus "court") and optionally "absent" (player ids).
    Returns (matchdays with "courts": {court: player rows}, standings).
    Standings rows: id, name, position, points, diff, sets_won, played (matchdays)
    and by_matchday (number -> points that day).
    """
    by_diff = scorer is games_points
    totals = {}
    results = []
    for md in matchdays:
        position = {r["id"]: r["position"] for r in _standings(totals.values(), by_diff)}
        by_court = {}
        for m in md["sets"]:
            by_court.setdefault(m["court"], []).append(m)
        absent = frozenset(md.get("absent", ()))
        courts = {c: court_table(s, position, absent, scorer)
                  for c, s in sorted(by_court.items())}

        for rows in courts.values():
            for r in rows:  # a player on two courts adds up both
                if not r["sets"]:  # only pending sets so far
                    continue
                t = totals.setdefault(r["id"], {"id": r["id"], "name": r["name"], "points": 0,
                                                "diff": 0, "sets_won": 0, "played": 0,
                                                "by_matchday": {}})
                if md["number"] not in t["by_matchday"]:
                    t["by_matchday"][md["number"]] = 0
                    t["played"] += not r["absent"]
                t["by_matchday"][md["number"]] += r["points"]
                t["points"] += r["points"]
                t["sets_won"] += r["sets_won"]
                t["diff"] += r["diff"]
        results.append({**md, "courts": courts})
    return results, _standings(totals.values(), by_diff)


def court_moves(courts, count):
    """Suggest who changes court after a matchday. Court 1 is the top court.

    The best `count` players of each court move up a court and the worst `count`
    move down (no one goes above court 1 or below the last court).
    """
    numbers = sorted(courts)
    moves = []
    for i, court in enumerate(numbers):
        names = [r["name"] for r in courts[court]]
        up = names[:count] if i > 0 else []
        down = []
        if i < len(numbers) - 1:
            down = [n for n in names if n not in up][-count:]
        moves.append({
            "court": court,
            "up": up, "up_to": numbers[i - 1] if i > 0 else None,
            "down": down, "down_to": numbers[i + 1] if i < len(numbers) - 1 else None,
        })
    return moves


def next_courts(courts, count):
    """Players per court for the next matchday, after the moves of court_moves().
    Returns {court: [player ids]}: those who stay, then those who arrive."""
    numbers = sorted(courts)
    new = {c: [] for c in numbers}
    for i, court in enumerate(numbers):
        ids = [r["id"] for r in courts[court]]
        up = ids[:count] if i > 0 else []
        down = [p for p in ids if p not in up][-count:] if i < len(numbers) - 1 else []
        new[court] = [p for p in ids if p not in up and p not in down] + new[court]
        if up:
            new[numbers[i - 1]] += up
        if down:
            new[numbers[i + 1]] += down
    return new


# Scoring per rule type (rule_types.code).
SCORING = {
    "liga_amigos": tournament_results,
    "americano": partial(tournament_results, scorer=games_points),
    "mexicano": partial(tournament_results, scorer=games_points),
    "manual": tournament_results,  # sets made by hand, Liga de amigos points
}
# Rule types played in rounds of one match per court, to a number of points.
ROUND_MODES = {"americano", "mexicano"}
