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
