# Changelog

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
