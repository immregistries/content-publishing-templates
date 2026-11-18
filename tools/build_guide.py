"""Build a self-contained web guide from a content project's core document.

The guide uses the AIRA Web theme so it matches InteropHub: AIRA header, the
topic title with a status tag, a dark section bar, a right rail with the
current section's subsections, and on-page comments kept in the reader's
browser and exported as JSON.

Run from the content project's root:

    python process/tools/build_guide.py --assembly Project.qmd --version v0.1.0

The project's guide.json supplies the status, the InteropHub topic, the
repository URL, an optional document type such as "Topic Reference", and
optional short labels for the section bar. Pandoc is
required; Quarto's bundled copy is used when pandoc is not on the PATH.

A Workspace Topic Reference ("topicReferenceType": "workspace") has no Git
version; the page shows its build date and the "location" where it is kept.
A private Standing Topic Reference kept in a workspace ("keptIn": "workspace")
has no Git either; the page shows the "version" label set in guide.json, such
as v0.1.0, its build date, and its "location".

When content/infographic.yml exists, the primary infographic is drawn from it
and placed in the front section, after the Executive Summary and What changed
and before the Scope (above the first section when there is no Executive
Summary), each part linking to the section it summarizes. It is drawn here rather than copied from
output/, so the guide builds without a browser; build_infographic.py draws the
same figure for the PNG, PDF, and Word document.

A Topic Reference's front section, content/00-executive-summary.md and
content/00-scope.md (see front_section.py), opens the guide: the status
notice as a banner, the Executive Summary, "What changed" in this version,
the infographic, and the Scope's lists as cards. None of it is in the section
bar or counted as a chapter. A summary over 650 words, a malformed Scope, or
the retired content/00-status-and-scope.md fails the build.

Change markers (<!-- changed v0.5.0: ... -->, see change_markers.py) are
resolved to the review area and block they cover and written into the page
as the guide-change-markers element, for guide.js to draw; markers older than
the current version are left out. A marker that cannot be placed fails the
build.

Each guide carries a build manifest in its <head>, a JSON script element with
the ID "guide-build-manifest": the shared templates' version and release
registry, the document's identity and version, how it was built, its
structure, and the findings of check_content.py, each warning with a stable
code. InteropHub reads it to show the guide's status. Readers can see it, so
it names files only by their path in the project and holds no machine paths,
workspace location, or secrets.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_core_markdown import (  # noqa: E402
    FRONT_MATTER_PATTERN,
    LINK_TARGET_PATTERN,
    ROW_ANCHORS_PATTERN,
    anchor_name_problem,
    front_matter_value,
    include_paths,
    plain_mermaid_fences,
    row_anchor_name,
)
import change_markers  # noqa: E402
import front_section  # noqa: E402
import infographic  # noqa: E402
import process_release  # noqa: E402


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "guide"
MERMAID_SCRIPT = TEMPLATE_DIR / "mermaid" / "mermaid.min.js"
MERMAID_BLOCK_PATTERN = re.compile(
    r'<pre class="mermaid"><code>(.*?)</code></pre>', re.DOTALL
)
HEADING_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
ANCHOR_PATTERN = re.compile(
    r"^\s*<!-- anchor: ([a-z0-9]+(?:-[a-z0-9]+)*) -->\s*$"
)
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
SECTION_PATTERN = re.compile(
    r'<section id="([^"]+)" class="level2[^"]*"[^>]*>\s*<h2[^>]*>(.*?)</h2>', re.DOTALL
)
TAG_PATTERN = re.compile(r"<[^>]+>")
SUGGESTED_MAX_CHAPTERS = 7
APPENDIX_PATTERN = re.compile(r"Appendix\b", re.IGNORECASE)
INTEROPHUB_TOPIC_URL = "https://informatics.immregistries.org/hub/es/topic/{topic}"
STATUS_TAGS = {
    "collecting ideas": "aira-tag--outline",
    "draft": "aira-tag--warning",
    "review": "aira-tag--info",
    "final": "aira-tag--success",
    "published": "aira-tag--success",
}
DOCUMENT_START_ANCHOR = "document-start"
ROW_ANCHORS_MARKER = "guide-row-anchors"
ROW_TABLE_PATTERN = re.compile(
    r'<div class="guide-row-anchors">\s*</div>\s*'
    r'(?:<div class="aira-table-wrap">(<table class="aira-table"[^>]*>.*?</table>)</div>)?',
    re.DOTALL,
)
TABLE_OPEN_PATTERN = re.compile(r"<table((?:\s[^>]*)?)>")
BODY_PATTERN = re.compile(r"(<tbody>)(.*?)(</tbody>)", re.DOTALL)
ROW_PATTERN = re.compile(r"<tr\b([^>]*)>(.*?)</tr>", re.DOTALL)
FIRST_CELL_PATTERN = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.DOTALL)
MANIFEST_ID = "guide-build-manifest"
MANIFEST_SCHEMA = 1
MANIFEST_GENERATOR = "content-publishing-templates"
# InteropHub ignores a manifest over 64 KB; these limits keep one well under it.
MANIFEST_MAX_BYTES = 64 * 1024
MANIFEST_MESSAGE_LIMIT = 300
MANIFEST_WARNING_LIMIT = 100
DOCUMENT_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_DOCUMENT_KEYS = {"comments", "review-flags", "token"}
HOSTING_MODES = {"local", "github-pages", "interophub"}


def comments_config(config: dict) -> dict | None:
    """Validate and normalize the optional comment backend settings."""
    comments = config.get("comments")
    if comments is None:
        return None
    if not isinstance(comments, dict):
        raise RuntimeError("guide.json comments must be an object.")
    mode = comments.get("mode")
    if mode not in {"local", "interophub"}:
        raise RuntimeError("guide.json comments.mode must be 'local' or 'interophub'.")
    result = {"mode": mode}
    if mode == "local":
        return result
    hub = comments.get("hub")
    document = comments.get("document")
    if not isinstance(hub, str):
        raise RuntimeError("guide.json comments.hub is required in interophub mode.")
    parsed = urlsplit(hub)
    local_http = parsed.scheme == "http" and parsed.hostname in {
        "localhost", "127.0.0.1"
    }
    if not (parsed.scheme == "https" or local_http) or not parsed.netloc:
        raise RuntimeError(
            "guide.json comments.hub must be an absolute https URL, or http on localhost."
        )
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise RuntimeError("guide.json comments.hub must not contain credentials, a query, or a fragment.")
    if not isinstance(document, str) or len(document) > 100 or not DOCUMENT_KEY_PATTERN.fullmatch(document):
        raise RuntimeError("guide.json comments.document is not a valid document key.")
    if document in RESERVED_DOCUMENT_KEYS:
        raise RuntimeError("guide.json comments.document uses a reserved document key.")
    result.update({"hub": hub.rstrip("/"), "document": document})
    return result


def hosting_config(config: dict) -> str:
    """Validate hosting and its relationship to the comment backend."""
    hosting = config.get("hosting", "github-pages")
    if hosting not in HOSTING_MODES:
        raise RuntimeError(
            "guide.json hosting must be 'local', 'github-pages', or 'interophub'."
        )
    comments = comments_config(config)
    if hosting == "interophub":
        if not comments or comments.get("mode") != "interophub":
            raise RuntimeError(
                "guide.json comments.mode must be 'interophub' when hosting is 'interophub'."
            )
        # comments_config validates and requires hub and document in this mode.
    return hosting


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly", required=True, help="Quarto assembly file.")
    parser.add_argument("--root", default=".", help="Content project root.")
    parser.add_argument("--config", default="guide.json", help="Guide settings file.")
    parser.add_argument(
        "--output", default="output/guide/index.html", help="Guide HTML to write."
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Version label shown on the page. Defaults to git describe.",
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="Git ref for links to repository files. Defaults to the version, or main.",
    )
    parser.add_argument(
        "--infographic",
        default=infographic.SPEC_PATH,
        help="Primary infographic specification, drawn in the front section when it exists.",
    )
    return parser.parse_args()


INFOGRAPHIC_ID = "guide-infographic"


def infographic_figure(root: Path, spec: str, config: dict, version: str | None) -> str:
    """The primary infographic as an inline figure, or "" when the project has none."""
    if not (root / spec).is_file():
        return ""
    release = infographic.release_label(root, version, config)
    svg, report = infographic.build(root, config, release, date.today().isoformat(), spec,
                                    links=True, id_prefix=INFOGRAPHIC_ID)
    for warning in report.warnings:
        print(f"Warning: {warning}")
    if svg is None:
        raise RuntimeError("The primary infographic cannot be drawn:\n  " + "\n  ".join(report.errors))
    return (
        f'<figure class="guide-infographic" id="{INFOGRAPHIC_ID}">\n{svg}'
        '<figcaption class="aira-meta">At a glance. The sections below state in full everything '
        "this figure summarizes; select a part of it to go to its section.</figcaption>\n</figure>\n"
    )


def pandoc_command() -> list[str]:
    if shutil.which("pandoc"):
        return ["pandoc"]
    if shutil.which("quarto"):
        return ["quarto", "pandoc"]
    raise RuntimeError("Pandoc is required. Install pandoc or Quarto.")


def is_workspace(config: dict) -> bool:
    """A Workspace Topic Reference: no Git or releases; it is identified by its build date."""
    return config.get("topicReferenceType") == "workspace"


KEPT_IN = {"git", "workspace"}


def kept_in_config(config: dict) -> str:
    """Validate where a Standing project is kept: "git" (the default) or "workspace".

    A project kept in a workspace has no repository, is private, is hosted only
    in InteropHub, and names its version and location in guide.json.
    """
    kept_in = config.get("keptIn", "workspace" if is_workspace(config) else "git")
    if kept_in not in KEPT_IN:
        raise RuntimeError("guide.json keptIn must be 'git' or 'workspace'.")
    if "keptIn" not in config or is_workspace(config):
        return kept_in
    if kept_in == "workspace":
        problems = []
        if config.get("repository"):
            problems.append("it has no repository, so remove repository")
        if config.get("hosting") != "interophub":
            problems.append("hosting must be 'interophub'")
        if not config.get("interophubTopic"):
            problems.append("interophubTopic is required")
        if not config.get("location"):
            problems.append("location, where it is kept, is required")
        version = config.get("version")
        if not isinstance(version, str) or not infographic.RELEASE_PATTERN.fullmatch(version):
            problems.append("version must be a label such as v0.1.0, set by hand for each upload")
        if problems:
            raise RuntimeError(
                "guide.json keptIn is 'workspace', for a private Standing Topic Reference kept "
                "without Git: " + "; ".join(problems) + "."
            )
    return kept_in


def git_version(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unversioned"


def section_id(path: Path) -> str:
    return re.sub(r"^\d+-", "", path.stem)


def replace_anchors(text: str) -> str:
    """Replace anchor directives outside fenced code blocks."""
    output = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            output.append(line)
            continue
        match = ANCHOR_PATTERN.fullmatch(line.rstrip("\r\n")) if fence is None else None
        if fence is None and ROW_ANCHORS_PATTERN.fullmatch(line.rstrip("\r\n")):
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            output.append(f'<div class="{ROW_ANCHORS_MARKER}"></div>{ending}')
        elif match:
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            name = match.group(1)
            output.append(
                f'<div id="{name}" class="guide-anchor" '
                f'data-guide-anchor="{name}"></div>{ending}'
            )
        else:
            output.append(line)
    return "".join(output)


IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


CHANGE_SLOT_CLASS = "guide-change-slot"
CHANGE_SLOT_PATTERN = re.compile(
    r'<div class="' + CHANGE_SLOT_CLASS + r'" data-change="(\d+)"(?: data-anchor="([^"]*)")?>\s*</div>\n?'
)
ROW_DIRECTIVE_THEN_SLOTS = re.compile(
    r'(<div class="' + ROW_ANCHORS_MARKER + r'"></div>\s*)'
    r'((?:<div class="' + CHANGE_SLOT_CLASS + r'" data-change="\d+"></div>\s*)+)'
)


def replace_change_markers(text: str, relative: str, markers: list) -> str:
    """Put a placeholder where each change marker is, to find what it covers.

    The marker is checked here; the placeholder is resolved to its review area
    and block in the built HTML (resolve_change_markers) and then removed.
    Raises RuntimeError for a marker that cannot be placed.
    """
    found, problems = change_markers.parse(text)
    if problems:
        raise RuntimeError(
            "Change markers cannot be placed:\n  "
            + "\n  ".join(f"{relative}:{line}: {problem}" for line, problem in problems)
        )
    if not found:
        return text
    by_start = {marker.line - 1: marker for marker in found}
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    while index < len(lines):
        marker = by_start.get(index)
        if marker is None:
            output.append(lines[index])
            index += 1
            continue
        marker.source = relative
        output.append(f'\n<div class="{CHANGE_SLOT_CLASS}" data-change="{len(markers)}"></div>\n\n')
        markers.append(marker)
        index = marker.end_line
    return "".join(output)


def prepared_markdown(
    root: Path, paths: list[Path], repository: str | None, ref: str,
    markers: list | None = None,
) -> str:
    """Give each included file a stable section ID and make its links work.

    Each change marker becomes a placeholder and is added to markers.
    """
    anchors = {path.resolve(): section_id(path) for path in paths}
    markers = [] if markers is None else markers
    parts = []
    for path in paths:
        text = path.read_text(encoding="utf-8").strip()
        relative = Path(os.path.relpath(path, root)).as_posix()
        text = replace_change_markers(text, relative, markers)
        text = plain_mermaid_fences(replace_anchors(text))
        # A marker on a row-anchored table follows the row-anchors line; put
        # its placeholder first so the line still comes just before the table.
        text = ROW_DIRECTIVE_THEN_SLOTS.sub(r"\2\1", text)
        text = HEADING_PATTERN.sub(
            lambda match: f"# {match.group(1)} {{#{anchors[path.resolve()]}}}",
            text,
            count=1,
        )

        def relink(match: re.Match[str], source: Path = path) -> str:
            target = match.group(2)
            if re.match(r"^[a-z]+:", target) or target.startswith(("#", "/")):
                return match.group(0)
            relative, _, fragment = target.partition("#")
            resolved = (source.parent / relative).resolve()
            if resolved in anchors:
                moved = "#" + (fragment or anchors[resolved])
            elif resolved.suffix.lower() in IMAGE_TYPES and resolved.is_file():
                # Embed images so the guide stays one self-contained file and
                # shows them even when the repository is private.
                data = base64.b64encode(resolved.read_bytes()).decode("ascii")
                moved = f"data:{IMAGE_TYPES[resolved.suffix.lower()]};base64,{data}"
            elif repository:
                relative_to_root = Path(os.path.relpath(resolved, root)).as_posix()
                moved = f"{repository.rstrip('/')}/blob/{ref}/{relative_to_root}"
                if fragment:
                    moved += "#" + fragment
            else:
                return match.group(0)
            return match.group(1) + moved + match.group(3)

        parts.append(LINK_TARGET_PATTERN.sub(relink, text))
    return "\n\n".join(parts) + "\n"


def body_html(markdown: str) -> str:
    result = subprocess.run(
        pandoc_command()
        + [
            "--from=markdown",
            "--to=html5",
            "--section-divs",
            "--shift-heading-level-by=1",
            "--wrap=none",
        ],
        input=markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    # Pandoc writes <table style="width:100%;"> when a table's column widths
    # fill the line, so keep any attributes it adds.
    body = TABLE_OPEN_PATTERN.sub(
        r'<div class="aira-table-wrap"><table class="aira-table"\1>', result.stdout
    ).replace("</table>", "</table></div>")
    # Mermaid reads a diagram's text from its element, so drop pandoc's <code>.
    # Until the diagram is drawn, or if scripts are off, the text is shown.
    body = MERMAID_BLOCK_PATTERN.sub(
        r'<div class="guide-diagram"><pre class="mermaid">\1</pre></div>', body
    )
    return annotate_commentable_blocks(front_layout(apply_row_anchors(body)))


def apply_row_anchors(body: str) -> str:
    """Give each body row of a table marked with row-anchors its own anchor.

    The row's ID comes from its first cell, so "OQ-13" becomes "oq-13". Each
    such row is a review area of its own, and the table as a whole is not a
    comment block.
    """

    def anchor_row(match: re.Match[str]) -> str:
        attributes, cells = match.group(1), match.group(2)
        cell = FIRST_CELL_PATTERN.search(cells)
        name = row_anchor_name(html.unescape(cell.group(1))) if cell else ""
        problem = anchor_name_problem(name)
        if problem:
            raise RuntimeError(
                f"Row anchor {name!r} from the first cell {problem}. Row anchors "
                "are named from the first cell of each row, such as 'OQ-13'."
            )
        attributes = CLASS_PATTERN.sub("", attributes).strip()
        attributes = (" " + attributes) if attributes else ""
        return (
            f'<tr id="{name}" class="guide-row-block" data-guide-anchor="{name}"'
            f"{attributes}>{cells}</tr>"
        )

    def anchor_table(match: re.Match[str]) -> str:
        table = match.group(1)
        if table is None:
            raise RuntimeError(
                "A '<!-- row-anchors -->' line must come just before a table."
            )
        table = BODY_PATTERN.sub(
            lambda body_match: body_match.group(1)
            + ROW_PATTERN.sub(anchor_row, body_match.group(2))
            + body_match.group(3),
            table,
        )
        return f'<div class="aira-table-wrap guide-row-table">{table}</div>'

    return ROW_TABLE_PATTERN.sub(anchor_table, body)


TOKEN_PATTERN = re.compile(r"<[^>]+>|[^<]+")
TAG_NAME_PATTERN = re.compile(r"</?\s*([a-zA-Z0-9]+)")
ID_PATTERN = re.compile(r'\bid="([^"]+)"')
CLASS_PATTERN = re.compile(r'\bclass="([^"]*)"')
COMMENTABLE_TAGS = {"p", "ul", "ol", "blockquote"}


def annotate_commentable_blocks(body: str) -> str:
    """Mark outermost commentable blocks with their anchor area and position."""
    area = DOCUMENT_START_ANCHOR
    area_before_rows: str | None = None
    positions: dict[str, int] = {}
    open_commentable: list[str] = []
    output: list[str] = []

    for token in TOKEN_PATTERN.findall(body):
        tag_match = TAG_NAME_PATTERN.match(token)
        if not tag_match or token.startswith(("<!--", "<!DOCTYPE")):
            output.append(token)
            continue

        tag = tag_match.group(1).lower()
        closing = token.startswith("</")
        self_closing = token.rstrip().endswith("/>")
        classes_match = CLASS_PATTERN.search(token)
        classes = set(classes_match.group(1).split()) if classes_match else set()

        if closing:
            output.append(token)
            if open_commentable and open_commentable[-1] == tag:
                open_commentable.pop()
            if tag == "table" and area_before_rows is not None:
                area = area_before_rows
                area_before_rows = None
            continue

        if CHANGE_SLOT_CLASS in classes:
            # A change marker's placeholder records the area it is in.
            output.append(token[:-1] + f' data-anchor="{html.escape(area, quote=True)}">')
            continue

        identifier = ID_PATTERN.search(token)
        if tag == "section" and identifier:
            area = html.unescape(identifier.group(1))
        elif "guide-anchor" in classes and identifier:
            area = html.unescape(identifier.group(1))
        elif "guide-row-table" in classes:
            # Rows name their own areas; text after the table returns to the
            # area the table is in.
            area_before_rows = area
        elif "guide-row-block" in classes and identifier:
            area = html.unescape(identifier.group(1))

        commentable = (
            tag in COMMENTABLE_TAGS
            or "guide-row-block" in classes
            or (
                bool({"aira-table-wrap", "guide-diagram"} & classes)
                and "guide-row-table" not in classes
            )
        )
        if commentable:
            if not open_commentable:
                position = positions.get(area, 0)
                positions[area] = position + 1
                insertion = (
                    f' data-anchor="{html.escape(area, quote=True)}"'
                    f' data-block-index="{position}"'
                )
                token = token[:-1] + insertion + ">"
            if not self_closing:
                open_commentable.append(tag)

        output.append(token)

    return "".join(output)


SECTION_OPEN_PATTERN = re.compile(r'<section id="([^"]+)" class="(level\d)[^"]*"[^>]*>\s*<h\d[^>]*>(.*?)</h\d>', re.DOTALL)
BLOCK_ATTRIBUTES_PATTERN = re.compile(r'data-anchor="([^"]*)" data-block-index="(\d+)"')


def resolve_change_markers(body: str, markers: list) -> tuple[str, list[dict]]:
    """Find what each change marker covers in the built HTML, and remove the placeholders.

    Returns the body and one entry per covered area, in document order:
    {"anchor", "blockIndex"?, "version", "level", "note", "section", "marker"}.
    A marker before a heading covers that section; before a row-anchored
    table, the rows it names; before a commentable block, that block; before
    anything else (a code block or an image), the review area it is in.
    """
    entries: list[dict] = []
    tokens = list(re.finditer(r"<[^>]+>|[^<]+", body))
    stack: list[tuple[str, str]] = []  # open sections: (id, heading text)
    headings = {match.start(): (match.group(1), html.unescape(TAG_PATTERN.sub("", match.group(3))).strip())
                for match in SECTION_OPEN_PATTERN.finditer(body)}
    for position, token_match in enumerate(tokens):
        token = token_match.group(0)
        if token.startswith("<section"):
            stack.append(headings.get(token_match.start(), ("", "")))
            continue
        if token.startswith("</section"):
            if stack:
                stack.pop()
            continue
        slot = CHANGE_SLOT_PATTERN.match(token + "</div>") if CHANGE_SLOT_CLASS in token and token.startswith("<div") else None
        if not slot:
            continue
        marker = markers[int(slot.group(1))]
        area = html.unescape(slot.group(2) or DOCUMENT_START_ANCHOR)
        where = f"{getattr(marker, 'source', 'content')}:{marker.line}"
        # The next element that is not a closing tag, a placeholder, or an anchor.
        following = None
        for later in tokens[position + 1:]:
            text = later.group(0)
            if not text.startswith("<") or text.startswith("</") or text.startswith("<!--"):
                continue
            if CHANGE_SLOT_CLASS in text or 'class="guide-anchor"' in text:
                continue
            following = later
            break
        if following is None:
            raise RuntimeError(f"{where}: the change marker is followed by nothing it can cover.")
        tag = following.group(0)
        base = {"version": marker.version, "level": marker.level, "note": marker.note, "marker": marker}
        section_match = re.match(r'<section id="([^"]+)"', tag)
        if section_match:
            if marker.covers != "heading":
                raise RuntimeError(f"{where}: the change marker covers a block, but a heading follows it.")
            anchor = html.unescape(section_match.group(1))
            title = headings.get(following.start(), (anchor, anchor))[1]
            entries.append(dict(base, anchor=anchor, section=title))
            continue
        section = stack[-1][1] if stack else ""
        if marker.covers == "row-table":
            if "guide-row-table" not in tag:
                raise RuntimeError(f"{where}: rows= needs the row-anchored table to follow the marker.")
            end = body.find("</table>", following.start())
            table = body[following.start():end]
            for name, label in zip(marker.rows, marker.row_labels):
                if f'<tr id="{name}"' not in table:
                    raise RuntimeError(f"{where}: rows= names {label}, not a row of the table that follows.")
                entries.append(dict(base, anchor=name, section=section))
            continue
        block = BLOCK_ATTRIBUTES_PATTERN.search(tag)
        if block:
            entries.append(dict(base, anchor=html.unescape(block.group(1)),
                                blockIndex=int(block.group(2)), section=section))
        else:
            entries.append(dict(base, anchor=area, section=section))
    return CHANGE_SLOT_PATTERN.sub("", body), entries


def change_marker_script(entries: list[dict]) -> str:
    """The guide-change-markers element guide.js draws (README, "Change markers")."""
    if not entries:
        return ""
    data = [
        {key: entry[key] for key in ("anchor", "blockIndex", "version", "level", "note") if key in entry}
        for entry in entries
    ]
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="guide-change-markers">{text}</script>\n'


WHAT_CHANGED_ID = "guide-what-changed"


def what_changed_html(entries: list[dict]) -> str:
    """The front section's "What changed" list: feedback wanted first, each linking to its spot."""
    if not entries:
        return ""
    versions = sorted({entry["version"] for entry in entries}, key=change_markers.version_key)
    title = f"What changed in {versions[0]}" if len(versions) == 1 else "What changed"
    ordered = ([entry for entry in entries if entry["level"] == "feedback"]
               + [entry for entry in entries if entry["level"] != "feedback"])
    items = []
    for entry in ordered:
        feedback = entry["level"] == "feedback"
        level = ('<span class="guide-what-changed__level guide-what-changed__level--feedback">Feedback wanted</span>'
                 if feedback else '<span class="guide-what-changed__level">Changed</span>')
        where = html.escape(entry["section"] or entry["anchor"])
        items.append(
            f'<li class="guide-what-changed__item">{level} '
            f'<a href="#{html.escape(entry["anchor"], quote=True)}">{where}</a>: '
            f'{html.escape(entry["note"])}</li>'
        )
    return (
        f'<section id="{WHAT_CHANGED_ID}" class="level2 guide-front guide-what-changed">\n'
        f"<h2>{html.escape(title)}</h2>\n"
        '<p class="aira-meta">These changes are also marked in the text. '
        '<a href="?lens=changes">Show them in the text</a>.</p>\n'
        f'<ul class="guide-what-changed__list">\n' + "\n".join(items) + "\n</ul>\n</section>\n"
    )


