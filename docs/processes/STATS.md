# Player statistics

Every player page has two tabs: **📋 Resumen** (`/players/{id}`: tournaments, partners,
sets) and **📊 Estadísticas** (`/players/{id}/stats`). Anyone in the organization can see
them, like the standings. Accounts reach their own from `/me`.

```mermaid
flowchart LR
    S["set_rows(player): played sets,<br/>oldest first"] --> D["stats.dashboard()<br/>(pure functions)"]
    D --> T[tiles: sets, won, lost, win %, ± games, current streak]
    D --> C["charts.py: inline SVG<br/>donut · form strip · win % line ·<br/>points per tournament · bars"]
    D --> H["highlights: partner most / wins most / loses most,<br/>rival, nemesis, favorite victim"]
```

| Shown | How it's computed (`app/stats.py`) |
|---|---|
| Sets, won, lost, tied, win % | Played sets only. A set with no winner is tied |
| ± games | Games for minus games against (points in Americano and Mexicano) |
| Current / best / worst streak | Runs of consecutive results, oldest first |
| Form | The last 30 results as green, red and grey squares |
| Win % (last 10 sets) | After each set, the wins among the last 10 |
| Points over time | Per tournament, the cumulative points of each matchday (from the standings) |
| Most frequent partner | The most sets together |
| Wins most / loses most with | The most wins or losses together, among partners with at least 3 sets |
| Rival | The opponent faced most |
| Nemesis / favorite victim | The opponent who beat you most / you beat most |
| Sets per month | The last 12 months with sets |

The charts are plain SVG built on the server (`app/charts.py`), with no JavaScript. They
use the stylesheet's colors, so they work in dark mode. Tapping a point or bar shows its
value. Labels are escaped.

## 🎯 Chances of winning a set

`stats.player_rates` (everyone's sets won and played in the organization) and
`stats.win_probability(rates, team, rivals)`:

- **A player's level** is (won + 1) / (played + 2): a newcomer starts at 50%, and a few
  sets don't make 0% or 100%.
- **A pair's level** is the average of its two players.
- **The chance** compares the two levels as odds (like a simple Elo): equal levels give
  50%, and 2/3 against 1/3 gives 80%.

```mermaid
flowchart LR
    S["every played set of the organization"] --> R["player_rates: won / played"]
    R --> L["level = (won+1)/(played+2)"]
    L --> P["pair = average of its 2 players"]
    P --> W["chance = odds(A) / (odds(A) + odds(B))"]
    W --> J["jornada: bar on each pending set"]
    W --> E["⏰ game-day email: each set"]
    W --> H["⚔️ Cara a cara: you vs that player"]
```

## ⚔️ Cara a cara (head to head)

The player's tab `/players/{id}/vs?other={id}`: one player against another of the
organization. The list offers everyone they've shared a set with, most sets first, and
starts on their main rival (the opponent faced most).

```mermaid
flowchart LR
    S["the player's played sets"] --> H["stats.head_to_head(sets, pid, other)"]
    H --> A["against: sets, won by each, ties, games for / against,<br/>results strip (oldest first)"]
    H --> T["together: sets as partners, won, win %"]
    H --> L["their last 10 sets, newest first"]
```

Like the rest of the dashboard it's calculated from the sets every time, and only
played sets count.
