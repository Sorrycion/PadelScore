"""A player's performance, from their played sets (pure functions, no database).

`sets` are rows like main.set_rows() gives (a1_id/a1 ... b2_id/b2, team_a_games,
team_b_games, winner, played_on), oldest first, played ones only.
"""
from collections import Counter, defaultdict

TEAMS = {"A": ("a1", "a2"), "B": ("b1", "b2")}
MIN_PARTNER_SETS = 3  # a "best" or "worst" partner needs this many sets together


def side(s, pid):
    """'A' or 'B': the player's team in this set."""
    return "A" if pid in (s["a1_id"], s["a2_id"]) else "B"


def outcome(s, pid):
    """'W', 'L' or 'T' (a tied set) for the player."""
    if s["winner"] is None:
        return "T"
    return "W" if s["winner"] == side(s, pid) else "L"


def partner(s, pid):
    a, b = TEAMS[side(s, pid)]
    other = b if s[a + "_id"] == pid else a
    return s[other + "_id"], s[other]


def opponents(s, pid):
    return [(s[k + "_id"], s[k]) for k in TEAMS["B" if side(s, pid) == "A" else "A"]]


def games(s, pid):
    """(games for, games against) of the player's team."""
    a, b = s["team_a_games"], s["team_b_games"]
    return (a, b) if side(s, pid) == "A" else (b, a)


def totals(sets, pid):
    results = Counter(outcome(s, pid) for s in sets)
    won_games = sum(games(s, pid)[0] for s in sets)
    lost_games = sum(games(s, pid)[1] for s in sets)
    played = len(sets)
    return {"played": played, "won": results["W"], "lost": results["L"], "tied": results["T"],
            "win_pct": round(100 * results["W"] / played) if played else 0,
            "games_for": won_games, "games_against": lost_games, "diff": won_games - lost_games}


def streaks(sets, pid):
    """The current run (outcome and length), the longest winning and losing runs."""
    best = {"W": 0, "L": 0}
    run_kind, run = None, 0
    for s in sets:
        kind = outcome(s, pid)
        run = run + 1 if kind == run_kind else 1
        run_kind = kind
        if kind in best:
            best[kind] = max(best[kind], run)
    return {"current": run_kind, "current_len": run, "best_win": best["W"], "worst_loss": best["L"]}


def partners(sets, pid):
    """Everyone the player partnered: sets together, won and lost; most played first."""
    table = defaultdict(lambda: {"played": 0, "won": 0, "lost": 0})
    for s in sets:
        row = table[partner(s, pid)]
        kind = outcome(s, pid)
        row["played"] += 1
        row["won"] += kind == "W"
        row["lost"] += kind == "L"
    rows = [{"id": k[0], "name": k[1], **v} for k, v in table.items()]
    return sorted(rows, key=lambda r: (-r["played"], r["name"]))


def opponents_table(sets, pid):
    """Everyone the player faced: sets against, sets they beat the player, sets the
    player beat them; most faced first."""
    table = defaultdict(lambda: {"faced": 0, "beat_me": 0, "i_beat": 0})
    for s in sets:
        kind = outcome(s, pid)
        for o in opponents(s, pid):
            row = table[o]
            row["faced"] += 1
            row["beat_me"] += kind == "L"
            row["i_beat"] += kind == "W"
    rows = [{"id": k[0], "name": k[1], **v} for k, v in table.items()]
    return sorted(rows, key=lambda r: (-r["faced"], r["name"]))


def top(rows, key, minimum=1, where=lambda r: True):
    """The row with the highest `key` (at least `minimum`), or None."""
    rows = [r for r in rows if where(r) and r[key] >= minimum]
    return max(rows, key=lambda r: (r[key], -r.get("played", r.get("faced", 0)))) if rows else None


def highlights(sets, pid):
    """The dashboard's leaderboard cards."""
    mates, rivals = partners(sets, pid), opponents_table(sets, pid)
    enough = lambda r: r["played"] >= MIN_PARTNER_SETS  # noqa: E731
    return {
        "most_partner": mates[0] if mates else None,
        "best_partner": top(mates, "won", where=enough),
        "worst_partner": top(mates, "lost", where=enough),
        "rival": rivals[0] if rivals else None,
        "nemesis": top(rivals, "beat_me"),
        "victim": top(rivals, "i_beat"),
    }


def rolling_win_pct(sets, pid, window=10):
    """Win % over the last `window` sets, after each set."""
    out, wins = [], []
    for s in sets:
        wins.append(outcome(s, pid) == "W")
        recent = wins[-window:]
        out.append(round(100 * sum(recent) / len(recent)))
    return out


def by_month(sets):
    """[(YYYY-MM, sets played)] in order."""
    counts = Counter(str(s["played_on"])[:7] for s in sets)
    return sorted(counts.items())


def dashboard(sets, pid):
    """Everything the statistics page shows."""
    return {"totals": totals(sets, pid), "streaks": streaks(sets, pid),
            "highlights": highlights(sets, pid), "partners": partners(sets, pid),
            "opponents": opponents_table(sets, pid),
            "form": [outcome(s, pid) for s in sets][-30:],
            "rolling": rolling_win_pct(sets, pid), "months": by_month(sets)}
