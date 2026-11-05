"""Draw the medal images: app/static/medals/<code>.svg, one per medal_types row.

Each image is just the icon of the situation (no medal or ribbon around it): a big
emoji on a transparent square, so it reads well from 20 px (ranking tables) up to
the medal pages. Tiers show as a colored glow from the stylesheet (img.medal.tier-N).
Run it again after changing a medal:

    python scripts/make_medals.py
"""
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "medals"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.medals import ICONS as MEDALS  # noqa: E402  (code: icon of the situation)


def svg(code, icon):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img">
  <title>{code}</title>
  <text x="60" y="94" text-anchor="middle" font-size="88">{icon}</text>
</svg>
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for code, icon in MEDALS.items():
        (OUT / f"{code}.svg").write_text(svg(code, icon), encoding="utf-8")
    print(f"{len(MEDALS)} medals written to {OUT}")


if __name__ == "__main__":
    main()
