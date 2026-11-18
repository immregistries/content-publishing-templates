# Changelog

## v0.22.1

- **Fix:** in the reading copy (`CoreDocument.md`), the quoted status notice
  no longer swallows the blank line after it. GitHub had drawn the first
  paragraph of the Executive Summary inside the quote.
- To adopt: move `process/` to v0.22.1 and regenerate the reading copy with
  `build_core_markdown.py`.

**Upgrade impact:** rebuild

## v0.22.0

Needs InteropHub 0.12.0 for comment modes, version settings, and
`--check-token`. Against an older hub, guides behave as in v0.21.0,
`--check-token` says the hub is too old to describe tokens, and version
settings fail with the hub's error.

- **Executive Summary and Scope.** A Topic Reference opens with a front
  section above Chapter 1: the status banner, the Executive Summary, "What
  changed", the infographic, and the Scope as cards. None of it is in the
  section bar or counted as a chapter; the right rail lists it as
  "Overview".
  - `content/00-executive-summary.md` is the one section that may repeat the
    chapters, for a reader who reads nothing else. The checks warn below 150
    words and above 550, and fail above 650 (`SUMMARY_SHORT`,
    `SUMMARY_LONG`).
  - `content/00-scope.md` has `## In scope` and `## Out of scope`, both
    required, optionally `## Not yet decided`, and no other headings. Each
    Out of scope item links to where it is handled, or says "(not covered by
    any current topic)" (`SCOPE_OUT_UNLINKED`).
  - `content/00-status-and-scope.md` is retired. A project that still has it
    fails the content check and the build, with the migration steps in the
    message. There is no compatibility mode.
  - Word follows the same order through a new Quarto filter,
    `templates/word/topic-reference.lua`, which also makes the Scope a table
    and puts the status notice in the reference document's new "Status
    Notice" style. `insert_word_infographic.py` places the infographic
    before the Scope heading.
  - The manifest gains `hasExecutiveSummary`, `executiveSummaryWords`, and
    `hasScope`.
