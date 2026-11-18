"""The front section of a Topic Reference: Executive Summary and Scope.

Every Topic Reference opens, above Chapter 1, with two files:

- content/00-executive-summary.md (section ID executive-summary): "# Executive
  Summary", a `::: {.status-notice}` block, then prose for a reader who reads
  nothing else, about one printed page. It may repeat the chapters.
- content/00-scope.md (section ID scope): "# Scope", one sentence of purpose,
  then "## In scope" and "## Out of scope" (both required) and optionally
  "## Not yet decided", each a bullet list. Each out-of-scope item says where
  the topic is handled, with a link, or "(not covered by any current topic)".

The tools find them by their section IDs, not their place in the file list.
They are not chapters: they are not in the section bar and are not counted.
content/00-status-and-scope.md, which they replace, is an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SUMMARY_PATH = "content/00-executive-summary.md"
SCOPE_PATH = "content/00-scope.md"
RETIRED_PATH = "content/00-status-and-scope.md"
SUMMARY_ID = "executive-summary"
SCOPE_ID = "scope"
FRONT_IDS = (SUMMARY_ID, SCOPE_ID)
SUMMARY_WARN_ABOVE = 550
SUMMARY_FAIL_ABOVE = 650
SUMMARY_WARN_BELOW = 150
SCOPE_HEADINGS = ("In scope", "Out of scope", "Not yet decided")
REQUIRED_SCOPE_HEADINGS = ("In scope", "Out of scope")
NOT_COVERED = "(not covered by any current topic)"

MIGRATION = (
    "content/00-status-and-scope.md is retired. Move its parts into the front section: "
    "(1) create content/00-executive-summary.md with '# Executive Summary', the status notice "
    "in a '::: {.status-notice}' block, and the In brief text expanded to about one page; "
    "(2) create content/00-scope.md with '# Scope', the Purpose as one sentence, '## In scope' "
    "(What this project covers), '## Out of scope' (What this project does not cover, each item "
    "linked to where it is handled), and optionally '## Not yet decided'; (3) include both files "
    "first in the assembly file and remove the old include; (4) remove status-and-scope from "
    "navLabels in guide.json; (5) delete the old file and update links to it. See "
    "process/guidance/TopicReference.md, 'Executive Summary and Scope'."
)

COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
FENCED_DIV_PATTERN = re.compile(r"^:::+\s*\{?\.?status-notice\}?\s*$.*?^:::+\s*$", re.DOTALL | re.MULTILINE)
FENCE_BLOCK_PATTERN = re.compile(r"^(`{3,}|~{3,}).*?^\1\s*$", re.DOTALL | re.MULTILINE)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*(?:\{[^}]*\})?\s*$")
LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
# Letters and digits in any script; "don't", "v0.5.0", and "risk-based" are one word each.
WORD_PATTERN = re.compile(r"[^\W_]+(?:['’.\-][^\W_]+)*")
LIST_ITEM_PATTERN = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\([^)\s]+\)|<https?://[^>]+>")


@dataclass
class Finding:
    """A front-section finding. Errors fail the check and the build; warnings do not."""

    code: str
    file: str
    message: str
    error: bool = False

    def text(self) -> str:
        return f"[{self.code}] {self.file}: {self.message}"


@dataclass
class FrontReport:
    findings: list[Finding] = field(default_factory=list)
    has_summary: bool = False
    has_scope: bool = False
    summary_words: int | None = None

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.error]

    @property
    def warnings(self) -> list[Finding]:
        return [finding for finding in self.findings if not finding.error]


def summary_words(text: str) -> int:
    """Words of the Executive Summary's prose and lists.

    Not counted: headings, the status notice, HTML comments (CONFIRM notes,
    anchors, change markers), and code.
    """
    text = COMMENT_PATTERN.sub(" ", text)
    text = FENCED_DIV_PATTERN.sub(" ", text)
    text = FENCE_BLOCK_PATTERN.sub(" ", text)
    kept = []
    for line in text.splitlines():
        if HEADING_PATTERN.match(line) or line.strip().startswith(":::"):
            continue
        kept.append(line)
    text = LINK_PATTERN.sub(r"\1", "\n".join(kept))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return len(WORD_PATTERN.findall(text))


def _scope_lists(text: str) -> tuple[list[tuple[int, str]], dict[str, list[tuple[int, str]]]]:
    """Level-2 headings with line numbers, and each heading's top-level list items."""
    text = COMMENT_PATTERN.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    headings: list[tuple[int, str]] = []
    items: dict[str, list[tuple[int, str]]] = {}
    current: str | None = None
    for number, line in enumerate(text.splitlines(), 1):
        heading = HEADING_PATTERN.match(line)
        if heading:
            if len(heading.group(1)) == 2:
                current = heading.group(2).strip()
                headings.append((number, current))
                items.setdefault(current, [])
            elif len(heading.group(1)) == 1:
                current = None
            continue
        if current is None:
            continue
        item = LIST_ITEM_PATTERN.match(line)
        if item and not item.group(1):
            items[current].append((number, item.group(2).strip()))
        elif items.get(current) and line.startswith((" ", "\t")) and line.strip():
            number_first, first_text = items[current][-1]
            items[current][-1] = (number_first, first_text + " " + line.strip())
    return headings, items


