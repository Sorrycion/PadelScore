---
name: padelscore-screenshot
description: See PadelScore pages as a phone shows them, in light and dark mode and as any visitor (admin, player account, guest, anonymous). It runs the app on a copy of the database and takes headless Chrome screenshots. Use it after UI or CSS changes, or when the user sends a phone screenshot of a problem.
---

# Phone screenshots

Run this from **PowerShell**: Git Bash turns arguments like `/me` into Windows paths.
`$S` is the scratchpad.

```powershell
# 1. A copy of the database (never padelscore.db itself), and a fresh server: an old one
#    keeps serving stale code.
Copy-Item padelscore.db "$S\view.db" -Force
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -Confirm:$false }
$env:PADELSCORE_DB = "$S\view.db"
Start-Process .venv\Scripts\python.exe -ArgumentList "-m","uvicorn","app.main:app","--port","8765" -WindowStyle Hidden
Start-Sleep 5

# 2. Save the pages as a given visitor. {t} = the newest tournament.
& .venv\Scripts\python.exe -X utf8 scripts\render_pages.py "$S\view.db" $S `
    "as=admin" "/users" "as=player" "/me" "as=guest" "/welcome?t={t}" "as=none" "/tournaments/{t}"

# 3. Screenshot each page with a fresh Chrome profile. Headless Chrome won't render
#    narrower than about 500 px; narrower windows just crop the right side.
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
foreach ($i in 0..3) { foreach ($mode in "light","dark") {
  $extra = @(); if ($mode -eq "dark") { $extra = "--force-dark-mode","--blink-settings=preferredColorScheme=0" }
  & $chrome --headless=new --disable-gpu "--user-data-dir=$S\chrome-$([guid]::NewGuid())" --window-size=500,1600 @extra "--screenshot=$S\page$i-$mode.png" "file:///$($S -replace '\\','/')/page$i.html"
} }
```

4. Look at the PNGs with the Read tool, fix what's off, and stop the server when you're
   done.

Notes:

- **Visitors (`as=`):**
  - `none`: a visitor who entered the first organization;
  - `admin`: its admin;
  - `player`: a player account; the script creates `demo` in the copy if needed;
  - `guest`: someone who logged in with the newest tournament's password.
- **The copy migrates when the server starts.** That's also a quick check that new
  `sql/predeployment` files work on real data.
- **For `/enter`, `/login` and `/rules`,** which need no cookies, you can use an iframe
  page at 402 px.
- **New CSS reaches phones by itself:** `style.css?v=` is a hash of every file under
  `app/static`.
