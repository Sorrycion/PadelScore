"""Small charts drawn as inline SVG (no JavaScript). Colors are the stylesheet's
variables, so they follow light and dark mode; every mark has a <title> that shows its
value on hover or tap. All text is escaped."""
from markupsafe import Markup, escape

COLORS = {"W": "var(--up)", "L": "var(--error)", "T": "var(--muted)"}


def _svg(width, height, body, label):
    return Markup(f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
                  f'aria-label="{escape(label)}" preserveAspectRatio="xMidYMid meet">'
                  f'<title>{escape(label)}</title>{body}</svg>')


def line_chart(values, label, labels=None, width=360, height=150, suffix="",
               color="var(--accent)", top=None):
    """A line with a soft area under it. `values`: numbers in order; `labels`: the
    x labels for each point (the first and last are drawn); `top`: a fixed top of the
    scale (e.g. 100 for percentages)."""
    if not values:
        return Markup("")
    pad_l, pad_r, pad_t, pad_b = 34, 10, 10, 22
    lo, hi = min(min(values), 0), top if top is not None else max(max(values), 1)
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    step = w / max(len(values) - 1, 1)

    def x(i):
        return pad_l + i * step

    def y(v):
        return pad_t + h - (v - lo) / (hi - lo) * h

    points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
    labels = labels or [str(i + 1) for i in range(len(values))]
    body = [
        f'<line x1="{pad_l}" y1="{y(0):.1f}" x2="{width - pad_r}" y2="{y(0):.1f}" class="axis"/>',
        f'<text x="{pad_l - 6}" y="{y(hi) + 4:.1f}" class="tick" text-anchor="end">{hi}{escape(suffix)}</text>',
        f'<text x="{pad_l - 6}" y="{y(lo) + 4:.1f}" class="tick" text-anchor="end">{lo}{escape(suffix)}</text>',
        f'<polygon points="{x(0):.1f},{y(lo):.1f} {points} {x(len(values) - 1):.1f},{y(lo):.1f}" '
        f'fill="{color}" opacity=".12"/>',
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>',
    ]
    for i, v in enumerate(values):
        body.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5" fill="{color}">'
                    f'<title>{escape(labels[i])}: {v}{escape(suffix)}</title></circle>')
    body.append(f'<text x="{pad_l}" y="{height - 4}" class="tick">{escape(labels[0])}</text>')
    if len(values) > 1:
        body.append(f'<text x="{width - pad_r}" y="{height - 4}" class="tick" '
                    f'text-anchor="end">{escape(labels[-1])}</text>')
    return _svg(width, height, "".join(body), label)


def bar_chart(items, label, width=360, color="var(--accent)", suffix=""):
    """Horizontal bars, one per (name, value), longest first as given."""
    if not items:
        return Markup("")
    row, name_w, pad_r = 26, 110, 34
    top = max(v for _, v in items) or 1
    body = []
    for i, (name, value) in enumerate(items):
        y = i * row
        bar = (width - name_w - pad_r) * value / top
        body.append(
            f'<g><title>{escape(name)}: {value}{escape(suffix)}</title>'
            f'<text x="{name_w - 8}" y="{y + 17}" class="tick name" text-anchor="end">{escape(name)}</text>'
            f'<rect x="{name_w}" y="{y + 5}" width="{max(bar, 2):.1f}" height="16" rx="5" fill="{color}"/>'
            f'<text x="{name_w + bar + 6:.1f}" y="{y + 17}" class="tick">{value}{escape(suffix)}</text></g>')
    return _svg(width, row * len(items) + 4, "".join(body), label)


def donut(parts, label, center="", size=150):
    """A ring split into (name, value, color) parts, with `center` text inside."""
    total = sum(v for _, v, _ in parts)
    if not total:
        return Markup("")
    r, c = 52, size / 2
    circumference = 2 * 3.14159265 * r
    body, offset = [], 0.0
    for name, value, color in parts:
        if not value:
            continue
        length = circumference * value / total
        body.append(
            f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{color}" stroke-width="20" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {c} {c})">'
            f'<title>{escape(name)}: {value}</title></circle>')
        offset += length
    body.append(f'<text x="{c}" y="{c + 8}" text-anchor="middle" class="donut-center">'
                f'{escape(center)}</text>')
    return _svg(size, size, "".join(body), label)


def streak_strip(results, label, names=None):
    """One small square per set ('W', 'L' or 'T'), oldest first."""
    if not results:
        return Markup("")
    size, gap = 14, 4
    names = names or {"W": "W", "L": "L", "T": "T"}
    body = "".join(
        f'<rect x="{i * (size + gap)}" y="0" width="{size}" height="{size}" rx="3" '
        f'fill="{COLORS[r]}"><title>{i + 1}: {escape(names[r])}</title></rect>'
        for i, r in enumerate(results))
    return _svg(len(results) * (size + gap), size, body, label)
