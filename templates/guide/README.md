# Web Guide Template

The web guide is the format in which a Topic Reference is published, and it can
be used for other core documents too.

`tools/build_guide.py` builds a single, self-contained HTML page from a content
project's core document, styled to match InteropHub:

- the AIRA header, with a "Return to InteropHub" link to the project's topic;
- the topic title, subtitle, a status tag such as DRAFT, and the version;
- a dark, sticky section bar with one entry per top-level section;
- a right rail listing the current section's subsections, which follows the
  reader's scroll;
- comments that readers add beside any paragraph, list item, quote, or table.

## Comments

Comments are saved only in the reader's browser (local storage), so nothing is
sent anywhere. A reader can download their comments as JSON and load other
people's files to see everyone's comments together; loading merges by comment
ID. Each comment records the document version, section, paragraph position, the
start of the paragraph's text, and any quoted selection, so it can be placed
again after the text changes. A comment that can no longer be placed is listed
in the rail as "not placed."

`tools/import_guide_comments.py` turns one or more downloaded files into a dated
Markdown review record in the project's `review/` folder.

## Files

| File | Purpose |
|---|---|
| `aira.css` | AIRA Web theme stylesheet, copied from `immregistries/aira-web` version 0.1.13 (commit 330811d). Update it deliberately and note the version here and in the changelog. |
| `AIRA_2018Logo_BlueGreen_Hor.png` | AIRA logo, from the same aira-web release. |
| `guide.css` | Reading layout and comment styles, composed on the AIRA Web classes. |
| `guide.js` | Section tracking and comments. No external libraries. |

## Project settings

The content project supplies `guide.json`:

```json
{
  "id": "contextual-conditions",
  "documentType": "Topic Reference",
  "status": "Draft",
  "interophubTopic": 7,
  "repository": "https://github.com/immregistries/contextual-conditions",
  "license": "Content licensed CC BY 4.0",
  "navLabels": { "the-concept": "Concept" }
}
```

`documentType`, when present, is shown above the title and in the browser tab.
A Topic Reference uses `"Topic Reference"`; see
[the Topic Reference guidance](../../guidance/TopicReference.md).

Each included content file becomes a section whose ID is its file name without
the number prefix, so `03-the-concept.md` becomes `#the-concept`. `navLabels`
gives short names for the section bar; otherwise the section heading is used.
Links between content files become links within the page, and links to other
repository files point to GitHub at the version being built.
