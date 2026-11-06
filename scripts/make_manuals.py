"""Make the user manuals (PDF, in Spanish) with fresh phone screenshots:

    python scripts/make_manuals.py            # docs/manuales/*.pdf and app/static/manuals/

- 📘 Manual del administrador: everything an organization admin does.
- 🎾 Manual del jugador: everything a player does.

It builds a demo league in a temporary database (made-up names, never real data), runs
the app on it (port 8765), saves each page as the admin or the player would see it,
screenshots it with headless Chrome at phone width, and lays the manuals out with fpdf2
(the texts are in scripts/manual_texts.py). Run it again when screens change.
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PORT = 8765
SERVER = f"http://127.0.0.1:{PORT}"
CHROME = [os.environ.get("CHROME", ""),
          r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          shutil.which("google-chrome") or "", shutil.which("chromium") or ""]
NAMES = ["Ana Torres", "Bruno Díaz", "Carla Méndez", "Diego Ruiz", "Elena Vega", "Fer Castillo",
         "Gaby Ortiz", "Héctor Luna", "Iván Rojas", "Julia Paredes", "Kike Salas", "Lupita Ramos"]
ADMIN, ADMIN_PW = "admin_demo", "clave-demo-admin"
PLAYER, PLAYER_PW = "ana", "clave-demo-ana"


def seed(dbfile):
    """A demo league: club "Club Pádel Demo" (admin admin_demo), 12 players, the account
    "ana" (Ana Torres, with email and phone), the "Liga de Otoño" with 3 jornadas played
    and the 4th today with its courts made, and an ended "Liga de Verano"."""
    os.environ["PADELSCORE_DB"] = str(dbfile)
    from app import db, orgs, users
    from app.scoring import court_rotation
    db.DB_PATH = str(dbfile)
    db.init_db()
    random.seed(11)
    today = date.today()
    with db.connect() as conn:
        org = orgs.create_org(conn, "Club Pádel Demo", ADMIN, ADMIN_PW)
        ids = [conn.execute("INSERT INTO players (organization_id, name) VALUES (?, ?)",
                            (org, n)).lastrowid for n in NAMES]
        ana = users.create_user(conn, "player", PLAYER, PLAYER_PW, email="ana@example.com",
                                first_name="Ana", last_name="Torres", display_name="Ana Torres",
                                phone_country="MX", phone="5512345678")
        users.link_player(conn, ana, ids[0])
        for i, n in ((1, "bruno"), (2, "carla")):
            uid = users.create_user(conn, "player", n, "clave-demo-" + n,
                                    email=f"{n}@example.com", display_name=NAMES[i])
            users.link_player(conn, uid, ids[i])
        rule = dict(conn.execute("SELECT code, id FROM rule_types").fetchall())
        skill = {p: random.random() for p in ids}

        def tournament(name, held_on, jornadas, pending, ended=0):
            t = conn.execute("INSERT INTO tournaments (organization_id, name, held_on, "
                             "rule_type_id, player_password, ended) VALUES (?, ?, ?, ?, ?, ?)",
                             (org, name, held_on.isoformat(), rule["liga_amigos"],
                              "otono2026" if not ended else "verano2026", ended)).lastrowid
            conn.executemany("INSERT INTO tournament_players VALUES (?, ?)", [(t, p) for p in ids])
            for n in range(1, jornadas + pending + 1):
                played_on = held_on + timedelta(days=7 * (n - 1))
                d = conn.execute("INSERT INTO matchdays (tournament_id, number, played_on) "
                                 "VALUES (?, ?, ?)", (t, n, played_on.isoformat())).lastrowid
                order = [ids[0]] + random.sample(ids[1:], len(ids) - 1)
                for c in range(3):
                    four = order[c * 4:c * 4 + 4]
                    for k, ((a1, a2), (b1, b2)) in enumerate(court_rotation(four)):
                        ga = gb = winner = None
                        if n <= jornadas:
                            sa = skill[a1] + skill[a2] + random.random()
                            sb = skill[b1] + skill[b2] + random.random()
                            lose = random.choice([1, 2, 3, 4, 4, 5, 6])
                            ga, gb = (6, lose) if sa > sb else (lose, 6)
                            if lose == 6:
                                ga, gb = (7, 6) if sa > sb else (6, 7)
                            winner = "A" if ga > gb else "B"
                        conn.execute("INSERT INTO matches (matchday_id, court, a1, a2, b1, b2, "
                                     "team_a_games, team_b_games, winner) VALUES "
                                     "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                     (d, c + 1, a1, a2, b1, b2, ga, gb, winner))
                if n == 2:
                    conn.execute("INSERT INTO absences VALUES (?, ?)", (d, ids[11]))
            return t

        tournament("Liga de Verano", today - timedelta(days=120), 3, 0, ended=1)
        tournament("Liga de Otoño", today - timedelta(days=21), 3, 1)
        conn.execute("INSERT INTO email_log (day, organization_id, user_id, address, kind, "
                     "subject, status) VALUES (?, ?, ?, 'ana@example.com', 'reminder', "
                     "'⏰ Hoy juegas: Jornada 4 · Liga de Otoño', 'sent')",
                     (today.isoformat(), org, ana))
        conn.commit()


def ids(dbfile):
    """What the page list needs: the demo's tournament, jornadas, sets and players."""
    import sqlite3
    conn = sqlite3.connect(dbfile)
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]  # noqa: E731
    t = one("SELECT id FROM tournaments WHERE name = 'Liga de Otoño'")
    out = {"t": t, "slug": one("SELECT slug FROM organizations"),
           "past": one("SELECT id FROM tournaments WHERE name = 'Liga de Verano'"),
           "md1": one("SELECT id FROM matchdays WHERE tournament_id = ? AND number = 1", t),
           "md3": one("SELECT id FROM matchdays WHERE tournament_id = ? AND number = 3", t),
           "md4": one("SELECT id FROM matchdays WHERE tournament_id = ? AND number = 4", t),
           "ana": one("SELECT id FROM players WHERE name = 'Ana Torres'"),
           "bruno": one("SELECT id FROM players WHERE name = 'Bruno Díaz'"),
           "ana_user": one("SELECT id FROM users WHERE username = 'ana'")}
    out["pending"] = one("SELECT m.id FROM matches m WHERE m.matchday_id = ? AND ? IN "
                         "(m.a1, m.a2, m.b1, m.b2) ORDER BY m.id", out["md4"], out["ana"])
    out["played"] = one("SELECT m.id FROM matches m WHERE m.matchday_id = ? ORDER BY m.id", out["md3"])
    conn.close()
    return out


