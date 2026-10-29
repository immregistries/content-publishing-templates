# Repository Instructions

## Purpose

- This public repository supplies shared templates and tools to content
  projects, which consume it as a pinned Git submodule at `process/`.
- It is the public counterpart of AIRA's internal content publishing process
  and may diverge from it. Do not copy internal material here.

## Public repository

- Everything committed here is public. Do not add project content, internal
  plans, communication strategy, private URLs, names, or personal metadata.
- Strip author and editor metadata from Office files before committing them.

## Changing templates and tools

- Keep the tools generic. Project names, titles, and paths come from arguments
  or the project's own files, never from constants here.
- Keep the tools free of third-party Python dependencies, except the PowerPoint
  generator, which uses the pinned `python-pptx` in `requirements-pptx.txt`.
- Strip author names from Office files and use only images that may be
  redistributed publicly.
- Keep the `AIRA2` table style ID in the Word reference document, or update
  `tools/apply_word_table_style.py` and its callers together.
- `templates/guide/aira.css` and the logo are copies from `immregistries/aira-web`.
  Do not edit them; replace them from a named aira-web release and record the
  version in `templates/guide/README.md` and the changelog. Guide-specific
  styling goes in `guide.css`.
- A change that alters built output or tool behavior needs a CHANGELOG entry and
  a new release tag. Projects adopt it deliberately.

## Validation

- Run `validate.ps1`. It tests the tools against `tests/fixture-project/`.
- After changing `build_core_markdown.py`, regenerate the fixture's reading copy
  and review the difference.
- Do not commit, push, tag, or publish without explicit instruction.
