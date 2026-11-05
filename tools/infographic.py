"""Read, check, lay out, and draw a Topic Reference's primary infographic.

The primary infographic is a "topic at a glance": the topic's name, its
purpose in one sentence, three to six key ideas with the relationships between
them, the status, version, and build date, the InteropHub topic, and the
project's notice. Its wording lives in content/infographic.yml; this module
turns that specification into SVG. It uses only the standard library, so the
web guide can draw the same figure without a browser.

build_infographic.py exports the SVG, PNG, and PDF and checks the rendered
text in a headless browser. check_content.py and build_guide.py use the
checks and the drawing here.

Specification (content/infographic.yml):

    layout: topic-at-a-glance      # required; the only layout so far
    arrangement: cycle             # sequence, cycle, or set (default set)
    title: Topic name              # required
    purpose:                       # required
      text: One sentence.
      ref: purpose                 # heading ID or anchor in content/
    ideas:                         # three to six
      - id: first                  # lowercase words joined by hyphens
        label: Short name          # required
        text: One short sentence.  # optional
        ref: first-section         # required
    relationships:                 # optional; each joins two ideas
      - from: first
        to: second
        label: feeds               # optional
        ref: some-heading          # required
    alt: Short alt text.           # required
    topic_link: true               # false draws the topic number without its address
    notice: Text                   # optional; defaults to guide.json "license"
    artwork:                       # optional selected artwork, never essential text
      file: content/assets/infographic-art.png
      placement: background        # the only placement so far
      opacity: 0.15                # 0 to 1, default 0.15

The status comes from guide.json, the version from the build, and the date is
the build date, so they always match the guide.

Text containing "CONFIRM" is starter text: it is reported, not failed. Missing
fields, unresolved references, missing artwork, and text that does not fit
its box fail.
"""

from __future__ import annotations

import base64
import html
import math
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path


SPEC_PATH = "content/infographic.yml"
LAYOUTS = {"topic-at-a-glance"}
ARRANGEMENTS = {"sequence", "cycle", "set"}
PLACEMENTS = {"background"}
MIN_IDEAS, MAX_IDEAS = 3, 6
MAX_RELATIONSHIPS = 10
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TARGET_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
PLACEHOLDER = "CONFIRM"
INTEROPHUB_TOPIC_URL = "https://informatics.immregistries.org/hub/es/topic/{topic}"
LOGO = Path(__file__).resolve().parent.parent / "templates" / "guide" / "AIRA_2018Logo_BlueGreen_Hor.png"

WIDTH, HEIGHT = 1600, 900
MARGIN = 64
FONT_FAMILY = "Arial, 'Liberation Sans', Arimo, Helvetica, sans-serif"
COLORS = {
    "navy": "#1c3c50",
    "green": "#629f44",
    "light-green": "#c9e1c9",
    "blue-gray": "#8098a4",
    "light-gray": "#cccccb",
    "muted": "#58646c",
    "off-white": "#f2f2f2",
    "white": "#ffffff",
}
STATUS_COLORS = {
    "draft": ("#ecbc0a", "#1c3c50"),
    "review": ("#005ea8", "#ffffff"),
    "final": ("#0b6b3a", "#ffffff"),
    "published": ("#0b6b3a", "#ffffff"),
}

# Advance widths in thousandths of an em for the Arial metrics, which
# Liberation Sans, Arimo, and Helvetica share. Characters not listed are
# estimated; the browser check in build_infographic.py measures real text.
_CHARS = (
    "".join(chr(code) for code in range(32, 127))
    + "‘’“”–—…·•é →"
)
_REGULAR = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
    222, 222, 333, 333, 556, 1000, 1000, 333, 350, 556, 278, 1000,
]
_BOLD = [
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
    278, 278, 500, 500, 556, 1000, 1000, 333, 350, 556, 278, 1000,
]
WIDTHS = {False: dict(zip(_CHARS, _REGULAR)), True: dict(zip(_CHARS, _BOLD))}
FALLBACK_WIDTH = 600


class SpecError(ValueError):
    """A specification that cannot be read."""


# --- A small YAML reader -----------------------------------------------------

