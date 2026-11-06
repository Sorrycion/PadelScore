"""Lay out a user manual (scripts/manual_texts.py) as a PDF with fpdf2.

A manual is {"title", "subtitle", "who", "sections": [{"title", "blocks": [...]}]}.
Blocks:
    ("p", text)                    a paragraph; **bold** works
    ("steps", [text, ...])         numbered steps
    ("bullets", [text, ...])       a list
    ("table", [[cell, ...], ...])  a small table, the first row is the header
    ("tip", text) / ("warn", text) a box: Consejo / Importante
    ("h", text)                    a small heading inside a section
    ("shots", [(png name, top px, bottom px, caption), ...])  1 or 2 screenshots
                                   side by side (cut to those pixel rows)
PDF core fonts only speak Latin-1 (fine for Spanish): no emoji in the texts.
"""
import tempfile
from datetime import date
from pathlib import Path

from fpdf import FPDF

INK, MUTED, LINE, SOFT = (20, 27, 45), (95, 102, 116), (214, 218, 228), (241, 242, 246)
ACCENT, ACCENT_SOFT = (69, 104, 245), (231, 237, 255)
TIP, WARN = ((231, 247, 238), (31, 157, 85)), ((253, 240, 225), (196, 112, 18))
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")
PX = 0.152  # mm per screenshot pixel at full size (500 px = 76 mm)


def latin(text):
    plain = str(text).translate(str.maketrans({"–": "-", "—": "-", "’": "'", "“": '"', "”": '"',
                                               "…": "...", "→": "->", "·": "-"}))
    return plain.encode("latin-1", "replace").decode("latin-1")


class Manual(FPDF):
    name = ""

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*MUTED)
            self.set_y(6)
            self.cell(0, 5, latin(self.name), align="R")
            self.set_draw_color(*LINE)
            self.set_line_width(0.2)
            self.line(self.l_margin, 12, self.w - self.r_margin, 12)
            self.set_y(16)

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-11)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*MUTED)
            self.cell(0, 5, f"{self.page_no()}", align="C")


def room(pdf, height):
    if pdf.get_y() + height > pdf.page_break_trigger:
        pdf.add_page()


def para(pdf, text, size=10.5, color=INK, indent=0, height=5.4):
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(*color)
    pdf.set_x(pdf.l_margin + indent)
    pdf.multi_cell(pdf.epw - indent, height, latin(text), markdown=True, align="L",
                   new_x="LMARGIN", new_y="NEXT")


def numbered(pdf, items, bullet=False):
    for i, text in enumerate(items, 1):
        room(pdf, 8)
        y = pdf.get_y()
        if bullet:
            pdf.set_fill_color(*ACCENT)
            pdf.ellipse(pdf.l_margin + 2.2, y + 2, 1.6, 1.6, style="F")
        else:
            pdf.set_fill_color(*ACCENT)
            pdf.ellipse(pdf.l_margin, y + 0.2, 5, 5, style="F")
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(255, 255, 255)
            pdf.set_xy(pdf.l_margin, y + 0.2)
            pdf.cell(5, 5, str(i), align="C")
        pdf.set_xy(pdf.l_margin + 8, y)
        para(pdf, text, indent=8)
        pdf.ln(1.2)


def box(pdf, kind, text):
    fill, edge = TIP if kind == "tip" else WARN
    label = "Consejo" if kind == "tip" else "Importante"
    pdf.set_font("Helvetica", "", 10)
    lines = pdf.multi_cell(pdf.epw - 12, 5, latin(text), markdown=True, dry_run=True,
                           align="L", output="LINES")
    h = 5 * len(lines) + 11
    room(pdf, h + 2)
    x, y = pdf.l_margin, pdf.get_y() + 1
    pdf.set_fill_color(*fill)
    pdf.rect(x, y, pdf.epw, h, style="F", round_corners=True, corner_radius=2)
    pdf.set_fill_color(*edge)
    pdf.rect(x, y, 1.6, h, style="F")
    pdf.set_xy(x + 6, y + 2.5)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*edge)
    pdf.cell(0, 5, label, new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(x + 6, y + 7.5)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(pdf.epw - 12, 5, latin(text), markdown=True, align="L",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(y + h + 3)


def table(pdf, rows):
    from fpdf import FontFace
    widths = [pdf.epw * 0.3, pdf.epw * 0.7] if len(rows[0]) == 2 else None
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.2)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*INK)
    head = FontFace(emphasis="BOLD", color=ACCENT, fill_color=ACCENT_SOFT)
    body = FontFace(color=INK, fill_color=(255, 255, 255))
    with pdf.table(col_widths=widths, line_height=5.2, text_align="LEFT", headings_style=head,
                   padding=1.6) as t:
        for row in rows:
            r = t.row()
            for cell in row:
                r.cell(latin(cell), style=None if row is rows[0] else body)
    pdf.ln(3)


def cut(work, name, top, bottom, tmp):
    """The screenshot `name` cut to rows top..bottom: (path, width px, height px)."""
    from PIL import Image
    im = Image.open(Path(work) / f"{name}.png")
    bottom = min(bottom or im.height, im.height)
    part = im.crop((0, top, im.width, bottom))
    path = Path(tmp) / f"{name}-{top}-{bottom}.png"
    part.save(path)
    return path, part.width, part.height


