"""Check a content project's maintained Markdown for broken links and open items.

Run from the content project's root:

    python process/tools/check_content.py
    python process/tools/check_content.py --report-term CLEAR --include "notes/*.md"

Broken internal links, and unresolved template placeholders in content/, fail
the check. CONFIRM notes and any --report-term uses in content/ are reported for
human review but do not fail it.

When content/80-ideas.md, the ideas register, exists, its columns, IDs,
statuses, sources, and links are checked, and the number of Open ideas is
reported.

A Topic Reference (guide.json "documentType": "Topic Reference") must have a
primary infographic specification, content/infographic.yml. When one exists,
its fields, heading references, artwork, and layout fit are checked; starter
text left in it is reported but does not fail.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_core_markdown import (  # noqa: E402
    ROW_ANCHORS_LIKE_PATTERN,
    ROW_ANCHORS_PATTERN,
    row_anchors,
)
from build_guide import hosting_config  # noqa: E402


LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+|<[^>]+>)\)|!\[[^\]]*\]\(([^)\s]+|<[^>]+>)\)")
CONFIRM_PATTERN = re.compile(r"<!--\s*CONFIRM:(.*?)-->", re.DOTALL)
PLACEHOLDER_PATTERNS = [
    re.compile(r"_To be (?:completed|assigned)_", re.IGNORECASE),
    re.compile(r"YYYY-MM-DD"),
    re.compile(r"\bTODO\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\bXXX\b"),
    re.compile(r"\[placeholder\]", re.IGNORECASE),
]
ANCHOR_PATTERN = re.compile(
    r"^\s*<!-- anchor: ([a-z0-9]+(?:-[a-z0-9]+)*) -->\s*$"
)
ANCHOR_LIKE_PATTERN = re.compile(r"^\s*<!--\s*anchor\s*:", re.IGNORECASE)
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
EXPLICIT_ID_PATTERN = re.compile(r"\s+\{#([A-Za-z0-9_-]+)(?:\s+[^}]*)?\}\s*$")

# Maintained Markdown in a standard content project. Projects add others with
# --include. Historical material in sources/ is preserved as received and is
# not checked, apart from its README.
MAINTAINED = [
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CoreDocument.md",
    "content/**/*.md",
    "sources/README.md",
    "review/**/*.md",
    "products/**/*.md",
]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=".",
        help="Content project root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Additional glob of maintained Markdown, relative to the root.",
    )
    parser.add_argument(
        "--report-term",
        action="append",
        default=[],
        help="Whole word to count in content/ for human review.",
    )
    return parser.parse_args()


def maintained_files(root: Path, extra: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in MAINTAINED + extra:
        files.update(root.glob(pattern))
    return sorted(path for path in files if path.is_file())


def broken_links(root: Path, path: Path, text: str) -> list[str]:
    problems = []
    for match in LINK_PATTERN.finditer(text):
        target = (match.group(1) or match.group(2)).strip("<>")
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        target = unquote(target.split("#", 1)[0])
        if not target:
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            problems.append(f"{path.relative_to(root).as_posix()}: broken link -> {target}")
    return problems


def heading_id(heading: str) -> str:
    explicit = EXPLICIT_ID_PATTERN.search(heading)
    if explicit:
        return explicit.group(1)
    heading = re.sub(r"[`*_~]", "", heading)
    heading = re.sub(r"[^\w\s-]", "", heading, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s-]+", "-", heading)


def content_targets(root: Path) -> dict[str, tuple[str, int]]:
    """Heading IDs and anchors in content/, mapped to their file and line."""
    targets: dict[str, tuple[str, int]] = {}
    for path in sorted((root / "content").glob("**/*.md")):
        if path.name == "README.md":
            continue
        relative = path.relative_to(root).as_posix()
        first_heading = True
        fence: tuple[str, int] | None = None
        text = path.read_text(encoding="utf-8")
        for name, line_number in row_anchors(text)[0]:
            targets.setdefault(name, (relative, line_number))
        for line_number, line in enumerate(text.splitlines(), 1):
            fence_match = FENCE_PATTERN.match(line)
            if fence_match:
                marker = fence_match.group(1)
                if fence is None:
                    fence = (marker[0], len(marker))
                elif marker[0] == fence[0] and len(marker) >= fence[1]:
                    fence = None
                continue
            if fence is not None:
                continue
            anchor_match = ANCHOR_PATTERN.fullmatch(line)
            if anchor_match:
                targets.setdefault(anchor_match.group(1), (relative, line_number))
                continue
            heading_match = HEADING_PATTERN.match(line)
            if heading_match:
                identifier = heading_id(heading_match.group(2))
                if first_heading and heading_match.group(1) == "#":
                    identifier = re.sub(r"^\d+-", "", path.stem)
                    first_heading = False
                if identifier:
                    targets.setdefault(identifier, (relative, line_number))
    return targets


IDEAS_PATH = "content/80-ideas.md"
IDEAS_COLUMNS = ["ID", "Date", "Idea", "Source", "Chapter", "Status"]
IDEA_ID_PATTERN = re.compile(r"IDEA-\d{3,}")
IDEA_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
IDEA_STATUSES = ["Open", "Sorted", "Set aside"]
CELL_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def table_cells(line: str) -> list[str]:
    """The cells of a pipe table row, allowing escaped pipes inside cells."""
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row)]


def idea_status(cell: str) -> tuple[str | None, str]:
    """The status word a Status cell begins with, and the text after it."""
    text = re.sub(r"[*_]", "", cell).strip()
    for status in IDEA_STATUSES:
        if text.lower().startswith(status.lower()):
            return status, text[len(status):].strip(" :;,.-–—")
    return None, text


def ideas_problems(root: Path) -> tuple[list[str], int | None]:
    """Check the ideas register. Returns (failures, number of Open ideas)."""
    path = root / IDEAS_PATH
    if not path.is_file():
        return [], None
    lines = path.read_text(encoding="utf-8").splitlines()
    failures: list[str] = []
    header_index = next(
        (index for index, line in enumerate(lines) if line.strip().startswith("|")), None
    )
    if header_index is None:
        return [f"{IDEAS_PATH}: the ideas register has no table"], None
    columns = table_cells(lines[header_index])
    if columns != IDEAS_COLUMNS:
        failures.append(
            f"{IDEAS_PATH}:{header_index + 1}: the register's columns must be "
            f"{' | '.join(IDEAS_COLUMNS)}"
        )
        return failures, None
    targets = content_targets(root)
    seen: dict[str, int] = {}
    open_count = 0
    for index in range(header_index + 2, len(lines)):
        line = lines[index]
        if not line.strip().startswith("|"):
            break
        where = f"{IDEAS_PATH}:{index + 1}"
        cells = table_cells(line)
        if len(cells) != len(IDEAS_COLUMNS):
            failures.append(f"{where}: the row has {len(cells)} cells, not {len(IDEAS_COLUMNS)}")
            continue
        row = dict(zip(IDEAS_COLUMNS, cells))
        identifier = row["ID"]
        if not IDEA_ID_PATTERN.fullmatch(identifier):
            failures.append(f"{where}: ID {identifier!r} must look like IDEA-001")
        elif identifier in seen:
            failures.append(f"{where}: ID {identifier} is also used on line {seen[identifier]}")
        else:
            seen[identifier] = index + 1
        if not IDEA_DATE_PATTERN.fullmatch(row["Date"]):
            failures.append(f"{where}: Date must be written as 2026-01-31")
        if not row["Idea"]:
            failures.append(f"{where}: the Idea is empty")
        if not row["Source"]:
            failures.append(f"{where}: every idea needs its Source")
        status, rest = idea_status(row["Status"])
        if status is None:
            failures.append(
                f"{where}: Status must begin with {', '.join(IDEA_STATUSES[:-1])}, or {IDEA_STATUSES[-1]}"
            )
        elif status == "Open":
            open_count += 1
        elif status == "Sorted" and not CELL_LINK_PATTERN.search(row["Status"]):
            failures.append(f"{where}: a Sorted idea links to where it went, such as a section, WD-n, or OQ-n")
        elif status == "Set aside" and not rest:
            failures.append(f"{where}: a Set aside idea gives the reason")
        for column in ("Chapter", "Status"):
            for match in CELL_LINK_PATTERN.finditer(row[column]):
                target = match.group(1)
                if re.match(r"^[a-z]+:", target) or "#" not in target:
                    continue
                fragment = unquote(target.split("#", 1)[1])
                if fragment and fragment not in targets:
                    failures.append(f"{where}: {column} links to #{fragment}, which is not in content/")
    return failures, open_count


def infographic_problems(root: Path) -> tuple[list[str], list[str]]:
    """Check the primary infographic specification. Returns (failures, warnings)."""
    import infographic  # noqa: PLC0415 - infographic imports this module

    config_path = root / "guide.json"
    config = {}
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as error:
            return [f"guide.json: {error}"], []
    spec = root / infographic.SPEC_PATH
    if not spec.is_file():
        if config.get("documentType") == "Topic Reference":
            return [f"{infographic.SPEC_PATH} is missing; every Topic Reference has a primary "
                    "infographic. See process/guidance/TopicReference.md."], []
        return [], []
    _, report = infographic.build(root, config, "v00.00.00", "2000-01-01")
    return report.errors, report.warnings


def main() -> int:
    # Labels may hold characters the console encoding lacks; never fail on printing them.
    sys.stdout.reconfigure(errors="backslashreplace")
    args = arguments()
    root = Path(args.root).resolve()
    terms = {term: re.compile(rf"\b{re.escape(term)}\b") for term in args.report_term}
    failures: list[str] = []
    confirms: list[str] = []
    term_uses: dict[str, dict[str, int]] = {term: {} for term in terms}
    anchors: dict[str, tuple[str, int]] = {}
    headings: dict[str, tuple[str, int]] = {}

    for path in maintained_files(root, args.include):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        failures.extend(broken_links(root, path, text))

        if relative.startswith("content/") and path.name != "README.md":
            first_heading = True
            fence: tuple[str, int] | None = None
            for line_number, line in enumerate(text.splitlines(), 1):
                fence_match = FENCE_PATTERN.match(line)
                if fence_match:
                    marker = fence_match.group(1)
                    if fence is None:
                        fence = (marker[0], len(marker))
                    elif marker[0] == fence[0] and len(marker) >= fence[1]:
                        fence = None
                    continue
                if fence is not None:
                    continue
                anchor_match = ANCHOR_PATTERN.fullmatch(line)
                if anchor_match:
                    name = anchor_match.group(1)
                    if name in anchors:
                        first_file, first_line = anchors[name]
                        failures.append(
                            f"{relative}:{line_number}: duplicate anchor {name!r} "
                            f"(first used at {first_file}:{first_line})"
                        )
                    else:
                        anchors[name] = (relative, line_number)
                    if name == "document-start" or name.startswith(("comment-", "guide-")):
                        failures.append(
                            f"{relative}:{line_number}: anchor name {name!r} is reserved"
                        )
                    continue
                if ANCHOR_LIKE_PATTERN.search(line):
                    failures.append(f"{relative}:{line_number}: malformed anchor syntax")
                if ROW_ANCHORS_LIKE_PATTERN.search(line) and not ROW_ANCHORS_PATTERN.fullmatch(line):
                    failures.append(f"{relative}:{line_number}: malformed row-anchors syntax")
                heading_match = HEADING_PATTERN.match(line)
                if heading_match:
                    identifier = heading_id(heading_match.group(2))
                    if first_heading and heading_match.group(1) == "#":
                        identifier = re.sub(r"^\d+-", "", path.stem)
                        first_heading = False
                    if identifier:
                        headings.setdefault(identifier, (relative, line_number))
            names, problems = row_anchors(text)
            for line_number, problem in problems:
                failures.append(f"{relative}:{line_number}: {problem}")
            for name, line_number in names:
                if name in anchors:
                    first_file, first_line = anchors[name]
                    failures.append(
                        f"{relative}:{line_number}: duplicate row anchor {name!r} "
                        f"(first used at {first_file}:{first_line})"
                    )
                else:
                    anchors[name] = (relative, line_number)

        if relative.startswith("content/") and path.name != "README.md":
            for pattern in PLACEHOLDER_PATTERNS:
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    failures.append(
                        f"{relative}:{line}: unresolved placeholder {match.group(0)!r}"
                    )
            for match in CONFIRM_PATTERN.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                note = " ".join(match.group(1).split())
                confirms.append(f"{relative}:{line}: {note}")
            for term, pattern in terms.items():
                count = len(pattern.findall(text))
                if count:
                    term_uses[term][relative] = count

    for name, (relative, line_number) in anchors.items():
        if name in headings:
            heading_file, heading_line = headings[name]
            failures.append(
                f"{relative}:{line_number}: anchor {name!r} collides with heading ID "
                f"at {heading_file}:{heading_line}"
            )

    idea_failures, open_ideas = ideas_problems(root)
    failures.extend(idea_failures)

    infographic_failures, infographic_warnings = infographic_problems(root)
    failures.extend(infographic_failures)
    for warning in infographic_warnings:
        confirms.append(warning)

    config_path = root / "guide.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
            hosting_config(config)
        except (json.JSONDecodeError, RuntimeError) as error:
            failures.append(f"guide.json: {error}")

    if confirms:
        print(f"{len(confirms)} CONFIRM item(s) awaiting human resolution:")
        for item in confirms:
            print(f"  {item}")
    if open_ideas:
        print(f"{open_ideas} Open idea(s) in {IDEAS_PATH} awaiting sorting.")
    for term, uses in term_uses.items():
        if uses:
            print(f"Uses of {term} in content/ (review for intent):")
            for relative, count in uses.items():
                print(f"  {relative}: {count}")

    if failures:
        print(f"{len(failures)} problem(s) found:")
        for item in failures:
            print(f"  {item}")
        return 1

    print("Content checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
