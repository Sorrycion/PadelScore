# PadelScore

A website for local padel players: track participants, matches and scores.

Built with Python, [FastAPI](https://fastapi.tiangolo.com/), Jinja2 templates and SQLite.

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
- **Sets:** created sets are *pending* until their games are entered, right on the matchday page. Any score can be entered (a set may be cut short); a tied set gives no one the set-won point. Sets can also be added one by one, edited, deleted and filtered by tournament or player. A court that already has results keeps its players.
- **Matchday points (Liga):** when all the sets of a court are played, its players get a place (1st 9, 2nd 6, 3rd 4, 4th 3) plus 1 point per set won. Places go by sets won, then games difference (won − lost), then league position before the matchday; on the first matchday a draw (fixed per court) settles ties. The same order decides court changes.
- **Tournament standings** add up the matchday points, with one column per matchday. A matchday can be deleted with its sets; the later ones are renumbered.
- **Court changes:** each matchday page suggests who moves up or down a court (1 or 2 players, per the draw). Court 1 is the top court.
- **Players:** each has a profile with results per matchday, partners and sets. Players can be renamed, and deleted while they have no sets.
- **Home page:** standings of the latest tournament.
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

- **Organization admin**: logs in with the organization's admin user and password and
  may change everything in it.
- **Super admin**: logs in with their own user and password, sees every organization
  (⭐ Organizaciones), creates organizations with their admin, resets admin passwords,
  and is admin in every organization.
- **Players**: leave the user empty and type their tournament's player password to
  enter its results.

Passwords are stored hashed. Create organizations and super admins from the command
line (it only needs the standard library, so it also works in Azure's Kudu console):

```
python -m app.orgs create "Name" "admin user" "admin password"
python -m app.orgs password "admin user" "new password"
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
  "subject": "repo:Sorrycion/PadelScore:environment:production",
  "audiences": ["api://AzureADTokenExchange"]}' -o none
echo "AZURE_CLIENT_ID=$APP AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)"
```

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
  main.py        # web routes
  db.py          # SQLite connection and schema
  scoring.py     # set validation, matchday placings, standings, court moves
  i18n.py        # UI texts in Spanish and English
  templates/     # HTML pages
  static/        # CSS
docs/            # league rules (REGLAMENTO.md)
tests/           # pytest tests
```