class _Yaml:
    """Read the block-style YAML subset used by specifications and briefs.

    Mappings, sequences, plain and quoted scalars, multi-line plain scalars,
    folded (>) and literal (|) block scalars, comments, and empty [] and {}
    are understood. Anchors, tags, and flow collections with content are not.
    """

    KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:(?:\s+(.*)|\s*)$")

    def __init__(self, text: str, name: str):
        self.lines = text.replace("\t", "    ").splitlines()
        self.name = name
        self.index = 0

    def error(self, message: str, index: int | None = None) -> SpecError:
        line = (self.index if index is None else index) + 1
        return SpecError(f"{self.name}:{line}: {message}")

    @staticmethod
    def _uncomment(line: str) -> str:
        if line.lstrip().startswith("#"):
            return ""
        return line

    def peek(self) -> tuple[int, str] | None:
        while self.index < len(self.lines):
            line = self._uncomment(self.lines[self.index])
            if line.strip():
                return len(line) - len(line.lstrip(" ")), line.strip()
            self.index += 1
        return None

    def parse(self):
        first = self.peek()
        if first is None:
            return None
        value = self.block(first[0])
        if self.peek() is not None:
            raise self.error("unexpected indentation")
        return value

    def block(self, indent: int):
        _, content = self.peek()
        if content == "-" or content.startswith("- "):
            return self.sequence(indent)
        return self.mapping(indent)

    def sequence(self, indent: int) -> list:
        items = []
        while True:
            next_line = self.peek()
            if next_line is None or next_line[0] != indent:
                break
            content = next_line[1]
            if not (content == "-" or content.startswith("- ")):
                break
            rest = content[1:].lstrip()
            if not rest:
                self.index += 1
                items.append(self.nested(indent))
            elif self.KEY.match(rest):
                column = indent + len(content) - len(rest)
                self.lines[self.index] = " " * column + rest
                items.append(self.mapping(column))
            else:
                self.index += 1
                items.append(self.scalar(rest, indent))
        return items

    def mapping(self, indent: int) -> dict:
        result: dict = {}
        while True:
            next_line = self.peek()
            if next_line is None or next_line[0] < indent:
                break
            if next_line[0] > indent:
                raise self.error("unexpected indentation")
            content = next_line[1]
            if content == "-" or content.startswith("- "):
                break
            match = self.KEY.match(content)
            if not match:
                raise self.error("expected 'key: value'")
            key, rest = match.group(1), (match.group(2) or "").strip()
            if key in result:
                raise self.error(f"duplicate key {key!r}")
            line_index = self.index
            self.index += 1
            if not rest or rest.startswith("#"):
                result[key] = self.nested(indent)
            elif rest[0] in ">|":
                result[key] = self.block_scalar(rest, indent, line_index)
            else:
                result[key] = self.scalar(rest, indent, line_index)
        return result

    def nested(self, indent: int):
        next_line = self.peek()
        if next_line is None:
            return None
        if next_line[0] > indent:
            return self.block(next_line[0])
        if next_line[0] == indent and (next_line[1] == "-" or next_line[1].startswith("- ")):
            return self.sequence(indent)
        return None

    def block_scalar(self, header: str, indent: int, line_index: int) -> str:
        match = re.fullmatch(r"([>|])([+-]?)\s*(?:#.*)?", header)
        if not match:
            raise self.error("unsupported block scalar header", line_index)
        style, chomp = match.groups()
        lines: list[str] = []
        block_indent = None
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if line.strip():
                current = len(line) - len(line.lstrip(" "))
                if current <= indent:
                    break
                if block_indent is None:
                    block_indent = current
                if current < block_indent:
                    break
                lines.append(line[block_indent:])
            else:
                lines.append("")
            self.index += 1
        while lines and not lines[-1]:
            lines.pop()
        if style == "|":
            text = "\n".join(lines)
        else:
            paragraphs, current_lines = [], []
            for line in lines:
                if line:
                    current_lines.append(line.strip())
                else:
                    paragraphs.append(" ".join(current_lines))
                    current_lines = []
            paragraphs.append(" ".join(current_lines))
            text = "\n".join(paragraphs)
        return text if chomp == "-" else text + "\n"

    def scalar(self, text: str, indent: int, line_index: int | None = None):
        line_index = self.index - 1 if line_index is None else line_index
        if text[0] in "\"'":
            quote = text[0]
            end = 1
            value = []
            while True:
                if end >= len(text):
                    raise self.error("unterminated quoted value; keep quoted values on one line", line_index)
                char = text[end]
                if quote == "'" and char == "'":
                    if text[end + 1:end + 2] == "'":
                        value.append("'")
                        end += 2
                        continue
                    break
                if quote == '"' and char == "\\":
                    escaped = text[end + 1:end + 2]
                    value.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/"}.get(escaped, "\\" + escaped))
                    end += 2
                    continue
                if quote == '"' and char == '"':
                    break
                value.append(char)
                end += 1
            remainder = text[end + 1:].strip()
            if remainder and not remainder.startswith("#"):
                raise self.error("unexpected text after a quoted value", line_index)
            return "".join(value)
        text = re.split(r"\s+#", text, maxsplit=1)[0].rstrip()
        if text in ("[]", "{}"):
            return [] if text == "[]" else {}
        if text[0] in "[{&*!%@`":
            raise self.error(f"unsupported YAML syntax {text[0]!r}; quote the value", line_index)
        if ": " in text or text.endswith(":"):
            raise self.error("quote values that contain ': '", line_index)
        parts = [text]
        while True:
            next_line = self.peek()
            if next_line is None or next_line[0] <= indent:
                break
            continuation = next_line[1]
            if continuation.startswith("- ") or self.KEY.match(continuation):
                raise self.error("unexpected indentation")
            parts.append(re.split(r"\s+#", continuation, maxsplit=1)[0].rstrip())
            self.index += 1
        value = " ".join(parts)
        if len(parts) == 1:
            if value in ("null", "~"):
                return None
            if value in ("true", "false"):
                return value == "true"
            if re.fullmatch(r"-?\d+", value):
                return int(value)
            if re.fullmatch(r"-?\d+\.\d+", value):
                return float(value)
        return value


