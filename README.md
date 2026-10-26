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
  - **Manual individual**: a matchday is just a date; each set is created by hand (court and pairs). Each player scores the games their pair won.
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

## Editing password

Anyone can view the site. To add or change data, set a club password in the
`PADELSCORE_EDIT_PASSWORD` environment variable; people then use **Entrar / Log in**
once per browser. Without it (e.g. on your own computer) editing is open.

## Deploy to Azure (free F1 plan)

The app runs on Azure App Service (Linux, Python 3.12) with these app settings:

| Setting | Value |
|---|---|
| `PADELSCORE_DB` | `/home/data/padelscore.db` (`/home` is the only folder that survives restarts) |
| `PADELSCORE_EDIT_PASSWORD` | the club password |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` (installs `requirements.txt` on deploy) |

Startup command: `gunicorn -w 1 -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000 app.main:app`

Keep the plan at one instance: SQLite must not be shared between servers.

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
