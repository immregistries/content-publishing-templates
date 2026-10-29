"""Check a content project's maintained Markdown for broken links and open items.

Run from the content project's root:

    python process/tools/check_content.py
    python process/tools/check_content.py --report-term CLEAR --include "notes/*.md"

Broken internal links, and unresolved template placeholders in content/, fail
the check. CONFIRM notes and any --report-term uses in content/ are reported for
human review but do not fail it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote


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


def main() -> int:
    args = arguments()
    root = Path(args.root).resolve()
    terms = {term: re.compile(rf"\b{re.escape(term)}\b") for term in args.report_term}
    failures: list[str] = []
    confirms: list[str] = []
    term_uses: dict[str, dict[str, int]] = {term: {} for term in terms}

    for path in maintained_files(root, args.include):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        failures.extend(broken_links(root, path, text))

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

    if confirms:
        print(f"{len(confirms)} CONFIRM item(s) awaiting human resolution:")
        for item in confirms:
            print(f"  {item}")
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
