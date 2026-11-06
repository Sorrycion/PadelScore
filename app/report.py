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


def evolution(pdf, data, _):
    """Small multiples: one panel per player (by position), their total points from 0
    at the start and after each jornada in blue over everyone else's in gray, all on the same scale."""
    evo = data["evolution"]
    if not evo["numbers"]:
        return
    section(pdf, _("pdf_evolution"), _("pdf_evolution_note"), keep=33)
    per_row, gap, ph = 4, 3, 30
    pw = (pdf.epw - gap * (per_row - 1)) / per_row
    every = [p["values"] for p in evo["players"]]
    lo = min(0, min(min(v) for v in every))
    hi = max(1, max(max(v) for v in every))
    n = len(evo["numbers"]) + 1  # the points start at 0, before the first jornada
    for i, p in enumerate(evo["players"]):
        if i % per_row == 0:
            room(pdf, ph + gap)
            y = pdf.get_y()
        x = pdf.l_margin + (i % per_row) * (pw + gap)
        pdf.set_fill_color(*SOFT)
        pdf.rect(x, y, pw, ph, style="F", round_corners=True, corner_radius=2)
        pdf.set_xy(x + 1.8, y + 1.2)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*INK)
        pdf.cell(pw - 14, 4, fit(pdf, f"{p['position']}. {p['name']}", pw - 15))
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*ACCENT)
        pdf.set_xy(x + pw - 13, y + 1.2)
        pdf.cell(11.2, 4, str(p["values"][-1]), align="R")
        cx, cy, cw, ch = x + 3, y + 7, pw - 6, ph - 12

        def point(k, v):
            return (cx + cw * k / (n - 1), cy + ch - ch * (v - lo) / (hi - lo))

        pdf.set_line_width(0.25)
        pdf.set_draw_color(*GRAY_LINE)
        for other in every:
            pdf.polyline([point(k, v) for k, v in enumerate(other)])
        pdf.set_line_width(0.7)
        pdf.set_draw_color(*ACCENT)
        mine = [point(k, v) for k, v in enumerate(p["values"])]
        pdf.polyline(mine)
        pdf.set_fill_color(*ACCENT)
        pdf.circle(*mine[-1], 0.9, style="F")
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(cx - 1, y + ph - 3.2)
        pdf.cell(8, 2.6, latin(evo["first"]))
        pdf.set_xy(cx + cw - 7, y + ph - 3.2)
        pdf.cell(8, 2.6, latin(evo["last"]), align="R")
        if i % per_row == per_row - 1 or i == len(evo["players"]) - 1:
            pdf.set_xy(pdf.l_margin, y + ph + gap)


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
