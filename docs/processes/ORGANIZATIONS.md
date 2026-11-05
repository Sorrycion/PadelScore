# Organizations

An organization is a club or group of friends. Everything belongs to one: players,
tournaments, and through them jornadas, sets and absences. Nobody sees anything until
they have entered an organization.

- **Fields:** name (unique, case-insensitive) and a random `secret` that signs the
  `org` cookie.
- **Its admin** is an account (a `users` row with role `org_admin` and the organization;
  see [USERS.md](USERS.md)). The username is unique among all accounts. The admin's
  password is a PBKDF2 hash plus a readable copy (`password_plain`) that super admins
  see on `/orgs`. Passwords saved before that copy existed show "unknown" until someone
  changes them. The old `organizations.admin_*` columns are deprecated, but kept in sync
  so the previous app version still works.
- **Player names** are unique per organization, ignoring case, accents and spacing.
  Two organizations may each have a "Julio".
- **Adoption:** the first organization ever created adopts every player and tournament
  that had none, which is how the data from before organizations became Nene's.


## Each organization's URLs (`/<slug>/...`)

Every organization has a **slug**, its name in its URLs (`Nene` → `nene`). Its pages
live under it, so a link shows that organization only and the browsing stays inside it
(the user's request, 2026-11-05):

| URL | Page |
|---|---|
| `/nene` | its standings (same as `/nene/standings`) |
| `/nene/tournaments`, `/nene/tournaments/4`, `/nene/tournaments/4/summary` | tournaments |
| `/nene/matchdays/19`, `/nene/matches`, `/nene/matches/12/edit` | jornadas and sets |
| `/nene/players`, `/nene/players/2`, `/nene/players/2/vs`, `/nene/medals` | players, stats, medals |
| `/nene/users`, `/nene/courts` | admin pages |

```mermaid
flowchart TD
    U["GET /nene/tournaments/4"] --> G{"OrganizationGate:<br/>is 'nene' an organization's slug?"}
    G -- yes --> P["organization = Nene (from the URL, not the cookie)<br/>path goes on as /tournaments/4<br/>org cookie set to Nene"]
    P --> R["route + template (links written as /tournaments/…)"]
    R --> K["keep_inside: href/action and redirects to an<br/>organization page get /nene in front"]
    G -- "no: /tournaments/4 (an old link)" --> C{"org cookie?"}
    C -- yes --> X["303 → /<its slug>/tournaments/4"]
    C -- no --> E["/enter to choose one"]
```

- **The slug** is `orgs.slugify(name)`: lowercase ASCII, accents removed, dashes between
  words, `-2`, `-3`… if taken. Names that match one of the app's paths (`players`,
  `login`…, `orgs.RESERVED`) get `-org`. Existing organizations got theirs from
  `sql/predeployment/0007_org_slugs.sql`. ⭐ Organizaciones shows each one's link.
- **Templates and routes don't change:** they keep writing `/tournaments/4`. The gate
  (`main.OrganizationGate`) strips the prefix on the way in and adds it on the way out
  (links in the HTML and `Location` headers, for the paths in `orgs.SECTIONS`).
- **What stays outside a slug:** the home page `/` (an account's tournaments in every
  organization, as before), `/me`, `/login`, `/enter`, `/orgs`, `/install`, `/rules`,
  `/welcome`, `/signup`, `/r/…` and `/unsubscribe/…`. Their links to an organization's
  pages pass through `/enter` or are redirected into `/<slug>/…`.
- **Emails** link to `/<slug>/matchdays/<id>`.

## Entering an organization

```mermaid
flowchart TD
    A[Any page] --> B{org cookie?}
    B -- yes --> C[Page of that organization]
    B -- no --> D{super admin?}
    D -- yes --> E["/orgs: list of all organizations"]
    D -- no --> F["/enter: top 10 organizations + type a name"]
    F -- tap or type name --> G[Set org cookie] --> C
    E -- Entrar --> G
    H["/login as org admin"] --> G
    I["/login with a player password"] --> G
```

- `/enter` lists the 10 organizations with the most tournaments (then by name) as
  one-tap buttons. Below the list, any organization's name can be typed.
- The header shows "🏢 name". Tapping it goes back to `/enter` to change organization.
- Pages open without an organization: `/enter`, `/login`, `/logout`, `/static`,
  `/lang`, `/rules`, `/orgs`.
- A middleware, `OrganizationGate` in `app/main.py`, enforces this. Every query
  filters on the current organization (`org_id()`, `ORG_SCOPE`), so one
  organization's admin can't see or change another's data, even by typing ids in the URL.

## Creating and managing organizations (super admin)

```mermaid
sequenceDiagram
    actor S as Super admin
    participant O as /orgs
    S->>O: Create: name, admin user, admin password
    O-->>S: Card: 🏆 tournaments · 👥 players · user · password
    S->>O: ✏️ change user and/or password (empty password = keep)
    S->>O: Entrar (acts as admin inside it)
```

From the command line, including the Azure Kudu console: `python -m app.orgs create
"Name" "user" "password"`, `password "user" "new"`, or `superadmin "user" "password"`.
The skill `.claude/skills/padelscore-live-admin` has the steps for the live site.

Organizations can't be deleted from the app.
