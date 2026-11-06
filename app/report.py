"""📄 The jornada summary as a PDF (fpdf2), for admins to send or share.

`build(data, _)` turns what main.jornada_summary() gathers into the PDF's bytes:
1. the ranking after the jornada, with each player's medals in the tournament;
2. the jornada's set medals (stats.set_highlights: el más reñido, la sorpresa...);
3. every set and its result, by court, with the chance each pair had;
4. the points jornada by jornada, one small chart per player (all of them on the same
   scale, the others in gray);
5. the next jornada's sets with each pair's chance, if it's already made.

PDF core fonts only speak Latin-1, which covers Spanish; anything else (emoji, arrows)
is replaced, so icons are images: app/static/medals/png/<code>.png
(scripts/make_medals.py).
"""
from pathlib import Path

from fpdf import FPDF

ICONS = Path(__file__).parent / "static" / "medals" / "png"

INK, MUTED, LINE, SOFT = (20, 27, 45), (107, 114, 128), (226, 229, 236), (241, 242, 246)
ACCENT, ACCENT_SOFT = (69, 104, 245), (231, 237, 255)
BLUE, RED, UP, DOWN = (69, 104, 245), (200, 49, 42), (31, 157, 85), (200, 49, 42)
GRAY_LINE = (205, 209, 218)

PLAIN = str.maketrans({"–": "-", "—": "-", "·": "|", "’": "'", "‘": "'", "“": '"',
                       "”": '"', "…": "...", "▲": "+", "▼": "-", "×": "x"})


def latin(text):
    """Text the PDF's core fonts can draw."""
    return str(text).translate(PLAIN).encode("latin-1", "replace").decode("latin-1")


class Summary(FPDF):
    footer_text = ""

    def footer(self):
        self.set_y(-10)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 5, latin(self.footer_text), align="L")
        self.cell(0, 5, f"{self.page_no()}/{{nb}}", align="R")


def fit(pdf, text, width):
    """The text cut with '...' to fit `width` in the current font."""
    text = latin(text)
    if pdf.get_string_width(text) <= width:
        return text
    while text and pdf.get_string_width(text + "...") > width:
        text = text[:-1]
    return text.rstrip() + "..."


def room(pdf, height):
    """A new page unless `height` mm still fit on this one."""
    if pdf.get_y() + height > pdf.page_break_trigger:
        pdf.add_page()


def section(pdf, title, note="", keep=0):
    """A section title, on a new page unless it and `keep` mm of what follows fit."""
    room(pdf, 24 + keep)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 7, latin(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 18, pdf.get_y())
    pdf.ln(1.5)
    if note:
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 4, latin(note), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)


def icon(pdf, code, x, y, size):
    path = ICONS / f"{code}.png"
    if path.exists():
        pdf.image(str(path), x=x, y=y, w=size, h=size)


