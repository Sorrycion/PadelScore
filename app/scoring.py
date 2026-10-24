"""League scoring, following docs/REGLAMENTO.md.

A tournament (league) has matchdays (jornadas). On a matchday the players are split
into courts of four; each court plays three sets, every player partnering each of the
other three once.

Points are given per set, whatever the court: the two winners share 1st place (9) and
get 1 more for the set won (10 each); the two losers share 2nd place (6 each). In a
tied set all four share 1st (9 each, no set won). A player's matchday points are the
sum over their sets, and the tournament standings add up the matchdays.
"""

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


def court_table(sets, position):
    """Add up each player's sets on one court on one matchday.

    sets: rows with a1_id/a1 ... b2_id/b2, team_a_games, team_b_games, winner.
    position: player id -> league position before this matchday.
    Rows are ordered by points, then games difference, then league position (then
    name; the rules' coin toss on matchday 1 is done on court). The order only
    decides who changes court; it never changes anyone's points.
    """
    stats = {}
    for m in sets:
        diff = m["team_a_games"] - m["team_b_games"]
        pts_a, pts_b = set_points(m["winner"])
        for side, d, pts in (("A", diff, pts_a), ("B", -diff, pts_b)):
            for key in (side.lower() + "1", side.lower() + "2"):
                r = stats.setdefault(m[key + "_id"], {
                    "id": m[key + "_id"], "name": m[key],
                    "points": 0, "diff": 0, "sets": 0, "sets_won": 0,
                })
                r["points"] += pts
                r["diff"] += d
                r["sets"] += 1
                r["sets_won"] += m["winner"] == side
    unranked = len(position) + 1
    return sorted(stats.values(), key=lambda r: (
        -r["points"], -r["diff"], position.get(r["id"], unranked), r["name"].lower()))


def _standings(rows):
    """Order by points and number positions; equal points share a position (1, 1, 3).
    The rules settle ties for prize positions with a sudden-death game on court."""
    rows = sorted(rows, key=lambda r: (-r["points"], r["name"].lower()))
    for i, r in enumerate(rows):
        r["position"] = rows[i - 1]["position"] if i and r["points"] == rows[i - 1]["points"] else i + 1
    return rows


def tournament_results(matchdays):
    """Score a whole tournament.

    matchdays: in playing order, each a dict with "number" and "sets" (as for
    court_table, plus "court").
    Returns (matchdays with "courts": {court: player rows}, standings).
    Standings rows: id, name, position, points, sets_won, played (matchdays) and
    by_matchday (number -> points that day).
    """
    totals = {}
    results = []
    for md in matchdays:
        position = {r["id"]: r["position"] for r in _standings(totals.values())}
        by_court = {}
        for m in md["sets"]:
            by_court.setdefault(m["court"], []).append(m)
        courts = {c: court_table(s, position) for c, s in sorted(by_court.items())}

        for rows in courts.values():
            for r in rows:  # a player on two courts adds up both
                t = totals.setdefault(r["id"], {"id": r["id"], "name": r["name"], "points": 0,
                                                "sets_won": 0, "played": 0, "by_matchday": {}})
                if md["number"] not in t["by_matchday"]:
                    t["by_matchday"][md["number"]] = 0
                    t["played"] += 1
                t["by_matchday"][md["number"]] += r["points"]
                t["points"] += r["points"]
                t["sets_won"] += r["sets_won"]
        results.append({**md, "courts": courts})
    return results, _standings(totals.values())


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
