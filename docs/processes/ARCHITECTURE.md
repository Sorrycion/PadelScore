# Architecture

One FastAPI app, rendered on the server with Jinja2. SQLite is the database, in one file:
`padelscore.db` locally, `/home/data/padelscore.db` on Azure. There is no JavaScript
framework: only a small player picker (`app/static/picker.js`).

## Modules

```mermaid
flowchart TD
    subgraph web["app/main.py (routes, queries, templates)"]
        GATE[OrganizationGate middleware]
        ROUTES[routes: tournaments, jornadas, sets, players,<br/>accounts, profile, stats, medals, orgs, health]
    end
    AUTH[auth.py<br/>cookies, roles, can_score] --> web
    USERS[users.py<br/>accounts, hashing — stdlib] --> AUTH
    ORGS[orgs.py<br/>organizations + CLI — stdlib] --> USERS
    DB[db.py<br/>SCHEMA, connect, ORG context, init_db — stdlib] --> web
    MIG[migrate.py<br/>sql/predeployment runner — stdlib] --> DB
    SCORING[scoring.py<br/>courts, placings, standings] --> web
    ROUNDS[rounds.py<br/>Americano / Mexicano draws] --> web
    STATS[stats.py<br/>player dashboard numbers] --> web
    MEDALS[medals.py<br/>who has which medal] --> web
    STATS --> MEDALS
    CHARTS[charts.py<br/>inline SVG] --> web
    I18N[i18n.py<br/>es / en texts] --> web
    SQL[(sql/predeployment/*.sql)] --> MIG
```

The modules marked *stdlib* use only the standard library, so the pipeline and the Kudu
console can run them on Azure without the app's dependencies.

## A request

```mermaid
sequenceDiagram
    participant B as Browser
    participant G as OrganizationGate
    participant R as Route
    participant A as auth.py
    participant D as SQLite
    B->>G: GET /tournaments/5 (cookies: org, user, player_5)
    G->>D: organization from the signed org cookie
    alt no organization (and not an open path)
        G-->>B: 303 → /enter (super admins → /orgs)
    end
    G->>R: db.ORG = organization id
    R->>A: is_editor / can_score? (signed user cookie, role, linked player)
    R->>D: queries filtered by org_id() (get_or_404, set_rows, ...)
    R-->>B: Jinja page (i18n, auth context, css_version)
```

- **Open paths** (no organization needed): `/` (the login, or an account's home across
  organizations), `/enter`, `/login`, `/logout`, `/static`, `/lang`, `/rules`, `/orgs`,
  `/me`, `/health`, `/signup` (an account with no tournament), `/join` (a tournament's
  password, from the home page). The standings of an organization are at `/standings`.
- **Calculated, not stored:** standings, statistics and medals are always worked out
  from the sets. Only sets, absences and the lists are stored.
- **Pages that span organizations** run their queries per organization with
  `in_org(org_id, work)`. That's `/` (the home: tournaments and next sets in every
  organization) and `/me`, which lists an account's players everywhere and adds them up
  (`career`).
- **Navigation:** on wide screens the sections are a row of pills under the header. On
  phones (640 px or less) they fold, with the account links and the language, into a
  ☰ menu. It's a hidden checkbox (`#menu-toggle`) and CSS, with no JavaScript.

## Data

```mermaid
erDiagram
    organizations ||--o{ players : has
    organizations ||--o{ tournaments : has
    organizations ||--o{ users : "org_admin of"
    users ||--o{ players : "claims (one per org)"
    rule_types ||--o{ tournaments : "scored with"
    tournaments ||--o{ tournament_players : lists
    tournaments ||--o{ matchdays : has
    matchdays ||--o{ matches : "sets, by court"
    matchdays ||--o{ absences : marks
    medal_types }o--o{ players : "awarded live (medals.py)"
    schema_migrations }o--|| organizations : "(records applied SQL files)"
```

## Where things run

| Where | What |
|---|---|
| Laptop | `uvicorn app.main:app --reload` on `padelscore.db`. It migrates on start |
| GitHub Actions | Tests on every PR; on `main`: tests, backup, pre-deployment SQL, deploy, `/health` check ([DEPLOY.md](DEPLOY.md)) |
| Azure App Service F1 | gunicorn + uvicorn worker, one instance (SQLite must not be shared) |
