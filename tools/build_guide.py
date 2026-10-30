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
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_core_markdown import (  # noqa: E402
    FRONT_MATTER_PATTERN,
    LINK_TARGET_PATTERN,
    front_matter_value,
    include_paths,
)


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "guide"
HEADING_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
ANCHOR_PATTERN = re.compile(
    r"^\s*<!-- anchor: ([a-z0-9]+(?:-[a-z0-9]+)*) -->\s*$"
)
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
SECTION_PATTERN = re.compile(
    r'<section id="([^"]+)" class="level2[^"]*"[^>]*>\s*<h2[^>]*>(.*?)</h2>', re.DOTALL
)
TAG_PATTERN = re.compile(r"<[^>]+>")
INTEROPHUB_TOPIC_URL = "https://informatics.immregistries.org/hub/es/topic/{topic}"
STATUS_TAGS = {
    "draft": "aira-tag--warning",
    "review": "aira-tag--info",
    "final": "aira-tag--success",
    "published": "aira-tag--success",
}
DOCUMENT_START_ANCHOR = "document-start"


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
    return parser.parse_args()


def pandoc_command() -> list[str]:
    if shutil.which("pandoc"):
        return ["pandoc"]
    if shutil.which("quarto"):
        return ["quarto", "pandoc"]
    raise RuntimeError("Pandoc is required. Install pandoc or Quarto.")


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
        if match:
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            name = match.group(1)
            output.append(
                f'<div id="{name}" class="guide-anchor" '
                f'data-guide-anchor="{name}"></div>{ending}'
            )
        else:
            output.append(line)
    return "".join(output)


def prepared_markdown(
    root: Path, paths: list[Path], repository: str | None, ref: str
) -> str:
    """Give each included file a stable section ID and make its links work."""
    anchors = {path.resolve(): section_id(path) for path in paths}
    parts = []
    for path in paths:
        text = path.read_text(encoding="utf-8").strip()
        text = replace_anchors(text)
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
    body = result.stdout.replace(
        "<table>", '<div class="aira-table-wrap"><table class="aira-table">'
    ).replace("</table>", "</table></div>")
    return annotate_commentable_blocks(body)


TOKEN_PATTERN = re.compile(r"<[^>]+>|[^<]+")
TAG_NAME_PATTERN = re.compile(r"</?\s*([a-zA-Z0-9]+)")
ID_PATTERN = re.compile(r'\bid="([^"]+)"')
CLASS_PATTERN = re.compile(r'\bclass="([^"]*)"')
COMMENTABLE_TAGS = {"p", "ul", "ol", "blockquote"}


def annotate_commentable_blocks(body: str) -> str:
    """Mark outermost commentable blocks with their anchor area and position."""
    area = DOCUMENT_START_ANCHOR
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
            continue

        identifier = ID_PATTERN.search(token)
        if tag == "section" and identifier:
            area = html.unescape(identifier.group(1))
        elif "guide-anchor" in classes and identifier:
            area = html.unescape(identifier.group(1))

        commentable = tag in COMMENTABLE_TAGS or "aira-table-wrap" in classes
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


def section_nav(body: str, labels: dict[str, str]) -> str:
    links = []
    for identifier, heading in SECTION_PATTERN.findall(body):
        label = labels.get(identifier) or html.unescape(TAG_PATTERN.sub("", heading))
        links.append(
            f'<a href="#{html.escape(identifier)}">{html.escape(label)}</a>'
        )
    return "\n        ".join(links)


def logo_data_uri() -> str:
    data = (TEMPLATE_DIR / "AIRA_2018Logo_BlueGreen_Hor.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def page(
    title: str,
    subtitle: str | None,
    config: dict,
    version: str,
    nav: str,
    body: str,
) -> str:
    status = config.get("status", "Draft")
    status_class = STATUS_TAGS.get(status.lower(), "aira-tag--info")
    topic = config.get("interophubTopic")
    topic_url = INTEROPHUB_TOPIC_URL.format(topic=topic) if topic else None
    repository = config.get("repository")
    doc_id = config.get("id") or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    guide_data = {
        "id": doc_id,
        "title": title,
        "version": version,
        "built": date.today().isoformat(),
    }

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
    license_note = config.get("license", "")
    subtitle_html = (
        f'<p class="aira-topic-summary">{html.escape(subtitle)}</p>' if subtitle else ""
    )
    document_type = config.get("documentType")
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
</head>
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
    </div>
  </div>
  <main class="aira-main" id="guide-main">
    <div class="guide-page aira-container--wide">
      <header class="aira-topic-header guide-header">
        <div class="aira-topic-header__top">
          <div>
            {document_type_html}
            <h1 class="aira-topic-title">{html.escape(title)}</h1>
            {subtitle_html}
          </div>
          <div class="aira-topic-actions guide-status">
            <span class="aira-tag {status_class} guide-status-tag">{html.escape(status.upper())}</span>
            <span class="aira-meta">Version {html.escape(version)}</span>
          </div>
        </div>
      </header>
      <div class="aira-right-rail-layout guide-layout">
        <article class="aira-prose guide-content" id="guide-content">
