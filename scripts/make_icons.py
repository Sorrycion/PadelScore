"""Draw the app icons: app/static/icons/icon.svg and the PNGs phones need.

The icon is a padel ball on the app's blue. The SVG is the favicon; the PNGs are for
"Add to Home Screen" (apple-touch-icon, 180 px) and the web app manifest (192 and
512 px, plus a "maskable" 512 with room around the ball for Android's round masks).
The PNGs are screenshots of the SVG taken with headless Chrome:

    python scripts/make_icons.py "C:/Program Files/Google/Chrome/Application/chrome.exe"
"""
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"


def svg(pad=0, square=False):
    """The icon on a 512 square; `pad` shrinks the ball (maskable icons) and `square`
    leaves the corners to the phone (iOS rounds them, and fills see-through ones black)."""
    r = 170 - pad
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#6aa5ff"/><stop offset="1" stop-color="#4568f5"/>
    </linearGradient>
    <radialGradient id="ball" cx="40%" cy="35%" r="70%">
      <stop offset="0" stop-color="#f4ff9a"/><stop offset="1" stop-color="#c6e33a"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" rx="{0 if pad or square else 112}" fill="url(#bg)"/>
  <circle cx="256" cy="256" r="{r}" fill="url(#ball)"/>
  <path d="M{256 - r * 0.93:.0f} {256 - r * 0.38:.0f} C {256 - r * 0.25:.0f} {256 - r * 0.2:.0f}, {256 - r * 0.25:.0f} {256 + r * 0.2:.0f}, {256 - r * 0.93:.0f} {256 + r * 0.38:.0f}"
        fill="none" stroke="#fff" stroke-width="{r * 0.09:.0f}" stroke-linecap="round"/>
  <path d="M{256 + r * 0.93:.0f} {256 - r * 0.38:.0f} C {256 + r * 0.25:.0f} {256 - r * 0.2:.0f}, {256 + r * 0.25:.0f} {256 + r * 0.2:.0f}, {256 + r * 0.93:.0f} {256 + r * 0.38:.0f}"
        fill="none" stroke="#fff" stroke-width="{r * 0.09:.0f}" stroke-linecap="round"/>
</svg>
'''


def main(chrome=None):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(svg(), encoding="utf-8")
    if not chrome:
        print("icon.svg written; pass Chrome's path to also draw the PNGs")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for name, size, pad, square in (("apple-touch-icon.png", 180, 0, True),
                                        ("icon-192.png", 192, 0, False),
                                        ("icon-512.png", 512, 0, False),
                                        ("icon-maskable-512.png", 512, 50, True)):
            page = Path(tmp) / f"{name}.html"
            page.write_text(f'<!doctype html><body style="margin:0">'
                            f'<div style="width:{size}px;height:{size}px">'
                            f'{svg(pad, square).replace("<svg ", f"<svg width={size} height={size} ")}'
                            f'</div></body>', encoding="utf-8")
            subprocess.run([chrome, "--headless=new", "--disable-gpu",
                            "--default-background-color=00000000", "--hide-scrollbars",
                            f"--user-data-dir={tmp}/profile-{size}-{pad}",
                            f"--window-size={size},{size}", f"--screenshot={OUT / name}",
                            page.as_uri()], check=True, capture_output=True)
            print("wrote", OUT / name)


if __name__ == "__main__":
    main(*sys.argv[1:2])