def shots(pdf, items, work, tmp):
    """1 or 2 screenshots side by side, at most 76 mm wide and 125 mm tall, framed, with
    their caption under them."""
    cuts = [(cut(work, name, top, bottom, tmp), caption)
            for name, top, bottom, caption in items if (Path(work) / f"{name}.png").exists()]
    if not cuts:
        return
    gap = 8
    max_w = 76 if len(cuts) == 1 else min(76, (pdf.epw - gap) / 2)
    sizes = []
    for (path, w, h), caption in cuts:
        scale = min(max_w / w, 125 / h)
        sizes.append((w * scale, h * scale))
    tallest = max(h for _, h in sizes)
    room(pdf, tallest + 14)
    total = sum(w for w, _ in sizes) + gap * (len(sizes) - 1)
    x, y = pdf.l_margin + (pdf.epw - total) / 2, pdf.get_y() + 2
    for ((path, _, _), caption), (w, h) in zip(cuts, sizes):
        pdf.set_fill_color(225, 228, 236)
        pdf.rect(x + 0.8, y + 0.8, w, h, style="F", round_corners=True, corner_radius=2.5)
        pdf.image(str(path), x=x, y=y, w=w, h=h)
        pdf.set_draw_color(*LINE)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, w, h, round_corners=True, corner_radius=2.5)
        pdf.set_xy(x, y + h + 1.8)
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(w, 4, latin(caption), align="C")
        x += w + gap
    pdf.set_y(y + tallest + 13)


def cover(pdf, manual):
    pdf.add_page()
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, pdf.w, 112, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(pdf.l_margin, 40)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "PadelScore", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 32)
    pdf.cell(0, 16, latin(manual["title"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.multi_cell(pdf.epw, 7, latin(manual["subtitle"]), align="L", new_x="LMARGIN",
                   new_y="NEXT")
    pdf.set_y(124)
    para(pdf, manual["who"], size=11.5, height=6.2)
    pdf.ln(4)
    para(pdf, "Sitio: **https://padelscore-sorrycion.azurewebsites.net**", size=10.5)
    today = date.today()
    para(pdf, f"Versión de {MONTHS[today.month - 1]} de {today.year}. Las capturas son de una "
              "liga de demostración con nombres inventados.", size=9.5, color=MUTED)


def toc(pdf, outline):
    pdf.set_xy(pdf.l_margin, 22)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(0, 12, "Contenido", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    for entry in outline:
        if entry.level:
            continue
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*INK)
        link = pdf.add_link(page=entry.page_number)
        title = latin(entry.name)
        number = str(entry.page_number)
        dots = pdf.epw - pdf.get_string_width(title) - pdf.get_string_width(number) - 4
        pdf.cell(pdf.get_string_width(title) + 2, 7.5, title, link=link)
        pdf.set_text_color(*LINE)
        pdf.cell(dots, 7.5, "." * int(dots / pdf.get_string_width(".")), link=link)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 7.5, number, align="R", new_x="LMARGIN", new_y="NEXT", link=link)


def build(manual, work):
    """The manual's PDF bytes; `work`: the folder with the screenshots (<name>.png)."""
    pdf = Manual(format="A4")
    pdf.name = f"PadelScore  |  {manual['title']}"
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, 16)
    pdf.set_title(latin(f"PadelScore - {manual['title']}"))
    pdf.set_author("PadelScore")
    cover(pdf, manual)
    pdf.add_page()
    pdf.insert_toc_placeholder(toc, pages=1)
    with tempfile.TemporaryDirectory() as tmp:
        for n, section in enumerate(manual["sections"], 1):
            if n > 1:  # the first follows the contents page, which starts a new one
                pdf.add_page()
            title = f"{n}. {section['title']}"
            pdf.start_section(latin(title))
            pdf.set_font("Helvetica", "B", 20)
            pdf.set_text_color(*ACCENT)
            pdf.multi_cell(pdf.epw, 10, latin(title), new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(*ACCENT)
            pdf.set_line_width(0.8)
            pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.l_margin + 24, pdf.get_y() + 1)
            pdf.ln(5)
            for kind, value in section["blocks"]:
                if kind == "p":
                    room(pdf, 12)
                    para(pdf, value)
                    pdf.ln(2.5)
                elif kind == "h":
                    room(pdf, 34)  # a heading never ends a page alone
                    pdf.ln(2)
                    pdf.set_font("Helvetica", "B", 12.5)
                    pdf.set_text_color(*INK)
                    pdf.multi_cell(pdf.epw, 6.5, latin(value), new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(1.5)
                elif kind in ("steps", "bullets"):
                    numbered(pdf, value, bullet=kind == "bullets")
                    pdf.ln(1.5)
                elif kind in ("tip", "warn"):
                    box(pdf, kind, value)
                elif kind == "table":
                    room(pdf, 20)
                    table(pdf, value)
                elif kind == "shots":
                    shots(pdf, value, work, tmp)
                else:
                    raise ValueError(kind)
    return bytes(pdf.output())


def render_pdf_page(pdf_file, png, page=0, width=1000):
    """A PNG of one page of a PDF (needs PyMuPDF, only to make the manuals: if it's
    missing, the manual just leaves that picture out)."""
    try:
        import pymupdf
    except ImportError:
        return False
    doc = pymupdf.open(pdf_file)
    zoom = width / doc[page].rect.width
    doc[page].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).save(png)
    return True
