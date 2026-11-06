# Tournaments

A tournament belongs to an organization. It has a name, a date, a rule type, a player
password, a list of players and its jornadas. Only admins change tournaments: the
organization admin, or a super admin who entered the organization.

```mermaid
stateDiagram-v2
    [*] --> EnCurso: Admin creates it (/tournaments → ➕)
    EnCurso --> EnCurso: add jornadas, sets, players, replace players
    EnCurso --> Pasado: 🏁 Terminar torneo
    Pasado --> EnCurso: Reabrir torneo
    EnCurso --> [*]: 🗑️ Eliminar torneo
    Pasado --> [*]: 🗑️ Eliminar torneo
    note right of Pasado
        Shown in the "Pasados" tab.
        Results are kept and still editable.
    end note
```

## Creating one

You give it a name, a date (`held_on`), a rule type and its players: existing ones,
plus new names typed in, which become players. Optionally you also give a player
password and, for Americano and Mexicano, the points per match.

| Rule type | How it's played | Needs |
|---|---|---|
| Liga de amigos score | Jornadas; courts of 4 play 3 sets each, places 9/6/4/3 + 1 per set won | — |
| Americano | Rounds; partners rotate so everyone partners everyone | ≥ 4 players |
| Mexicano | Rounds; round 1 drawn, then the ranking makes the courts | ≥ 4 players |
| Manual individual | Jornadas with only a date; sets added by hand; points = games difference | — |
| 🔄 Retas | One jornada in rounds on several courts: winners move up, losers down; new pairs each round; points = games difference | courts of 4 |
| 👑 Rey de la cancha | One court and a line of pairs: the winner stays, the loser goes to the end; 1 point per set won | ≥ 2 pairs |
| 🪜 Escalafón | A ladder of fixed pairs that challenge up to 3 places above (5 if none free); a won challenge swaps places; each reto is a jornada, best of 3 sets | pairs |

## 🔄 Retas, 👑 Rey de la cancha and 🪜 Escalafón

The rules are pure functions in `app/formats.py`; the routes in `app/main.py`; the
written rules on `/rules` (`docs/RETAS.md`, `REY_CANCHA.md`, `ESCALAFON.md`, the
Escalafón taken from the club's reglamento, without its hours and deadlines).
`sql/predeployment/0010_retas_rey_escalafon.sql` adds the rule types, `matches.round`,
`matches.sets_detail`, `ladder_pairs` and `queue_pairs`.

```mermaid
flowchart TD
    subgraph Retas["🔄 Retas (one jornada)"]
        R1["Round 1: courts drawn by the app<br/>(courts screen, editable)"] --> RP["results of the round"]
        RP --> RN["🔄 Siguiente ronda: formats.retas_move<br/>winners up, losers down (ties block)"]
        RN --> RC["each court: 3 pairings; the app's draw<br/>preselected; ⚠️ pair already together today"]
        RC --> RP
    end
    subgraph Rey["👑 Rey de la cancha (one jornada)"]
        K1["line of pairs (queue_pairs): drawn or by hand"] --> K2["match: king vs next in line"]
        K2 --> K3["▶️ Siguiente partido: formats.king_line<br/>winner stays, loser to the end"]
        K3 --> K2
    end
    subgraph Esc["🪜 Escalafón"]
        E1["pairs (ladder_pairs), last place on joining;<br/>🎲 draw before the first reto"] --> E2["⚔️ Retar: formats.targets<br/>3 places up (5 if none free), one reto at a time"]
        E2 --> E3["a jornada with one match: challenger = pair A"]
        E3 --> E4["result set by set (best of 3, super tie-break)<br/>formats.best_of_three → sets_detail"]
        E4 --> E5["formats.ladder replays every reto: a won challenge swaps"]
    end
```

- **Points:** Retas = the games difference of every set (negative is possible); Rey =
  1 per set won (`scoring.win_points`); Escalafón = 1 per match won, but its standings
  are ordered by the ladder (`load_results` re-sorts them; the tournament page shows
  the ladder instead of the points table).
- **Who:** admins and the tournament's players (Siguiente ronda / partido, results);
  an Escalafón reto by an admin or a player of the challenging pair. Admins add pairs,
  draw positions and remove pairs (the ones below move up; not with a reto pending).
- **The ladder is never stored:** it's rebuilt from the pairs' starting order and every
  played reto, so correcting a result corrects the ladder. Replacing a player keeps
  their pair's place.
- **Jornada pages:** Retas and Rey show the jornada by rounds (Ronda / Partido N), what
  comes next and the jornada's table; their courts screen only applies to Retas round 1.

## Players of a tournament

These actions are on the tournament page, in the players section:

- **Add**: pick a player, or type a new name and create it.
- **Remove**: takes the player out of the list. Their sets and points so far stay.
  Someone who played the last jornada is still suggested for the next one; saving it
  puts them back on the list. To take them out for good, change their court in the
  new jornada before saving.
- **Replace**: the new player takes the old one's place in the list and in the
  *pending* (not yet played) sets. **🎯 Puntos ya jugados** chooses what happens to
  the sets already played in this tournament (the user's request, 2026-11-05):
  - **Se quedan con quien sale** (the default): played sets and their points stay with
    the old player, and the new one starts from zero.
  - **Pasan al nuevo jugador**: the played sets and the absences move too, so the new
    player takes the whole place: points, per-jornada history and medals of this
    tournament. It's refused if the new player already played with or against the
    old one in this tournament (a set can't have the same player twice).

  It can also be started from the jornada page, with the "Reemplazar" link next to a
  player in a court table.

```mermaid
flowchart LR
    R["🔁 Reemplazar a Bruno por Charly"] --> Q{"🎯 Puntos ya jugados"}
    Q -- "Se quedan con quien sale" --> K["pending sets + list → Charly<br/>played sets, points → stay with Bruno<br/>Charly starts at 0"]
    Q -- "Pasan al nuevo jugador" --> M["every set of the tournament + absences + list → Charly<br/>Charly has Bruno's points"]
```

## 🏁 Summary (Resumen del torneo)

`/tournaments/{id}/summary`, linked as "🏁 Resumen" under the tournament's name once it
has a jornada. It says "Resultado final" when the tournament has ended and "Hasta
ahora" while it's going, and shows:

```mermaid
flowchart LR
    R["load_results: matchdays + standings"] --> S["stats.season()"]
    P["the tournament's played sets"] --> S
    S --> H["highlights: best jornada · longest streak · most sets won ·<br/>best games difference · most often on court 1 (Liga) ·<br/>pair of the tournament · never missed a jornada"]
    R --> D["podium: positions 1-3 (ties share)"]
    M["tournament_medals()"] --> X["the tournament's medals and who won them"]
```

A highlight only shows when someone stands out (e.g. a streak of 2+ wins, a pair with 2+
wins together). Everything is calculated from the sets, like the standings.

## Ending (Terminar torneo)

- **Who:** only an admin. Visitors and players don't see the button.
- **Where:** the button **🏁 Terminar torneo** is at the bottom of the tournament page,
  above **Eliminar torneo**.
- **Conditions:** none. Any tournament can be ended at any time, even with pending sets.
- **Effect:** it moves from the "En curso" tab to "Pasados", and from the home tabs
  to the past list. Nothing is locked: results stay and can still be edited. **Reabrir
  torneo** brings it back.

## Deleting

**Eliminar torneo** asks for confirmation, then deletes the tournament with all its
jornadas, sets and absences. Players are kept.