def section_bounds(body: str, identifier: str) -> tuple[int, int] | None:
    """Where the section with this ID starts and ends in the body, by balanced tags."""
    start = body.find(f'<section id="{identifier}"')
    if start < 0:
        return None
    depth = 0
    for match in re.finditer(r"<section\b|</section>", body[start:]):
        depth += 1 if match.group(0) == "<section" else -1
        if depth == 0:
            return start, start + match.end()
    return start, len(body)


def balanced_div(body: str, start: int) -> int:
    """The end of the div that opens at start."""
    depth = 0
    for match in re.finditer(r"<div\b|</div>", body[start:]):
        depth += 1 if match.group(0) == "<div" else -1
        if depth == 0:
            return start + match.end()
    return len(body)


SCOPE_CARDS = {
    "in scope": ("in", "circle-check"),
    "out of scope": ("out", "circle-x"),
    "not yet decided": ("undecided", "circle-help"),
}
ICON_DIR = Path(__file__).resolve().parent.parent / "templates" / "infographic" / "icons"


def scope_icon(name: str) -> str:
    svg = (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8").strip()
    return svg.replace("<svg ", '<svg class="guide-scope-icon" aria-hidden="true" focusable="false" ', 1)


def front_layout(body: str) -> str:
    """Lay out the front section: the status banner above the Executive Summary,
    and the Scope's lists as cards. Both sections are marked as front matter."""
    for identifier in front_section.FRONT_IDS:
        body = re.sub(
            rf'<section id="{identifier}" class="(level2[^"]*)"',
            rf'<section id="{identifier}" class="\1 guide-front"',
            body, count=1,
        )
    summary = section_bounds(body, front_section.SUMMARY_ID)
    if summary:
        notice = body.find('<div class="status-notice">', summary[0], summary[1])
        if notice >= 0:
            end = balanced_div(body, notice)
            banner = body[notice:end].replace(
                '<div class="status-notice">', '<div class="status-notice guide-status-banner" role="note">', 1)
            body = body[:notice] + body[end:]
            body = body[:summary[0]] + banner + "\n" + body[summary[0]:]
    scope = section_bounds(body, front_section.SCOPE_ID)
    if scope:
        part = body[scope[0]:scope[1]]

        def card(match: re.Match[str]) -> str:
            name = html.unescape(TAG_PATTERN.sub("", match.group(4))).strip().lower()
            if name not in SCOPE_CARDS:
                return match.group(0)
            kind, icon = SCOPE_CARDS[name]
            return (f'<section id="{match.group(1)}" class="{match.group(2)} guide-scope-card '
                    f'guide-scope-card--{kind}"{match.group(3)}>'
                    f"<h3>{scope_icon(icon)}{match.group(4)}</h3>")

        part = re.sub(
            r'<section id="([^"]+)" class="(level3[^"]*)"([^>]*)>\s*<h3[^>]*>(.*?)</h3>',
            card, part, flags=re.DOTALL)
        body = body[:scope[0]] + part + body[scope[1]:]
    return body


def place_front(body: str, what_changed: str, figure: str) -> str:
    """Put the What changed list and the infographic after the Executive Summary,
    or at the top when there is none."""
    addition = what_changed + figure
    if not addition:
        return body
    summary = section_bounds(body, front_section.SUMMARY_ID)
    position = summary[1] if summary else 0
    return body[:position] + "\n" + addition + body[position:]


def front_list(body: str) -> list[dict]:
    """The front sections the right rail lists while the reader is in one."""
    labels = {front_section.SUMMARY_ID: "Executive Summary", WHAT_CHANGED_ID: "What changed",
              front_section.SCOPE_ID: "Scope"}
    found = [(body.find(f'<section id="{identifier}"'), identifier) for identifier in labels]
    return [{"id": identifier, "label": labels[identifier]} for position, identifier in sorted(found) if position >= 0]


def guide_sections(body: str, labels: dict[str, str]) -> list[dict]:
    """The top-level sections in reading order, with their header label.

    An appendix is a top-level section whose heading begins "Appendix". The
    skeleton writes them that way, such as "Appendix: Working Decisions and
    Open Questions". The front section is not listed: it has no section-bar
    entry and is not counted as a chapter.
    """
    sections = []
    for identifier, heading in SECTION_PATTERN.findall(body):
        # The front section (Executive Summary, What changed, Scope) is not a chapter.
        if identifier in front_section.FRONT_IDS or identifier == WHAT_CHANGED_ID:
            continue
        text = html.unescape(TAG_PATTERN.sub("", heading)).strip()
        sections.append({
            "id": identifier,
            "label": labels.get(identifier) or text,
            "appendix": bool(APPENDIX_PATTERN.match(text)),
        })
    return sections


def appendices_out_of_place(sections: list[dict]) -> list[str]:
    """Body chapters that come after an appendix. Appendices belong at the end."""
    misplaced = []
    seen_appendix = False
    for section in sections:
        if section["appendix"]:
            seen_appendix = True
        elif seen_appendix:
            misplaced.append(section["label"])
    return misplaced


def section_nav(sections: list[dict]) -> str:
    """Header links: one per body chapter, then one for all the appendices.

    The header row has room for few links, so with two or more appendices it
    shows a single "Appendices" link to the first one; the right rail lists
    them all while the reader is in one. A single appendix keeps its own label.
    """
    links = []
    appendices = [section for section in sections if section["appendix"]]
    for section in sections:
        if section["appendix"]:
            continue
        links.append(
            f'<a href="#{html.escape(section["id"])}">{html.escape(section["label"])}</a>'
        )
    if len(appendices) == 1:
        appendix = appendices[0]
        links.append(
            f'<a href="#{html.escape(appendix["id"])}">{html.escape(appendix["label"])}</a>'
        )
    elif appendices:
        ids = " ".join(appendix["id"] for appendix in appendices)
        links.append(
            f'<a href="#{html.escape(appendices[0]["id"])}" '
            f'data-guide-sections="{html.escape(ids)}">Appendices</a>'
        )
    return "\n        ".join(links)


def coded_warning(code: str, message: str, file: str | None = None) -> dict:
    """A build warning as the manifest records it, with its stable code."""
    if len(message) > MANIFEST_MESSAGE_LIMIT:
        message = message[: MANIFEST_MESSAGE_LIMIT - 3].rstrip() + "..."
    result = {"code": code, "message": message}
    if file:
        result["file"] = file
    return result


def section_warnings(sections: list[dict], assembly: str | None = None) -> list[dict]:
    """Coded warnings on the number of chapters and where the appendices are."""
    warnings = []
    chapters = sum(1 for section in sections if not section["appendix"])
    if chapters > SUGGESTED_MAX_CHAPTERS:
        warnings.append(coded_warning(
            "CHAPTER_COUNT",
            f"the guide has {chapters} chapters, not counting appendices; the suggested "
            f"range is six to {SUGGESTED_MAX_CHAPTERS}. Consider merging chapters. "
            "See guidance/Conventions.md, 'Keep chapters few'.",
            assembly,
        ))
    misplaced = appendices_out_of_place(sections)
    if misplaced:
        warnings.append(coded_warning(
            "APPENDIX_ORDER",
            f"{', '.join(misplaced)} comes after an appendix. Put appendices after all "
            "chapters. See guidance/Conventions.md, 'Keep chapters few'.",
            assembly,
        ))
    return warnings


def chapter_warnings(sections: list[dict]) -> list[str]:
    """Warnings on the number of chapters and where the appendices are."""
    return [warning["message"] for warning in section_warnings(sections)]


def appendix_list(sections: list[dict]) -> list[dict]:
    """The appendices the right rail lists, when there are two or more."""
    appendices = [
        {"id": section["id"], "label": section["label"]}
        for section in sections
        if section["appendix"]
    ]
    return appendices if len(appendices) > 1 else []


def logo_data_uri() -> str:
    data = (TEMPLATE_DIR / "AIRA_2018Logo_BlueGreen_Hor.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def diagram_scripts(body: str) -> str:
    """Inline the vendored Mermaid library when the body has diagrams.

    The guide stays one file that works offline and in a private project. The
    comments script waits for the diagrams, because a comment records the text
    of its block and a diagram's text changes when it is drawn.
    """
    if 'class="mermaid"' not in body:
        return ""
    library = MERMAID_SCRIPT.read_text(encoding="utf-8")
    if "</script" in library.lower():
        raise RuntimeError(f"{MERMAID_SCRIPT} cannot be inlined: it contains '</script'.")
    return f"""<script>
{library}
</script>
<script>
mermaid.initialize({{ startOnLoad: false }});
window.guideDiagramsReady = mermaid
  .run({{ querySelector: ".guide-diagram pre.mermaid" }})
  .catch(function (error) {{ console.error("Diagrams could not be drawn.", error); }});
</script>
"""


def document_id(config: dict, title: str) -> str:
    return config.get("id") or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def git_output(root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def source_state(root: Path, kept_in: str) -> dict:
    """The project's commit and whether its files differ from it.

    Empty for a project kept in a workspace or outside any Git repository.
    """
    if kept_in == "workspace" or git_output(root, "rev-parse", "--show-toplevel") is None:
        return {}
    commit = (git_output(root, "rev-parse", "--short", "HEAD") or "").strip()
    status = git_output(root, "status", "--porcelain", "--", ".")
    if not commit or status is None:
        return {}
    return {"sourceCommit": commit, "sourceDirty": bool(status.strip())}


def pandoc_version() -> str | None:
    try:
        result = subprocess.run(
            pandoc_command() + ["--version"], capture_output=True, text=True, check=True
        )
    except (OSError, RuntimeError, subprocess.CalledProcessError):
        return None
    words = result.stdout.split()
    return words[1] if len(words) > 1 else None


def visibility(config: dict, hosting: str) -> str | None:
    """Who may read the guide, when the settings say so.

    An explicit "visibility" wins. GitHub Pages is public and InteropHub
    hosting is access-controlled; a local guide's settings do not say.
    """
    if config.get("visibility") in {"public", "private"}:
        return config["visibility"]
    return {"github-pages": "public", "interophub": "private"}.get(hosting)


def check_warnings(report) -> list[dict]:
    """Coded warnings from check_content.py's findings.

    CONFIRM notes are hidden comments for authors, so only their places are
    recorded, never their text.
    """
    warnings = []
    lines_by_file: dict[str, list[int]] = {}
    for relative, line, _ in report.confirms:
        lines_by_file.setdefault(relative, []).append(line)
    for relative, lines in lines_by_file.items():
        noun = "note" if len(lines) == 1 else "notes"
        where = "line" if len(lines) == 1 else "lines"
        warnings.append(coded_warning(
            "CONFIRM_OPEN",
            f"{len(lines)} CONFIRM {noun} awaiting resolution, at {where} "
            f"{', '.join(str(line) for line in lines)}.",
            relative,
        ))
    for message in report.infographic_warnings:
        warnings.append(coded_warning("INFOGRAPHIC_WARNING", message, infographic.SPEC_PATH))
    for warning in getattr(report, "coded_warnings", []):
        warnings.append(coded_warning(warning["code"], warning["message"], warning.get("file")))
    return warnings


def build_manifest(
    root: Path,
    config: dict,
    title: str,
    version: str,
    sections: list[dict],
    has_infographic: bool,
    assembly: str | None = None,
    front: front_section.FrontReport | None = None,
    markers: list[dict] | None = None,
) -> dict:
    """The guide's build manifest, schema 1. See the module docstring.

    markers are the change markers shown in this build (resolve_change_markers);
    a marker on several table rows counts once.
    """
    import check_content  # noqa: PLC0415 - check_content imports this module

    kept_in = kept_in_config(config)
    hosting = hosting_config(config)
    document = {"id": document_id(config, title), "title": title}
    if config.get("documentType"):
        document["documentType"] = config["documentType"]
    document["status"] = config.get("status", "Draft")
    document["version"] = version
    document["keptIn"] = kept_in
    seen_by = visibility(config, hosting)
    if seen_by:
        document["visibility"] = seen_by
    document["hosting"] = hosting
    if config.get("interophubTopic"):
        document["interophubTopic"] = config["interophubTopic"]

    build = {"builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    build.update(source_state(root, kept_in))
    build["python"] = platform.python_version()
    pandoc = pandoc_version()
    if pandoc:
        build["pandoc"] = pandoc

    report = check_content.run_checks(root, version=version)
    checks: dict = {"confirmOpen": len(report.confirms)}
    if report.open_ideas is not None:
        checks["openIdeas"] = report.open_ideas
    warnings = section_warnings(sections, assembly) + check_warnings(report)
    checks["warnings"] = warnings[:MANIFEST_WARNING_LIMIT]

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generator": MANIFEST_GENERATOR,
        "processVersion": process_release.read_version(),
    }
    commit = process_release.process_commit()
    if commit:
        manifest["processCommit"] = commit
    manifest.update({
        "processReleases": process_release.read_registry(),
        "document": document,
        "build": build,
        "structure": structure(sections, has_infographic, front or report.front, markers or []),
        "checks": checks,
    })
    return manifest


def structure(sections: list[dict], has_infographic: bool,
              front: front_section.FrontReport | None, markers: list[dict]) -> dict:
    """The manifest's structure: chapters, the front section, and change markers."""
    result = {
        "chapters": sum(1 for section in sections if not section["appendix"]),
        "appendices": sum(1 for section in sections if section["appendix"]),
        "hasInfographic": has_infographic,
    }
    if front is not None:
        result["hasExecutiveSummary"] = front.has_summary
        if front.summary_words is not None:
            result["executiveSummaryWords"] = front.summary_words
        result["hasScope"] = front.has_scope
    distinct = {id(entry["marker"]): entry["marker"] for entry in markers}.values()
    result["changeMarkers"] = len(distinct)
    result["feedbackMarkers"] = sum(1 for marker in distinct if marker.feedback)
    return result


def manifest_script(manifest: dict) -> str:
    """The manifest as a JSON script element that cannot end early."""
    text = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    if len(text.encode("utf-8")) > MANIFEST_MAX_BYTES:
        raise RuntimeError("The guide's build manifest is larger than 64 KB.")
    return f'<script type="application/json" id="{MANIFEST_ID}">{text}</script>\n'


def page(
    title: str,
    subtitle: str | None,
    config: dict,
    version: str,
    nav: str,
    body: str,
    figure: str = "",
    appendices: list[dict] | None = None,
    manifest: dict | None = None,
    front: list[dict] | None = None,
    change_markers_script: str = "",
) -> str:
    status = config.get("status", "Draft")
    status_class = STATUS_TAGS.get(status.lower(), "aira-tag--info")
    topic = config.get("interophubTopic")
    topic_url = INTEROPHUB_TOPIC_URL.format(topic=topic) if topic else None
    repository = config.get("repository")
    doc_id = document_id(config, title)
    guide_data = {
        "id": doc_id,
        "title": title,
        "version": version,
        "built": date.today().isoformat(),
    }
    if appendices:
        guide_data["appendices"] = appendices
    if front:
        guide_data["front"] = front
    hosting_config(config)
    normalized_comments = comments_config(config)
    if normalized_comments is not None:
        guide_data["comments"] = normalized_comments

    return_link = (
        f'<a class="aira-button aira-button--tertiary aira-button--small" '
        f'href="{html.escape(topic_url)}">Return to InteropHub</a>'
        if topic_url
        else ""
    )
    rail_links = []
    if topic_url:
        rail_links.append(
            f'<li><a href="{html.escape(topic_url)}">InteropHub topic {html.escape(str(topic))}</a></li>'
        )
    if repository:
        rail_links.append(
            f'<li><a href="{html.escape(repository)}">Source on GitHub</a></li>'
        )
        rail_links.append(
            f'<li><a href="{html.escape(repository)}/releases">Releases and downloads</a></li>'
        )
    workspace = is_workspace(config)
    location = config.get("location") if workspace or infographic.kept_in_workspace(config) else None
    if location:
        rail_links.append(f'<li class="aira-meta">Kept in {html.escape(str(location))}</li>')
    version_label = f"Workspace build {guide_data['built']}" if workspace else f"Version {version}"
    license_note = config.get("license", "")
    subtitle_html = (
        f'<p class="aira-topic-summary">{html.escape(subtitle)}</p>' if subtitle else ""
    )
    document_type = config.get("documentType")
    if workspace and document_type == "Topic Reference":
        document_type = "Workspace Topic Reference"
    document_type_html = (
        f'<p class="aira-meta guide-document-type">{html.escape(document_type)}</p>'
        if document_type
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}{" - " + html.escape(document_type) if document_type else ""}</title>
<style>
{(TEMPLATE_DIR / "aira.css").read_text(encoding="utf-8")}
{(TEMPLATE_DIR / "guide.css").read_text(encoding="utf-8")}
</style>
{manifest_script(manifest) if manifest else ""}</head>
<body>
<div class="aira-app">
  <a class="aira-skip-link" href="#guide-main">Skip to main content</a>
  <header class="aira-global-header">
    <div class="aira-identity">
      <a class="aira-identity-link" href="https://www.immregistries.org/">
        <img class="aira-logo" src="{logo_data_uri()}" alt="American Immunization Registry Association">
      </a>
    </div>
    <nav class="aira-global-actions" aria-label="Global actions">
      {return_link}
    </nav>
  </header>
  <div class="aira-context-header guide-context">
    <div class="aira-context-inner">
      <nav class="aira-context-nav" aria-label="Sections">
        {nav}
      </nav>
      <div class="guide-lens-strip" role="group" aria-label="Annotations">
        <button type="button" class="guide-lens-button" data-guide-lens="comments" aria-controls="guide-annotations" aria-expanded="false"><span class="guide-lens-icon" aria-hidden="true">&#x1F4AC;</span><span class="guide-lens-label">Comments</span> <span class="guide-lens-count" data-guide-count="comments">0</span></button>
        <span class="guide-lens-separator" aria-hidden="true">&middot;</span>
        <button type="button" class="guide-lens-button" data-guide-lens="review" aria-controls="guide-annotations" aria-expanded="false"><span class="guide-lens-icon" aria-hidden="true">&#x2691;</span><span class="guide-lens-label">Review</span> <span class="guide-lens-count" data-guide-count="review">0</span></button>
        <span class="guide-lens-separator" aria-hidden="true">&middot;</span>
        <button type="button" class="guide-lens-button" data-guide-lens="changes" aria-controls="guide-annotations" aria-expanded="false"><span class="guide-lens-icon" aria-hidden="true">&#x394;</span><span class="guide-lens-label">Changes</span> <span class="guide-lens-count" data-guide-count="changes">0</span></button>
      </div>
    </div>
  </div>
  <section class="guide-annotations" id="guide-annotations" role="region" aria-labelledby="guide-annotations-title" hidden>
    <div class="guide-annotations__resize" id="guide-annotations-resize" role="separator" aria-orientation="vertical" aria-controls="guide-annotations" aria-label="Resize the annotations panel" title="Drag to resize. Double-click to reset." tabindex="0"></div>
    <div class="guide-annotations__header">
      <h2 class="guide-annotations__title" id="guide-annotations-title">Annotations</h2>
      <button type="button" class="guide-annotations__close" id="guide-annotations-close" aria-label="Close the annotations panel">&times;</button>
    </div>
    <div class="guide-annotations__tabs" role="tablist" aria-label="Annotation types">
      <button type="button" role="tab" id="guide-tab-comments" data-guide-tab="comments" aria-controls="guide-tabpanel-comments" aria-selected="true">Comments <span class="guide-tab-count" data-guide-count="comments">0</span></button>
      <button type="button" role="tab" id="guide-tab-review" data-guide-tab="review" aria-controls="guide-tabpanel-review" aria-selected="false" tabindex="-1">Review <span class="guide-tab-count" data-guide-count="review">0</span></button>
      <button type="button" role="tab" id="guide-tab-changes" data-guide-tab="changes" aria-controls="guide-tabpanel-changes" aria-selected="false" tabindex="-1">Changes <span class="guide-tab-count" data-guide-count="changes">0</span></button>
    </div>
    <div class="guide-annotations__body" id="guide-annotations-body">
      <div class="guide-tabpanel" role="tabpanel" id="guide-tabpanel-comments" aria-labelledby="guide-tab-comments">
        <div id="guide-comments-status"><p class="aira-meta">Comments are saved only in this browser. Download them to share.</p></div>
        <div id="guide-local-identity" class="guide-local-control"><label class="aira-label" for="guide-commenter">Your name</label>
        <input class="aira-input" id="guide-commenter" type="text" autocomplete="name"></div>
        <div class="guide-comment-actions guide-local-control">
          <button type="button" class="aira-button aira-button--secondary aira-button--small" id="guide-comments-download">Download</button>
          <label class="aira-button aira-button--secondary aira-button--small guide-file-button">Load<input type="file" id="guide-comments-load" accept="application/json,.json" multiple hidden></label>
          <button type="button" class="aira-button aira-button--ghost aira-button--small" id="guide-comments-clear">Clear all</button>
        </div>
        <p class="guide-label-note" id="guide-label-note" role="status" hidden></p>
        <div class="guide-filters" role="group" aria-label="Filter comments">
          <span class="guide-filter-segment" data-guide-filter="comments-state">
            <button type="button" data-value="open" aria-pressed="true">Open</button><button type="button" data-value="all" aria-pressed="false">All</button>
          </span>
          <button type="button" class="guide-filter-toggle" data-guide-filter="mine" aria-pressed="false">Mine</button>
        </div>
        <div class="guide-annotation-list" id="guide-list-comments"></div>
      </div>
      <div class="guide-tabpanel" role="tabpanel" id="guide-tabpanel-review" aria-labelledby="guide-tab-review" hidden>
        <div class="guide-filters" role="group" aria-label="Filter review flags">
          <span class="guide-filter-segment" data-guide-filter="review-state">
            <button type="button" data-value="open" aria-pressed="true">Open</button><button type="button" data-value="all" aria-pressed="false">All</button>
          </span>
        </div>
        <div class="guide-annotation-list" id="guide-list-review"></div>
      </div>
      <div class="guide-tabpanel" role="tabpanel" id="guide-tabpanel-changes" aria-labelledby="guide-tab-changes" hidden>
        <div class="guide-annotation-list" id="guide-list-changes"></div>
      </div>
    </div>
  </section>
  <main class="aira-main" id="guide-main">
    <div class="guide-page aira-container--wide">
      <header class="aira-topic-header guide-header">
        <div class="aira-topic-header__top">
          <div>
            {document_type_html}
            <h1 class="aira-topic-title"><a class="guide-title-link" href="#{DOCUMENT_START_ANCHOR}">{html.escape(title)}</a></h1>
            {subtitle_html}
          </div>
          <div class="aira-topic-actions guide-status">
            <span class="aira-tag {status_class} guide-status-tag">{html.escape(status.upper())}</span>
            <span class="aira-meta">{html.escape(version_label)}</span>
          </div>
        </div>
      </header>
      <div class="aira-right-rail-layout guide-layout">
        <article class="aira-prose guide-content" id="guide-content">
<div id="{DOCUMENT_START_ANCHOR}" class="guide-anchor" data-guide-anchor="{DOCUMENT_START_ANCHOR}"></div>
{figure}{body}
        </article>
        <aside class="aira-right-rail guide-rail" aria-label="On this page">
          <section class="aira-sidebar-section">
            <h2 class="aira-sidebar-title" id="guide-rail-title">On this page</h2>
            <ul class="guide-subnav" id="guide-subnav"></ul>
          </section>
          <section class="aira-sidebar-section">
            <ul class="guide-links">
              {"".join(rail_links)}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  </main>
  <footer class="aira-footer" aria-label="Document information">
    <p><a href="https://www.immregistries.org/">American Immunization Registry Association (AIRA)</a> supports collaboration, standards, and shared solutions that strengthen immunization information systems and improve the use of vaccination data to protect public health.</p>
    <p>{html.escape(title)} &middot; {html.escape(version_label[0].lower() + version_label[1:])} &middot; generated {guide_data["built"]}{" &middot; " + html.escape(license_note) if license_note else ""}</p>
  </footer>
</div>
{change_markers_script}<script type="application/json" id="guide-data">{json.dumps(guide_data)}</script>
{diagram_scripts(body)}<script>
{(TEMPLATE_DIR / "guide.js").read_text(encoding="utf-8")}
</script>
</body>
</html>
"""


def duplicate_ids(document: str) -> list[str]:
    # Text inside scripts, such as the inlined diagram library, is not markup.
    markup = re.sub(r"(<script\b[^>]*>).*?(</script>)", r"\1\2", document, flags=re.DOTALL)
    counts: dict[str, int] = {}
    for identifier in re.findall(r'\bid="([^"]+)"', markup):
        identifier = html.unescape(identifier)
        counts[identifier] = counts.get(identifier, 0) + 1
    return sorted(identifier for identifier, count in counts.items() if count > 1)


def main() -> int:
    # Labels may hold characters the console encoding lacks; never fail on printing them.
    sys.stdout.reconfigure(errors="backslashreplace")
    args = arguments()
    root = Path(args.root).resolve()
    assembly = root / args.assembly
    config = json.loads((root / args.config).read_text(encoding="utf-8-sig"))

    text = assembly.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(text)
    front_matter = match.group(1) if match else ""
    title = front_matter_value(front_matter, "title")
    if not title:
        raise RuntimeError(f"No title in the front matter of {assembly}")
    subtitle = config.get("subtitle") or front_matter_value(front_matter, "subtitle")

    kept_in_config(config)
    if args.version:
        version = args.version
    elif is_workspace(config):
        version = f"workspace-{date.today().isoformat()}"
    elif infographic.kept_in_workspace(config):
        version = config["version"]
    else:
        version = git_version(root)
    ref = args.ref or (version if re.match(r"^v\d", version) else "main")
    paths = include_paths(root, assembly)
    front = front_section.check(root, config.get("documentType") == "Topic Reference")
    if front.errors:
        raise RuntimeError(
            "The front section has problems:" + "".join("\n  " + finding.text() for finding in front.errors)
        )
    for finding in front.warnings:
        print(f"Warning: {finding.text()}")
    markers: list = []
    markdown = prepared_markdown(root, paths, config.get("repository"), ref, markers)
    body = body_html(markdown)
    body, entries = resolve_change_markers(body, markers)
    current = change_markers.current_version(root, version, config)
    shown = [entry for entry in entries if change_markers.is_shown(entry["marker"], current)]
    sections = guide_sections(body, config.get("navLabels", {}))
    nav = section_nav(sections)
    assembly_name: str | None = Path(os.path.relpath(assembly, root)).as_posix()
    if assembly_name.startswith("../"):
        assembly_name = None
    for warning in section_warnings(sections, assembly_name):
        print(f"Warning: {warning['message']}")

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    figure = infographic_figure(root, args.infographic, config, args.version)
    body = place_front(body, what_changed_html(shown), figure)
    manifest = build_manifest(root, config, title, version, sections, bool(figure), assembly_name,
                              front, shown)
    document = page(title, subtitle, config, version, nav, body, "", appendix_list(sections), manifest,
                    front_list(body), change_marker_script(shown))
    duplicates = duplicate_ids(document)
    if duplicates:
        names = ", ".join(repr(name) for name in duplicates)
        raise RuntimeError(
            f"Guide HTML contains duplicate id value(s): {names}. "
            "Give one heading a unique explicit ID, for example "
            "'## Representations {#related-representations}'. A heading ID is also "
            "an anchor name, so choose a stable ID."
        )
    output.write_text(document, encoding="utf-8", newline="\n")
    print(f"Built guide {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
