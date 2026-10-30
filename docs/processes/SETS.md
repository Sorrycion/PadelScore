# Sets

A set belongs to a jornada and a court. It has two pairs, A (a1 + a2) and B (b1 + b2),
the games of each team and the winner. A set with no games yet is **pending** and
scores nothing.

## Who enters what

```mermaid
flowchart TD
    A{Who?} -- Admin --> B["Everything: add, edit, delete sets<br/>(the whole set on its Edit page)"]
    A -- "Player (account or tournament password)" --> C["✏️ Edit on a set of their tournament:<br/>a page with just the games"]
    C --> D{Manual tournament?}
    D -- yes --> E[Also add and edit whole sets]
    D -- no --> F["Sets come from the courts;<br/>players only type the games"]
    A -- Visitor --> G[Read only]
```

- **Results are always entered on the set's Edit page** (`/matches/{id}/edit`), never
  in the set card (the user's decision, 2026-10-30). On the jornada page every set has
  ✏️ Editar for whoever may score it. Admins, and players of Manual tournaments, get
  the whole set form. Other players get a page with just the two games boxes
  (`match_score.html`), which posts to `/matches/{id}/score` and returns to the
  jornada. Both games are required. A tie is allowed (no winner).
- **Players find their sets** on the home page (`/`): "⏳ Mis próximos sets" lists the
  pending sets of every tournament they play, oldest date first, each with a link to
  enter its result.
- **The set form** (`/matches/new`, `/matches/{id}/edit`) checks:
  - 4 different players, all from this organization;
  - a jornada of this organization;
  - a court of 1 or more;
  - both games, or neither.
- **Deleting a set** is for admins only.
- **The Sets tab** (`/matches`) lists every set and can be filtered by tournament,
  jornada and player.

## Points per set, by rule type

| Rule type | Each player of the pair gets |
|---|---|
| Liga de amigos | Nothing per set by itself. When the court's 3 sets are played: place points 9 / 6 / 4 / 3 + 1 per set won |
| Americano / Mexicano | The games (points) their pair won |
| Manual individual | The games difference: 6-3 gives +3 to the winners and −3 to the losers; totals can be negative |

An absent player scores 0 for that jornada, whatever their substitute did.

```mermaid
sequenceDiagram
    actor P as Player / Admin
    participant H as Home / Jornada page
    participant E as Set's Edit page
    participant DB as matches table
    P->>H: ✏️ Editar (or Resultado in "Mis próximos sets")
    H->>E: /matches/{id}/edit
    P->>E: type games 6 - 3 → Guardar
    E->>DB: team_a_games=6, team_b_games=3, winner=A
    E-->>P: back to the jornada: court table and standings recalculated
```

Standings are always calculated from the sets; no totals are stored.
