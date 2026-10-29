"""Turn comment files downloaded from a web guide into a review record.

Run from the content project's root, naming one or more downloaded files:

    python process/tools/import_guide_comments.py comments-a.json comments-b.json

Comments are merged (duplicates are removed by ID), grouped by section, and
written as Markdown to review/<date>-guide-comments.md for adjudication.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


FORMAT = "content-guide-comments"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="Downloaded comment JSON files.")
    parser.add_argument(
        "--output",
        default=None,
        help="Markdown file to write. Defaults to review/<today>-guide-comments.md.",
    )
    return parser.parse_args()


def read_comments(paths: list[Path]) -> tuple[list[dict], set[str], set[str]]:
    comments: dict[str, dict] = {}
    titles: set[str] = set()
    versions: set[str] = set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format") != FORMAT:
            raise ValueError(f"{path} is not a guide comment export.")
        titles.add(payload.get("documentTitle") or payload.get("documentId", ""))
        for comment in payload.get("comments", []):
            if comment.get("id") and comment.get("text"):
                comments[comment["id"]] = comment
                if comment.get("documentVersion"):
                    versions.add(comment["documentVersion"])
    ordered = sorted(comments.values(), key=lambda item: item.get("created", ""))
    return ordered, titles, versions


def one_line(text: str) -> str:
    return " ".join((text or "").split())


def markdown(comments: list[dict], titles: set[str], versions: set[str], sources: list[Path]) -> str:
    lines = [
        f"# Guide Comments — {date.today().isoformat()}",
        "",
        "Comments made on the web guide and downloaded as JSON. They are review",
        "inputs: none changes the document until it is adjudicated into `content/`.",
        "",
        f"- Document: {', '.join(sorted(t for t in titles if t)) or 'unknown'}",
        f"- Versions commented on: {', '.join(sorted(versions)) or 'unknown'}",
        f"- Source files: {', '.join(path.name for path in sources)}",
        f"- Comments: {len(comments)}",
        "",
    ]
    sections: dict[str, list[dict]] = {}
    for comment in comments:
        key = comment.get("sectionTitle") or comment.get("sectionId") or "Unplaced"
        sections.setdefault(key, []).append(comment)

    for section, items in sections.items():
        lines += [f"## {section}", ""]
        for comment in items:
            author = comment.get("author") or "Anonymous"
            created = (comment.get("created") or "")[:16].replace("T", " ")
            version = comment.get("documentVersion") or "unknown version"
            lines.append(f"### {author}, {created} ({version})")
            lines.append("")
            context = comment.get("quote") or one_line(comment.get("blockText", ""))
            if context:
                lines.append(f"> {one_line(context)}")
                lines.append("")
            lines.append(comment.get("text", "").strip())
            lines += ["", "**Outcome:** pending", ""]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = arguments()
    sources = [Path(name) for name in args.files]
    comments, titles, versions = read_comments(sources)
    output = Path(args.output or f"review/{date.today().isoformat()}-guide-comments.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown(comments, titles, versions, sources), encoding="utf-8", newline="\n")
    print(f"Wrote {len(comments)} comment(s) to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