def load_yaml(text: str, name: str = "<yaml>"):
    return _Yaml(text, name).parse()


def load_spec(path: Path) -> dict:
    data = load_yaml(path.read_text(encoding="utf-8-sig"), path.as_posix())
    if not isinstance(data, dict):
        raise SpecError(f"{path.as_posix()}: the specification must be a mapping")
    return data


# --- Text measurement ---------------------------------------------------------

def text_width(text: str, size: float, bold: bool = False) -> float:
    table = WIDTHS[bold]
    return sum(table.get(char, FALLBACK_WIDTH) for char in text) * size / 1000


def wrap(text: str, width: float, size: float, bold: bool = False) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}" if current else word
            if current and text_width(candidate, size, bold) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


# --- Checking the specification ----------------------------------------------

@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    return str(value).strip() or None


def check_spec(spec: dict, root: Path, targets: set[str], name: str = SPEC_PATH) -> Report:
    """Check fields, heading references, and artwork. Layout fit is in layout()."""
    report = Report()
    err = report.errors.append
    starter: list[str] = []

    def placeholder(where: str, value) -> None:
        if isinstance(value, str) and PLACEHOLDER in value:
            starter.append(where)

    def reference(where: str, value) -> None:
        ref = _text(value)
        if not ref:
            err(f"{name}: {where} needs a ref, the heading ID or anchor in content/ it summarizes")
        elif not TARGET_PATTERN.fullmatch(ref):
            err(f"{name}: {where} ref {ref!r} is not a heading ID")
        elif ref not in targets:
            err(f"{name}: {where} ref {ref!r} does not match a heading ID or anchor in content/")

    known = {"layout", "arrangement", "title", "purpose", "ideas", "relationships",
             "alt", "topic_link", "notice", "artwork"}
    for key in spec:
        if key not in known:
            err(f"{name}: unknown field {key!r}")

    if spec.get("layout") not in LAYOUTS:
        err(f"{name}: layout must be one of: {', '.join(sorted(LAYOUTS))}")
    arrangement = spec.get("arrangement", "set")
    if arrangement not in ARRANGEMENTS:
        err(f"{name}: arrangement must be one of: {', '.join(sorted(ARRANGEMENTS))}")
    for key in ("title", "alt"):
        if not _text(spec.get(key)):
            err(f"{name}: {key} is required")
        placeholder(key, spec.get(key))
    if "topic_link" in spec and not isinstance(spec["topic_link"], bool):
        err(f"{name}: topic_link must be true or false")
    if "notice" in spec and spec["notice"] is not None and not _text(spec["notice"]):
        err(f"{name}: notice must be text")

    purpose = spec.get("purpose")
    if not isinstance(purpose, dict) or not _text(purpose.get("text")):
        err(f"{name}: purpose needs text and a ref")
    else:
        placeholder("purpose", purpose.get("text"))
        reference("purpose", purpose.get("ref"))

    ideas = spec.get("ideas")
    ids: set[str] = set()
    if not isinstance(ideas, list) or not MIN_IDEAS <= len(ideas) <= MAX_IDEAS:
        err(f"{name}: ideas must list {MIN_IDEAS} to {MAX_IDEAS} key ideas")
        ideas = ideas if isinstance(ideas, list) else []
    for number, idea in enumerate(ideas, 1):
        where = f"idea {number}"
        if not isinstance(idea, dict):
            err(f"{name}: {where} must be a mapping")
            continue
        for key in idea:
            if key not in {"id", "label", "text", "ref"}:
                err(f"{name}: {where} has unknown field {key!r}")
        identifier = _text(idea.get("id"))
        if not identifier or not ID_PATTERN.fullmatch(identifier):
            err(f"{name}: {where} needs an id of lowercase words joined by hyphens")
        elif identifier in ids:
            err(f"{name}: duplicate idea id {identifier!r}")
        else:
            ids.add(identifier)
            where = f"idea {identifier!r}"
        if not _text(idea.get("label")):
            err(f"{name}: {where} needs a label")
        placeholder(f"{where} label", idea.get("label"))
        placeholder(f"{where} text", idea.get("text"))
        reference(where, idea.get("ref"))

    relationships = spec.get("relationships") or []
    if not isinstance(relationships, list):
        err(f"{name}: relationships must be a list")
        relationships = []
    if len(relationships) > MAX_RELATIONSHIPS:
        err(f"{name}: at most {MAX_RELATIONSHIPS} relationships")
    pairs: set[frozenset] = set()
    for number, relationship in enumerate(relationships, 1):
        where = f"relationship {number}"
        if not isinstance(relationship, dict):
            err(f"{name}: {where} must be a mapping")
            continue
        for key in relationship:
            if key not in {"from", "to", "label", "ref"}:
                err(f"{name}: {where} has unknown field {key!r}")
        source, target = _text(relationship.get("from")), _text(relationship.get("to"))
        for end, value in (("from", source), ("to", target)):
            if value not in ids:
                err(f"{name}: {where} {end} {value!r} is not an idea id")
        if source and source == target:
            err(f"{name}: {where} joins an idea to itself")
        pair = frozenset((source, target))
        if pair in pairs:
            err(f"{name}: {where} repeats a pair of ideas; draw one relationship between two ideas")
        pairs.add(pair)
        placeholder(f"{where} label", relationship.get("label"))
        reference(where, relationship.get("ref"))

    artwork = spec.get("artwork")
    if artwork is not None:
        if not isinstance(artwork, dict) or not _text(artwork.get("file")):
            err(f"{name}: artwork needs a file")
        else:
            path = root / str(artwork["file"])
            if not path.is_file():
                err(f"{name}: artwork file {artwork['file']} does not exist")
            elif path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                err(f"{name}: artwork must be a PNG or JPEG file")
            if artwork.get("placement", "background") not in PLACEMENTS:
                err(f"{name}: artwork placement must be one of: {', '.join(sorted(PLACEMENTS))}")
            opacity = artwork.get("opacity", 0.15)
            if not isinstance(opacity, (int, float)) or isinstance(opacity, bool) or not 0 <= opacity <= 1:
                err(f"{name}: artwork opacity must be a number from 0 to 1")
    if starter:
        report.warnings.append(f"{name}: {len(starter)} field(s) still have {PLACEHOLDER} starter "
                               f"text: {', '.join(starter)}")
    return report


