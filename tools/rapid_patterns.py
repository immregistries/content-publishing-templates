"""Expressive slide patterns for the rapid presentation template.

Each pattern draws native, editable PowerPoint shapes, tables, and charts on one
of the template's standard layouts (Title Only, Blank, or Title Dark), so the
template's footer band, logo, fonts, and colors are kept. A slide in the JSON
source selects a pattern with "pattern" and supplies that pattern's fields; see
templates/powerpoint/README.md and example-patterns.json.

Colors match templates/powerpoint/aira-rapid-presentation.yml.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt

HEADING_FONT = "Open Sans Light"
BODY_FONT = "Open Sans"

DARK_BLUE = "1C3C50"
GREEN = "72A850"  # the green of the template's bands and title art
DARK_GREEN = "4E8A35"  # green for small text on white, for contrast
BLUE_GRAY = "8098A4"
LIGHT_GREEN = "C9E2CA"
WHITE = "FFFFFF"
MUTED = "5B6F7A"
NEUTRAL_PANEL = "F1F1F0"
RULE_GRAY = "CCCCCB"

FAMILIES: dict[str, dict[str, Any]] = {
    "Blue": {
        "primary": DARK_BLUE,
        "accent": GREEN,
        "label": DARK_GREEN,
        "tint": "E6ECEF",
        "tint2": "CFDAE0",
        "ramp": ["CFDAE0", "A6B8C2", BLUE_GRAY, GREEN, DARK_BLUE],
        "series": [DARK_BLUE, GREEN, BLUE_GRAY, LIGHT_GREEN],
    },
    "Green": {
        "primary": GREEN,
        "accent": DARK_BLUE,
        "label": DARK_GREEN,
        "tint": "EAF3E6",
        "tint2": LIGHT_GREEN,
        "ramp": [LIGHT_GREEN, "9CC487", GREEN, DARK_GREEN, DARK_BLUE],
        "series": [GREEN, DARK_BLUE, "9CC487", BLUE_GRAY],
    },
}

# Slide geometry in points (16:9, 960 x 540).
LEFT = 66
RIGHT = 894
WIDTH = RIGHT - LEFT
BODY_TOP = 145
BODY_BOTTOM = 470
BAND_TOP = 486  # the footer band starts here


class PatternError(ValueError):
    pass


_slide_label = ""


def warn(message: str) -> None:
    print(f"warning: {_slide_label}: {message}", file=sys.stderr)


# ----------------------------------------------------------------- color helpers

def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def _luminance(hex_color: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def on(fill: str) -> str:
    """Text color for text placed on a fill: white or dark blue, whichever reads better."""
    return WHITE if _contrast(fill, WHITE) >= _contrast(fill, DARK_BLUE) else DARK_BLUE


def label_on(fill: str) -> str:
    """Small uppercase label color on a filled panel."""
    return LIGHT_GREEN if on(fill) == WHITE else WHITE


# ----------------------------------------------------------------- drawing helpers

def box(slide, x, y, w, h, fill: str | None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Pt(x), Pt(y), Pt(w), Pt(h))
    s.shadow.inherit = False
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    s.line.fill.background()
    return s


def _estimate_lines(text: str, width_pt: float, size: float, font: str) -> int:
    per_char = size * (0.50 if font == HEADING_FONT else 0.55)
    capacity = max(1, int(width_pt / per_char))
    lines = 0
    for paragraph in text.split("\n"):
        line_len = 0
        lines += 1
        for word in paragraph.split():
            if line_len and line_len + 1 + len(word) > capacity:
                lines += 1
                line_len = len(word)
            else:
                line_len += (1 if line_len else 0) + len(word)
    return lines


def write(slide, x, y, w, h, paragraphs, *, size=18, color=DARK_BLUE, font=BODY_FONT,
          bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, shape=None,
          space_after=6, line_spacing=None, field="text"):
    """Write text into a new text box, or into an existing shape.

    paragraphs is a string, or a list whose items are strings or lists of
    (text, overrides) runs.
    """
    target = shape or slide.shapes.add_textbox(Pt(x), Pt(y), Pt(w), Pt(h))
    frame = target.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    frame.vertical_anchor = anchor
    margin = Pt(0) if shape is None else Pt(8)
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = margin
    if isinstance(paragraphs, str):
        paragraphs = [paragraphs]
    plain = []
    for index, paragraph in enumerate(paragraphs):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        if line_spacing:
            p.line_spacing = line_spacing
        runs = [(paragraph, {})] if isinstance(paragraph, str) else paragraph
        plain.append("".join(text for text, _ in runs))
        for text, overrides in runs:
            run = p.add_run()
            run.text = text
            run.font.name = overrides.get("font", font)
            run.font.size = Pt(overrides.get("size", size))
            run.font.bold = overrides.get("bold", bold)
            run.font.color.rgb = rgb(overrides.get("color", color))
    if shape is None and h:
        lines = _estimate_lines("\n".join(plain), w, size, font)
        spacing = (line_spacing or 1.0) * 1.22
        needed = lines * size * spacing + (len(plain) - 1) * space_after
        if needed > h * 1.08:
            warn(f"{field} may not fit its space ({lines} estimated lines); shorten it or split the slide")
    return target


def label(slide, x, y, w, text, color, field="eyebrow"):
    write(slide, x, y, w, 20, text.upper(), size=13, color=color, bold=True, field=field)


def set_title(slide, title: str) -> None:
    for shape in slide.placeholders:
        if shape.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
            shape.text = title
            return
    raise PatternError("layout has no title placeholder")


def require(spec: dict[str, Any], key: str):
    if key not in spec or spec[key] in (None, "", []):
        raise PatternError(f"pattern {spec['pattern']!r} requires {key!r}")
    return spec[key]


def require_list(spec, key, low, high):
    items = require(spec, key)
    if not isinstance(items, list) or not low <= len(items) <= high:
        count = len(items) if isinstance(items, list) else "not a list"
        raise PatternError(
            f"pattern {spec['pattern']!r} needs {low}-{high} {key!r} items, got {count}; "
            "split the content across slides"
        )
    return items


def columns(count: int, gap: float, left=LEFT, width=WIDTH):
    w = (width - gap * (count - 1)) / count
    return [(left + i * (w + gap), w) for i in range(count)]


# ----------------------------------------------------------------- patterns

def statement(slide, spec, c):
    box(slide, LEFT, 150, 8, 190, c["accent"])
    if spec.get("eyebrow"):
        label(slide, 100, 150, 700, spec["eyebrow"], c["label"])
    write(slide, 100, 180, 760, 160, require(spec, "text"), size=40, font=HEADING_FONT,
          line_spacing=1.05, field="text")


def big_numbers(slide, spec, c):
    stats = require_list(spec, "stats", 1, 4)
    size = 110 if len(stats) <= 3 else 88
    for (x, w), stat in zip(columns(len(stats), 24), stats):
        write(slide, x, 175, w, 130, str(stat["value"]), size=size, font=HEADING_FONT,
              color=c["primary"] if c["primary"] == DARK_BLUE else c["label"], field="value")
        box(slide, x, 322, 60, 4, c["accent"])
        runs = [(stat["label"] + " ", {"bold": True})]
        if stat.get("detail"):
            runs.append((stat["detail"], {}))
        write(slide, x, 340, w - 10, 120, [runs], size=18, field="label")


def quote(slide, spec, c):
    mark = slide.shapes.add_textbox(Pt(70), Pt(40), Pt(160), Pt(160))
    write(slide, 0, 0, 0, 0, "“", size=200, font="Georgia",
          color=c["accent"] if c["accent"] == GREEN else c["primary"], shape=mark)
    write(slide, 150, 140, 700, 210, require(spec, "text"), size=30, font=HEADING_FONT,
          line_spacing=1.1, field="text")
    box(slide, 150, 362, 40, 3, c["primary"])
    runs = [(require(spec, "attribution"), {"bold": True})]
    if spec.get("role"):
        runs.append((", " + spec["role"], {"color": MUTED}))
    write(slide, 150, 374, 700, 50, [runs], size=18, field="attribution")


def split(slide, spec, c):
    panel = c["primary"]
    box(slide, 0, 0, 380, BAND_TOP, panel)
    if spec.get("eyebrow"):
        label(slide, 50, 150, 290, spec["eyebrow"], label_on(panel))
    write(slide, 50, 180, 290, 240, require(spec, "message"), size=30, font=HEADING_FONT,
          color=on(panel), line_spacing=1.05, field="message")
    items = require_list(spec, "items", 1, 4)
    step = 330 / len(items)
    y = BODY_TOP + max(0, (330 - step * len(items)) / 2)
    for item in items:
        box(slide, 420, y + 7, 10, 10, c["accent"], MSO_SHAPE.OVAL)
        runs = []
        if item.get("lead"):
            runs.append((item["lead"] + " ", {"bold": True}))
        runs.append((item["text"], {}))
        write(slide, 446, y, 448, step - 10, [runs], size=20, field="items")
        y += step


def cards(slide, spec, c):
    items = require_list(spec, "cards", 2, 4)
    numbered = spec.get("numbered", True)
    top, height = 150, 310
    for index, ((x, w), card) in enumerate(zip(columns(len(items), 18), items)):
        box(slide, x, top, w, height, c["tint"])
        box(slide, x, top, w, 6, c["primary"])
        heading_top = top + 30
        if numbered:
            circle = box(slide, x + 22, top + 30, 46, 46, c["primary"], MSO_SHAPE.OVAL)
            write(slide, 0, 0, 0, 0, str(index + 1), size=20, bold=True, color=on(c["primary"]),
                  align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, shape=circle)
            heading_top = top + 96
        write(slide, x + 22, heading_top, w - 44, 60, card["heading"], size=21, bold=True,
              color=DARK_BLUE, field="card heading")
        write(slide, x + 22, heading_top + 64, w - 44, top + height - heading_top - 74,
              card["text"], size=18, field="card text")


def grid(slide, spec, c):
    cells = require_list(spec, "cells", 4, 4)
    gap = 18
    w, h = (WIDTH - gap) / 2, 150
    for index, cell in enumerate(cells):
        x = LEFT + (index % 2) * (w + gap)
        y = BODY_TOP + (index // 2) * (h + gap)
        box(slide, x, y, w, h, c["tint"])
        box(slide, x, y, 8, h, c["accent"] if index in (0, 3) else c["primary"])
        write(slide, x + 30, y + 24, w - 50, 36, cell["heading"], size=22, bold=True,
              color=DARK_BLUE, field="cell heading")
        write(slide, x + 30, y + 64, w - 50, 76, cell["text"], size=18, field="cell text")


def agenda(slide, spec, c):
    items = require_list(spec, "items", 2, 6)
    row = min(84, 330 / len(items))
    y = 140
    for index, item in enumerate(items):
        write(slide, LEFT, y, 90, row, f"{index + 1:02d}", size=40 if row >= 70 else 32,
              font=HEADING_FONT, color=c["label"] if c["primary"] == GREEN else c["accent"], field="number")
        write(slide, 160, y + 4, 734, 34, item["heading"], size=22, bold=True, field="agenda heading")
        if item.get("detail"):
            write(slide, 160, y + 36, 734, 30, item["detail"], size=18, color=MUTED, field="agenda detail")
        if index < len(items) - 1:
            box(slide, 160, y + row - 10, 734, 1, c["tint2"])
        y += row


def process(slide, spec, c):
    steps = require_list(spec, "steps", 3, 5)
    count, overlap, top, height = len(steps), 10, 160, 70
    w = (WIDTH + overlap * (count - 1)) / count
    ramp = c["ramp"]
    for index, step in enumerate(steps):
        x = LEFT + index * (w - overlap)
        fill = ramp[round(index * (len(ramp) - 1) / (count - 1))]
        chevron = box(slide, x, top, w, height, fill, MSO_SHAPE.PENTAGON if index == 0 else MSO_SHAPE.CHEVRON)
        write(slide, 0, 0, 0, 0, step["label"], size=22 if count <= 4 else 18, bold=True,
              color=on(fill), align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, shape=chevron)
        if step.get("text"):
            write(slide, x + 22, top + 95, w - 50, 210, step["text"], size=18, field="step text")


def timeline(slide, spec, c):
    milestones = require_list(spec, "milestones", 3, 6)
    line_y, x0, x1 = 300, 106, 854
    box(slide, x0, line_y - 2, x1 - x0, 4, c["tint2"])
    step = (x1 - x0) / (len(milestones) - 1)
    label_w = min(170, step * 2 - 16)
    for index, milestone in enumerate(milestones):
        cx = x0 + index * step
        last = index == len(milestones) - 1
        box(slide, cx - 11, line_y - 11, 22, 22, c["accent"] if last else c["primary"], MSO_SHAPE.OVAL)
        top = line_y - 110 if index % 2 == 0 else line_y + 28
        write(slide, cx - label_w / 2, top, label_w, 24, milestone["when"], size=16, bold=True,
              color=c["label"] if c["accent"] == GREEN else DARK_BLUE, align=PP_ALIGN.CENTER, field="when")
        write(slide, cx - label_w / 2, top + 26, label_w, 70, milestone["text"], size=18,
              align=PP_ALIGN.CENTER, field="milestone text")


def _picture_fill(slide, path: Path, x, y, w, h, alt: str):
    picture = slide.shapes.add_picture(str(path), Pt(x), Pt(y), Pt(w), Pt(h))
    image_w, image_h = picture.image.size
    box_ratio, image_ratio = w / h, image_w / image_h
    if image_ratio > box_ratio:
        trim = (1 - box_ratio / image_ratio) / 2
        picture.crop_left = picture.crop_right = trim
    else:
        trim = (1 - image_ratio / box_ratio) / 2
        picture.crop_top = picture.crop_bottom = trim
    picture._element.nvPicPr.cNvPr.set("descr", alt)
    return picture


def image(slide, spec, c, base: Path):
    path = spec.get("image")
    if path:
        resolved = (base / path).resolve()
        if not resolved.is_file():
            raise PatternError(f"image {path!r} not found (resolved to {resolved})")
        if not spec.get("alt"):
            raise PatternError("pattern 'image' requires 'alt' text when an image is given")
        _picture_fill(slide, resolved, 0, 0, 520, BAND_TOP, spec["alt"])
    else:
        placeholder = box(slide, 0, 0, 520, BAND_TOP, LIGHT_GREEN)
        write(slide, 0, 0, 0, 0, "Image goes here", size=20, color=DARK_BLUE,
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, shape=placeholder)
    if spec.get("eyebrow"):
        label(slide, 560, 130, 340, spec["eyebrow"], c["label"])
    write(slide, 560, 158, 340, 125, require(spec, "title"), size=28, font=HEADING_FONT,
          line_spacing=1.05, field="title")
    box(slide, 560, 292, 40, 3, c["primary"])
    if spec.get("caption"):
        write(slide, 560, 308, 340, 160, spec["caption"], size=18, color=MUTED, field="caption")


def takeaway(slide, spec, c):
    points = spec.get("points") or []
    if len(points) > 4:
        raise PatternError("pattern 'takeaway' allows at most 4 'points'; split the slide")
    y = 150
    for point in points:
        box(slide, 70, y + 8, 9, 9, c["accent"], MSO_SHAPE.OVAL)
        write(slide, 96, y, 798, 44, point, size=20, field="points")
        y += 46
    fill = c["primary"]
    box(slide, LEFT, 340, WIDTH, 110, fill)
    box(slide, LEFT, 340, 10, 110, c["accent"])
    write(slide, 100, 356, 300, 22, spec.get("label", "Takeaway").upper(), size=13, bold=True,
          color=label_on(fill), field="label")
    write(slide, 100, 380, 770, 62, require(spec, "takeaway"), size=22, color=on(fill), field="takeaway")


def table(slide, spec, c):
    header = require(spec, "columns")
    rows = require_list(spec, "rows", 1, 7)
    if not 2 <= len(header) <= 6:
        raise PatternError("pattern 'table' needs 2-6 'columns'")
    for row in rows:
        if len(row) != len(header):
            raise PatternError("every table row needs one value per column")
    data = [header] + rows
    row_h = min(52, 325 / len(data))
    size = 18 if row_h >= 46 else 16
    shape = slide.shapes.add_table(len(data), len(header), Pt(LEFT), Pt(BODY_TOP), Pt(WIDTH), Pt(row_h * len(data)))
    grid_table = shape.table
    weights = spec.get("column_widths") or [1] * len(header)
    total = sum(weights)
    for index, weight in enumerate(weights):
        grid_table.columns[index].width = Pt(WIDTH * weight / total)
    head_fill = c["primary"]
    for r, values in enumerate(data):
        grid_table.rows[r].height = Pt(row_h)
        for col, value in enumerate(values):
            cell = grid_table.cell(r, col)
            fill = head_fill if r == 0 else (c["tint"] if r % 2 == 0 else WHITE)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(fill)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Pt(12)
            frame = cell.text_frame
            frame.text = ""
            run = frame.paragraphs[0].add_run()
            run.text = str(value)
            run.font.name = BODY_FONT
            run.font.size = Pt(size)
            run.font.bold = r == 0 or (col == 0 and spec.get("first_column_bold", True))
            run.font.color.rgb = rgb(on(fill) if r == 0 else DARK_BLUE)


CHART_TYPES = {
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "line": XL_CHART_TYPE.LINE_MARKERS,
}


def chart(slide, spec, c):
    definition = require(spec, "chart")
    kind = definition.get("type", "bar")
    if kind not in CHART_TYPES:
        raise PatternError(f"chart type must be one of {sorted(CHART_TYPES)}")
    series = definition.get("series") or []
    if not 1 <= len(series) <= 4:
        raise PatternError("a chart needs 1-4 'series'")
    data = CategoryChartData()
    data.categories = definition["categories"]
    for item in series:
        if len(item["values"]) != len(definition["categories"]):
            raise PatternError(f"series {item['name']!r} needs one value per category")
        data.add_series(item["name"], item["values"])
    callout = spec.get("callout")
    width = 560 if callout else WIDTH
    frame = slide.shapes.add_chart(CHART_TYPES[kind], Pt(LEFT), Pt(140), Pt(width), Pt(330), data)
    ch = frame.chart
    ch.font.name = BODY_FONT
    ch.font.size = Pt(14)
    ch.font.color.rgb = rgb(DARK_BLUE)
    ch.has_legend = len(series) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
    if kind == "bar":
        ch.category_axis.reverse_order = True
    ch.category_axis.format.line.color.rgb = rgb(RULE_GRAY)
    ch.value_axis.has_major_gridlines = kind == "line"
    if kind != "line":
        ch.value_axis.visible = False
    plot = ch.plots[0]
    if kind != "line":
        plot.gap_width = 60
        plot.overlap = -10
    for item, color in zip(plot.series, c["series"]):
        if kind == "line":
            item.format.line.color.rgb = rgb(color)
            item.format.line.width = Pt(3)
            item.smooth = False
        else:
            item.format.fill.solid()
            item.format.fill.fore_color.rgb = rgb(color)
    if definition.get("data_labels", kind != "line"):
        plot.has_data_labels = True
        labels = plot.data_labels
        labels.font.size = Pt(14)
        if definition.get("number_format"):
            labels.number_format = definition["number_format"]
            labels.number_format_is_linked = False
        if kind != "line":
            labels.position = XL_LABEL_POSITION.OUTSIDE_END
    if callout:
        box(slide, 660, 160, 234, 290, c["tint"])
        write(slide, 684, 184, 194, 70, str(callout["value"]), size=48, font=HEADING_FONT,
              color=DARK_BLUE, field="callout value")
        write(slide, 684, 262, 190, 180, callout["text"], size=16, color=MUTED, field="callout text")


def before_after(slide, spec, c):
    before, after = require(spec, "before"), require(spec, "after")
    top, height = 150, 300

    def panel(x, w, side, fill, heading_color, body_color, label_color):
        box(slide, x, top, w, height, fill)
        label(slide, x + 26, top + 24, w - 50, side.get("label", ""), label_color, field="panel label")
        heading_lines = min(2, _estimate_lines(side["heading"], w - 50, 26, HEADING_FONT))
        heading_height = heading_lines * 26 * 1.22
        write(slide, x + 26, top + 52, w - 50, heading_height + 4, side["heading"], size=26,
              font=HEADING_FONT, color=heading_color, field="panel heading")
        points = side.get("points") or []
        if len(points) > 4:
            raise PatternError("each before/after panel allows at most 4 points")
        # Points start below the heading, however many lines it takes.
        points_top = top + 52 + heading_height + 18
        write(slide, x + 26, points_top, w - 50, top + height - points_top - 14, points or [""],
              size=18, color=body_color, space_after=10, field="panel points")

    panel(LEFT, 360, before, NEUTRAL_PANEL, DARK_BLUE, MUTED, MUTED)
    box(slide, 446, top + height / 2 - 28, 48, 56, c["accent"], MSO_SHAPE.RIGHT_ARROW)
    fill = c["primary"]
    panel(514, 380, after, fill, on(fill), on(fill), label_on(fill))


def closing(slide, spec, c):
    for shape in slide.placeholders:
        if shape.placeholder_format.type == PP_PLACEHOLDER.SUBTITLE and spec.get("subtitle"):
            shape.text = spec["subtitle"]


# pattern name -> (layout kind, has standard title, draw function)
PATTERNS: dict[str, tuple[str, bool, Callable]] = {
    "statement": ("Blank", False, statement),
    "big_numbers": ("Title Only", True, big_numbers),
    "quote": ("Blank", False, quote),
    "split": ("Blank", False, split),
    "cards": ("Title Only", True, cards),
    "grid": ("Title Only", True, grid),
    "agenda": ("Title Only", True, agenda),
    "process": ("Title Only", True, process),
    "timeline": ("Title Only", True, timeline),
    "image": ("Blank", False, image),
    "takeaway": ("Title Only", True, takeaway),
    "table": ("Title Only", True, table),
    "chart": ("Title Only", True, chart),
    "before_after": ("Title Only", True, before_after),
    "closing": ("Title Dark", True, closing),
}


def layout_name(pattern: str, family: str) -> str:
    kind = PATTERNS[pattern][0]
    if kind == "Title Dark":
        return f"Rapid - Title - {family} Dark"
    return f"Rapid - {kind} - {family}"


def add_pattern_slide(presentation, spec: dict[str, Any], family: str, base: Path, find_layout):
    """Add a slide drawn by the named pattern. find_layout(presentation, name) returns a layout."""
    global _slide_label
    pattern = spec["pattern"]
    if pattern not in PATTERNS:
        raise PatternError(f"unknown pattern {pattern!r}; choose one of {', '.join(PATTERNS)}")
    if family not in FAMILIES:
        raise PatternError(f"family must be one of {', '.join(FAMILIES)}, got {family!r}")
    _slide_label = f"{pattern} slide {spec.get('title') or spec.get('text', '')[:40]!r}"
    _, has_title, draw = PATTERNS[pattern]
    slide = presentation.slides.add_slide(find_layout(presentation, layout_name(pattern, family)))
    if has_title:
        set_title(slide, require(spec, "title"))
    if draw is image:
        draw(slide, spec, FAMILIES[family], base)
    else:
        draw(slide, spec, FAMILIES[family])
    return slide
