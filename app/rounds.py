"""Drawing the rounds of Americano and Mexicano tournaments.

Both are individual formats played in rounds: on each court one match of two pairs,
to a fixed number of points; every player scores the points their pair won. With a
player count that isn't a multiple of four, the rest rotate: nobody rests twice before
everyone has rested once.

- Americano: partners rotate so that everyone partners everyone (as evenly as the
  numbers allow) and meets varied opponents.
- Mexicano: round 1 is a draw; after that the ranking makes the courts. On court 1 the
  1st and 3rd play the 2nd and 4th, on court 2 the 5th and 7th play the 6th and 8th...

A round is a list of courts, each [a1, a2, b1, b2] (pair a1+a2 against b1+b2).
"""
import random
from collections import Counter

TRIES = 300  # random restarts when looking for the Americano round with fewest repeats


def rests(players, history):
    """How many rounds each player has rested so far."""
    count = Counter({p: 0 for p in players})
    for courts in history:
        playing = {p for court in courts for p in court}
        for p in players:
            count[p] += p not in playing
    return count


def _resting(players, history, tiebreak):
    """Who rests this round: those who rested least, then by `tiebreak`."""
    resting = len(players) % 4
    order = sorted(players, key=lambda p: (rests(players, history)[p], tiebreak(p)))
    return order[:resting]


def americano_round(players, history, seed):
    """The next Americano round: (courts, resting players)."""
    rng = random.Random(seed)
    resting = _resting(players, history, lambda p: rng.random())
    active = [p for p in players if p not in resting]
    partners, opponents = Counter(), Counter()
    for courts in history:
        for a1, a2, b1, b2 in courts:
            partners.update([frozenset((a1, a2)), frozenset((b1, b2))])
            opponents.update(frozenset((x, y)) for x in (a1, a2) for y in (b1, b2))

    def against(pair_a, pair_b):
        return sum(opponents[frozenset((x, y))] for x in pair_a for y in pair_b)

    best, best_cost = [], None
    for _ in range(TRIES):
        pool = active[:]
        rng.shuffle(pool)
        pairs = []
        while pool:
            p = pool.pop(0)
            q = min(pool, key=lambda x: (partners[frozenset((p, x))], rng.random()))
            pool.remove(q)
            pairs.append((p, q))
        courts = []
        while pairs:
            a = pairs.pop(0)
            b = min(pairs, key=lambda x: (against(a, x), rng.random()))
            pairs.remove(b)
            courts.append([*a, *b])
        # A repeated partner costs far more than a repeated opponent.
        cost = sum(100 * partners[frozenset(c[:2])] ** 2 + 100 * partners[frozenset(c[2:])] ** 2
                   + against(c[:2], c[2:]) for c in courts)
        if best_cost is None or cost < best_cost:
            best, best_cost = courts, cost
            if cost == 0:
                break
    return best, resting


def mexicano_round(players, history, ranking, seed):
    """The next Mexicano round: (courts, resting players).

    ranking: player ids, best first (players not in it go after, in draw order).
    Round 1 (no history) is a draw.
    """
    rng = random.Random(seed)
    order = players[:]
    rng.shuffle(order)
    if history:
        rank = {p: i for i, p in enumerate(ranking)}
        order.sort(key=lambda p: rank.get(p, len(rank)))
    place = {p: i for i, p in enumerate(order)}
    resting = _resting(players, history, lambda p: -place[p])  # the lowest ranked rest first
    active = [p for p in order if p not in resting]
    courts = []
    for i in range(0, len(active) - 3, 4):
        first, second, third, fourth = active[i:i + 4]
        courts.append([first, third, second, fourth])
    return courts, resting