def cookies(dbfile, who):
    from app import auth, db, users
    db.DB_PATH = str(dbfile)
    with db.connect() as conn:
        org = conn.execute("SELECT * FROM organizations").fetchone()
        cookie = f"org={auth.org_cookie(org)}; lang=es; install_banner=closed"
        if who == "admin":
            cookie += f"; user={auth.user_cookie(users.org_admin(conn, org['id']))}"
        elif who == "player":
            cookie += f"; user={auth.user_cookie(users.find_login(conn, PLAYER))}"
        elif who == "anon":
            cookie = "lang=es; install_banner=closed"
    return cookie


def page(dbfile, outdir, name, who, url, options=()):
    """Save one page as `who` sees it. Options: "menu" (the ☰ menu open), "open=<id>"
    (that folded <details> open), "banner" (keep the install banner), "games" (a score
    typed in: 6-3)."""
    req = urllib.request.Request(SERVER + url, headers={"Cookie": cookies(dbfile, who)})
    html = urllib.request.urlopen(req).read().decode()
    html = html.replace('="/static/', f'="{SERVER}/static/')
    if "menu" in options:
        html = html.replace('id="menu-toggle" class="menu-toggle" hidden',
                            'id="menu-toggle" class="menu-toggle" hidden checked')
    for option in options:
        if option.startswith("open="):
            html = html.replace(f'id="{option[5:]}"', f'id="{option[5:]}" open', 1)
    if "games" in options:
        html = html.replace('name="team_a_games"', 'name="team_a_games" value="6"', 1)
        html = html.replace('name="team_b_games"', 'name="team_b_games" value="3"', 1)
    if "banner" not in options:
        html = html.replace("</head>", "<style>#install-banner{display:none!important}</style></head>")
    (Path(outdir) / f"{name}.html").write_text(html, encoding="utf-8")


def shoot(chrome, outdir, name, height=4400):
    """<name>.png: the page at phone width (500 px), cut where the page ends."""
    from PIL import Image
    html, png = Path(outdir) / f"{name}.html", Path(outdir) / f"{name}.png"
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([chrome, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
                        "--hide-scrollbars", f"--window-size=500,{height}",
                        f"--screenshot={png}", html.as_uri()],
                       check=True, capture_output=True, timeout=120)
    im = Image.open(png).convert("RGB")
    bg = im.getpixel((2, im.height - 2))
    bottom = im.height
    px = im.load()
    while bottom > 200 and all(px[x, bottom - 1] == bg for x in range(0, im.width, 4)):
        bottom -= 1
    im.crop((0, 0, im.width, min(bottom + 16, im.height))).save(png, optimize=True)
    return png


