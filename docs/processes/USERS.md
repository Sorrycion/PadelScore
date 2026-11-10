# Users and logins

> **🏠 Mi pádel** (2026-11-06): every player account comes with its own private space for friendlies, and can invite friends and hand them their players. See [ORGANIZATIONS.md](ORGANIZATIONS.md#-mi-pádel-a-players-own-space).

Everyone who logs in has an **account** (table `users`, code in `app/users.py`), with a
unique username, an optional email (required for players), names and a role. An account
logs in with its **username or email** and password. Players can also come in as
**guests** with a tournament's player password.

| Who | Logs in with | May do |
|---|---|---|
| **Visitor** (not logged in) | nothing; just enters an organization | See standings, tournaments, jornadas, sets, players |
| **👻 Guest player** | a tournament's *player password* | Enter games of sets in that tournament from the jornada page. In Manual tournaments, also add and edit sets |
| **🎾 Player account** | username or email + password | The same, in every tournament its linked player plays in |
| **🏢 Organization admin** | username or email + password | Everything inside their organization (an *editor*), including its accounts |
| **⭐ Super admin** | username or email + password | Create organizations, see and change admin credentials, change roles, act as admin in any organization |

```mermaid
flowchart LR
    R["/ (not logged in): welcome page"] --> L["👤 Mi cuenta · 🎾 Jugadores (✨ Crear cuenta)<br/>· 🔍 Buscar organización"]
    L -- username/email + password --> U{role}
    U -- org_admin --> O["enters their organization"] --> H
    U -- "super / player" --> H["/ home: ⏳ Mis próximos sets (by date)<br/>+ 🏆 Mis torneos (every organization)"]
    L -- tournament password --> G["cookie player_{tid}<br/>(+ enters its organization)"] --> W["/welcome: account or guest"]
    L -- "🔍 club name" --> V["/enter?q=…: matching clubs"]
    R -. "browser remembers a club" .-> T["its tournaments in a table<br/>(search by name)"]
```

## The home page (`/`)

- **Nobody logged in:** `/` is the welcome page (the user's request, 2026-11-10): 👤 Mi
  cuenta (log in), 🎾 Jugadores (✨ Crear cuenta, and the guest tournament password
  folded away) and 🔍 Buscar organización. It shows **no organization**: no club menu
  (`landing` hides the sections and the organization line). Only if the browser
  remembers a club (its org cookie) does it add, below everything, that club's
  tournaments in a table with a search box (`table-filter.js`).
- **A new account** enters its 🏠 Mi pádel (not a club left in the browser). Logging in
  enters it only if the browser views no organization (`main.enter_mine`).
- **Logged in:** `/` lists:
  - **⏳ Mis próximos sets:** the pending sets of the account's players, in every
    organization, oldest date first. Each has a link to enter its result (the set's
    Edit page, see [SETS.md](SETS.md)).
  - **🏆 Mis torneos:** every tournament the account plays (🎾, with position and points)
    or runs (🛠️ Admin: all of their organization's for an org admin, every club's for
    a super admin). Tournaments still going come first. **Only your own friendlies**
    (the user's request, 2026-11-10): no other account's 🏠 Mi pádel, and a club's
    🤝 Amistosos only if you play in it, even for its admin.
  - A **guest** sees the tournaments whose password the browser has, with all their
    pending sets.
- Links into another organization go through `/enter`, which switches the browser to
  that organization first. The code is `home`, `account_home` and `guest_home` in
  `app/main.py`.

## Accounts and players

**Players belong to an organization; accounts belong to the whole app.** A player row
is a name inside one organization (its sets, tournaments and standings live there). An
account is the person, and it unifies their players:

- A player row without `user_id` is a **guest player**: just a name.
- An account claims **one player per organization** (`players.user_id`). Claiming
  applies everywhere that player appears: every set, tournament, ranking, stat and
  medal of it is the account's.
- Someone who plays in two organizations has two players (one in each) and one account.
  `/me` adds them up under **🌐 Todo mi pádel** (sets, wins, win rate, tournaments,
  organizations, medals) and lists each organization below.
- **Duplicates in one organization are joined, not linked.** If the person was entered
  twice (another name for the same person), the account's player absorbs the duplicate:
  its sets, tournament lists and absences move over, and the duplicate is deleted
  (`users.merge_players`). It's refused if the two played in the same set, because then
  they're two people. The player can do it on `/welcome` (🧩 ¿También eres tú?) with a
  tournament's password, and admins can do it on the account's page in 🔑 Cuentas.
- The display name is the league name: it renames the account's players in every
  organization (when the name is free there). **Rankings show "Display name
  (username)"** for players with an account. Guests show just their name.

```mermaid
erDiagram
    users ||--o{ players : "claims (one per organization)"
    organizations ||--o{ users : "org_admin of"
    organizations ||--o{ players : has
```

```mermaid
flowchart LR
    U["👤 account: ana"] --> P1["Nene: player 'Ana L'"]
    U --> P2["Club B: player 'Ana L'"]
    D["Nene: duplicate 'Anita'"] -- "🧩 join (merge_players)" --> P1
    P1 --> M["/me: 🌐 Todo mi pádel = Nene + Club B"]
    P2 --> M
```

## Account first: joining tournaments with their password

Players are asked to **make an account first** (the user's decision, 2026-10-30). The
login's 🎾 Jugadores section says "¿No tienes cuenta? Créala" and links to `/signup`,
which then asks for no tournament. Once inside, the home page has **🎟️ Unirme a un
torneo**: the tournament's player password works as its invitation (`POST /join`).

```mermaid
flowchart TD
    L["/ login: 🎾 Jugadores"] --> S["✨ Crear cuenta → /signup<br/>(no tournament)"]
    S --> H["/ home"]
    H -- "🎟️ Unirme a un torneo: its password" --> J["/join: player cookie + enters its organization"]
    J --> W{"/welcome: ¿Quién eres en {torneo}?<br/>(one list)"}
    W -- "one of the tournament's players" --> E{"my account has a<br/>player here already?"}
    E -- no --> C["claims it: its sets and points are mine"]
    E -- yes --> K["🧩 ¿{name} eres tú? → Sí, soy yo: unir<br/>(merge_players into mine)"]
    W -- "🎟️ Unirte como {mine}" --> A["my player, added to the tournament's list"]
    W -- "✨ Crear un jugador nuevo para mí" --> N["new player = display name,<br/>added to the list (no player here yet)"]
    W -- "already plays it" --> T["✅ just a link to the tournament"]
    C --> H
    K --> H
    A --> H
    N --> H
```

- **One question, one list** (the user's request, 2026-10-30): when the account isn't in
  the tournament, `/welcome` asks "¿Quién eres en {torneo}?". The list has the
  tournament's players nobody has claimed (the admin may have put the person on it
  already) and, under "O entrar como yo", either **Unirte como {my player}** or
  **Crear un jugador nuevo para mí**.
- **Picking someone on the list when the account already has a player in that
  organization** would make them one, so it asks first (`/welcome?t=&confirm=<id>`:
  "¿{name} eres tú?" → "Sí, soy yo: unir" or Cancelar).

- A wrong password waits 1 second and shows the error on the home page's card.
- **Guests still work:** under 🎾 Jugadores, "👻 Solo anotar resultados, sin cuenta"
  folds out the old tournament-password form. That's for someone who only enters a
  result.

## From guest to account

After a tournament's player password, a browser without an account lands on
`/welcome`:

```mermaid
flowchart TD
    W["/welcome (tournament password accepted)"] --> G["👻 Seguir como invitado → the tournament, as before"]
    W --> C["✨ Crear cuenta → /signup"]
    W --> H["👤 Ya tengo cuenta → log in → pick my player → linked"]
    C --> Q{"¿Quién eres?"}
    Q -- "one of the tournament's free players" --> L["account claims that player:<br/>its earlier sets and points come along"]
    Q -- "Soy nuevo/a" --> N["new player named after the display name,<br/>added to the tournament"]
    L --> M["/me"]
    N --> M
```

An account that is already logged in gets the account-first `/welcome` instead (see
above). A guest's tournament password still offers the three choices.

- **Who can claim:** only a browser that has the tournament's password can claim one of
  its players, and only players nobody has claimed yet.
- **Signup asks for:** first and last name, display name, username, email, an optional
  **cell phone**, and a password of at least 8 characters, entered twice.
- **📱 Cell phone** (`sql/predeployment/0004_users_phone.sql`): the country, picked from
  a list with its dialing code (`app/countries.py`, México +52 first), and the number.
  The account keeps the country's ISO code (`phone_country`, e.g. `MX`; several
  countries share +1) and only the number's digits (`phone`, 6 to 14). Spaces, dashes,
  dots and parentheses are dropped, and an empty number removes the phone. It's shown
  as `+52 5512345678` and only to the account (on `/me`) and its admins (on 🔑 Cuentas,
  as a `tel:` link). Editable on `/me` and on the admin's account page.
- **The display name is the league name:** it renames the claimed player, unless
  another player of that organization already has that name.
- **A player account** scores in its tournaments without the tournament password.

## Profile (`/me`)

Any account can open `/me`, from the 👤 name in the header. It shows:

- for each of its players, by organization: the tournaments with position and points,
  the sets still to play (with a link to the jornada to score them), and the latest
  sets;
- a form to edit names, display name, username and email;
- a form to change the password, which asks for the current one.

## Details

- **🔑 Cuentas** (`/<slug>/users`) is a **table**: name, actions (✏️ edit, 📧 test
  email, ⏰ test reminder), username, role, email, cell phone, player. A text filter
  (ignores accents and case) and a role filter work right on the page
  (`static/table-filter.js`).
- **Admins manage accounts** on `/users`:
  - Organization admins see their organization's admins and the accounts of its
    players. They change details and passwords, and link or unlink players.
  - Super admins see every account and can also change roles.
- **Passwords** are PBKDF2 hashes. Organization admins' passwords are also kept
  readable (`password_plain`) so super admins can look them up on `/orgs`. Players'
  passwords never are.
- **Cookies** are signed with HMAC:
  - `org`: which organization this browser is in.
  - `user`: the account. Includes the password hash, so a new password logs that
    account out everywhere.
  - `player_{tid}`: a guest of tournament `tid`.
- **Wrong passwords** wait 1 second before answering. **Log out** clears the account
  and guest cookies; the organization is kept.
- **Player password** of a tournament: the default is its name in lowercase with
  underscores. Admins see and change it on the tournament page.
- Accounts came from the old `superadmins` table and `organizations.admin_*` columns
  through `sql/predeployment/0001_users.sql`. The old columns are kept in sync, so the
  previous app version keeps working.
