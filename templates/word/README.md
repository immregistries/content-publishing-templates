# Word Reference Document

`aira-reference-document.docx` gives Quarto-built Word documents AIRA styles,
headers, and footers. It contains no body text; Pandoc uses only its styles and
page setup.

## Use in a project

In the project's `_quarto.yml`:

```yaml
format:
  docx:
    reference-doc: process/templates/word/aira-reference-document.docx
```

The template's "Status Notice" paragraph style shades the status notice at
the top of a Topic Reference's Executive Summary.

## Topic Reference filter

`topic-reference.lua` makes the Word document match the web guide. A Topic
Reference lists it under the docx format in `_quarto.yml`:

```yaml
format:
  docx:
    filters:
      - process/templates/word/topic-reference.lua
```

It writes each change marker for the current version as an italic note above
what it covers ("Changed in v0.5.0: ...", with "Feedback wanted." first for a
feedback marker) and drops older ones; gives the status notice the "Status
Notice" style; adds "What changed in v0.5.0" before the Scope heading; and turns
the Scope's In scope and Out of scope lists into a two-column table, with Not
yet decided as a full-width row. The current version comes from the
`change-version` metadata, which `build.ps1` passes:

```powershell
$changeVersion = & $python.Source .\process\tools\change_markers.py --current-version
& $quarto.Source render -M "change-version:$changeVersion"
```

Without it, every marker is shown. `insert_word_infographic.py` then places
the infographic before the Scope heading.

Pandoc cannot assign a table style, so after `quarto render` the project's
`build.ps1` applies the template's AIRA 2 table style to every table:

```powershell
& $python.Source .\process\tools\apply_word_table_style.py .\output\<Document>.docx
```

## Changing the template

Edit the template here, not in a project, and remove author metadata before
committing. Projects pick up the change when they choose by moving their
`process/` pointer, rebuilding, reviewing the output, and committing. Keep the
`AIRA2` table style ID, or update `tools/apply_word_table_style.py` and its
callers together.
