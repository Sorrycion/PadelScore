"""Draw the medal images: app/static/medals/<code>.svg, one per medal_types row.

Each image is just the icon of the situation (no medal or ribbon around it): a big
emoji on a transparent square, so it reads well from 20 px (ranking tables) up to
the medal pages. Tiers show as a colored glow from the stylesheet (img.medal.tier-N).
The 📄 jornada summary (a PDF) can't draw emoji, so each image also has a PNG
(app/static/medals/png/<code>.png), screenshot from the SVG by headless Chrome so it
looks like the web. The jornada's set medals (medals.SET_ICONS) are set_<code>.
Run it again after changing a medal:

    python scripts/make_medals.py            # SVG and PNG (needs Chrome)
    python scripts/make_medals.py --svg      # SVG only
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "medals"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.medals import ICONS, SET_ICONS  # noqa: E402  (code: icon of the situation)

MEDALS = {**ICONS, **{f"set_{code}": icon for code, icon in SET_ICONS.items()}}
CHROME = [os.environ.get("CHROME", ""),
          r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          shutil.which("google-chrome") or "", shutil.which("chromium") or ""]


def svg(code, icon):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img">
  <title>{code}</title>
  <text x="60" y="94" text-anchor="middle" font-size="88">{icon}</text>
</svg>
'''


SIZE, PER_ROW = 120, 4  # headless Chrome won't draw a window narrower than ~500 px


def pngs(chrome):
    """app/static/medals/png/<code>.png (120 px, transparent) from the SVGs: one page
    with every icon in a grid, one screenshot, cut into squares."""
    from PIL import Image  # installed with fpdf2

    codes = list(MEDALS)
    rows = -(-len(codes) // PER_ROW)
    cells = "".join(f'<img src="{(OUT / (c + ".svg")).as_uri()}">' for c in codes)
    page = (f"<html><body style='margin:0;background:transparent;display:grid;"
            f"grid-template-columns:repeat({PER_ROW},{SIZE}px)'>"
            f"<style>img{{width:{SIZE}px;height:{SIZE}px;display:block}}</style>{cells}</body></html>")
    (OUT / "png").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        html, shot = Path(tmp) / "medals.html", Path(tmp) / "medals.png"
        html.write_text(page, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", f"--user-data-dir={tmp}/profile",
                        "--hide-scrollbars", "--default-background-color=00000000",
                        f"--window-size={max(SIZE * PER_ROW, 500)},{SIZE * rows}",
                        f"--screenshot={shot}", html.as_uri()],
                       check=True, capture_output=True, timeout=120)
        sheet = Image.open(shot)
        for i, code in enumerate(codes):
            x, y = (i % PER_ROW) * SIZE, (i // PER_ROW) * SIZE
            sheet.crop((x, y, x + SIZE, y + SIZE)).save(OUT / "png" / f"{code}.png", optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for code, icon in MEDALS.items():
        (OUT / f"{code}.svg").write_text(svg(code, icon), encoding="utf-8")
    print(f"{len(MEDALS)} medals written to {OUT}")
    if "--svg" in sys.argv:
        return
    chrome = next((c for c in CHROME if c and Path(c).exists()), None)
    if chrome is None:
        sys.exit("Chrome not found (set CHROME=...): PNGs not drawn")
    pngs(chrome)
    print(f"{len(MEDALS)} PNGs written to {OUT / 'png'}")


if __name__ == "__main__":
    main()
