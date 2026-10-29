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
  Content, Title Only, or Blank layouts.

Generated slides stay editable. Follow the brief, outline, and manifest steps in
[the process](../../guidance/Process.md) before generating a deck.
