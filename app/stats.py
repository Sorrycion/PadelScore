"""A player's performance, from their played sets (pure functions, no database).

`sets` are rows like main.set_rows() gives (a1_id/a1 ... b2_id/b2, team_a_games,
team_b_games, winner, played_on), oldest first, played ones only.
"""
import math
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


def head_to_head(sets, pid, other):
    """The player against (and with) one other player: their sets as rivals (won, lost,
    tied, games) and as partners, the results against them oldest first, and every set
    the two played, newest first."""
    against = {"played": 0, "won": 0, "lost": 0, "tied": 0, "games_for": 0, "games_against": 0}
    together = {"played": 0, "won": 0, "lost": 0}
    form, both = [], []
    for s in sets:
        kind = outcome(s, pid)
        if other in (o for o, _ in opponents(s, pid)):
            mine, theirs = games(s, pid)
            against["played"] += 1
            against[{"W": "won", "L": "lost", "T": "tied"}[kind]] += 1
            against["games_for"] += mine
            against["games_against"] += theirs
            form.append(kind)
        elif partner(s, pid)[0] == other:
            together["played"] += 1
            together["won"] += kind == "W"
            together["lost"] += kind == "L"
        else:
            continue
        both.append(s)
    together["win_pct"] = (round(100 * together["won"] / together["played"])
                           if together["played"] else 0)
    return {"against": against, "together": together, "form": form, "sets": both[::-1]}


def player_rates(sets):
    """{player id: (sets won, sets played)} for everyone in these sets."""
    table = defaultdict(lambda: [0, 0])
    for s in sets:
        for team, keys in TEAMS.items():
            for key in keys:
                row = table[s[key + "_id"]]
                row[0] += s["winner"] == team
                row[1] += 1
    return {pid: tuple(row) for pid, row in table.items()}


def level(rates, pid):
    """A player's level: their share of sets won, smoothed as (won + 1) / (played + 2) so
    a newcomer starts at 50% and a few sets don't make 0% or 100%."""
    won, played = rates.get(pid, (0, 0))
    return (won + 1) / (played + 2)


def win_probability(rates, team, rivals):
    """The chance that `team` (two player ids) wins a set against `rivals`, from their
    records: each pair's level is the average of its two players', and the two levels
    are compared as odds (like a simple Elo): equal levels give 50%."""
    logit = lambda p: math.log(p / (1 - p))  # noqa: E731
    mine = sum(level(rates, p) for p in team) / len(team)
    theirs = sum(level(rates, p) for p in rivals) / len(rivals)
    return 1 / (1 + math.exp(logit(theirs) - logit(mine)))


def rolling_win_pct(sets, pid, window=10):
    """Win % over the last `window` sets, after each set."""
    out, wins = [], []
    for s in sets:
        wins.append(outcome(s, pid) == "W")
        recent = wins[-window:]
        out.append(round(100 * sum(recent) / len(recent)))
    return out


