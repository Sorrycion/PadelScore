# PadelScore: context for Claude Code

A FastAPI + Jinja2 + SQLite web app for padel leagues: organizations, accounts,
tournaments, jornadas, sets, standings, stats and medals. The UI is Spanish first
(English too), mobile first, and the reference phone is an iPhone 18 Pro (402 px).
It's live at https://padelscore-sorrycion.azurewebsites.net (repo `Sorrycion/PadelScore`).

## Start of every session

1. Your auto-memory (`MEMORY.md` index) loads by itself. It holds the live state,
   decisions and open items. Open a memory file when its topic comes up.
2. **Read `docs/processes/README.md` before changing an area**, then the page for that
   area. Each has diagrams:
   - ORGANIZATIONS, USERS, TOURNAMENTS, JORNADAS, SETS
   - STATS, MEDALS
   - DEPLOY
   - ARCHITECTURE: modules and the request flow
3. Use the project skills in `.claude/skills/`:

| Skill | When |
|---|---|
| `padelscore-feature` | Any change: branch → code → tests → screenshots → docs/memory → PR |
| `padelscore-db-change` | Any schema or seed-data change (`sql/predeployment`) |
| `padelscore-deploy` | "push", "deploy", "ship": PR → merge → pipeline; Kudu fallback |
| `padelscore-live-admin` | Look at or fix the live database on Azure |
| `padelscore-screenshot` | See pages at phone width, light and dark |
| `padelscore-medal` | Add or change a medal |

## Rules (from the user; keep them)

- **`main` is protected.** Work on a branch and open a PR as Sorrycion
  (`GH_TOKEN=$(gh auth token --user Sorrycion) gh pr create -R Sorrycion/PadelScore ...`).
  Merging deploys automatically. Commit, push or deploy only when asked; a request to
  build a feature includes opening its PR.
- **Database changes** are only new numbered files in `sql/predeployment/`. The pipeline
  runs them on the live database before the deploy. Never edit a file that has already
  run.
- **Azure:** only the personal subscription `af2fe534-02d1-4920-8bea-24efdcac3083`.
  Never touch the work subscriptions or change the az default account.
- **Secrets:** never put real credentials in code, tests, commits, docs or memory, and
  never print hashes or `password_plain`. Changing Azure secrets or identities is for
  the user to do: give them the command.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. PR bodies end
  with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- **Every user-visible text** goes in `app/i18n.py` in both `es` and `en`. A test checks
  every `_("key")`.
- The user often adds requests mid-task: fold them into the work in progress.
- **Every PR documents itself** (the user's rule, 2026-10-30). Before opening any PR,
  in the same branch:

  - **Process docs:** the `docs/processes/` page of each area touched, with its Mermaid
    diagram redrawn if the flow, the data or the screens changed. A new area gets a
    new page, linked from `docs/processes/README.md`.
  - **Architecture:** `docs/processes/ARCHITECTURE.md` if a module, route group,
    table or the navigation changed. `README.md` if setup or the project layout changed.
  - **Skills:** `.claude/skills/` updated if a procedure changed, or a new skill if
    it's a task that will repeat. New skills go in the table in `CLAUDE.md`.
  - **Memory:** the area's memory file (live state, decisions and why, open items)
    and its line in `MEMORY.md`.
  - **PR body:** a "Docs and memory" section that lists the above.

  A PR with no behavior change (e.g. only docs) still checks the list. The template
  `.github/pull_request_template.md` carries the same checklist.

## Commands

```
.venv/Scripts/python.exe -m uvicorn app.main:app --reload     # run locally (padelscore.db)
.venv/Scripts/python.exe -m pytest -q                         # tests (needs requirements-dev.txt)
.venv/Scripts/python.exe -m app.migrate --status              # pending database changes
.venv/Scripts/python.exe -m app.orgs superadmin "user" "pw"   # accounts CLI (also on Kudu)
.venv/Scripts/python.exe scripts/make_medals.py               # redraw medal images
.venv/Scripts/python.exe scripts/render_pages.py DB OUT as=... URL...   # pages for screenshots
```

On this Windows machine, Bash is Git Bash: heredocs with many quotes break, so write
patch scripts to a file and run them. PowerShell is better for anything that passes
`/paths` to Python.
