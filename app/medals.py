"""Who has which medal (catalog: table medal_types, sql/predeployment/0002_medals.sql).

Computed live from the player's played sets and tournament rows, so medals fix
themselves when a result is corrected. Podium and last place only count ended
tournaments. Medals about games (6-0, 7-6...) only count Liga and Manual sets: in
Americano and Mexicano the "games" are points to 21 or so.
"""
from collections import Counter

from . import stats

GAME_RULES = ("liga_amigos", "manual")  # rule types whose sets count games
LIGA = "liga_amigos"
TIERS = {"racha": (3, 5, 10), "gafe": (3, 5, 8), "veterano": (25, 50, 100)}
# Medals for a total reaching a threshold (counted across tournaments).
THRESHOLDS = {"fantasma": 2, "escalador": 3, "paracaidas": 3}


def tier(code, value):
    """0 (not earned), 1 bronze, 2 silver or 3 gold."""
    return sum(value >= t for t in TIERS[code])


def court_moves(history):
    """(times up, times down) between consecutive Liga matchdays (court 1 is the top)."""
    up = down = 0
    for before, after in zip(history, history[1:]):
        if after["court"] < before["court"]:
            up += 1
        elif after["court"] > before["court"]:
            down += 1
    return up, down


def awards(sets, pid, tournaments):
    """{code: {"count": n, "tier": 0-3, "detail": [names...]}} for every medal earned.

    sets: the player's played sets, oldest first (as stats.py).
    tournaments: main.player_tournaments() rows (position, last_position, players,
    ended, rule_code, matchdays and history: the player's row on each matchday).
    """
    won, totals = Counter(), Counter()
    detail = {}

    def give(code, n=1, what=None):
        won[code] += n
        if what:
            detail.setdefault(code, []).append(what)

    for t in tournaments:
        last = t["players"] >= 4 and t["position"] == t["last_position"]
        if t["ended"] and t["position"]:
            for code, place in (("campeon", 1), ("subcampeon", 2), ("tercero", 3)):
                if t["position"] == place:
                    give(code, what=t["name"])
            if last:
                give("farolillo", what=t["name"])
        days = {h["id"]: h for h in t["history"]}  # one row per matchday (first court)
        if t["ended"] and t["matchdays"] and len(days) == t["matchdays"] \
                and not any(h["absent"] for h in t["history"]):
            give("asistencia", what=t["name"])
        totals["fantasma"] += sum(1 for h in t["history"] if h["absent"])
        if t["rule_code"] == LIGA:
            for h in t["history"]:
                if h["absent"] or h["sets"] < 3:
                    continue
                if h["sets_won"] == h["sets"]:
                    give("perfecta")
                if h["sets_won"] == 0:
                    give("jornada_negra")
                if h["court"] == 1 and h.get("place") == 1:
                    give("rey_pista")
            up, down = court_moves(list(days.values()))
            totals["escalador"] += up
            totals["paracaidas"] += down

    for s in sets:
        if s["rule_code"] not in GAME_RULES:
            continue
        mine, theirs = stats.games(s, pid)
        if (mine, theirs) == (6, 0):
            give("rosco")
        if (mine, theirs) == (0, 6):
            give("comio_rosco")
        if mine > theirs and theirs <= 1:
            give("muro")
        if (mine, theirs) == (7, 6):
            give("infarto")

    for code, minimum in THRESHOLDS.items():
        if totals[code] >= minimum:
            give(code, totals[code])

    streak = stats.streaks(sets, pid)
    hl = stats.highlights(sets, pid)
    gold_pairs = [p for p in stats.partners(sets, pid) if p["won"] >= 5]
    for p in gold_pairs:
        give("pareja_oro", what=p["name"])
    if hl["rival"] and hl["rival"]["faced"] >= 3:
        give("rival", what=hl["rival"]["name"])
    if hl["victim"] and hl["victim"]["i_beat"] >= 3:
        give("verdugo", what=hl["victim"]["name"])
    if hl["nemesis"] and hl["nemesis"]["beat_me"] >= 5:
        give("bestia_negra", what=hl["nemesis"]["name"])

    out = {code: {"count": n, "tier": 0, "detail": detail.get(code, [])}
           for code, n in won.items() if n}
    for code, value in (("racha", streak["best_win"]), ("gafe", streak["worst_loss"]),
                        ("veterano", len(sets))):
        if tier(code, value):
            out[code] = {"count": 1, "tier": tier(code, value), "detail": [], "value": value}
    return out