def season(results, standings, sets, liga=False):
    """A tournament's highlights for its summary page.

    results, standings: scoring.tournament_results() of the tournament; sets: its played
    sets, oldest first. Each highlight is None when nobody stands out (e.g. no sets).
    """
    plays = lambda s, pid: pid in (s["a1_id"], s["a2_id"], s["b1_id"], s["b2_id"])  # noqa: E731
    best = lambda rows, key: max(rows, key=lambda r: r[key], default=None)  # noqa: E731
    out = {}
    days = [{"id": r["id"], "name": r["name"], "points": pts, "number": n}
            for r in standings for n, pts in r["by_matchday"].items()]
    top_day = best(days, "points")
    out["best_day"] = top_day if top_day and top_day["points"] > 0 else None
    runs = [{"id": r["id"], "name": r["name"],
             "value": streaks([s for s in sets if plays(s, r["id"])], r["id"])["best_win"]}
            for r in standings]
    top_run = best(runs, "value")
    out["streak"] = top_run if top_run and top_run["value"] >= 2 else None
    pairs = defaultdict(lambda: {"won": 0, "played": 0})
    for s in sets:
        for team, (a, b) in TEAMS.items():
            key = tuple(sorted(((s[a + "_id"], s[a]), (s[b + "_id"], s[b]))))
            pairs[key]["played"] += 1
            pairs[key]["won"] += s["winner"] == team
    pair = max(pairs.items(), key=lambda kv: (kv[1]["won"], -kv[1]["played"]), default=None)
    out["pair"] = ({"players": [{"id": i, "name": n} for i, n in pair[0]], **pair[1]}
                   if pair and pair[1]["won"] >= 2 else None)
    for key, field in (("sets_won", "sets_won"), ("diff", "diff")):
        row = best(standings, field)
        out[key] = row if row and row[field] > 0 else None
    on_one = Counter()
    for md in results if liga else ():
        for r in md["courts"].get(1, []):
            if r["sets"] and not r["absent"]:
                on_one[(r["id"], r["name"])] += 1
    king = on_one.most_common(1)
    out["court1"] = ({"id": king[0][0][0], "name": king[0][0][1], "value": king[0][1]}
                     if king and len(results) > 1 else None)
    played_days = sum(1 for md in results if any(md["courts"].values()))
    out["ever_present"] = [r for r in standings
                           if played_days > 1 and r["played"] == played_days]
    return out


UPSET = 0.45     # winners who had less chance than this: 😱 La sorpresa
SAFE_BET = 0.70  # winners who had at least this: 🔮 Estaba cantado


def set_highlights(sets, rates):
    """A jornada's set medals (the 📄 jornada summary), from its played sets and
    everyone's record BEFORE it (player_rates of the earlier sets):

    - renido: the longest set (most games), when it was close (2 games or fewer apart);
    - parejo: the closest of the others (a tie or 1 game);
    - aplastante: the widest gap (3 games or more);
    - sorpresa: the winners with the lowest chance (under UPSET);
    - cantado: the winners with the highest chance (SAFE_BET or more).

    Returns [{"code", "set", "chance"}], chance being the winners' % before the set
    (None for a tie). The superlatives need two sets or more to compare."""
    played = [s for s in sets if s["team_a_games"] is not None]

    def total(s):
        return s["team_a_games"] + s["team_b_games"]

    def gap(s):
        return abs(s["team_a_games"] - s["team_b_games"])

    def chance(s):
        if s["winner"] is None:
            return None
        a = win_probability(rates, (s["a1_id"], s["a2_id"]), (s["b1_id"], s["b2_id"]))
        return a if s["winner"] == "A" else 1 - a

    def pct(s):
        c = chance(s)
        return None if c is None else round(100 * c)

    out = []
    if len(played) >= 2:
        close = [s for s in played if gap(s) <= 2]
        renido = max(close, key=lambda s: (total(s), -gap(s)), default=None)
        if renido:
            out.append({"code": "renido", "set": renido, "chance": pct(renido)})
        parejo = min([s for s in played if gap(s) <= 1 and s is not renido],
                     key=lambda s: (gap(s), -total(s)), default=None)
        if parejo:
            out.append({"code": "parejo", "set": parejo, "chance": pct(parejo)})
        wide = max(played, key=lambda s: (gap(s), -min(s["team_a_games"], s["team_b_games"])))
        if gap(wide) >= 3:
            out.append({"code": "aplastante", "set": wide, "chance": pct(wide)})
    decided = [s for s in played if s["winner"] is not None]
    upset = min(decided, key=chance, default=None)
    if upset and chance(upset) < UPSET:
        out.append({"code": "sorpresa", "set": upset, "chance": pct(upset)})
    sure = max(decided, key=chance, default=None)
    if sure and chance(sure) >= SAFE_BET:
        out.append({"code": "cantado", "set": sure, "chance": pct(sure)})
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
