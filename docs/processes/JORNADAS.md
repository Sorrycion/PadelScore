# Jornadas (matchdays and rounds)

A jornada (called "Ronda" in Americano and Mexicano) is one day of a tournament. Its
players are split into courts (canchas) of four. Jornadas are numbered 1, 2, 3… with
no gaps: deleting one renumbers the later ones. Only admins create, change or delete
jornadas.

## Liga de amigos

```mermaid
flowchart TD
    A["Tournament page → New jornada (date)"] --> B{Previous jornada?}
    B -- no --> C[Empty courts: pick 4 players per court]
    B -- yes --> D["Choose how many change court: 1 or 2"]
    D --> E["Suggested courts: best 1-2 of each court go up,<br/>worst 1-2 go down (court 1 is the top)"]
    C --> F[Review / change courts → Save]
    E --> F
    F --> G["Each court gets its 3 sets:<br/>every player partners each other once"]
    G --> H[Players / admin enter the games of each set]
    H --> I{All 3 sets of a court played?}
    I -- no --> J["⏳ court shows only sets won so far"]
    I -- yes --> K["Places 1-4: 9 / 6 / 4 / 3 pts + 1 per set won"]
    K --> L[Court changes suggested for the next jornada]
```

- **Place order:** sets won, then games difference, then league position before the
  jornada. On jornada 1 a draw settles ties.
- **Changing courts** (`/matchdays/{id}/courts`): a court that keeps the same four
  players keeps its sets. A court with new players gets 3 new sets, and its old sets
  are deleted.
- **Absent player** (🚫 next to the name in the court table): a substitute plays in
  their place, but the absent player scores 0 that day and goes last on the court.
  Tap again to mark them present.
- **Replace** (next to the name in the court table): opens the replace page. The new
  player takes the place in pending sets and in the tournament list. See
  [Tournaments](TOURNAMENTS.md).

## Americano and Mexicano (rounds)

```mermaid
flowchart LR
    A[New round] --> B["Courts available + who asks to rest"]
    B --> C{Rule}
    C -- Americano --> D["Rotate partners: everyone partners everyone,<br/>varied opponents"]
    C -- Mexicano --> E["Round 1: draw. Then by ranking:<br/>1st+3rd vs 2nd+4th on court 1, 5th+7th vs 6th+8th…"]
    D --> F["One match per court (to the points per match)"]
    E --> F
    F --> G["Rests rotate: nobody rests twice<br/>before everyone rested once"]
```

Each player scores the points their pair won in every match.

## Manual individual

A jornada has only a date. There are no courts to assign: the admin, or players logged
in with the tournament's player password, add sets one by one.

## The jornada page

Each court is shown on its own panel, alternating gray and blue so it's easy to tell
the courts apart. A panel holds the court's sets with their games and the court's table
(place, player, games difference, sets won, points). Below the courts are the resting
players (rounds), the court changes (Liga), and the button for the next jornada.

Code: matchday routes are in `app/main.py` (`/matchdays/...`,
`/tournaments/{id}/matchdays/new`). Scoring is in `app/scoring.py`, and round drawing
is in `app/rounds.py`.
