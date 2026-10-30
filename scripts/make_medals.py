"""Draw the medal images: app/static/medals/<code>.svg, one per medal_types row.

Every medal shares one design: a ribbon and a round medal with a glyph. The kind sets
the colors: glory gold, rival steel blue, shame purple. The podium medals are gold,
silver and bronze with their number. Run it again after changing a medal:

    python scripts/make_medals.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "medals"

KINDS = {  # medal fill, ring, ribbon left, ribbon right
    "glory": ("#ffd75e", "#c9971c", "#e04848", "#3f6fd8"),
    "rival": ("#a9c8ee", "#3e6fa8", "#2c3e66", "#c0392b"),
    "shame": ("#c9a6f0", "#6d44a3", "#6d44a3", "#3fae6a"),
}
PODIUM = {"campeon": ("#ffd75e", "#c9971c", "1"), "subcampeon": ("#e3e7ee", "#8d96a6", "2"),
          "tercero": ("#f0b27a", "#a35f25", "3")}
MEDALS = {  # code: (kind, glyph)
    "campeon": ("glory", "1"), "subcampeon": ("glory", "2"), "tercero": ("glory", "3"),
    "racha": ("glory", "🔥"), "perfecta": ("glory", "💯"), "rey_pista": ("glory", "👑"),
    "escalador": ("glory", "🧗"), "rosco": ("glory", "🍩"), "muro": ("glory", "🧱"),
    "infarto": ("glory", "❤️"), "pareja_oro": ("glory", "🤝"), "asistencia": ("glory", "📅"),
    "veterano": ("glory", "⭐"),
    "rival": ("rival", "⚔️"), "verdugo": ("rival", "🪓"),
    "gafe": ("shame", "🐈‍⬛"), "comio_rosco": ("shame", "🥯"), "farolillo": ("shame", "🏮"),
    "jornada_negra": ("shame", "🌑"), "paracaidas": ("shame", "🪂"),
    "bestia_negra": ("shame", "😈"), "fantasma": ("shame", "👻"),
}


def svg(code, kind, glyph):
    fill, ring, left, right = KINDS[kind]
    if code in PODIUM:
        fill, ring, glyph = PODIUM[code]
    number = glyph.isdigit()
    text = (f'<text x="60" y="104" text-anchor="middle" font-family="Georgia, serif" '
            f'font-size="40" font-weight="700" fill="{ring}">{glyph}</text>' if number else
            f'<text x="60" y="102" text-anchor="middle" font-size="34">{glyph}</text>')
    nose = ('<circle cx="60" cy="117" r="5" fill="#e53935" stroke="#fff" stroke-width="1.5"/>'
            if kind == "shame" else "")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 140" role="img">
  <title>{code}</title>
  <defs>
    <radialGradient id="g" cx="40%" cy="35%" r="70%">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".85"/>
      <stop offset=".45" stop-color="{fill}"/>
      <stop offset="1" stop-color="{ring}"/>
    </radialGradient>
  </defs>
  <path d="M30 4 h24 l14 50 h-24 z" fill="{left}"/>
  <path d="M90 4 h-24 l-14 50 h24 z" fill="{right}"/>
  <path d="M42 4 h6 l12 44 l-3 6 z" fill="#ffffff" opacity=".25"/>
  <circle cx="60" cy="90" r="44" fill="{ring}"/>
  <circle cx="60" cy="90" r="38" fill="url(#g)"/>
  <circle cx="60" cy="90" r="38" fill="none" stroke="#ffffff" stroke-opacity=".5" stroke-width="2" stroke-dasharray="3 4"/>
  {text}
  {nose}
</svg>
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for code, (kind, glyph) in MEDALS.items():
        (OUT / f"{code}.svg").write_text(svg(code, kind, glyph), encoding="utf-8")
    print(f"{len(MEDALS)} medals written to {OUT}")


if __name__ == "__main__":
    main()
