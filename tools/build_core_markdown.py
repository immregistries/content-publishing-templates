"""Generate or verify the GitHub reading copy of a project's core document.

Run from the content project's root, naming its Quarto assembly file:

    python process/tools/build_core_markdown.py --assembly Project.qmd
    python process/tools/build_core_markdown.py --assembly Project.qmd --check

The title and subtitle come from the assembly file's YAML front matter, and the
sections come from its include directives, in order.
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


def generated_text(root: Path, assembly: Path, output: Path) -> str:
    sections = []
    for path in include_paths(root, assembly):
        section = path.read_text(encoding="utf-8").strip()
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
