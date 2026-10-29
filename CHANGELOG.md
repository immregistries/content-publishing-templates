# Changelog

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