- **Change markers.** Mark what changed in a version in the source:
  `<!-- changed v0.5.0: note -->`, with `feedback` after the version when
  feedback is wanted, and `rows=A,B` for rows of a row-anchored table.
  - Markers show in every output: a badge and bar in the guide (the
    annotations panel's Changes tab, and the Review tab for feedback wanted),
    an italic note in Word, and a quoted note in the reading copy. Each
    output lists them under "What changed in vX", feedback wanted first.
  - The version shown is the build's release label, otherwise `version` in
    `guide.json`: the version being prepared. Older markers are hidden and
    reported as stale (`STALE_CHANGE_MARKER`). The content check warns when a
    release build's tag differs from `version` (`VERSION_MISMATCH`), and
    when there are markers but no `version` (`VERSION_MISSING`).
  - A malformed marker, a marker with nothing after it, or `rows=` naming a
    missing row fails the content check and the build.
  - The manifest counts `changeMarkers` and `feedbackMarkers`.
  - New projects start with `"version": "v0.1.0"` in `guide.json`.
- **Annotations panel.** Comments, review flags, and change markers move to
  a left panel with **Comments**, **Review**, and **Changes** tabs, closed by
  default. The active tab decides which markers show in the text, and the
  right rail shows only navigation ("On this page").
  - The panel is resizable (280 to 640 px; double-click or Home resets it)
    and remembers its tab, width, and open state per document. `?lens=`
    links open a tab.
  - A count strip in the section bar opens the panel. Below 900 px it is a
    bottom sheet.
  - Comment filters: Open, All, and Mine. Review flags can be listed with
    cleared ones, and edited and cleared from their cards.
- **Version comment modes.** The guide sends its address (`pageUrl`) with
  each comment, reply, flag, and read, so InteropHub knows which version it
  was written on, and follows that version's comment mode.
  - **Release:** readers see comments for this version and earlier; authors
    see all, with others marked "From another version".
  - **Closed:** no comments or comment controls; a refused comment keeps its
    text as a draft.
  - A mode changed while the page is open takes effect at the next refresh.
- **Publishing and agent breadcrumbs.**
  - `publish_guide_to_hub.py`:
    - `--display` (`current`, `listed`, `unlisted`, `authors_only`,
      `retired`) and `--comment-mode` (`open`, `release`, `closed`) set the
      first `--label`'s settings after an upload or `--manifest-only`.
    - `--settings-only` sets them on a published label without sending a
      guide.
    - `--check-token` reports the account, scopes, expiry, and whether the
      token can publish this guide, and exits 1 when it can't.
    - Uploads warn when the token expires within 14 days.
    - Errors print InteropHub's help link and a plain explanation, including
      `comments_closed`, `insufficient_scope` (with the scope), and
      `forbidden` (must be a topic editor).
    - An HTML answer is reported as a firewall, with what to report.
    - The label pattern now matches InteropHub's.
  - The project `AGENTS.md` gains "Publishing to InteropHub", per profile:
    - where the token lives, and that an agent never prints, commits, or
      asks for it;
    - the first call;
    - the publishing commands;
    - the steps only the author can take, in words to pass on;
    - the help page.

    It also names the Executive Summary exception and how to write change
    markers.
  - `new_topic_reference.py` sets the hub for every Standing profile.
  - The guidance gains "Becoming an author", "Version display and comment
    modes", "Executive Summary and Scope", and "Change markers", and drops
    the example lines that put a token in a shell variable.
- `tests/mock_hub.py` follows InteropHub 0.12.0: labels, comment modes,
  `GET /api/token`, and `help` on errors, and can stand in for a firewall or
  an older hub. The fixture has real change markers and a front section.
- To adopt, for each Topic Reference:
  1. Move `process/` to v0.22.0.
  2. **`guide.json`:**
     - add `"version"`: the version being prepared, such as `v0.5.0`;
     - remove `status-and-scope` from `navLabels`.
  3. **Create `content/00-executive-summary.md`:**
     - `# Executive Summary`;
     - a `::: {.status-notice}` … `:::` block holding the old status text,
       without its `> ` quote marks;
     - the old "In brief", expanded to 150–550 words.
  4. **Create `content/00-scope.md`:**
     - `# Scope` and the old purpose in one sentence;
     - `## In scope`, the old "What this project covers";
     - `## Out of scope`, each item linked to where it is handled;
     - optionally `## Not yet decided`, each item linked to its open
       question or working decision.
  5. **Retire the old file:**
     - Move anything else in `content/00-status-and-scope.md` into a
       chapter, keeping its heading IDs and anchors, then delete it.
     - In the assembly `.qmd`, include the two new files first.
     - Update `content/README.md`.
     - Fix links to the old file and its headings, including refs in
       `content/infographic.yml` and, with the presentation option,
       `slides.json` sources.
  6. **`_quarto.yml`:** under `format: docx:`, add
     `filters: [process/templates/word/topic-reference.lua]`.
  7. **`build.ps1`:** before `quarto render`, add
     `$changeVersion = & $python.Source .\process\tools\change_markers.py --current-version`,
     and render with `-M "change-version:$changeVersion"`, as in the
     skeleton.
  8. **`AGENTS.md`:**
     - Copy "Publishing to InteropHub" from the profile's
       `templates/topic-reference/profiles/<profile>/fragments/AGENTS_PUBLISHING.txt`,
       replacing `{{HUB_URL}}`, `{{TOPIC_NAME}}`, and `{{TOPIC_URL}}`.
     - Copy the Executive Summary and change-marker lines under "Writing
       the source" from the skeleton's `AGENTS.md`.
  9. Remove any `$env:INTEROPHUB_TOKEN = "<…>"` lines copied into the
     project's own documents.
  10. Rebuild the reading copy, run `validate.ps1` and `build.ps1`, publish,
      and run `publish_guide_to_hub.py --check-token`.

  When releasing, set `version` to the tag before tagging. Right after,
  raise it to the next version and delete the markers the content check
  reports as stale.

**Upgrade impact:** content

## v0.21.0

- **The process knows its own version.** `VERSION` holds the current release
  label, and `process-releases.json` lists every release, newest first, with
  its date, a one-sentence summary, and its upgrade impact: `rebuild` (move
  `process/`, rebuild, and republish), `config` (also edit `guide.json` or a
  workflow), or `content` (authors write or restructure content). Earlier
  releases are backfilled, and each CHANGELOG entry now ends with its upgrade
  impact. New `tools/process_release.py` fails when `VERSION`, the newest
  registry entry, and the newest CHANGELOG heading disagree, when the
  registry and the CHANGELOG list different releases, or when an impact is
  not one of the three; `validate.ps1` and CI run it.
- **Build manifest.** `build_guide.py` embeds a machine-readable record of
  each build in the guide's `<head>`, as
  `<script type="application/json" id="guide-build-manifest">` (schema 1):
  the templates' version, commit, and the whole release registry; the
  document's ID, title, type, status, version, where it is kept, visibility,
  hosting, and InteropHub topic; when and from which commit it was built, and
  with which Python and pandoc; its chapters, appendices, and whether it has
  an infographic; and the content check findings. Warnings carry stable codes
  (`CHAPTER_COUNT`, `APPENDIX_ORDER`, `CONFIRM_OPEN`, `INFOGRAPHIC_WARNING` in
  this release) so InteropHub's status page can filter on them. Readers can
  see the manifest, so it names files by their path in the project and holds
  no machine paths, workspace location, tokens, or the text of CONFIRM notes.
  A project kept in a workspace, or outside Git, has no source commit.
- `check_content.py`'s checks are callable as `run_checks()`, which
  `build_guide.py` uses to fill the manifest. The command line is unchanged.
- **Publishing saves the manifest.** A guide is not published until its
  manifest is saved in InteropHub.
  - `publish_guide_to_hub.py` refuses a guide that has no manifest. Hosted
    uploads are otherwise unchanged; InteropHub reads the manifest from the
    page.
  - `publish_guide_to_hub.py --manifest-only` sends only the manifest, with an
    optional `--label`, to `/api/guide/{document}/builds`, for a guide hosted
    elsewhere. The hub comes from `--hub` or `comments.hub`. The document key
    is set in `guide.json`: `comments.document`, or else the project `id`;
    `--document` overrides it. The tool explains the hub's `invalid_request`
    and `document_inactive` errors.
  - The public profile's `publish-guide.yml` checks for the
    `INTEROPHUB_TOKEN` repository secret before deploying, and fails without
    it, then saves the manifest after deploying to GitHub Pages.
  - `new_topic_reference.py` records `visibility` in `guide.json`. The
    manifest uses it, and infers visibility from hosting only when it is
    missing.
  - `Process.md`, `TopicReference.md`, and the project README's publishing
    section list saving the manifest as a publishing step.
- `tests/mock_hub.py` serves the builds endpoint and records the manifest of
  each uploaded guide, as InteropHub does. `workspace_process.py` copies
  `VERSION` and `process-releases.json` into a workspace's `process/`.
- To adopt:
  - Register the guide in InteropHub if it is not already, under its
    document key (`comments.document`, or else `id`). Saving the manifest
    fails with `not_found` for an unregistered guide, including one that
    uses local comments.
  - Add `"visibility": "public"` or `"private"` to `guide.json`.
  - Move `process/` to v0.21.0, rebuild, and republish. A hosted guide's
    upload carries the manifest.
  - A public project also copies the "Check InteropHub token" and "Save
    build manifest in InteropHub" steps from the skeleton's
    `.github/workflows/publish-guide.yml`, and adds an `INTEROPHUB_TOKEN`
    repository secret: a personal access token with `topics:write`.
  - A private guide built locally reports with
    `publish_guide_to_hub.py --manifest-only` when it is released.

**Upgrade impact:** config

## v0.20.0

- **Chapters and appendices.** The suggested size of a core document is six to
  seven chapters, not counting appendices. An appendix is a top-level chapter
  whose heading begins "Appendix", and appendices come after all other
  chapters.
  - `build_guide.py` counts only the other chapters, warns above seven, and
    warns when a chapter follows an appendix.
  - With two or more appendices, the guide's top menu shows one
    **Appendices** link instead of one per appendix. It is highlighted while
    any appendix is in view, and the right rail then lists every appendix,
    with the current one's subsections beneath it. A single appendix keeps its
    own link. Word and HTML copies are unchanged.
- **Ideas register.** `new_topic_reference.py --with ideas` adds
  `content/80-ideas.md`, "Appendix: Ideas", before the working decisions: one
  table of ideas, each with an ID (`IDEA-001`), date, source, target chapter,
  and status (Open, Sorted, or Set aside), and each row a review area of its
  own. `check_content.py` checks its columns, IDs, statuses, sources, and links,
  and reports the number of Open ideas without failing. Conventions defines an
  idea, the register's rules, and optional "Guiding questions" sections.
- **"Collecting ideas" status.** `guide.json` may set `"status": "Collecting
  ideas"` for a document that only gathers ideas so far; the guide and
  infographic give it its own tag style. Conventions gives matching
  status-notice wording.
- **Restricted-use notice.** Both private profiles replace "AIRA internal use
  only" with one notice that ties access to the InteropHub topic: "Restricted
  to readers of InteropHub topic N". A private topic's readers may include
  partner organizations, so the notice fits topics read only by AIRA staff and
  topics shared with partners. `INTERNAL-USE.md` keeps its file name. The
  guide footer and infographic notice (`license` in `guide.json`), the status
  notices, `CONTRIBUTING.md`, the briefs, and the default subtitle change to
  match. The `AGENTS.md` rules now say `content/` holds only what every reader
  of the topic may see.
- Existing projects keep their wording until they next refresh `process/`.
  Private projects then adopt the new notice: replace `INTERNAL-USE.md`, set
  `license` in `guide.json`, and update the status notices, `CONTRIBUTING.md`,
  and the private-repository section of `AGENTS.md` from the skeleton. Projects
  with an appendix between chapters, or a long chapter list, see the new
  warnings.

**Upgrade impact:** content

## v0.19.0

- A private Standing Topic Reference can be kept in a shared folder, such as a
  synced Dropbox folder, with no Git repository, and published only by
  uploading its guide to InteropHub. Where a Standing Topic Reference is kept
  is now separate from its type: a public one is kept in Git; a private one in
  Git or in a shared folder.
  - `new_topic_reference.py --kept-in workspace` creates one. It needs
    `--visibility private --hosting interophub --hub` and `--location`, takes
    no `--owner`, creates no Git repository, and copies the shared templates
    into `process/` as for a Workspace. It uses the new `private-workspace`
    profile, whose README says the project has no repository by design.
  - `guide.json` records `"keptIn": "workspace"`, `location`, and a `version`
    label such as `v0.1.0`, set by hand and raised before each upload.
    `build_guide.py` shows that label and the build date, and fails when the
    label is missing or the settings do not fit a private, InteropHub-hosted
    project without a repository. The infographic draws the same label.
  - `check_products.py` reports the checks that need Git as not applicable
    and shows a product's `core_release` beside its `core_built`.
- Guidance: `TopicReference.md` describes where a Standing Topic Reference is
  kept, when to keep a private one in a shared folder, how to start one, and
  how to promote a Workspace to one in place. Conventions, Process, and the
  README no longer say that Standing means Git.
- Existing projects need no change.

**Upgrade impact:** rebuild

## v0.18.0

- Review flags are redrawn in purple, which signals "look here" without
  clashing with yellow comments or red errors. They no longer outline and
  shade each paragraph in yellow.
  - A flagged area starts with a purple **Review** badge that shows the start
    of the note.
  - A purple bar runs unbroken down the area's left side.
  - A flagged table row has the bar on its left edge and a small badge in its
    first cell.
  - Hovering over or focusing the badge shows the whole note, who flagged it,
    and when. Clicking keeps it open.
  - Authors can **Edit** or **Clear** the flag from the badge.
- Authors flag an area with a flag button that appears under the comment
  button on hover. It replaces the "Flag for review" text button that was
  always shown on every area. The button turns purple on a flagged area.
- Section links in the top bar and the subsection rail show a purple dot when
  their section holds a flagged area.
- The comments panel lists flags first, under **Review flags (n)**. Authors
  can still clear them there.
- Everyone signed in sees flags. Only authors see the flag button and the
  Edit and Clear controls.
- `tests/browser_check.py` covers flagging an area and a row, the reader's
  view, and clearing a flag. A new `--screenshots` option saves images of the
  markers for a visual check.
- Projects adopt this by moving their `process` submodule to v0.18.0 and
  rebuilding and republishing the guide.

**Upgrade impact:** rebuild

## v0.17.0

- InteropHub comment forms save an unsaved draft in the browser as the reader
  types, per document, signed-in user, and form (new comment on a block,
  reply, edit, or review flag). Reopening the form after a reload or a failed
  save restores the draft, with a "Discard draft" link. A successful save
  clears it.
- When a request fails with a response that is not InteropHub's JSON, such
  as a block page from a proxy or web application firewall, the message says
  the request was stopped before it reached InteropHub and gives the HTTP
  status and UTC time, so the report can be matched to that system's logs.
  A network failure says InteropHub could not be reached. Both tell the
  reader their text is still in the form and saved in the browser. Before,
  the message was only "The request failed."
- Comment forms show a character count once three quarters of the limit is
  used. The review flag form now limits its note to 500 characters, matching
  InteropHub, instead of 4,000.
- `tests/mock_hub.py` answers a comment containing `TEST-FIREWALL-BLOCK` with
  an HTML 403, standing in for a firewall, and the browser check covers it.
- Projects adopt this by moving their `process` submodule to v0.17.0 and
  rebuilding and republishing the guide.

**Upgrade impact:** rebuild

## v0.16.0

- Row anchors. A `<!-- row-anchors -->` line just before a pipe table makes
  each body row a review area of its own, named from its first cell (`OQ-13`
  becomes `oq-13`). In the web guide, each row has its own comment button,
  review flag, and link target. Its comments and forms appear in a full-width
  row beneath it. Other tables are unchanged and stay one comment block.
- `check_content.py` reports duplicate, reserved, and malformed row anchors,
  and a directive with no table after it. `build_guide.py` fails on them too.
  `build_core_markdown.py` leaves the directive out of the reading copy.
- Comment snippets sent to InteropHub leave out the review flag button's text.
- Fix: a table whose column widths fill the line, which pandoc writes as
  `<table style="width:100%;">`, now gets the AIRA table styling and wrapper
  like any other table. Before, it was left unstyled and was not a comment
  block.
- Guidance: Topic References should use row anchors on their working
  decisions and open questions tables. Projects adopt this by adding the
  directive to those tables.

**Upgrade impact:** content

## v0.15.1

- The Topic Reference publishing workflows, public and private, install
  pandoc 3.7.0.2 from its GitHub release instead of the Ubuntu package
  servers. On 11 November 2026 the GitHub runners could not reach those
  servers, and every publish failed. Projects adopt the change by copying
  the new "Install pandoc" step into their own
  `.github/workflows/publish-guide.yml`.
- The repository's own validation workflow installs pandoc the same way.

**Upgrade impact:** config

## v0.15.0

- Guides declare `hosting` as `local`, `github-pages` (the default when
  absent), or `interophub`. Hosted guides require InteropHub comments with a
  hub URL and document key; builds and content checks enforce the rules.
- `publish_guide_to_hub.py` validates and uploads a self-contained guide under
  one or more labels using `INTEROPHUB_TOKEN`, with a no-network dry run.
- Private Standing projects may choose local or hosted setup. Hosted projects
  receive an Actions workflow that publishes `main`, release tags, and
  `latest`; local projects receive no publishing workflow.
- `tests/mock_hub.py` serves the version upload and listing endpoints in the
  shape the hub returns: `uploadedBy` is a display name, and the listing is
  `{"versions": [...]}` with `historyCount` and `earlier` per label.

**Upgrade impact:** rebuild

## v0.14.0

- A Topic Reference is one of two types. A **Standing Topic Reference** is a
  lasting, versioned reference for an InteropHub topic, as before. A
  **Workspace Topic Reference** is kept in a shared folder, such as a synced
  Dropbox folder, without Git, releases, or an InteropHub topic, and can later
  be promoted. See
  [Workspace and Standing Topic References](guidance/TopicReference.md#workspace-and-standing-topic-references),
  with the starting and promotion steps, and the terms in the conventions.
- `new_topic_reference.py --type workspace --location "<where it is kept>"`
  creates a Workspace from the new `profiles/workspace/`. It may be made in a
  working folder that already holds notes and documents, and stops if a
  skeleton file would replace one; `--id` names the project when the folder
  name is not an ID. `--type standing` is the default, and `--visibility`,
  `--topic`, and `--topic-name` are required only for it.
- New `tools/workspace_process.py` copies these templates into a workspace's
  `process/` at a tag or commit, with `process/PROCESS-VERSION.txt`, and
  refreshes the copy later.
- `build_guide.py`: with `"topicReferenceType": "workspace"` in `guide.json`,
  the page shows "Workspace Topic Reference", "Workspace build" and the build
  date instead of a version, and "Kept in" with the `location`.
- `check_products.py` works without Git: it compares core file dates with each
  manifest's `core_built`. The product manifest template has `core_built` and
  `core_location` for workspaces. Decks may give `core_built` instead of
  `core_release` in `slides.json`.
- Skeleton: the lines that link to an InteropHub topic or describe the Git
  submodule are now profile fragments (`PROJECT_IDENTITY`, `README_IDENTITY`,
  `README_BUILD_SETUP`, `SHARED_TEMPLATES_RULE`, `PROCESS_ROLE`,
  `GUIDE_IDENTITY`, `RELATED_TOPIC_ROW`, `TOPIC_SOURCE_ROW`, `REVIEW_INTRO`,
  `PRODUCTS_INTRO`); `GUIDE_COMMENTS` and `TOPIC_SOURCE_USE` are folded into
  them. Generated Standing projects are unchanged except that `build.ps1` and
  `validate.ps1` no longer name the submodule command when `process/` is
  missing, and `build.ps1` asks Dropbox not to sync the `.quarto` cache and
  keeps Python from writing caches.
- Periodic comment refreshes keep open reply, edit, and disposition forms in
  place, preserving their draft text, focus, and cursor position until the
  reader submits or closes the form.

**Upgrade impact:** rebuild

## v0.13.0

- Every Topic Reference has a primary infographic, the topic at a glance. Its
  specification is `content/infographic.yml`: the topic name, a one-sentence
  purpose, three to six key ideas with their relationships, and short alt text,
  each part naming the heading in `content/` it summarizes. The status, version,
  build date, InteropHub topic, and the guide footer's notice are drawn on the
  image. See [Primary infographic](guidance/TopicReference.md#primary-infographic).
- New tools: `tools/infographic.py` (specification reader, checks, layout, and
  SVG drawing, standard library only), `tools/build_infographic.py` (SVG, PNG,
  and PDF, checked and exported with an installed Chrome or Edge run headless),
  `tools/insert_word_infographic.py` (places the PNG in the built Word document),
  and `tools/headless_browser.py`.
- `build_guide.py` draws the infographic above the first section when
  `content/infographic.yml` exists, each part linking to its section. It needs
  no browser, so publishing workflows are unchanged.
- `check_content.py` checks the specification: missing fields, unresolved
  references, missing artwork, and text that does not fit fail; starter
  `CONFIRM` text is reported. A Topic Reference (`"documentType": "Topic
  Reference"` in `guide.json`) without `content/infographic.yml` now fails.
- The skeleton creates a starter `content/infographic.yml` and
  `products/infographic/brief.yml` for public and private projects; a private
  project's draws the topic number without its address. The skeleton's
  `build.ps1` builds the infographic before `quarto render` and places it in
  the Word document after.
- "Sanctioned summaries" in the conventions records the infographic as a
  deliberate exception to stating each fact once.
- The infographic is set in Open Sans, vendored with its license in
  `templates/infographic/fonts/` and embedded in each SVG. Text is wrapped with
  Open Sans's own advance widths, read from the vendored files.
- The image shows the status and build date, and the release tag only when the
  build is exactly on a clean tag; it never shows a git describe string.
- Ideas in a sequence or cycle are numbered. A sequence of four ideas reads
  left to right in one row; a cycle of four is a two-by-two loop.
- Each idea may name an `icon` from a vendored subset of Lucide icons (ISC
  license), listed in `templates/infographic/README.md`.

- The web guide embeds images linked from `content/` instead of linking them
  to the repository, so they show in a private project's guide and the guide
  stays one file. Link images relative to the Markdown file that uses them
  (for example, `images/figure.png` from `content/`); the skeleton's
  `_quarto.yml` adds `content` to Quarto's `resource-path` so the Word and
  HTML builds find them too. Existing projects should add the same
  `resource-path` entry.

- The web guide draws Mermaid diagrams. A ```` ```{mermaid} ```` block in
  `content/`, which Quarto already drew in the Word and HTML review copies,
  showed in the guide as a run of code text. The guide now embeds Mermaid
  11.12.0, the version Quarto bundles, vendored with its MIT license in
  `templates/guide/mermaid/`, but only when the document has diagrams.
  Diagrams are drawn in the page, so the guide still builds without a browser,
  and each diagram can take a comment. The comments script starts once the
  diagrams are drawn, because a comment records its block's text.
- `build_core_markdown.py` writes Mermaid fences as ```` ```mermaid ```` in
  `CoreDocument.md`, so GitHub draws them in the reading copy.
- The guide's duplicate-ID check ignores text inside scripts.
- New convention: [Diagrams](guidance/Conventions.md#diagrams). Draw diagrams
  as Mermaid, with the caption in an italic paragraph after the block.

To adopt this in an existing Topic Reference: move `process/` to this version;
copy `content/infographic.yml` and `products/infographic/brief.yml` from the
skeleton (`templates/topic-reference/project/content/` and
`templates/topic-reference/profiles/<visibility>/products/`), replacing the
`{{...}}` values (`topic_link: false` for a private project); add the two steps
from the skeleton's `build.ps1`; list the files in `content/README.md` and
`products/README.md`; write the specification from the existing sections; and
run `build.ps1` and `validate.ps1`. Chrome or Edge must be installed where
`build.ps1` runs.

**Upgrade impact:** content

## v0.12.1

- The web guide no longer stalls wheel scrolling at section boundaries. When
  the current section changed, the guide called `scrollIntoView` on its link in
  the sticky section bar; because that bar sits inside the page's
  `scroll-padding-top`, the browser scrolled the page back up, which could
  return the reader to the previous section. The guide now scrolls only the
  section bar, sideways, and only when the link is out of view. Rebuild guides
  to pick up the fix.

**Upgrade impact:** rebuild

## v0.12.0

- Topic References can be public or private. "Topic Reference" names both; a
  project's visibility follows its InteropHub topic. See
  [Visibility](guidance/TopicReference.md#visibility).
- `tools/new_topic_reference.py` requires `--visibility public|private`. A
  private project also requires `--owner`. Existing commands must add
  `--visibility public`; the public output is unchanged.
- A private project has no GitHub Pages workflow, no open licenses, and no code
  of conduct. It carries `INTERNAL-USE.md`, an internal contribution guide,
  private-repository rules in `AGENTS.md`, a web-guide brief for a guide that
  is built but not published, and an internal-use notice in the guide footer.
  Its comments use local mode.
- The skeleton's public-only files moved from
  `templates/topic-reference/project/` to `templates/topic-reference/profiles/public/`.
  Text that differs inside shared files comes from each profile's `fragments/`.
- `tests/test_new_topic_reference.py` and `validate.ps1` create, check, and
  build both kinds of project, and check that a private project contains no
  publishing workflow, open license, or public address.

**Upgrade impact:** rebuild

## v0.11.0

- New Topic References no longer include a "How this document is maintained"
  section or the process working decisions WD-1 and WD-2. How Topic References
  are maintained is described once, in the shared guidance and each
  repository's `README.md` and `CONTRIBUTING.md`. Existing Topic References may
  remove that section and those decisions.

**Upgrade impact:** rebuild

## v0.10.0

- The conventions add two rules for canonical source: state each fact once and
  link to it rather than repeating it, and keep the core document to about six
  top-level chapters, including appendices. Both apply only to the source;
  derived products may repeat, explain, and add sections. The process and Topic
  Reference guidance, the skeleton's `AGENTS.md`, and its `content/README.md`
  refer to them.
- `tools/build_guide.py` prints a warning, without failing, when a guide has
  more than six top-level chapters.
- The Topic Reference guidance allows a short related-work section to live in
  Status and Scope instead of its own chapter.

**Upgrade impact:** rebuild

## v0.9.0

- `tools/check_products.py` lists each derived product whose core has changed
  since the release recorded in its manifest, showing the files added,
  changed, renamed, or removed, and fails when a product's manifest, brief, or
  slides cite a source that no longer exists. `--fail-on-stale` also fails on
  products that need review.
- The PowerPoint generator stops with an error when a slide lists no sources or
  cites a file that does not exist. Sources are relative to `--root`, which
  defaults to the current directory.
- The before-and-after slide pattern places its points below the panel heading
  however many lines the heading takes.
- Fix: Topic Reference Word builds lost every top-level section heading,
  because the skeleton shifted headings up a level while its sections use
  level-1 headings. The skeleton no longer shifts headings. Existing Topic
  References should remove `shift-heading-level-by: -1` from `_quarto.yml`.
- The Topic Reference presentation add-on starts from its own four-slide deck
  that cites the skeleton's files, instead of the PowerPoint example.
- The process guidance asks for core releases to be tagged in Git and recorded
  as the `core_release` in manifests, and describes checking products after a
  new release. CI now runs the unit tests.

**Upgrade impact:** config

## v0.8.0

- Rapid presentations can use 15 expressive slide patterns in addition to the
  template layouts: statement, big numbers, quote, split panel, cards, 2x2 grid,
  numbered agenda, process, timeline, image with caption, key takeaway, table,
  chart, before and after, and closing. A slide selects one with `"pattern"`;
  the deck or slide sets the `"family"` (Blue or Green). Patterns draw native,
  editable shapes, tables, and charts on the Title Only, Blank, and Title Dark
  layouts, so the template file is unchanged.
- Pattern slides choose text colors for contrast, so text on the green family's
  panels is dark blue rather than white.
- The generator rejects counts a pattern cannot lay out, warns when text is
  likely to overflow its space, crops a supplied image to fill the image panel,
  and accepts JSON sources saved with a UTF-8 byte order mark.
- `templates/powerpoint/example-patterns.json` shows every pattern and is built
  by validation, which fails on any fit warning.

**Upgrade impact:** rebuild

## v0.7.0

- Show comment review states, dispositions, change notes, closed threads, and
  flagged review areas in connected guides.
- Add permission-based author controls for disposition, closing, deletion,
  orphan re-attachment, and review flags, with conflict handling.
- Replace blocking comment confirmations with in-page prompts and expand the
  mock comments service and browser checks for author review.

**Upgrade impact:** rebuild

## v0.6.0

- Guides can use a validated `comments` setting to select browser-local or
  signed-in hub comments. The hub mode supports PKCE sign-in, threads, replies,
  editing, withdrawal, attribution, deep links, and background refreshes.
- A standard-library mock comments service and contract checks cover sign-in,
  CORS, incremental refresh tombstones, edit windows, and reply depth.
- Topic Reference guidance explains where comments are stored in each mode.

**Upgrade impact:** rebuild

## v0.5.1

- Reading copies remove review anchors without leaving an extra blank line
  between the surrounding Markdown blocks.
- Upgrading to v0.5.x may expose a duplicate HTML ID that an earlier guide
  build silently allowed. Give one of the colliding headings a unique explicit
  ID, such as `## Representations {#related-representations}`; because a heading
  ID is also an anchor name, keep it stable as content changes.

**Upgrade impact:** rebuild

## v0.5.0

- Web guides support stable review anchors in canonical Markdown. Built guides
  mark commentable blocks with their anchor area and 0-based position, preserve
  a 120-character text snippet with new local comments, and place comments by
  anchor when text moves or changes.
- Comment targets are paragraphs, whole lists, quotes, and tables. Individual
  list items and code blocks are no longer separate targets; earlier local
  comments on either may appear at the start of their area or as orphaned.
- Anchor and comment deep links work on initial load and hash changes. Comments
  whose anchors no longer exist appear in an Orphaned comments group.
- Content checks reject malformed or duplicate anchors and names that collide
  with heading IDs. Reading copies omit anchor directives.
- Topic Reference and convention guidance describes stable anchor naming and
  placement.

**Upgrade impact:** rebuild

## v0.4.0

- Topic References: `guidance/TopicReference.md` describes the most common kind
  of project, a Topic Reference for one InteropHub topic, and the conventions
  name the term.
- `templates/topic-reference/` holds the skeleton for a new Topic Reference
  project, and `tools/new_topic_reference.py` creates one from it, with an
  optional presentation add-on. Confluence products are not part of the
  skeleton.
- Web guide: an optional `documentType` in `guide.json`, such as
  `"Topic Reference"`, is shown above the title and in the browser tab.

**Upgrade impact:** rebuild

## v0.3.0

- PowerPoint support: the AIRA rapid presentation template (18 layouts, author
  names removed, sample photograph replaced with a placeholder), its layout
  contract, the build checklist, and `tools/build_rapid_presentation.py` with an
  example slide source. Requires `python-pptx` (`requirements-pptx.txt`).
- The presentation generator now accepts a subtitle on Section layouts, which
  use a body placeholder for it, and slides without a title on Blank layouts.

**Upgrade impact:** rebuild

## v0.2.1

- Fix: the comment box in the web guide was hidden, so typing was invisible.

**Upgrade impact:** rebuild

## v0.2.0

- Web guide: `tools/build_guide.py` builds a self-contained HTML page styled
  with the AIRA Web theme (aira-web 0.1.13) to match InteropHub, with a section
  bar, a right rail that follows the reader, a status tag, and a return link to
  the project's InteropHub topic. Settings come from the project's `guide.json`.
- On-page comments saved in the reader's browser, downloadable and loadable as
  JSON. `tools/import_guide_comments.py` turns downloaded files into a review
  record.

**Upgrade impact:** rebuild

## v0.1.0

First public release, seeded from AIRA's internal content publishing process.

- Word reference document with AIRA styles and the `AIRA2` table style, with
  author metadata removed.
- `build_core_markdown.py`, generalized: the assembly file is an argument, the
  title and subtitle come from its front matter, and relative links in sections
  are rewritten so they resolve from the reading copy.
- `check_content.py`, generalized: optional `--include` globs and
  `--report-term` words.
- `apply_word_table_style.py`, unchanged.
- Process and conventions guidance, with internal pilot references removed.
- Generic product brief, manifest, and content-module templates.

**Upgrade impact:** rebuild