def header(pdf, data, _):
    md = data["matchday"]
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, pdf.w, 34, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(pdf.l_margin, 7)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, latin(f"PadelScore  |  {data['org']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, latin(f"{_('pdf_title')}: {data['label']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10.5)
    pdf.cell(0, 6, latin(f"{data['tournament']['name']}  |  {md['played_on']}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(40)


def ranking(pdf, data, _):
    section(pdf, _("pdf_ranking"), _("pdf_ranking_note", label=data["label"]))
    widths = (10, 64, 16, 20, 16)  # #, player, points, today, moved; then medals
    medal_w = pdf.epw - sum(widths)
    heads = ("#", _("player"), _("pdf_points"), data["short"], _("pdf_moved"))
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(*MUTED)
    for w, h in zip(widths, heads):
        pdf.cell(w, 6, latin(h), align="C" if w != 64 else "L")
    pdf.cell(medal_w, 6, latin(_("pdf_medals")), new_x="LMARGIN", new_y="NEXT")
    row_h, size = 7.5, 5.6
    for i, r in enumerate(data["ranking"]):
        room(pdf, row_h)
        x, y = pdf.l_margin, pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(*SOFT)
            pdf.rect(x, y, pdf.epw, row_h, style="F")
        pos = r["position"]
        pdf.set_font("Helvetica", "B", 9.5)
        if pos <= 3:
            pdf.set_fill_color(*((212, 160, 23), (150, 158, 172), (176, 112, 64))[pos - 1])
            pdf.set_text_color(255, 255, 255)
            pdf.ellipse(x + 2.2, y + 1.2, 5.2, 5.2, style="F")
        else:
            pdf.set_text_color(*INK)
        pdf.cell(widths[0], row_h, str(pos), align="C")
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", "B" if pos <= 3 else "", 9.5)
        pdf.cell(widths[1], row_h, fit(pdf, r["name"], widths[1] - 2))
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.cell(widths[2], row_h, str(r["points"]), align="C")
        pdf.set_font("Helvetica", "", 9.5)
        today = r["today"]
        pdf.set_text_color(*(MUTED if today is None else INK))
        pdf.cell(widths[3], row_h, "-" if today is None else f"{today:+d}" if data["signed"]
                 else str(today), align="C")
        moved = r["moved"]
        pdf.set_text_color(*(UP if moved and moved > 0 else DOWN if moved else MUTED))
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(widths[4], row_h, "-" if moved is None else f"+{moved}" if moved > 0
                 else str(moved) if moved else "=", align="C")
        mx = x + sum(widths)
        shown = r["medals"][: int(medal_w // (size + 0.6)) - 1]
        for k, code in enumerate(shown):
            icon(pdf, code, mx + k * (size + 0.6), y + (row_h - size) / 2, size)
        if len(r["medals"]) > len(shown):
            pdf.set_xy(mx + len(shown) * (size + 0.6), y)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*MUTED)
            pdf.cell(8, row_h, f"+{len(r['medals']) - len(shown)}")
        pdf.set_xy(x, y + row_h)
    if data["legend"]:
        pdf.ln(2)
        legend(pdf, data["legend"])


def legend(pdf, items):
    """The medals in the table: icon and name, wrapped in lines."""
    size, x = 4.2, pdf.l_margin
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    y = pdf.get_y()
    for code, name in items:
        w = size + 1 + pdf.get_string_width(latin(name)) + 4
        if x + w > pdf.l_margin + pdf.epw:
            x, y = pdf.l_margin, y + size + 1.5
        room(pdf, size + 2)
        icon(pdf, code, x, y, size)
        pdf.set_xy(x + size + 1, y)
        pdf.cell(w - size - 1, size, latin(name))
        x += w
    pdf.set_xy(pdf.l_margin, y + size + 2)


def pair(s, team):
    a, b = ("a1", "a2") if team == "A" else ("b1", "b2")
    return f"{s[a]} / {s[b]}"


def set_line(pdf, s, _, chance=None, bar=False):
    """One set: pair A (blue) | score | pair B (red). Played: the winners in bold, and
    the chance they had in gray. Pending (bar=True): a bar of each pair's chance."""
    side_w, mid_w, h = (pdf.epw - 28) / 2, 28, 7
    x, y = pdf.l_margin, pdf.get_y()
    played = s["team_a_games"] is not None
    for team, align, color in (("A", "R", BLUE), (None, "C", None), ("B", "L", RED)):
        if team is None:
            if played:
                pdf.set_fill_color(*ACCENT_SOFT)
                pdf.rect(pdf.get_x() + 4, y + 0.8, mid_w - 8, h - 1.6, style="F",
                         round_corners=True, corner_radius=1.6)
                pdf.set_font("Helvetica", "B", 10.5)
                pdf.set_text_color(*INK)
                pdf.cell(mid_w, h, f"{s['team_a_games']} - {s['team_b_games']}", align="C")
            else:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*MUTED)
                pdf.cell(mid_w, h, "vs", align="C")
            continue
        won = s["winner"] == team
        pdf.set_font("Helvetica", "B" if won or not played else "", 9.5)
        pdf.set_text_color(*(color if not played or won else INK))
        pdf.cell(side_w, h, fit(pdf, pair(s, team), side_w - 2), align=align)
    pdf.set_xy(x, y + h)
    if bar and chance is not None:
        bar_w = pdf.epw * 0.6
        bx = x + (pdf.epw - bar_w) / 2
        by = pdf.get_y()
        pdf.set_fill_color(*BLUE)
        pdf.rect(bx, by, bar_w * chance / 100, 2.2, style="F")
        pdf.set_fill_color(*RED)
        pdf.rect(bx + bar_w * chance / 100, by, bar_w * (100 - chance) / 100, 2.2, style="F")
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_xy(bx - 14, by - 1.2)
        pdf.set_text_color(*BLUE)
        pdf.cell(13, 4.5, f"{chance}%", align="R")
        pdf.set_xy(bx + bar_w + 1, by - 1.2)
        pdf.set_text_color(*RED)
        pdf.cell(13, 4.5, f"{100 - chance}%")
        pdf.set_xy(x, by + 4)
    elif played and chance is not None and s["winner"]:
        had = chance if s["winner"] == "A" else 100 - chance
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(x, pdf.get_y() - 1.2)
        pdf.cell(pdf.epw, 3.6, latin(_("pdf_had", n=had)), align="C")
        pdf.set_xy(x, pdf.get_y() + 3.8)


def first_court(courts_):
    """The height of the first court block (to keep it with its section's title)."""
    return 10 + 9 * len(courts_[0][1]) if courts_ else 0


def courts(pdf, courts_, _, bar=False):
    for court, sets in courts_:
        room(pdf, 10 + 9 * len(sets))
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*INK)
        y = pdf.get_y()
        pdf.set_fill_color(*SOFT)
        pdf.rect(pdf.l_margin, y, pdf.epw, 6.5, style="F")
        pdf.set_xy(pdf.l_margin + 2, y)
        pdf.cell(0, 6.5, latin(_("pdf_court", n=court)), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.5)
        for s in sets:
            set_line(pdf, s, _, s["chance"], bar=bar)
        pdf.ln(1.5)


def highlights(pdf, data, _):
    if not data["highlights"]:
        return
    section(pdf, _("pdf_set_medals"), keep=24)
    col_w, h, size = (pdf.epw - 4) / 2, 21, 13
    for i, hl in enumerate(data["highlights"]):
        if i % 2 == 0:
            room(pdf, h + 3)
            y = pdf.get_y()
        x = pdf.l_margin + (i % 2) * (col_w + 4)
        pdf.set_fill_color(*SOFT)
        pdf.rect(x, y, col_w, h, style="F", round_corners=True, corner_radius=2.5)
        icon(pdf, f"set_{hl['code']}", x + 2.5, y + (h - size) / 2, size)
        tx, tw = x + size + 5, col_w - size - 7
        s = hl["set"]
        pdf.set_xy(tx, y + 1.8)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(*INK)
        pdf.cell(tw, 5, fit(pdf, hl["name"], tw))
        pdf.set_xy(tx, y + 7.2)
        pdf.set_font("Helvetica", "", 8.5)
        winners, losers = ("A", "B") if s["winner"] != "B" else ("B", "A")
        score = (s["team_a_games"], s["team_b_games"])
        score = score if winners == "A" else score[::-1]
        pdf.cell(tw, 4.2, fit(pdf, pair(s, winners), tw))
        pdf.set_xy(tx, y + 11.2)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(tw, 4.2, fit(pdf, f"{score[0]} - {score[1]}  " + _("pdf_vs") + "  "
                              + pair(s, losers), tw))
        pdf.set_xy(tx, y + 15.4)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(tw, 4, fit(pdf, hl["how"], tw))
        if i % 2 == 1 or i == len(data["highlights"]) - 1:
            pdf.set_xy(pdf.l_margin, y + h + 3)


# One look per player in the points chart: 8 colors, then the same colors dashed, then
# dotted; the point shape changes too. (color i % 8, line i // 8) never repeats.
SERIES = [(69, 104, 245), (200, 49, 42), (31, 157, 85), (224, 138, 0), (142, 68, 173),
          (0, 151, 167), (216, 27, 96), (121, 85, 72)]
LINES = (None, (1.8, 1.0), (0.4, 0.8))  # solid, dashed, dotted (dash, gap in mm)
SHAPES = ("circle", "square", "triangle", "diamond")


def look(i):
    """(color, dash, shape) of the i-th player of the chart."""
    return SERIES[i % len(SERIES)], LINES[(i // len(SERIES)) % len(LINES)], SHAPES[i % len(SHAPES)]


def marker(pdf, shape, x, y, r):
    """A point of the chart, in the current fill color with a white edge."""
    pdf.set_draw_color(255, 255, 255)
    pdf.set_line_width(0.2)
    if shape == "circle":
        pdf.circle(x, y, r, style="DF")
    elif shape == "square":
        pdf.rect(x - r * 0.9, y - r * 0.9, r * 1.8, r * 1.8, style="DF")
    elif shape == "triangle":
        pdf.polygon([(x, y - r * 1.2), (x - r * 1.15, y + r * 0.85), (x + r * 1.15, y + r * 0.85)],
                    style="DF")
    else:
        pdf.polygon([(x, y - r * 1.3), (x + r * 1.1, y), (x, y + r * 1.3), (x - r * 1.1, y)],
                    style="DF")


def line(pdf, points, color, dash, width=0.6):
    pdf.set_draw_color(*color)
    pdf.set_line_width(width)
    if dash:
        pdf.set_dash_pattern(dash=dash[0], gap=dash[1])
    pdf.polyline(points)
    pdf.set_dash_pattern()


def nice_step(top):
    """A round step for about 4 gridlines up to `top`."""
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500):
        if top / step <= 5:
            return step
    return 1000


def lines_chart(pdf, labels, players, key, invert=False, first_marker=0):
    """One chart with a line per player (look(): color, line style, point shape), all
    on the same scale, and a legend by position under it. players[i][key]: the values,
    one per label (None: no point there). invert: smaller is higher (positions, 1st on
    top). first_marker: the first index that gets a point."""
    per_row = 3
    legend_h = 5.2 * -(-len(players) // per_row)
    chart_h = 92
    x0, y0 = pdf.l_margin, pdf.get_y()
    left, bottom = 10, 8  # room for the y and x labels
    cx, cy, cw, ch = x0 + left, y0 + 2, pdf.epw - left - 4, chart_h - bottom - 2
    every = [v for p in players for v in p[key] if v is not None]
    if invert:
        lo, hi = 1, max(every + [2])
        step = nice_step(hi - 1)
        ticks = list(range(1, hi + 1, step))
        if hi - ticks[-1] >= step / 2:  # the last place too, unless it would crowd
            ticks.append(hi)
    else:
        lo, hi = min(0, min(every)), max(1, max(every))
        step = nice_step(hi - lo)
        lo, hi = step * (lo // step), step * -(-hi // step)
        ticks = range(int(lo), int(hi) + 1, step)
    n = len(labels)

    def at(k, v):
        x = cx + (cw * k / (n - 1) if n > 1 else cw / 2)
        frac = (v - lo) / (hi - lo) if hi != lo else 0.5
        return x, (cy + ch * frac) if invert else (cy + ch - ch * frac)

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    for v in ticks:
        _x, y = at(0, v)
        pdf.set_draw_color(*(GRAY_LINE if v == 0 and not invert else LINE))
        pdf.set_line_width(0.4 if v == 0 and not invert else 0.2)
        pdf.line(cx, y, cx + cw, y)
        pdf.set_xy(x0, y - 2)
        pdf.cell(left - 2, 4, f"{v}." if invert else str(v), align="R")
    for k, label in enumerate(labels):
        x, _y = at(k, lo)
        pdf.set_draw_color(*SOFT)
        pdf.set_line_width(0.2)
        pdf.line(x, cy, x, cy + ch)
        pdf.set_xy(x - 8, cy + ch + 1.5)
        pdf.cell(16, 4, latin(label), align="C")
    # Last place first, so the leaders' lines end up on top.
    for i in reversed(range(len(players))):
        color, dash, shape = look(i)
        points = [(k, at(k, v)) for k, v in enumerate(players[i][key]) if v is not None]
        segment = []
        for k, xy in points + [(None, None)]:  # contiguous runs only
            if segment and (k is None or k != segment[-1][0] + 1):
                if len(segment) > 1:
                    line(pdf, [q for _k, q in segment], color, dash)
                segment = []
            if k is not None:
                segment.append((k, xy))
        pdf.set_fill_color(*color)
        for k, (x, y) in points:
            if k >= first_marker:
                marker(pdf, shape, x, y, 0.95)
    pdf.set_xy(x0, y0 + chart_h + 1)
    col_w = pdf.epw / per_row
    for i, p in enumerate(players):
        if i % per_row == 0:
            room(pdf, 5.2)
            y = pdf.get_y()
        x = x0 + (i % per_row) * col_w
        color, dash, shape = look(i)
        line(pdf, [(x + 0.5, y + 2.6), (x + 8.5, y + 2.6)], color, dash, width=0.7)
        pdf.set_fill_color(*color)
        marker(pdf, shape, x + 4.5, y + 2.6, 1.0)
        pdf.set_xy(x + 10, y)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*INK)
        pdf.cell(col_w - 11, 5.2, fit(pdf, f"{p['position']}. {p['name']} ({p['values'][-1]})",
                                      col_w - 12))
        if i % per_row == per_row - 1 or i == len(players) - 1:
            pdf.set_xy(x0, y + 5.2)
    pdf.ln(2)


def evolution(pdf, data, _):
    """Every player's total points from 0 at the start ("Inicio") and after each jornada,
    then (with 2 jornadas or more) everyone's position after each jornada."""
    evo = data["evolution"]
    if not evo["numbers"]:
        return
    players = evo["players"]
    keep = 92 + 5.2 * -(-len(players) // 3) + 4
    section(pdf, _("pdf_evolution"), _("pdf_evolution_note"), keep=keep)
    lines_chart(pdf, evo["labels"], players, "values", first_marker=1)
    if len(evo["numbers"]) > 1 and any(p.get("positions") for p in players):
        section(pdf, _("pdf_positions"), _("pdf_positions_note"), keep=keep)
        lines_chart(pdf, evo["labels"][1:], players, "positions", invert=True)


def build(data, _):
    """The PDF (bytes) of a jornada summary; `data`: main.jornada_summary()."""
    pdf = Summary(format="A4")
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(True, 14)
    pdf.set_title(latin(f"{_('pdf_title')}: {data['label']} | {data['tournament']['name']}"))
    pdf.set_author("PadelScore")
    pdf.footer_text = f"PadelScore  |  {data['org']}  |  {data['tournament']['name']}"
    pdf.add_page()
    header(pdf, data, _)
    ranking(pdf, data, _)
    highlights(pdf, data, _)
    section(pdf, _("pdf_sets"), _("pdf_sets_note"), keep=first_court(data["courts"]))
    courts(pdf, data["courts"], _)
    evolution(pdf, data, _)
    nxt = data["next"]
    if nxt:
        section(pdf, f"{_('pdf_next')}: {nxt['label']}  |  {nxt['played_on']}",
                _("pdf_next_note"), keep=first_court(nxt["courts"]))
        courts(pdf, nxt["courts"], _, bar=True)
    return bytes(pdf.output())
