# Rapid Presentation Template

`AIRA Rapid Presentation Template.pptx` is a small, predictable PowerPoint
starter with AIRA styling for building presentations from a content project.
It has 18 named layouts in two color families, Green and Blue, and one specimen
slide for each layout. [aira-rapid-presentation.yml](aira-rapid-presentation.yml)
describes the layouts, their placeholders, and the generation rules, and
[the checklist](../../guidance/PowerPointTemplateChecklist.md) records how the
template was made.

The public copy differs from AIRA's internal copy in two ways: author names are
removed from the file properties, and the sample photograph on the specimen
slides is replaced with a plain "Sample image" placeholder.

## Generate a deck

`tools/build_rapid_presentation.py` opens the template, removes the specimen
slides, and adds slides from a JSON source. Each slide names a layout and gives
its title, optional subtitle, content for each content placeholder in order,
speaker notes, and the source files it draws on. The core release and sources
are written into the speaker notes for traceability. See
[example-slides.json](example-slides.json).

```powershell
py -3.12 -m venv .venv-pptx
.\.venv-pptx\Scripts\python.exe -m pip install -r process\requirements-pptx.txt
.\.venv-pptx\Scripts\python.exe process\tools\build_rapid_presentation.py `
    --template "process\templates\powerpoint\AIRA Rapid Presentation Template.pptx" `
    --source products\my-deck\slides.json `
    --output output\my-deck.pptx
```

Notes on the source format:

- `title` is required except on Blank layouts, which have no title.
- On Title layouts `subtitle` fills the subtitle; on Section layouts it fills
  the orienting sentence under the section title.
- `content` has one list of text blocks for each remaining content placeholder,
  in placeholder order. Comparison layouts take four: left heading, left
  content, right heading, right content. A block has `text`, and optionally
  `level` for indentation and `bold`.
- Images and diagrams are added by hand after generation, using Title and Two
  Content, Title Only, or Blank layouts, or placed by the `image` pattern.

## Slide patterns

Bullet layouts alone make for flat decks. A slide can instead name a
`pattern`, which draws a more expressive slide from structured fields: native,
editable shapes, tables, and charts on the template's Title Only, Blank, or
Title Dark layout, so the AIRA band, logo, fonts, and colors stay. Set
`"family": "Blue"` or `"Green"` at the top of the source; a slide may override
it. Pattern slides take `speaker_notes` and `sources` like any other slide.
[example-patterns.json](example-patterns.json) uses every pattern.

| Pattern | Use it to | Fields |
|---|---|---|
| `statement` | State one big idea | `text`, optional `eyebrow` |
| `big_numbers` | Make 1–4 figures land | `title`, `stats`: `value`, `label`, optional `detail` |
| `quote` | Let a voice carry the point | `text`, `attribution`, optional `role` |
| `split` | Pair a key message with 1–4 supporting points | `message`, `items`: optional `lead`, `text`; optional `eyebrow` |
| `cards` | Show 2–4 parallel ideas | `title`, `cards`: `heading`, `text`; `numbered` (default true) |
| `grid` | Show four categories | `title`, `cells`: exactly 4 `heading`, `text` |
| `agenda` | Number 2–6 topics | `title`, `items`: `heading`, optional `detail` |
| `process` | Show 3–5 ordered steps | `title`, `steps`: `label`, optional `text` |
| `timeline` | Show 3–6 milestones | `title`, `milestones`: `when`, `text` |
| `image` | Lead with a picture | `title`, optional `eyebrow`, `caption`, `image` (path relative to the source file), `alt` (required with `image`) |
| `takeaway` | Close a point with its conclusion | `title`, `takeaway`, optional `points` (up to 4), `label` |
| `table` | Compare across 2–6 columns, up to 7 rows | `title`, `columns`, `rows`, optional `column_widths` (relative) |
| `chart` | Show data as a native chart | `title`, `chart`: `type` (`bar`, `column`, `line`), `categories`, `series` (1–4 of `name`, `values`), optional `number_format`, `data_labels`; optional `callout`: `value`, `text` |
| `before_after` | Contrast two states | `title`, `before` and `after`: `label`, `heading`, `points` (up to 4) |
| `closing` | End on the title art | `title`, optional `subtitle` |

The generator stops with an error when a pattern is given more items than it
can lay out, and prints a warning when text is likely to overflow its space;
shorten the text or split the slide. Text on filled panels is white or dark
blue, whichever contrasts better, so the Green family puts dark blue text on
green.

Generated slides stay editable. Follow the brief, outline, and manifest steps in
[the process](../../guidance/Process.md) before generating a deck.