def capture(dbfile, outdir, pages):
    """Run the app on the demo database and screenshot every page."""
    chrome = next((c for c in CHROME if c and Path(c).exists()), None)
    if chrome is None:
        sys.exit("Chrome not found (set CHROME=...)")
    # Email "on" (a made-up key): the pages show what admins see with email set up.
    # Only GETs are made, so nothing is ever sent.
    env = {**os.environ, "PADELSCORE_DB": str(dbfile), "MAIL_SENDER": "DoNotReply@demo.example",
           "ACS_CONNECTION_STRING": "endpoint=https://demo.example/;accesskey=ZGVtbw=="}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port",
                               str(PORT)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(SERVER + "/health", timeout=2)
                break
            except OSError:
                time.sleep(0.5)
        for name, (who, url, *rest) in pages.items():
            page(dbfile, outdir, name, who, url, rest)
            shoot(chrome, outdir, name)
            print("📸", name, who, url)
    finally:
        server.terminate()
        server.wait(10)


def pages_for(i):
    s = "/" + i["slug"]
    return {
        # who, url, options
        "login": ("anon", "/"),
        "admin_home": ("admin", "/"),
        "admin_menu": ("admin", f"{s}/standings", "menu"),
        "standings": ("admin", f"{s}/standings"),
        "tournaments": ("admin", f"{s}/tournaments", "open=new-tournament"),
        "tournament": ("admin", f"{s}/tournaments/{i['t']}"),
        "new_matchday": ("admin", f"{s}/tournaments/{i['t']}/matchdays/new"),
        "courts": ("admin", f"{s}/matchdays/{i['md4']}/courts"),
        "matchday_admin": ("admin", f"{s}/matchdays/{i['md3']}"),
        "set_edit_admin": ("admin", f"{s}/matches/{i['played']}/edit"),
        "replace": ("admin", f"{s}/tournaments/{i['t']}/players/{i['bruno']}/replace"),
        "summary": ("admin", f"{s}/tournaments/{i['t']}/summary"),
        "players": ("admin", f"{s}/players"),
        "users": ("admin", f"{s}/users"),
        "user_edit": ("admin", f"{s}/users/{i['ana_user']}"),
        "emails": ("admin", f"{s}/emails"),
        "sets": ("admin", f"{s}/matches?tournament={i['t']}"),
        "medals": ("admin", f"{s}/medals"),
        "rules": ("admin", "/rules"),
        "signup": ("anon", "/signup"),
        "player_home": ("player", "/", "banner"),
        "player_menu": ("player", f"{s}/standings", "menu"),
        "player_tournament": ("player", f"{s}/tournaments/{i['t']}"),
        "matchday_player": ("player", f"{s}/matchdays/{i['md4']}"),
        "set_score": ("player", f"{s}/matches/{i['pending']}/edit", "games"),
        "my_summary": ("player", f"{s}/players/{i['ana']}"),
        "my_stats": ("player", f"{s}/players/{i['ana']}/stats"),
        "my_medals": ("player", f"{s}/players/{i['ana']}/medals"),
        "vs": ("player", f"{s}/players/{i['ana']}/vs?other={i['bruno']}"),
        "recap": ("player", f"{s}/matchdays/{i['md3']}/recap?player={i['ana']}"),
        "me": ("player", "/me"),
        "install": ("player", "/install"),
    }


def main():
    from manual_texts import ADMIN_MANUAL, PLAYER_MANUAL  # noqa: E402 (next to this file)
    import manual_pdf
    # MANUAL_WORK=<folder>: reuse that folder's screenshots (to retouch only the texts)
    reuse = os.environ.get("MANUAL_WORK")
    work = Path(reuse) if reuse else Path(tempfile.mkdtemp(prefix="manuals-"))
    if reuse:
        (work / "demo.db").unlink(missing_ok=True)
    dbfile = work / "demo.db"
    seed(dbfile)
    info = ids(dbfile)
    if not reuse:
        capture(dbfile, work, pages_for(info))
    from app import db, main as app_main, report
    from app.i18n import translator
    db.DB_PATH = str(dbfile)
    with db.connect() as conn:
        data = app_main.in_org(1, lambda: app_main.jornada_summary(conn, info["md3"], "es"))
    (work / "jornada.pdf").write_bytes(report.build(data, translator("es")))
    manual_pdf.render_pdf_page(work / "jornada.pdf", work / "jornada_pdf.png")
    for manual, file in ((ADMIN_MANUAL, "manual-administrador.pdf"),
                         (PLAYER_MANUAL, "manual-jugador.pdf")):
        pdf = manual_pdf.build(manual, work)
        for out in (ROOT / "docs" / "manuales", ROOT / "app" / "static" / "manuals"):
            out.mkdir(parents=True, exist_ok=True)
            (out / file).write_bytes(pdf)
        print("📘", file, f"{len(pdf) // 1024} KB")
    print("work:", work)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
