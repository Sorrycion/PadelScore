# PadelScore

A website for local padel players: track participants, matches and scores.

Built with Python, [FastAPI](https://fastapi.tiangolo.com/), Jinja2 templates and SQLite.

## Features

Scoring follows the league rules in [`docs/REGLAMENTO.md`](docs/REGLAMENTO.md), also shown on the **Rules** page.

- **Tournaments (leagues)** are played over **matchdays** (*jornadas*), normally 6, one per week.
- **Sets:** on a matchday, players are split into courts of 4. Each court plays 3 sets, with every player partnering each of the other three once. Any score can be entered (a set may be cut short); a tied set gives no one the set-won point. Sets can be edited, deleted and filtered by tournament or player.
- **Matchday points:** every set is scored on its own, whatever the court. The two winners share 1st place (**9**) plus **1 for the set won** = 10 each; the two losers share 2nd place (**6** each). A tied set gives 9 to all four. A player's matchday points are the sum over their sets. On each court, players are listed by points, then games difference (games won − games lost), then league position before the matchday; that order only decides court changes.
- **Tournament standings** add up the matchday points, with one column per matchday.
- **Court changes:** each matchday page suggests who moves up or down a court (1 or 2 players, per the draw). Court 1 is the top court.
- **Players:** each has a profile with results per matchday, partners and sets.
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
