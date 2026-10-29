---
name: padelscore-screenshot
description: See a PadelScore page as a phone shows it (402 px wide, the width of an iPhone 18 Pro), in light or dark mode, by running the app locally and taking a headless Chrome screenshot. Use after UI or CSS changes, or when the user sends a phone screenshot of a problem.
---

# Phone screenshots of PadelScore

1. **Run a local server on a throwaway copy of the database.** Never use
   `padelscore.db` for this. Before starting, stop anything already on the port, because
   an old server keeps serving stale code:
   ```powershell
   Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -Confirm:$false }
   $env:PADELSCORE_DB = "<scratchpad>\view.db"   # a copy: Copy-Item padelscore.db <scratchpad>\view.db
   Start-Process .venv\Scripts\python.exe -ArgumentList "-m","uvicorn","app.main:app","--port","8765" -WindowStyle Hidden
   ```
2. **Pages that need an organization** (almost all of them) redirect to `/enter`
   without the `org` cookie. Fetch the HTML with that cookie and point it at the
   server's static files:
   ```python
   # run with PYTHONPATH=<project>
   import sqlite3, urllib.request
   from app import auth
   c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
   org = c.execute("SELECT * FROM organizations ORDER BY id LIMIT 1").fetchone()
   req = urllib.request.Request(URL, headers={"Cookie": f"org={auth.org_cookie(org)}; lang=es"})
   html = urllib.request.urlopen(req).read().decode().replace('="/static/', '="http://127.0.0.1:8765/static/')
   ```
   Pages open without an organization (`/enter`, `/login`, `/rules`) can go through an
   iframe page at 402 px instead.
3. **Screenshot** with a fresh profile each time, so no cookies or cache carry over:
   ```powershell
   & $chrome --headless=new --disable-gpu "--user-data-dir=<scratchpad>\chrome-<guid>" --window-size=402,1700 "--screenshot=<scratchpad>\shot.png" "file:///<page>.html"
   ```
   For dark mode, add `--force-dark-mode --blink-settings=preferredColorScheme=0`.
4. **Look at the PNG** with the Read tool, then stop the server.

`style.css?v=` is a hash of the static files, so phones get new CSS by themselves. No
version needs bumping by hand.
