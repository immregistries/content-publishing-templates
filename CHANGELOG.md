# Changelog

## Unreleased

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

## v0.12.1

- The web guide no longer stalls wheel scrolling at section boundaries. When
  the current section changed, the guide called `scrollIntoView` on its link in
  the sticky section bar; because that bar sits inside the page's
  `scroll-padding-top`, the browser scrolled the page back up, which could
  return the reader to the previous section. The guide now scrolls only the
  section bar, sideways, and only when the link is out of view. Rebuild guides
  to pick up the fix.

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

## v0.11.0

- New Topic References no longer include a "How this document is maintained"
  section or the process working decisions WD-1 and WD-2. How Topic References
  are maintained is described once, in the shared guidance and each
  repository's `README.md` and `CONTRIBUTING.md`. Existing Topic References may
  remove that section and those decisions.

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

## v0.7.0

- Show comment review states, dispositions, change notes, closed threads, and
  flagged review areas in connected guides.
- Add permission-based author controls for disposition, closing, deletion,
  orphan re-attachment, and review flags, with conflict handling.
- Replace blocking comment confirmations with in-page prompts and expand the
  mock comments service and browser checks for author review.

## v0.6.0

- Guides can use a validated `comments` setting to select browser-local or
  signed-in hub comments. The hub mode supports PKCE sign-in, threads, replies,
  editing, withdrawal, attribution, deep links, and background refreshes.
- A standard-library mock comments service and contract checks cover sign-in,
  CORS, incremental refresh tombstones, edit windows, and reply depth.
- Topic Reference guidance explains where comments are stored in each mode.

## v0.5.1

- Reading copies remove review anchors without leaving an extra blank line
  between the surrounding Markdown blocks.
- Upgrading to v0.5.x may expose a duplicate HTML ID that an earlier guide
  build silently allowed. Give one of the colliding headings a unique explicit
  ID, such as `## Representations {#related-representations}`; because a heading
  ID is also an anchor name, keep it stable as content changes.

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

## v0.3.0

- PowerPoint support: the AIRA rapid presentation template (18 layouts, author
  names removed, sample photograph replaced with a placeholder), its layout
  contract, the build checklist, and `tools/build_rapid_presentation.py` with an
  example slide source. Requires `python-pptx` (`requirements-pptx.txt`).
- The presentation generator now accepts a subtitle on Section layouts, which
  use a body placeholder for it, and slides without a title on Blank layouts.

## v0.2.1

- Fix: the comment box in the web guide was hidden, so typing was invisible.

## v0.2.0

- Web guide: `tools/build_guide.py` builds a self-contained HTML page styled
  with the AIRA Web theme (aira-web 0.1.13) to match InteropHub, with a section
  bar, a right rail that follows the reader, a status tag, and a return link to
  the project's InteropHub topic. Settings come from the project's `guide.json`.
- On-page comments saved in the reader's browser, downloadable and loadable as
  JSON. `tools/import_guide_comments.py` turns downloaded files into a review
  record.

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
