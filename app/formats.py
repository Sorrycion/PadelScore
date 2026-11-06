"""The rules of Retas, Rey de la cancha and Escalafón (pure functions, no database).

- Retas: one jornada in rounds. Each round, every court plays one set; then the winning
  pair of each court moves up a court and the losing pair moves down (court 1 is the
  top: its winners stay; the last court's losers stay). On each court the four players
  form new pairs, drawn by the app or chosen on court; a pair that already played
  together that jornada is allowed, with a warning.
- Rey de la cancha: one court and a line of pairs. The pair that wins stays on court
  (the king); the pair that loses goes to the end of the line and the next pair comes on.
- Escalafón: a ladder of fixed pairs, each with its own position. A pair challenges
  (reta) a pair up to RANGE places above it, or up to MAX_RANGE when none within RANGE
  is free; if the challenger wins, the two swap places. Matches are best of 3 sets, the
  third may be a super tie-break.

A pair is a tuple of two player ids; a set is a row like main.set_rows() gives.
"""
import random

RANGE, MAX_RANGE = 3, 5  # Escalafón: places above a pair may challenge


def pair(s, team):
    """The two player ids of team "A" or "B" of a set, as a frozenset."""
    keys = ("a1", "a2") if team == "A" else ("b1", "b2")
    return frozenset(s[k + "_id"] for k in keys)


def winners_losers(s):
    """(winning pair, losing pair) of a played set, or None for a tie."""
    if s["winner"] not in ("A", "B"):
        return None
    loser = "B" if s["winner"] == "A" else "A"
    return pair(s, s["winner"]), pair(s, loser)


# --- Retas -----------------------------------------------------------------------------

def draw_courts(players, seed, courts=None, rest=()):
    """Round 1 of a Retas jornada: (courts of 4, resting players), drawn at random.
    `courts`: how many courts are available; `rest`: players who sit out."""
    rng = random.Random(seed)
    free = [p for p in players if p not in set(rest)]
    rng.shuffle(free)
    most = len(free) // 4
    n = most if courts is None else max(0, min(courts, most))
    return [free[i * 4:i * 4 + 4] for i in range(n)], [p for p in players if p not in free[:4 * n]]


def retas_move(round_sets):
    """The next round's courts after the ups and downs: {court: [4 player ids]}.
    `round_sets`: the round's played sets, one per court.
    Raises ValueError(court) when a court's set is a tie (nobody knows who goes up)."""
    by_court = {s["court"]: s for s in round_sets}
    numbers = sorted(by_court)
    result = {}
    for c in numbers:
        wl = winners_losers(by_court[c])
        if wl is None:
            raise ValueError(c)
        result[c] = wl
    new = {c: [] for c in numbers}
    for i, c in enumerate(numbers):
        winners, losers = result[c]
        up = numbers[i - 1] if i > 0 else c
        down = numbers[i + 1] if i < len(numbers) - 1 else c
        new[down] = sorted(losers) + new[down]  # coming down (or staying at the bottom)
        new[up] += sorted(winners)  # coming up (or staying on top)
    return new


def pairings(four):
    """The three ways four players make two pairs: [(pair A, pair B), ...]."""
    p1, p2, p3, p4 = four
    return [((p1, p2), (p3, p4)), ((p1, p3), (p2, p4)), ((p1, p4), (p2, p3))]


def played_pairs(sets):
    """Every pair (frozenset) that played together in these sets."""
    return {pair(s, team) for s in sets for team in ("A", "B")}


def draw_pairing(four, seed):
    """The app's draw: the index (0-2) of the pairing for a court."""
    return random.Random(seed).randrange(3)


# --- Rey de la cancha --------------------------------------------------------------------

def king_line(pairs, sets):
    """(king, challenger, line) after these sets: `pairs` is the starting line (the first
    two play first), `sets` the jornada's played sets in order. The winner stays as
    king; the loser goes to the end of the line. Returns None for the challenger when
    there are fewer than two pairs. A tie keeps both: the king stays and the
    challenger plays again."""
    line = [frozenset(p) for p in pairs]
    if len(line) < 2:
        return (line[0] if line else None), None, []
    king, challenger, line = line[0], line[1], line[2:]
    for s in sets:
        wl = winners_losers(s)
        if wl is None:
            continue
        winners, losers = wl
        if {winners, losers} != {king, challenger}:
            continue  # a set edited by hand with other players: it doesn't move the line
        line.append(losers)
        king, challenger = winners, line.pop(0)
    return king, challenger, line


# --- Escalafón ---------------------------------------------------------------------------

def ladder(pairs, retos):
    """The ladder after these retos: pair ids, top first.

    pairs: pair ids in their starting order (the draw, then the order they joined).
    retos: (challenger id, challenged id, challenger won) for each played reto, in
    order. A won challenge swaps the two; anything else changes nothing."""
    order = list(pairs)
    for challenger, challenged, won in retos:
        if won and challenger in order and challenged in order:
            i, j = order.index(challenger), order.index(challenged)
            if i > j:
                order[i], order[j] = order[j], order[i]
    return order


def targets(order, challenger, busy=()):
    """The pairs `challenger` may challenge: the free ones up to RANGE places above it,
    or up to MAX_RANGE places when none within RANGE is free. `busy`: pairs with a reto
    still to play (they can't challenge or be challenged)."""
    if challenger not in order or challenger in busy:
        return []
    i = order.index(challenger)
    free = lambda reach: [p for p in order[max(0, i - reach):i] if p not in busy]  # noqa: E731
    return free(RANGE) or free(MAX_RANGE)


def best_of_three(games):
    """A best-of-3 match from its sets' games [(a, b), ...] (2 or 3 sets; the third may
    be a super tie-break, to 10). Returns (sets won by A, by B). Raises ValueError when
    it isn't a finished match: a tied set, fewer than 2 sets, or a third set after 2-0."""
    sets = [(a, b) for a, b in games if a is not None and b is not None]
    if any(a < 0 or b < 0 or a == b for a, b in sets):
        raise ValueError("set")
    won_a = won_b = 0
    for n, (a, b) in enumerate(sets):
        if won_a == 2 or won_b == 2:
            raise ValueError("extra set")
        won_a, won_b = won_a + (a > b), won_b + (b > a)
    if max(won_a, won_b) != 2:
        raise ValueError("unfinished")
    return won_a, won_b


def sets_text(games):
    """'6-4, 3-6, 10-8' from [(6, 4), (3, 6), (10, 8)]."""
    return ", ".join(f"{a}-{b}" for a, b in games)


def parse_sets(text):
    """[(a, b), ...] back from sets_text()."""
    out = []
    for part in (text or "").split(","):
        if "-" in part:
            a, b = part.strip().split("-", 1)
            out.append((int(a), int(b)))
    return out
