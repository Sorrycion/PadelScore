# PadelScore

A website for local padel players: track participants, matches and scores.

Built with Python, [FastAPI](https://fastapi.tiangolo.com/), Jinja2 templates and SQLite.

How each part works (organizations, logins, tournaments, jornadas, sets, deploy), with
diagrams: [docs/processes](docs/processes/README.md).

## Features

Scoring follows the league rules in [`docs/REGLAMENTO.md`](docs/REGLAMENTO.md), also shown on the **Rules** page.

- **Tournaments (leagues)** are played over **matchdays** (*jornadas*), normally 6, one per week.
- **Rules types** (table `rule_types`), chosen when creating a tournament:
  - **Liga de amigos score**: matchdays with courts of 4, three sets per court (rotating partners). When a court finishes, places 9 / 6 / 4 / 3 plus 1 per set won; places go by sets won, then games difference, then ranking (a draw on the first matchday). Court changes.
  - **Americano**: choose the players and the points per match (16/21/24/32). Each round has one match per court; partners rotate so everyone plays with everyone (rests rotate when the count isn't a multiple of 4). Each player scores the points their pair won; ranking by points, then difference, then wins.
  - **Mexicano**: like Americano, but round 1 is a draw and later rounds follow the ranking (1st+3rd vs 2nd+4th on court 1, and so on).
  - **Manual individual**: a matchday is just a date; each set is created by hand (court and pairs). Each player scores the games difference of each set (can go negative).
- **Absences:** on a matchday page a player can be marked absent. Their sets stay the same (a substitute plays), but they score 0 that matchday, win or lose, and it doesn't count as played.
- **Courts:** *Add matchday* opens a draft: from matchday 2 on it first asks whether 1 or 2 players move up and down per court (court 1's best and the last court's worst stay), then suggests the courts from the previous matchday. Move players, add or remove courts, and press **Save matchday**: only then are the matchday and each court's 3 sets saved (every player partnering each of the other three once). Cancelling saves nothing.
- **Sets:** created sets are *pending* until their games are entered on the set's Edit page. Any score can be entered (a set may be cut short); a tied set gives no one the set-won point. Sets can also be added one by one, edited, deleted and filtered by tournament or player. A court that already has results keeps its players.
- **Matchday points (Liga):** when all the sets of a court are played, its players get a place (1st 9, 2nd 6, 3rd 4, 4th 3) plus 1 point per set won. Places go by sets won, then games difference (won − lost), then league position before the matchday; on the first matchday a draw (fixed per court) settles ties. The same order decides court changes.
- **Tournament standings** add up the matchday points, with one column per matchday. A matchday can be deleted with its sets; the later ones are renumbered.
- **Court changes:** each matchday page suggests who moves up or down a court (1 or 2 players, per the draw). Court 1 is the top court.
- **Players:** each has a profile with results per matchday, partners and sets. Players can be renamed, and deleted while they have no sets.
- **Home page:** the login; once logged in, your next sets (by date) and every
  tournament you play or run. Standings of the latest tournament are at `/standings`.
- **Language:** Spanish (default) or English, switched with ES / EN in the header; the choice is remembered in a cookie. Texts live in `app/i18n.py`.
- Works on phones and supports dark mode.

## Run it locally (Windows)

```powershell
cd PadelScore
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 in your browser.

The database is a file named `padelscore.db` created in the project folder. Set the `PADELSCORE_DB` environment variable to store it somewhere else.

## Organizations and logins

Everything (players, tournaments, sets) belongs to an **organization**. Visitors first
enter one by its name (🏢 in the top bar changes it) and can then see its tournaments.

Logins (`/login` has two sections):

- **👤 My account**: a username or email and password (table `users`). The role
  decides what it may do:
  - **Super admin**: sees every organization (⭐ Organizaciones), creates them with
    their admin, sees and changes admin credentials, and is admin everywhere.
  - **Organization admin**: may change everything in their organization, including its
    accounts (🔑 Cuentas: details, passwords, linked player).
  - **Player**: enters results in the tournaments of the player it's linked to.
- **🎾 Players**: a tournament's player password logs in as a guest for that tournament.

Passwords are stored hashed (organization admins' also readable, for super admins).
Create organizations and super admins from the command line (it only needs the
standard library, so it also works in Azure's Kudu console):

```
python -m app.orgs create "Name" "admin user" "admin password"
python -m app.orgs password "user" "new password"
python -m app.orgs superadmin "user" "password"
```

The first organization created adopts the players and tournaments from before
organizations existed.

## Deploy to Azure (free F1 plan)

The app runs on Azure App Service (Linux, Python 3.12) with these app settings:

| Setting | Value |
|---|---|
| `PADELSCORE_DB` | `/home/data/padelscore.db` (`/home` is the only folder that survives restarts) |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` (installs `requirements.txt` on deploy) |

Startup command: `gunicorn -w 1 -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000 app.main:app`

Keep the plan at one instance: SQLite must not be shared between servers.

### Database changes (pre-deployment SQL)

Schema changes are numbered SQL files in `sql/predeployment/` (`0001_users.sql`,
`0002_...`). `app/migrate.py` runs the ones a database hasn't had yet, in order, each in
a transaction, and records them in `schema_migrations`. The app does it on start, and
the pipeline does it on the live database **before** deploying the new code, right
after backing it up. Write changes that the running version tolerates (add tables and
columns, don't drop or rename in the same release), and never edit a file that has
already run: add a new one.

```
python -m app.migrate --status   # applied / PENDING files (read only)
python -m app.migrate            # apply what's pending
```

### Automatic deploy

`.github/workflows/deploy.yml` runs on every push to `main` (merged pull requests
included) and from the Actions tab: it runs the tests, copies the live database to
`/home/data/padelscore-backup-<date>-gh.db`, deploys and checks that the site answers.

It logs in to Azure as the service principal `padelscore-github`, which has no password:
GitHub's OpenID Connect token for this repo's `production` environment is trusted
instead, and it can only manage this web app (role Website Contributor). To set it up
once, in Azure Cloud Shell (Bash) signed in with the account that owns the subscription:

```bash
SUB=<subscription id>
SITE=/subscriptions/$SUB/resourceGroups/padelscore-rg/providers/Microsoft.Web/sites/padelscore-sorrycion
APP=$(az ad app create --display-name padelscore-github --query appId -o tsv)
az ad sp create --id $APP -o none
az role assignment create --assignee $APP --role "Website Contributor" --scope $SITE -o none
az ad app federated-credential create --id $APP --parameters '{"name": "github-production",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:Sorrycion@28118944/PadelScore@1432403444:environment:production",
  "audiences": ["api://AzureADTokenExchange"]}' -o none
echo "AZURE_CLIENT_ID=$APP AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)"
```

The subject names the owner and repo with their GitHub ids (`Sorrycion@28118944`,
`PadelScore@1432403444`): it's what GitHub sends for this repo, as the failed login
shows if it ever changes.

Then add the repository secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and
`AZURE_SUBSCRIPTION_ID` (Settings → Secrets and variables → Actions).

## Run the tests

```powershell
pip install -r requirements-dev.txt
pytest
```

## Project layout

```
app/
  main.py        # web routes and queries
  auth.py        # cookies, roles, who may score
  users.py       # accounts and password hashing (standard library only)
  orgs.py        # organizations (also a CLI, standard library only)
  db.py          # SQLite connection, starting schema, older migrations
  migrate.py     # runs sql/predeployment files once each
  scoring.py     # set validation, matchday placings, standings, court moves
  rounds.py      # Americano / Mexicano round draws
  stats.py       # player statistics
  medals.py      # who has which medal
  charts.py      # inline SVG charts
  i18n.py        # UI texts in Spanish and English
  templates/     # HTML pages
  static/        # CSS, picker.js, medals/*.svg
sql/predeployment/  # numbered database changes, run before each deploy
scripts/         # make_medals.py (medal images), render_pages.py (screenshots)
docs/            # league rules (REGLAMENTO.md), processes/ (how each part works, diagrams)
CLAUDE.md        # context Claude Code loads in every session
.claude/skills/  # Claude Code skills: feature, db-change, deploy, live admin, screenshot, medal
.github/         # CI: tests on PRs; on main: test, backup, SQL, deploy, version check
tests/           # pytest tests
```