# --- Layout -------------------------------------------------------------------

@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def overlaps(self, other: "Box", gap: float = 0) -> bool:
        return not (self.x + self.w + gap <= other.x or other.x + other.w + gap <= self.x
                    or self.y + self.h + gap <= other.y or other.y + other.h + gap <= self.y)


@dataclass
class TextBlock:
    name: str
    box: Box
    lines: list[str]
    size: float
    line_height: float
    bold: bool
    color: str
    anchor: str = "start"
    first_baseline: float = 0
    letter_spacing: float = 0


@dataclass
class Layout:
    spec: dict
    header: list[TextBlock]
    status: tuple[str, str, str]
    status_box: Box
    meta: list[TextBlock]
    cards: list[tuple[dict, Box, list[TextBlock]]]
    arrows: list[tuple[dict, tuple[float, float, float, float], TextBlock | None, Box | None]]
    footer: list[TextBlock]
    logo: Box
    errors: list[str]


HEADER_BOTTOM = 220
BODY = Box(MARGIN, 252, WIDTH - 2 * MARGIN, 528)
FOOTER_TOP = 800
STATUS_WIDTH = 340
CARD_PAD = 24
CARD_BAR = 8
LABEL_SIZE, LABEL_LINE = 26, 32
TEXT_SIZE, TEXT_LINE = 20, 27
REL_SIZE, REL_LINE = 17, 21
REL_WRAP = 164
GAP_X, GAP_Y = 200, 112
MAX_CARD_WIDTH = 480
MIN_CARD_HEIGHT = 150
MAX_ONE_ROW_HEIGHT = 320
LABEL_OFFSET = 8
ARROW_MARGIN = 12