def check(root: Path, topic_reference: bool) -> FrontReport:
    """Check the front section. The files are required only in a Topic Reference."""
    report = FrontReport()
    summary = root / SUMMARY_PATH
    scope = root / SCOPE_PATH
    report.has_summary = summary.is_file()
    report.has_scope = scope.is_file()
    if (root / RETIRED_PATH).is_file():
        report.findings.append(Finding("RETIRED_STATUS_AND_SCOPE", RETIRED_PATH, MIGRATION, True))
    if topic_reference and not report.has_summary:
        report.findings.append(Finding(
            "SUMMARY_MISSING", SUMMARY_PATH,
            "every Topic Reference opens with an Executive Summary. See "
            "process/guidance/TopicReference.md, 'Executive Summary and Scope'.", True))
    if topic_reference and not report.has_scope:
        report.findings.append(Finding(
            "SCOPE_MISSING", SCOPE_PATH,
            "every Topic Reference states its Scope, with In scope and Out of scope. See "
            "process/guidance/TopicReference.md, 'Executive Summary and Scope'.", True))

    if report.has_summary:
        words = summary_words(summary.read_text(encoding="utf-8"))
        report.summary_words = words
        if words > SUMMARY_FAIL_ABOVE:
            report.findings.append(Finding(
                "SUMMARY_LONG", SUMMARY_PATH,
                f"the Executive Summary has {words} words; the limit is {SUMMARY_FAIL_ABOVE} "
                "(about one printed page). Shorten it.", True))
        elif words > SUMMARY_WARN_ABOVE:
            report.findings.append(Finding(
                "SUMMARY_LONG", SUMMARY_PATH,
                f"the Executive Summary has {words} words; aim for at most {SUMMARY_WARN_ABOVE}, "
                f"about one printed page. Above {SUMMARY_FAIL_ABOVE} the build fails."))
        elif words < SUMMARY_WARN_BELOW:
            report.findings.append(Finding(
                "SUMMARY_SHORT", SUMMARY_PATH,
                f"the Executive Summary has {words} words; at fewer than {SUMMARY_WARN_BELOW} it "
                "repeats the InteropHub topic overview. Write it for a reader who reads nothing else."))

    if report.has_scope:
        headings, items = _scope_lists(scope.read_text(encoding="utf-8"))
        for number, heading in headings:
            if heading not in SCOPE_HEADINGS:
                report.findings.append(Finding(
                    "SCOPE_HEADING", SCOPE_PATH,
                    f"line {number}: heading {heading!r} is not allowed; the Scope has only "
                    "'In scope', 'Out of scope', and 'Not yet decided'.", True))
        for heading in REQUIRED_SCOPE_HEADINGS:
            if heading not in items:
                report.findings.append(Finding(
                    "SCOPE_SECTION", SCOPE_PATH, f"the Scope needs a '## {heading}' list.", True))
            elif not items[heading]:
                report.findings.append(Finding(
                    "SCOPE_SECTION", SCOPE_PATH, f"the '## {heading}' list is empty.", True))
        for number, item in items.get("Out of scope", []):
            if not MARKDOWN_LINK_PATTERN.search(item) and NOT_COVERED not in item:
                report.findings.append(Finding(
                    "SCOPE_OUT_UNLINKED", SCOPE_PATH,
                    f"line {number}: say where this is handled, with a link to the related topic "
                    f"or document, or write {NOT_COVERED!r}."))
    return report
