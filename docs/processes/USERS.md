# Users and logins

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
    L["/login"] --> A[👤 Mi cuenta]
    L --> P[🎾 Jugadores]
    A -- username/email + password --> U{role}
    U -- super --> S["/orgs (or where they were going)"]
    U -- org_admin --> O[enters their organization]
    U -- player --> H[home]
    P -- tournament password --> G["cookie player_{tid} per tournament<br/>(+ enters its organization)"]
```

## Accounts and players

A player row without `user_id` is a **guest player**: just a name. An account can claim
one player per organization (`players.user_id`). Its sets and tournaments are then that
account's. Admins link and unlink players on **🔑 Cuentas** (`/users`).

```mermaid
erDiagram
    users ||--o{ players : "claims (one per organization)"
    organizations ||--o{ users : "org_admin of"
    organizations ||--o{ players : has
```

## Details

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
