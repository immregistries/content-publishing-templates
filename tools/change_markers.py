"""Change markers: what changed in this version, written in the source.

A change marker is an HTML comment on its own lines, just before what it
covers:

    <!-- changed v0.5.0: Consent now follows the state rule; former rule 3 removed. -->
    <!-- changed v0.5.0 feedback: New exception for school-based clinics. -->
    <!-- changed v0.5.0 rows=OQ-13,OQ-14: Reworded after the October call. -->

- Before a block (paragraph, list, table, figure, diagram), it covers that block.
- Before a heading, it covers that section, down to the next heading at the
  same or a higher level.
- Before a table with row anchors, it names the rows it covers with rows=, and
  sits after the `<!-- row-anchors -->` line.

"feedback" asks readers for feedback on the change. The note is required, at
most 300 characters of plain text, and says what changed. The version is a
release label such as v0.5.0.

Which markers show depends on the current version: markers for the current
version or a later one are shown, and older ones are stale. See
current_version(). The build tools show the markers in every output; the
content check warns about stale ones (STALE_CHANGE_MARKER).

Run from the content project's root to print the current version, as the
project's build passes it to the Word build:

    python process/tools/change_markers.py --current-version
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_core_markdown import (  # noqa: E402
    FENCE_PATTERN,
    ROW_ANCHORS_PATTERN,
    row_anchor_name,
)


# The release label pattern the primary infographic uses.
RELEASE_PATTERN = re.compile(r"^v\d+(?:\.\d+){0,3}$")
MARKER_START_PATTERN = re.compile(r"^\s*<!--\s*changed\b", re.IGNORECASE)
MARKER_PATTERN = re.compile(
    r"^<!--\s*changed\s+(?P<version>\S+?)"
    r"(?P<feedback>\s+feedback)?"
    r"(?:\s+rows=(?P<rows>[^\s:]+))?"
    r"\s*:\s*(?P<note>.*?)\s*-->$",
    re.DOTALL,
)
NOTE_LIMIT = 300
COMMENT_LINE_PATTERN = re.compile(r"^\s*<!--.*-->\s*$")
HEADING_LINE_PATTERN = re.compile(r"^#{1,6}\s")
STALE_CODE = "STALE_CHANGE_MARKER"


@dataclass
class Marker:
    """One change marker in a Markdown file."""

    version: str
    feedback: bool
    note: str
    line: int
    end_line: int
    # What follows the marker: "heading", "row-table", or "block".
    covers: str
    # Row anchor names, such as "oq-13", for a marker on a row-anchored table.
    rows: list[str] = field(default_factory=list)
    # The rows as written, such as "OQ-13", for notes in Word and the reading copy.
    row_labels: list[str] = field(default_factory=list)

    @property
    def level(self) -> str:
        return "feedback" if self.feedback else "changed"

    def label(self) -> str:
        """How the reading copy and Word introduce the note."""
        rows = f" ({', '.join(self.row_labels)})" if self.row_labels else ""
        if self.feedback:
            return f"Changed in {self.version}{rows}, feedback wanted"
        return f"Changed in {self.version}{rows}"


def version_key(version: str) -> tuple[int, ...]:
    parts = [int(part) for part in version[1:].split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def next_version(version: str) -> str:
    """The version after a release: the last of three numbers plus one (v0.3.0 -> v0.3.1).

    The smallest step, so a marker written for any coming release still shows.
    """
    parts = [int(part) for part in version[1:].split(".")]
    parts = (parts + [0, 0, 0])[:max(3, len(parts))]
    parts[-1] += 1
    return "v" + ".".join(str(part) for part in parts)


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def own_repository(root: Path) -> bool:
    """Whether root is the top of its own Git repository, as a content project is."""
    top = _git(root, "rev-parse", "--show-toplevel")
    if not top:
        return False
    try:
        return Path(top).resolve() == root.resolve()
    except OSError:
        return False


def newest_release_tag(root: Path) -> str | None:
    tags = [tag for tag in (_git(root, "tag", "--list", "v*") or "").split() if RELEASE_PATTERN.fullmatch(tag)]
    return max(tags, key=version_key) if tags else None


def current_version(root: Path, version: str | None = None, config: dict | None = None) -> str | None:
    """The version whose markers are shown, or None to show every marker.

    - A release label given to the build (--version v0.5.0) is the current version.
    - A project kept in a workspace uses its guide.json "version".
    - Otherwise, in the project's own Git repository: the release tag HEAD is
      on, or else the newest release tag plus one, so markers written for the
      coming release show on main. A project with no release yet shows every
      marker.
    """
    if version and RELEASE_PATTERN.fullmatch(version):
        return version
    config = config or {}
    if config.get("keptIn") == "workspace" or config.get("topicReferenceType") == "workspace":
        label = config.get("version")
        return label if isinstance(label, str) and RELEASE_PATTERN.fullmatch(label) else None
    if not own_repository(root):
        return None
    exact = _git(root, "describe", "--tags", "--exact-match", "HEAD")
    if exact and RELEASE_PATTERN.fullmatch(exact):
        return exact
    newest = newest_release_tag(root)
    return next_version(newest) if newest else None


def is_shown(marker: Marker, current: str | None) -> bool:
    return current is None or version_key(marker.version) >= version_key(current)


def _fence_state(line: str, fence: tuple[str, int] | None) -> tuple[bool, tuple[str, int] | None]:
    """Whether the line opens or closes a fence, and the fence state after it."""
    match = FENCE_PATTERN.match(line)
    if not match:
        return False, fence
    marker = match.group(1)
    if fence is None:
        return True, (marker[0], len(marker))
    if marker[0] == fence[0] and len(marker) >= fence[1]:
        return True, None
    return True, fence


def marker_spans(text: str) -> list[tuple[int, int]]:
    """The (first, last) 0-based line indexes of each marker outside fenced code."""
    lines = text.splitlines()
    spans = []
    fence: tuple[str, int] | None = None
    index = 0
    while index < len(lines):
        is_fence, fence_after = _fence_state(lines[index], fence)
        if is_fence:
            fence = fence_after
            index += 1
            continue
        if fence is None and MARKER_START_PATTERN.match(lines[index]):
            end = index
            while end < len(lines) and "-->" not in lines[end]:
                end += 1
            spans.append((index, min(end, len(lines) - 1)))
            index = end + 1
            continue
        index += 1
    return spans


def parse(text: str) -> tuple[list[Marker], list[tuple[int, str]]]:
    """The change markers in one Markdown file, and problems with their line numbers."""
    lines = text.splitlines()
    markers: list[Marker] = []
    problems: list[tuple[int, str]] = []
    spans = marker_spans(text)
    marker_lines = {line for first, last in spans for line in range(first, last + 1)}
    for first, last in spans:
        line_number = first + 1
        raw = " ".join(part.strip() for part in lines[first:last + 1])
        if "-->" not in lines[last] or not raw.rstrip().endswith("-->") or not lines[first].lstrip().startswith("<!--"):
            problems.append((line_number, "a change marker must stand on its own lines and end with -->"))
            continue
        match = MARKER_PATTERN.fullmatch(raw.strip())
        if not match:
            problems.append((line_number, "malformed change marker; write <!-- changed v0.5.0[ feedback][ rows=A,B]: note -->"))
            continue
        version = match.group("version")
        note = " ".join(match.group("note").split())
        if not RELEASE_PATTERN.fullmatch(version):
            problems.append((line_number, f"change marker version {version!r} is not a release label such as v0.5.0"))
            continue
        if not note:
            problems.append((line_number, "a change marker needs a note saying what changed"))
            continue
        if len(note) > NOTE_LIMIT:
            problems.append((line_number, f"the change marker's note is {len(note)} characters; the limit is {NOTE_LIMIT}"))
            continue
        if "<" in note or ">" in note:
            problems.append((line_number, "the change marker's note must be plain text, without < or >"))
            continue
        row_labels = [part for part in (match.group("rows") or "").split(",") if part]
        if match.group("rows") is not None and not row_labels:
            problems.append((line_number, "rows= names no rows"))
            continue

        # What does the marker come before? Skip blank lines, other markers,
        # anchor directives, and other comments; note a row-anchors line.
        row_table = any(
            ROW_ANCHORS_PATTERN.fullmatch(lines[index])
            for index in _previous_directives(lines, first, marker_lines)
        )
        index = last + 1
        while index < len(lines):
            line = lines[index]
            if not line.strip() or index in marker_lines:
                index += 1
                continue
            if ROW_ANCHORS_PATTERN.fullmatch(line):
                row_table = True
                index += 1
                continue
            if COMMENT_LINE_PATTERN.match(line):
                index += 1
                continue
            break
        if index >= len(lines):
            problems.append((line_number, "a change marker must be followed by the block or heading it covers"))
            continue
        following = lines[index]
        if HEADING_LINE_PATTERN.match(following):
            covers = "heading"
        elif following.lstrip().startswith("|") and row_table:
            covers = "row-table"
        else:
            covers = "block"
        rows: list[str] = []
        if covers == "row-table":
            if not row_labels:
                problems.append((line_number, "a change marker before a table with row anchors must name its rows with rows="))
                continue
            table_rows = _table_row_names(lines, index)
            rows = [row_anchor_name(label) for label in row_labels]
            missing = [label for label, name in zip(row_labels, rows) if name not in table_rows]
            if missing:
                problems.append((line_number, f"rows= names {', '.join(missing)}, not a row of the table that follows"))
                continue
        elif row_labels:
            problems.append((line_number, "rows= is only for a table with row anchors; put the marker after its <!-- row-anchors --> line"))
            continue
        markers.append(Marker(version, bool(match.group("feedback")), note, line_number, last + 1,
                              covers, rows, row_labels))
    return markers, problems


def _previous_directives(lines: list[str], first: int, marker_lines: set[int]) -> list[int]:
    """Indexes of the directive lines just above a marker (blank lines skipped)."""
    found = []
    index = first - 1
    while index >= 0:
        line = lines[index]
        if not line.strip() or index in marker_lines:
            index -= 1
            continue
        if ROW_ANCHORS_PATTERN.fullmatch(line):
            found.append(index)
        break
    return found


def _table_row_names(lines: list[str], start: int) -> set[str]:
    table = []
    index = start
    while index < len(lines) and lines[index].lstrip().startswith("|"):
        table.append(lines[index])
        index += 1
    names = set()
    for row in table[2:]:
        cells = re.split(r"(?<!\\)\|", row.strip().strip("|"))
        names.add(row_anchor_name(cells[0]))
    return names


def stale_warnings(markers: list[tuple[str, Marker]], current: str | None) -> list[dict]:
    """A coded warning for each marker older than the current version."""
    if current is None:
        return []
    return [
        {"code": STALE_CODE, "file": relative,
         "message": f"line {marker.line}: change marker for {marker.version} is older than the "
                    f"current version {current}; delete it when starting the next version."}
        for relative, marker in markers
        if not is_shown(marker, current)
    ]


def replace_for_reading_copy(text: str, current: str | None) -> str:
    """Write shown markers as quoted notes, and drop the others (D3)."""
    markers, _ = parse(text)
    by_line = {marker.line: marker for marker in markers}
    lines = text.splitlines(keepends=True)
    starts = {first: last for first, last in marker_spans(text)}
    output: list[str] = []
    index = 0
    while index < len(lines):
        if index not in starts:
            output.append(lines[index])
            index += 1
            continue
        last = starts[index]
        marker = by_line.get(index + 1)
        if marker is not None and is_shown(marker, current):
            ending = "\n" if lines[last].endswith("\n") else ""
            output.append(f"> **{marker.label()}:** {marker.note}{ending}")
            index = last + 1
            # A quote runs on into a line that follows it, so keep them apart.
            if index < len(lines) and lines[index].strip():
                output.append("\n")
            continue
        # A hidden marker leaves no gap: drop one of the blank lines around it.
        index = last + 1
        if (not output or not output[-1].strip()) and index < len(lines) and not lines[index].strip():
            index += 1
    return "".join(output)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Change markers in a content project.")
    parser.add_argument("--root", default=".", help="Content project root.")
    parser.add_argument("--config", default="guide.json", help="Guide settings file.")
    parser.add_argument("--version", help="Version label of the build, such as v0.5.0 or main.")
    parser.add_argument("--current-version", action="store_true",
                        help="Print the version whose markers are shown (empty when every marker is).")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    root = Path(args.root).resolve()
    config_path = root / args.config
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    current = current_version(root, args.version, config)
    print(current or "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
