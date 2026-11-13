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
and placed above the first section, each part linking
to the section it summarizes. It is drawn here rather than copied from
output/, so the guide builds without a browser; build_infographic.py draws the
same figure for the PNG, PDF, and Word document.
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
import infographic  # noqa: E402


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
SUGGESTED_MAX_CHAPTERS = 6
INTEROPHUB_TOPIC_URL = "https://informatics.immregistries.org/hub/es/topic/{topic}"
STATUS_TAGS = {
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
        help="Primary infographic specification, drawn above the first section when it exists.",
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


def prepared_markdown(
    root: Path, paths: list[Path], repository: str | None, ref: str
) -> str:
    """Give each included file a stable section ID and make its links work."""
    anchors = {path.resolve(): section_id(path) for path in paths}
    parts = []
    for path in paths:
        text = path.read_text(encoding="utf-8").strip()
        text = plain_mermaid_fences(replace_anchors(text))
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
    return annotate_commentable_blocks(apply_row_anchors(body))


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


def page(
    title: str,
    subtitle: str | None,
    config: dict,
    version: str,
    nav: str,
    body: str,
    figure: str = "",
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
            <span class="aira-meta">{html.escape(version_label)}</span>
          </div>
        </div>
      </header>
      <div class="aira-right-rail-layout guide-layout">
        <article class="aira-prose guide-content" id="guide-content">
<div id="{DOCUMENT_START_ANCHOR}" class="guide-anchor" data-guide-anchor="{DOCUMENT_START_ANCHOR}"></div>
{figure}{body}
        </article>
        <aside class="aira-right-rail guide-rail" aria-label="Page tools">
          <section class="aira-sidebar-section">
            <h2 class="aira-sidebar-title" id="guide-rail-title">On this page</h2>
            <ul class="guide-subnav" id="guide-subnav"></ul>
          </section>
          <section class="aira-sidebar-section guide-comments-panel" id="guide-comments-panel" hidden>
            <h2 class="aira-sidebar-title">Comments <span class="aira-badge" id="guide-comment-count">0</span></h2>
            <div id="guide-comments-status"><p class="aira-meta">Comments are saved only in this browser. Download them to share.</p></div>
            <div id="guide-local-identity"><label class="aira-label" for="guide-commenter">Your name</label>
            <input class="aira-input" id="guide-commenter" type="text" autocomplete="name"></div>
            <div class="guide-comment-actions">
              <button type="button" class="aira-button aira-button--secondary aira-button--small" id="guide-comments-toggle" aria-pressed="true">Hide comments</button>
              <button type="button" class="aira-button aira-button--secondary aira-button--small guide-local-control" id="guide-comments-download">Download</button>
              <label class="aira-button aira-button--secondary aira-button--small guide-file-button guide-local-control">Load<input type="file" id="guide-comments-load" accept="application/json,.json" multiple hidden></label>
              <button type="button" class="aira-button aira-button--ghost aira-button--small guide-local-control" id="guide-comments-clear">Clear all</button>
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
    <p>{html.escape(title)} &middot; {html.escape(version_label[0].lower() + version_label[1:])} &middot; generated {guide_data["built"]}{" &middot; " + html.escape(license_note) if license_note else ""}</p>
  </footer>
</div>
<script type="application/json" id="guide-data">{json.dumps(guide_data)}</script>
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
    markdown = prepared_markdown(root, paths, config.get("repository"), ref)
    body = body_html(markdown)
    nav = section_nav(body, config.get("navLabels", {}))
    chapters = len(SECTION_PATTERN.findall(body))
    if chapters > SUGGESTED_MAX_CHAPTERS:
        print(
            f"Warning: the guide has {chapters} top-level chapters; the suggested "
            f"maximum is {SUGGESTED_MAX_CHAPTERS}. Consider merging chapters. "
            "See guidance/Conventions.md, 'Keep chapters few'."
        )

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    figure = infographic_figure(root, args.infographic, config, args.version)
    document = page(title, subtitle, config, version, nav, body, figure)
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
