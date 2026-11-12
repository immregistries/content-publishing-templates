"""Generate or verify the GitHub reading copy of a project's core document.

Run from the content project's root, naming its Quarto assembly file:

    python process/tools/build_core_markdown.py --assembly Project.qmd
    python process/tools/build_core_markdown.py --assembly Project.qmd --check

The title and subtitle come from the assembly file's YAML front matter, and the
sections come from its include directives, in order. Mermaid diagram fences are
written in the form GitHub draws.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


INCLUDE_PATTERN = re.compile(r"\{\{<\s*include\s+([^\s>]+)\s*>\}\}")
FRONT_MATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LINK_TARGET_PATTERN = re.compile(r"(\]\()([^)\s]+)(\))")
ANCHOR_PATTERN = re.compile(
    r"^\s*<!-- anchor: [a-z0-9]+(?:-[a-z0-9]+)* -->\s*$"
)
ROW_ANCHORS_PATTERN = re.compile(r"^\s*<!-- row-anchors -->\s*$")
ROW_ANCHORS_LIKE_PATTERN = re.compile(r"^\s*<!--\s*row-anchors?\b", re.IGNORECASE)
ANCHOR_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_ANCHOR_PREFIXES = ("comment-", "guide-")
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
MERMAID_FENCE_PATTERN = re.compile(r"^(\s*)(`{3,}|~{3,})\s*\{mermaid\}\s*$")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--assembly",
        required=True,
        help="Quarto assembly file, relative to the project root.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Content project root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--output",
        default="CoreDocument.md",
        help="Reading copy to write, relative to the root.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the reading copy does not match the canonical source.",
    )
    return parser.parse_args()


def front_matter_value(front_matter: str, key: str) -> str | None:
    match = re.search(rf"^{key}:\s*(.+?)\s*$", front_matter, re.MULTILINE)
    if not match:
        return None
    value = match.group(1)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def header(assembly: Path) -> str:
    text = assembly.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(text)
    front_matter = match.group(1) if match else ""
    title = front_matter_value(front_matter, "title")
    if not title:
        raise RuntimeError(f"No title in the front matter of {assembly}")
    subtitle = front_matter_value(front_matter, "subtitle")

    lines = [
        "<!--",
        "GENERATED FILE. DO NOT EDIT DIRECTLY.",
        "",
        "The authoritative source is in content/. Regenerate this reading copy with:",
        f"    python process/tools/build_core_markdown.py --assembly {assembly.name}",
        "-->",
        "",
        f"# {title}",
        "",
    ]
    if subtitle:
        lines += [f"*{subtitle}*", ""]
    lines += [
        "> This is a generated reading copy for GitHub. For review and editing, use the",
        "> [canonical section files](content/README.md).",
        "",
        "---",
        "",
        "",
    ]
    return "\n".join(lines)


def include_paths(root: Path, assembly: Path) -> list[Path]:
    text = assembly.read_text(encoding="utf-8")
    relative_paths = INCLUDE_PATTERN.findall(text)
    if not relative_paths:
        raise RuntimeError(f"No include directives found in {assembly}")

    paths = [root / relative_path for relative_path in relative_paths]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing included files: " + ", ".join(missing))
    return paths


def relocated_links(text: str, source: Path, output: Path) -> str:
    """Rewrite relative link targets so they still resolve from the output file."""

    def relocate(match: re.Match[str]) -> str:
        target = match.group(2)
        if re.match(r"^[a-z]+:", target) or target.startswith(("#", "/")):
            return match.group(0)
        path, _, fragment = target.partition("#")
        moved = Path(os.path.relpath(source.parent / path, output.parent)).as_posix()
        if fragment:
            moved += "#" + fragment
        return match.group(1) + moved + match.group(3)

    return LINK_TARGET_PATTERN.sub(relocate, text)


def row_anchor_name(cell: str) -> str:
    """The anchor name for a table row, from the text of its first cell.

    "OQ-13" becomes "oq-13". Markup is ignored, so the same name comes from the
    Markdown cell and from the cell pandoc renders.
    """
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&[a-zA-Z0-9#]+;", " ", text)
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def anchor_name_problem(name: str) -> str | None:
    """Why a name cannot be an anchor, or None when it can."""
    if not ANCHOR_NAME_PATTERN.fullmatch(name):
        return "is not lowercase letters and digits separated by single hyphens"
    if name == "document-start" or name.startswith(RESERVED_ANCHOR_PREFIXES):
        return "is reserved"
    return None


def row_anchors(text: str) -> tuple[list[tuple[str, int]], list[tuple[int, str]]]:
    """Row anchors declared in one Markdown file.

    A `<!-- row-anchors -->` line placed just before a pipe table makes each
    body row a review area of its own, named from its first cell. Returns the
    names with their line numbers, and problems with their line numbers.
    """
    names: list[tuple[str, int]] = []
    problems: list[tuple[int, str]] = []
    lines = text.splitlines()
    fence: tuple[str, int] | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            index += 1
            continue
        if fence is not None or not ROW_ANCHORS_PATTERN.fullmatch(line):
            index += 1
            continue
        directive = index + 1
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
        table = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            table.append((index + 1, lines[index]))
            index += 1
        if len(table) < 2 or not re.fullmatch(r"[\s|:-]+", table[1][1]):
            problems.append(
                (directive, "row-anchors must be followed by a pipe table")
            )
            continue
        for line_number, row in table[2:]:
            cells = re.split(r"(?<!\\)\|", row.strip().strip("|"))
            name = row_anchor_name(cells[0])
            problem = anchor_name_problem(name)
            if problem:
                problems.append(
                    (line_number, f"row anchor {name!r} from the first cell {problem}")
                )
            else:
                names.append((name, line_number))
    return names, problems


def strip_anchors(text: str) -> str:
    """Remove anchor directives outside fenced code blocks."""
    output = []
    fence: tuple[str, int] | None = None
    lines = text.splitlines(keepends=True)
    skip_blank_after_anchor = False
    for line in lines:
        if skip_blank_after_anchor:
            skip_blank_after_anchor = False
            if not line.strip():
                continue
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            output.append(line)
        elif fence is None and (
            ANCHOR_PATTERN.fullmatch(line.rstrip("\r\n"))
            or ROW_ANCHORS_PATTERN.fullmatch(line.rstrip("\r\n"))
        ):
            skip_blank_after_anchor = bool(output and not output[-1].strip())
            continue
        else:
            output.append(line)
    return "".join(output)


def plain_mermaid_fences(text: str) -> str:
    """Write Quarto's ```{mermaid} diagram fences as ```mermaid.

    Quarto draws a diagram only from the braced form, so the canonical source
    uses it. GitHub and pandoc recognize only the plain form, so the reading
    copy and the web guide use that. The diagram text is unchanged.
    """
    output = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        mermaid = MERMAID_FENCE_PATTERN.fullmatch(body) if fence is None else None
        if mermaid:
            marker = mermaid.group(2)
            fence = (marker[0], len(marker))
            output.append(f"{mermaid.group(1)}{marker}mermaid{ending}")
            continue
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
        output.append(line)
    return "".join(output)


def generated_text(root: Path, assembly: Path, output: Path) -> str:
    sections = []
    for path in include_paths(root, assembly):
        section = path.read_text(encoding="utf-8").strip()
        section = plain_mermaid_fences(strip_anchors(section))
        sections.append(relocated_links(section, path, output))
    return header(assembly) + "\n\n---\n\n".join(sections) + "\n"


def main() -> int:
    args = arguments()
    root = Path(args.root).resolve()
    assembly = root / args.assembly
    output = root / args.output
    expected = generated_text(root, assembly, output)
    command = (
        f"python process/tools/build_core_markdown.py --assembly {args.assembly}"
    )

    if args.check:
        if not output.is_file():
            print(f"{output.name} is missing. Run: {command}")
            return 1
        actual = output.read_text(encoding="utf-8")
        if actual != expected:
            print(f"{output.name} is out of date. Run: {command}")
            return 1
        print(f"{output.name} matches the canonical source.")
        return 0

    output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Generated {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