def _grid(n: int, arrangement: str) -> list[tuple[int, float]]:
    """Row and column (fractional for centered rows) of each idea, in order."""
    if n == 3:
        if arrangement == "cycle":
            return [(0, 1), (1, 2), (1, 0)]
        return [(0, 0), (0, 1), (0, 2)]
    if n == 4:
        if arrangement == "set":
            return [(0, 0), (0, 1), (1, 0), (1, 1)]
        return [(0, 0), (0, 1), (1, 1), (1, 0)]
    if n == 5:
        if arrangement == "sequence":
            return [(0, 0), (0, 1), (0, 2), (1, 2), (1, 1)]
        if arrangement == "cycle":
            return [(0, 0), (0, 1), (0, 2), (1, 1.5), (1, 0.5)]
        return [(0, 0), (0, 1), (0, 2), (1, 0.5), (1, 1.5)]
    if arrangement == "set":
        return [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
    return [(0, 0), (0, 1), (0, 2), (1, 2), (1, 1), (1, 0)]


def card_boxes(n: int, arrangement: str, height: float | None = None) -> list[Box]:
    """Card boxes, centred in the body. Without a height, the tallest that fits."""
    cells = _grid(n, arrangement)
    rows = 1 + max(row for row, _ in cells)
    columns = 3 if n in (3, 5, 6) else 2
    gap = GAP_X if columns == 3 else 240
    width = min((BODY.w - (columns - 1) * gap) / columns, MAX_CARD_WIDTH)
    left = BODY.x + (BODY.w - (columns * width + (columns - 1) * gap)) / 2
    tallest = MAX_ONE_ROW_HEIGHT if rows == 1 else (BODY.h - GAP_Y) / 2
    height = tallest if height is None else min(height, tallest)
    top = BODY.y + (BODY.h - (rows * height + (rows - 1) * GAP_Y)) / 2
    tops = [top + row * (height + GAP_Y) for row in range(rows)]
    return [Box(left + column * (width + gap), tops[row], width, height) for row, column in cells]


def _card_blocks(idea: dict, box: Box, errors: list[str] | None) -> tuple[list[TextBlock], float]:
    """The label and text blocks of one card, and the height they need."""
    name = f"idea {idea.get('id')!r}"
    x, y, w = box.x + CARD_PAD, box.y + CARD_BAR + CARD_PAD - 4, box.w - 2 * CARD_PAD
    label = _block(f"{name} label", Box(x, y, w, 0), str(idea.get("label", "")),
                   LABEL_SIZE, LABEL_LINE, True, COLORS["navy"], errors=errors)
    label.box.h = len(label.lines) * LABEL_LINE
    blocks = [label]
    used = label.box.h
    if _text(idea.get("text")):
        body = _block(f"{name} text", Box(x, y + used + 10, w, 0), str(idea["text"]),
                      TEXT_SIZE, TEXT_LINE, False, COLORS["navy"], errors=errors)
        body.box.h = len(body.lines) * TEXT_LINE
        used += 10 + body.box.h
        blocks.append(body)
    return blocks, used


def _exit(box: Box, dx: float, dy: float) -> float:
    """Fraction of (dx, dy) from the box's centre to its edge plus the arrow margin."""
    half_w, half_h = box.w / 2 + ARROW_MARGIN, box.h / 2 + ARROW_MARGIN
    limits = []
    if dx:
        limits.append(half_w / abs(dx))
    if dy:
        limits.append(half_h / abs(dy))
    return min(limits)


def _segment_hits(box: Box, x1: float, y1: float, x2: float, y2: float) -> bool:
    """Liang-Barsky test: does the segment pass through the box?"""
    t0, t1 = 0.0, 1.0
    dx, dy = x2 - x1, y2 - y1
    for p, q in ((-dx, x1 - box.x), (dx, box.x + box.w - x1), (-dy, y1 - box.y), (dy, box.y + box.h - y1)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def _block(name, box, text, size, line, bold, color, anchor="start", max_lines=None,
           errors=None, top_pad=0.0, letter_spacing=0.0) -> TextBlock:
    lines = wrap(text, box.w, size, bold)
    block = TextBlock(name, box, lines, size, line, bold, color, anchor,
                      box.y + top_pad + size * 0.8, letter_spacing)
    if errors is not None:
        for value in lines:
            if text_width(value, size, bold) > box.w + 0.5:
                errors.append(f"{name}: {value!r} is too wide for its box; shorten it")
        if max_lines is not None and len(lines) > max_lines:
            errors.append(f"{name} needs {len(lines)} lines; at most {max_lines} fit. Shorten it.")
    return block


def layout(spec: dict, status: str, version: str, built: str, topic: int | None,
           notice: str | None) -> Layout:
    """Place every element. Text that does not fit is reported in errors."""
    errors: list[str] = []
    text_right = WIDTH - MARGIN - STATUS_WIDTH - 32
    header_box = Box(MARGIN, 0, text_right - MARGIN, HEADER_BOTTOM)

    kicker = TextBlock("kicker", Box(MARGIN, 30, 400, 20), ["TOPIC AT A GLANCE"], 15, 20, True,
                       COLORS["light-green"], first_baseline=46, letter_spacing=2)
    title = _block("title", Box(MARGIN, 62, header_box.w, 96), str(spec.get("title", "")),
                   40, 48, True, COLORS["white"], max_lines=2, errors=errors)
    purpose_top = title.box.y + len(title.lines) * 48 + 14
    purpose_text = (spec.get("purpose") or {}).get("text", "")
    purpose = _block("purpose", Box(MARGIN, purpose_top, header_box.w, 60), str(purpose_text),
                     22, 30, False, COLORS["light-green"], max_lines=2, errors=errors)
    purpose.box.h = max(len(purpose.lines), 1) * 30
    if purpose.box.y + purpose.box.h > HEADER_BOTTOM - 8:
        errors.append("title and purpose together are too long for the header; shorten one")

    status_right = WIDTH - MARGIN
    tag = status.upper()
    tag_width = text_width(tag, 16, True) + 2 * 14 + len(tag) * 1.5
    status_box = Box(status_right - tag_width, 38, tag_width, 32)
    meta = [
        _block("version", Box(status_right - STATUS_WIDTH, 92, STATUS_WIDTH, 24),
               f"Version {version}", 18, 24, False, COLORS["white"], "end", 1, errors),
        _block("date", Box(status_right - STATUS_WIDTH, 122, STATUS_WIDTH, 24),
               f"Built {built}", 18, 24, False, COLORS["light-gray"], "end", 1, errors),
    ]

    ideas = [idea for idea in spec.get("ideas") or [] if isinstance(idea, dict)]
    arrangement = spec.get("arrangement", "set")
    cards = []
    if MIN_IDEAS <= len(ideas) <= MAX_IDEAS:
        widest = card_boxes(len(ideas), arrangement)
        needed = max(_card_blocks(idea, box, None)[1] for idea, box in zip(ideas, widest))
        height = max(needed + CARD_BAR + 2 * CARD_PAD - 4, MIN_CARD_HEIGHT)
        for idea, box in zip(ideas, card_boxes(len(ideas), arrangement, height)):
            blocks, used = _card_blocks(idea, box, errors)
            room = box.h - CARD_BAR - 2 * CARD_PAD + 4
            if used > room + 0.5:
                errors.append(f"idea {idea.get('id')!r}: the label and text need {used:.0f}px but "
                              f"the card holds {room:.0f}px; shorten them")
            cards.append((idea, box, blocks))

    by_id = {str(idea.get("id")): box for idea, box, _ in cards}
    arrows = []
    labels: list[tuple[str, Box]] = []
    for relationship in spec.get("relationships") or []:
        if not isinstance(relationship, dict):
            continue
        source, target = by_id.get(str(relationship.get("from"))), by_id.get(str(relationship.get("to")))
        if source is None or target is None:
            continue
        name = f"relationship {relationship.get('from')} -> {relationship.get('to')}"
        dx, dy = target.cx - source.cx, target.cy - source.cy
        start = _exit(source, dx, dy)
        end = 1 - _exit(target, -dx, -dy)
        x1, y1 = source.cx + dx * start, source.cy + dy * start
        x2, y2 = source.cx + dx * end, source.cy + dy * end
        if end <= start:
            errors.append(f"{name}: the ideas are too close to draw an arrow")
            continue
        for idea, box, _ in cards:
            if box is not source and box is not target and _segment_hits(box, x1, y1, x2, y2):
                errors.append(f"{name}: the arrow crosses idea {idea.get('id')!r}; reorder the "
                              "ideas or choose another arrangement")
        block = pill = None
        label_text = _text(relationship.get("label"))
        if label_text:
            lines = wrap(label_text, REL_WRAP, REL_SIZE)
            width = max(text_width(line, REL_SIZE) for line in lines)
            height = len(lines) * REL_LINE
            # Beside the arrow, not on it: above a horizontal arrow, right of a vertical one.
            length = math.hypot(x2 - x1, y2 - y1)
            nx, ny = (y2 - y1) / length, -(x2 - x1) / length
            if ny > 0 or (abs(ny) < 1e-9 and nx < 0):
                nx, ny = -nx, -ny
            pill_w, pill_h = width + 24, height + 12
            offset = abs(nx) * pill_w / 2 + abs(ny) * pill_h / 2 + LABEL_OFFSET
            mx, my = (x1 + x2) / 2 + nx * offset, (y1 + y2) / 2 + ny * offset
            pill = Box(mx - pill_w / 2, my - pill_h / 2, pill_w, pill_h)
            block = TextBlock(f"{name} label", Box(mx - width / 2, my - height / 2, width, height),
                              lines, REL_SIZE, REL_LINE, False, COLORS["navy"], "middle",
                              my - height / 2 + REL_SIZE * 0.8)
            if width > REL_WRAP + 0.5:
                errors.append(f"{name}: label {label_text!r} has a word too long to fit; shorten it")
            for idea, box, _ in cards:
                if pill.overlaps(box):
                    errors.append(f"{name}: label {label_text!r} overlaps idea {idea.get('id')!r}; "
                                  "shorten it")
            for other_name, other in labels:
                if pill.overlaps(other, 4):
                    errors.append(f"{name}: label overlaps the label of {other_name}")
            labels.append((name, pill))
        arrows.append((relationship, (x1, y1, x2, y2), block, pill))

    logo_width, logo_height = _png_size(LOGO)
    logo_h = 52
    logo = Box(WIDTH - MARGIN - logo_width * logo_h / logo_height, FOOTER_TOP + 24,
               logo_width * logo_h / logo_height, logo_h)
    footer_width = logo.x - MARGIN - 32
    topic_line = "InteropHub topic"
    if topic is not None:
        topic_line = f"InteropHub topic {topic}"
        if spec.get("topic_link", True):
            topic_line += " · " + INTEROPHUB_TOPIC_URL.format(topic=topic)
    footer = [_block("topic", Box(MARGIN, FOOTER_TOP + 22, footer_width, 26), topic_line, 19, 26,
                     False, COLORS["navy"], max_lines=1, errors=errors)]
    if notice:
        footer.append(_block("notice", Box(MARGIN, FOOTER_TOP + 56, footer_width, 24), notice, 17, 24,
                             True, COLORS["muted"], max_lines=1, errors=errors))

    return Layout(spec, [kicker, title, purpose], (tag, *STATUS_COLORS.get(status.lower(),
                  ("#005ea8", "#ffffff"))), status_box, meta, cards, arrows, footer, logo, errors)


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SpecError(f"{path} is not a PNG file")
    return struct.unpack(">II", data[16:24])


# --- Drawing ------------------------------------------------------------------

def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _data_uri(path: Path) -> str:
    kind = "png" if path.suffix.lower() == ".png" else "jpeg"
    return f"data:image/{kind};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _text_svg(block: TextBlock) -> str:
    if block.anchor == "end":
        x = block.box.x + block.box.w
    elif block.anchor == "middle":
        x = block.box.x + block.box.w / 2
    else:
        x = block.box.x
    attributes = (f'font-size="{block.size}" fill="{block.color}"'
                  + (' font-weight="700"' if block.bold else "")
                  + (f' text-anchor="{block.anchor}"' if block.anchor != "start" else "")
                  + (f' letter-spacing="{block.letter_spacing}"' if block.letter_spacing else ""))
    texts = "".join(
        f'<text x="{x:.1f}" y="{block.first_baseline + index * block.line_height:.1f}" {attributes}>'
        f"{_esc(line)}</text>"
        for index, line in enumerate(block.lines)
    )
    box = block.box
    height = max(box.h, len(block.lines) * block.line_height)
    return (f'<g class="ig-text" data-name="{_esc(block.name)}" '
            f'data-box="{box.x:.1f} {box.y:.1f} {box.w:.1f} {height:.1f}">{texts}</g>')


def _link(content: str, ref, label: str, links: bool) -> str:
    if not links or not _text(ref):
        return content
    return (f'<a href="#{_esc(ref)}" aria-label="{_esc(label)}">'
            f"<title>{_esc(label)}</title>{content}</a>")


def render_svg(layout_result: Layout, root: Path, links: bool = False,
               id_prefix: str = "ig") -> str:
    """Draw a laid-out infographic. links=True makes each part link to its section."""
    spec = layout_result.spec
    title = str(spec.get("title", ""))
    parts: list[str] = []
    add = parts.append
    role = "" if links else ' role="img"'
    add(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}"{role} '
        f'aria-labelledby="{id_prefix}-title {id_prefix}-desc" font-family="{_esc(FONT_FAMILY)}">')
    add(f'<title id="{id_prefix}-title">{_esc(title)}: topic at a glance</title>')
    add(f'<desc id="{id_prefix}-desc">{_esc(spec.get("alt", ""))}</desc>')
    add("<defs>"
        f'<marker id="{id_prefix}-arrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="12" '
        f'markerHeight="12" markerUnits="userSpaceOnUse" orient="auto">'
        f'<path d="M1,1 L11,6 L1,11 Z" fill="{COLORS["blue-gray"]}"/></marker>'
        f'<clipPath id="{id_prefix}-body"><rect x="0" y="{HEADER_BOTTOM}" width="{WIDTH}" '
        f'height="{FOOTER_TOP - HEADER_BOTTOM}"/></clipPath>'
        "</defs>")

    add(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{COLORS["off-white"]}"/>')
    artwork = spec.get("artwork")
    if isinstance(artwork, dict) and _text(artwork.get("file")):
        path = root / str(artwork["file"])
        opacity = artwork.get("opacity", 0.15)
        add(f'<image class="ig-artwork" href="{_data_uri(path)}" x="0" y="{HEADER_BOTTOM}" '
            f'width="{WIDTH}" height="{FOOTER_TOP - HEADER_BOTTOM}" preserveAspectRatio="xMidYMid slice" '
            f'opacity="{opacity}" clip-path="url(#{id_prefix}-body)"/>')

    add(f'<rect width="{WIDTH}" height="{HEADER_BOTTOM}" fill="{COLORS["navy"]}"/>')
    kicker, title_block, purpose_block = layout_result.header
    add(_text_svg(kicker))
    add(_text_svg(title_block))
    purpose = spec.get("purpose") or {}
    add(_link(_text_svg(purpose_block), purpose.get("ref"), "Purpose: go to its section", links))

    tag, background, foreground = layout_result.status
    box = layout_result.status_box
    add(f'<rect x="{box.x:.1f}" y="{box.y}" width="{box.w:.1f}" height="{box.h}" rx="4" fill="{background}"/>')
    add(f'<text x="{box.cx:.1f}" y="{box.y + 22}" font-size="16" font-weight="700" letter-spacing="1.5" '
        f'text-anchor="middle" fill="{foreground}">{_esc(tag)}</text>')
    for block in layout_result.meta:
        add(_text_svg(block))

    for relationship, (x1, y1, x2, y2), block, pill in layout_result.arrows:
        add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{COLORS["blue-gray"]}" '
            f'stroke-width="3" marker-end="url(#{id_prefix}-arrow)"/>')
    for idea, box, blocks in layout_result.cards:
        card = (f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{box.h:.1f}" rx="8" '
                f'fill="{COLORS["white"]}" stroke="{COLORS["light-gray"]}" stroke-width="1.5"/>'
                f'<path d="M{box.x:.1f},{box.y + CARD_BAR:.1f} V{box.y + 8:.1f} '
                f'A8,8 0 0 1 {box.x + 8:.1f},{box.y:.1f} H{box.x + box.w - 8:.1f} '
                f'A8,8 0 0 1 {box.x + box.w:.1f},{box.y + 8:.1f} V{box.y + CARD_BAR:.1f} Z" '
                f'fill="{COLORS["green"]}"/>'
                + "".join(_text_svg(item) for item in blocks))
        label = str(idea.get("label", ""))
        add(f'<g class="ig-card" data-idea="{_esc(idea.get("id"))}" data-ref="{_esc(idea.get("ref"))}" '
            f'data-box="{box.x:.1f} {box.y:.1f} {box.w:.1f} {box.h:.1f}">'
            + _link(card, idea.get("ref"), f"{label}: go to its section", links) + "</g>")
    for relationship, _, block, pill in layout_result.arrows:
        if block is None:
            continue
        content = (f'<rect x="{pill.x:.1f}" y="{pill.y:.1f}" width="{pill.w:.1f}" height="{pill.h:.1f}" '
                   f'rx="{min(pill.h / 2, 14):.1f}" fill="{COLORS["white"]}" stroke="{COLORS["blue-gray"]}" '
                   f'stroke-width="1.5"/>' + _text_svg(block))
        add(f'<g class="ig-relationship" data-ref="{_esc(relationship.get("ref"))}">'
            + _link(content, relationship.get("ref"),
                    f"{relationship.get('label')}: go to its section", links) + "</g>")

    add(f'<rect y="{FOOTER_TOP}" width="{WIDTH}" height="{HEIGHT - FOOTER_TOP}" fill="{COLORS["white"]}"/>')
    add(f'<rect y="{FOOTER_TOP}" width="{WIDTH}" height="3" fill="{COLORS["green"]}"/>')
    for block in layout_result.footer:
        add(_text_svg(block))
    logo = layout_result.logo
    add(f'<image href="{_data_uri(LOGO)}" x="{logo.x:.1f}" y="{logo.y:.1f}" width="{logo.w:.1f}" '
        f'height="{logo.h:.1f}"><title>American Immunization Registry Association</title></image>')
    add("</svg>")
    return "\n".join(parts) + "\n"


# --- Putting it together ------------------------------------------------------

def link_targets(root: Path) -> set[str]:
    """Heading IDs and anchors in content/, as the guide will name them."""
    from check_content import content_targets  # noqa: PLC0415 - avoids an import cycle

    return set(content_targets(root))


def build(root: Path, config: dict, version: str, built: str, spec_path: str = SPEC_PATH,
          links: bool = False, id_prefix: str = "ig") -> tuple[str | None, Report]:
    """Check the specification and draw it. Returns (svg or None, report)."""
    path = root / spec_path
    report = Report()
    try:
        spec = load_spec(path)
    except (OSError, SpecError) as error:
        report.errors.append(str(error))
        return None, report
    report = check_spec(spec, root, link_targets(root), spec_path)
    if report.errors:
        return None, report
    notice = _text(spec.get("notice")) or _text(config.get("license"))
    result = layout(spec, str(config.get("status", "Draft")), version, built,
                    config.get("interophubTopic"), notice)
    report.errors.extend(f"{spec_path}: {message}" for message in result.errors)
    if report.errors:
        return None, report
    return render_svg(result, root, links, id_prefix), report


__all__ = [
    "SPEC_PATH", "SpecError", "Report", "load_yaml", "load_spec", "check_spec", "layout",
    "render_svg", "build", "link_targets", "text_width", "wrap", "WIDTH", "HEIGHT",
]
