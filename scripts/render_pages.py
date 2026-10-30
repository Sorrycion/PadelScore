"""Save app pages as a given visitor, ready for a headless-Chrome phone screenshot.

The app must be running on DB (e.g. a copy of padelscore.db; never the real one):

    python scripts/render_pages.py DB OUTDIR as=guest "/welcome?t={t}" as=player /me as=admin /users

`as=` sets who is looking for the URLs after it:
  none    a visitor who entered the first organization
  admin   that organization's admin
  player  a player account (one called "demo" is created in DB if there is none)
  guest   a guest with the tournament password of {t}
`{t}` in a URL is that organization's newest tournament. Pages are written to
OUTDIR/page0.html, page1.html..., with links to the server's stylesheet, for:

    chrome --headless=new --window-size=500,1600 --screenshot=OUT.png file:///OUTDIR/page0.html

(Headless Chrome won't go narrower than about 500 px. In Git Bash, arguments starting
with "/" become Windows paths: run this from PowerShell, or write "//me".)
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import auth, db, users  # noqa: E402

SERVER = "http://127.0.0.1:8765"


def main(dbfile, outdir, *args):
    db.DB_PATH = dbfile
    with db.connect() as conn:
        org = conn.execute("SELECT * FROM organizations ORDER BY id LIMIT 1").fetchone()
        admin = users.org_admin(conn, org["id"])
        player = conn.execute("SELECT * FROM users WHERE role = 'player' ORDER BY id").fetchone()
        t = conn.execute("SELECT * FROM tournaments WHERE organization_id = ? "
                         "ORDER BY id DESC LIMIT 1", (org["id"],)).fetchone()
        if player is None and t is not None:
            pid = conn.execute("SELECT m.a1 FROM matches m JOIN matchdays d ON d.id = "
                               "m.matchday_id WHERE d.tournament_id = ? LIMIT 1",
                               (t["id"],)).fetchone()
            uid = users.create_user(conn, "player", "demo", "clave-demo",
                                    email="demo@example.com", first_name="Demo")
            if pid:
                users.link_player(conn, uid, pid[0])
            player = users.get(conn, uid)
    who, i = "none", 0
    for arg in args:
        if arg.startswith("as="):
            who = arg[3:]
            continue
        url = "/" + arg.lstrip("/").replace("{t}", str(t["id"] if t else 0))
        cookie = f"org={auth.org_cookie(org)}; lang=es"
        if who == "admin":
            cookie += f"; user={auth.user_cookie(admin)}"
        elif who == "player":
            cookie += f"; user={auth.user_cookie(player)}"
        elif who == "guest":
            cookie += f"; player_{t['id']}={auth.player_token(t)}"
        req = urllib.request.Request(SERVER + url, headers={"Cookie": cookie})
        html = urllib.request.urlopen(req).read().decode()
        html = html.replace('="/static/', f'="{SERVER}/static/')
        out = Path(outdir) / f"page{i}.html"
        out.write_text(html, encoding="utf-8")
        print(out, who, url)
        i += 1


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:])