<div id="{DOCUMENT_START_ANCHOR}" class="guide-anchor" data-guide-anchor="{DOCUMENT_START_ANCHOR}"></div>
{body}
        </article>
        <aside class="aira-right-rail guide-rail" aria-label="Page tools">
          <section class="aira-sidebar-section">
            <h2 class="aira-sidebar-title" id="guide-rail-title">On this page</h2>
            <ul class="guide-subnav" id="guide-subnav"></ul>
          </section>
          <section class="aira-sidebar-section guide-comments-panel" id="guide-comments-panel" hidden>
            <h2 class="aira-sidebar-title">Comments <span class="aira-badge" id="guide-comment-count">0</span></h2>
            <p class="aira-meta">Comments are saved only in this browser. Download them to share.</p>
            <label class="aira-label" for="guide-commenter">Your name</label>
            <input class="aira-input" id="guide-commenter" type="text" autocomplete="name">
            <div class="guide-comment-actions">
              <button type="button" class="aira-button aira-button--secondary aira-button--small" id="guide-comments-toggle" aria-pressed="true">Hide comments</button>
              <button type="button" class="aira-button aira-button--secondary aira-button--small" id="guide-comments-download">Download</button>
              <label class="aira-button aira-button--secondary aira-button--small guide-file-button">Load<input type="file" id="guide-comments-load" accept="application/json,.json" multiple hidden></label>
              <button type="button" class="aira-button aira-button--ghost aira-button--small" id="guide-comments-clear">Clear all</button>
            </div>
            <ol class="guide-comment-index" id="guide-comment-index"></ol>
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
    <p>{html.escape(title)} &middot; version {html.escape(version)} &middot; generated {guide_data["built"]}{" &middot; " + html.escape(license_note) if license_note else ""}</p>
  </footer>
</div>
<script type="application/json" id="guide-data">{json.dumps(guide_data)}</script>
<script>
{(TEMPLATE_DIR / "guide.js").read_text(encoding="utf-8")}
</script>
</body>
</html>
"""


def duplicate_ids(document: str) -> list[str]:
    counts: dict[str, int] = {}
    for identifier in re.findall(r'\bid="([^"]+)"', document):
        identifier = html.unescape(identifier)
        counts[identifier] = counts.get(identifier, 0) + 1
    return sorted(identifier for identifier, count in counts.items() if count > 1)


def main() -> int:
    args = arguments()
    root = Path(args.root).resolve()
    assembly = root / args.assembly
    config = json.loads((root / args.config).read_text(encoding="utf-8"))

    text = assembly.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(text)
    front_matter = match.group(1) if match else ""
    title = front_matter_value(front_matter, "title")
    if not title:
        raise RuntimeError(f"No title in the front matter of {assembly}")
    subtitle = config.get("subtitle") or front_matter_value(front_matter, "subtitle")

    version = args.version or git_version(root)
    ref = args.ref or (version if re.match(r"^v\d", version) else "main")
    paths = include_paths(root, assembly)
    markdown = prepared_markdown(root, paths, config.get("repository"), ref)
    body = body_html(markdown)
    nav = section_nav(body, config.get("navLabels", {}))

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    document = page(title, subtitle, config, version, nav, body)
    duplicates = duplicate_ids(document)
    if duplicates:
        names = ", ".join(repr(name) for name in duplicates)
        raise RuntimeError(
            f"Guide HTML contains duplicate id value(s): {names}. "
            "Rename any explicit anchor that collides with a heading or guide element."
        )
    output.write_text(document, encoding="utf-8", newline="\n")
    print(f"Built guide {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
