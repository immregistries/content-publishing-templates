# Web Guide Template

The web guide is the format in which a Topic Reference is published, and it can
be used for other core documents too.

`tools/build_guide.py` builds a single, self-contained HTML page from a content
project's core document, styled to match InteropHub:

- the AIRA header, with a "Return to InteropHub" link to the project's topic;
- the topic title, subtitle, a status tag such as DRAFT, and the version;
- a dark, sticky section bar with one entry per top-level section, and at its
  right end a strip that counts comments, review items, and changes;
- a right rail for navigation only: the current section's subsections, which
  follow the reader's scroll, and links to the topic and source;
- an [annotations panel](#annotations-panel) on the left, closed by default,
  with Comments, Review, and Changes tabs;
- for a Topic Reference, a front section above Chapter 1: the status notice
  as a banner, the Executive Summary, "What changed" in this version (from the
  [change markers](#change-markers)), the primary infographic, and the Scope
  as cards. It has no section-bar entry; while the reader is in it, the right
  rail lists its parts, and the title links back to the top;
- comments that readers add beside any paragraph, list item, quote, table, or
  diagram;
- [Mermaid diagrams](../../guidance/Conventions.md#diagrams), drawn in the page;
- a build manifest in the page's `<head>`, a
  `<script type="application/json" id="guide-build-manifest">` element that
  records the release of these templates, the document's version and status,
  how and when it was built, its structure, and the content check findings,
  each warning with a stable code. InteropHub saves it when the guide is
  published; see
  [Saving the build manifest](../../guidance/TopicReference.md#saving-the-build-manifest).

## Annotations panel

Comments, review flags, and change markers share one panel.

- **The strip** at the right end of the section bar reads
  `Comments n · Review n · Changes n`. A count of zero is dimmed; a dash means
  the count is not known yet (a reader who has not signed in). Clicking a count
  opens the panel on that tab; clicking it again closes the panel.
- **The panel** slides in from the left and pushes the reading column over on
  screens 900 px and wider. Below 900 px it is a bottom sheet. Esc or the close
  button closes it and returns focus to the strip.
- **Resizing.** On wide screens, drag the panel's right edge to make it wider
  or narrower, from 280 px up to 640 px, or less if the reading column would
  get narrower than 640 px. Double-click the edge to return to 340 px. The edge
  can also be focused: Left and Right resize it in steps (larger with Shift),
  and Home resets it. The width is remembered per document with the tab. When
  the panel leaves too little room beside the text, the right rail moves under
  it.
- **The tabs:**

  | Tab | Lists, by section in reading order | Filters |
  |---|---|---|
  | Comments | Threads with their replies and controls, then "Not placed" | Open / All, Mine |
  | Review | InteropHub review flags and "feedback wanted" change markers | Open / All (flags) |
  | Changes | Every change marker | none |

  Each item starts with a link to its place in the text, which scrolls there
  and highlights it briefly. Author controls (disposition, close, reply, edit
  or clear a flag, re-attach a comment that is not placed) work in the panel.
  "Mine" lists threads the reader started or replied to, using the hub's
  `mine` field, or the reader's name in local-comments mode.
- **One layer at a time.** The open tab decides what the text shows: comment
  counts beside each commented block (Comments), purple flag and
  feedback-wanted badges and bars (Review), or change badges and bars
  (Changes). With the panel closed, the text shows only faint ticks in the left
  margin where something is annotated. The comment and flag buttons still
  appear on hover.
- **Links and memory.** `?lens=comments`, `?lens=review`, or `?lens=changes`
  opens the guide with the panel on that tab, so a release email can link
  straight to the changes. The last tab and whether the panel was open are
  remembered per document in local storage; a `?lens=` link overrides them.
- **Accessibility.** The strip buttons carry `aria-controls` and
  `aria-expanded`; the tabs are a `tablist` with `aria-selected` and arrow-key
  movement; the panel is a labeled region. In a list, Up and Down move between
  items. Badges carry text, so no marker relies on color alone.

## Versions and comment modes

A guide that uses InteropHub comments sends its own address (`pageUrl`) with
every comment, reply, and review flag, and with every read and refresh.
InteropHub turns the address into the guide's label (such as `v0.2.0` or
`main`), records each new item's label, and answers with that label's comment
mode (InteropHub's API contract, 5.3.1 and 5.4.1):

- **Open:** everything is shown, as before.
- **Release:** the Comments tab says it shows comments for this release and
  earlier. Readers see only those. Authors see every comment; those from
  another version are marked "From another version (label)" and are left out
  of the counts. Authors also see the label each item was written on.
- **Closed:** no comments or review flags, no comment or flag buttons, and the
  line "Comments are closed on this version." If a version is closed while
  someone is writing, the save is refused; the text stays in the form and in
  the browser, as for a blocked request.
- A page InteropHub does not recognize behaves as before.

Authors set each label's display state and comment mode on the guide's
settings page in InteropHub, or when publishing with `publish_guide_to_hub.py
--display … --comment-mode …`.

## Change markers

Change markers say what changed in this version of the document, either for
information ("changed") or as a request for feedback ("feedback"). They are
written in the source (see the Topic Reference guidance), and `build_guide.py`
writes the ones for the current version into the page as a JSON list.
`guide.js` draws the badges and bars and lists them in the panel.

The element sits in the body, before `guide-data`:

```html
<script type="application/json" id="guide-change-markers">
[
  {"anchor": "consent-requirements", "version": "v0.5.0", "level": "changed",
   "note": "Consent now follows the state rule; former rule 3 removed."},
  {"anchor": "consent-requirements", "blockIndex": 2, "version": "v0.5.0",
   "level": "feedback", "note": "New exception for school-based clinics."},
  {"anchor": "oq-13", "version": "v0.5.0", "level": "changed",
   "note": "Reworded after the October call."}
]
</script>
```

| Field | Required | Meaning |
|---|---|---|
| `anchor` | yes | The review-area anchor the marker covers, the same names comments and review flags use: a section's ID, a `<!-- anchor: -->` name, or a row anchor. |
| `blockIndex` | no | Narrows the marker to one block of the area: the block's position, counted from 0, as in the block's `data-block-index`. Without it the marker covers the whole area. |
| `version` | yes | The release label the change belongs to, such as `v0.5.0`. |
| `level` | yes | `changed` (for information) or `feedback` (feedback wanted). |
| `note` | yes | What changed, in plain text, at most 300 characters. |

What a marker covers depends on its anchor:

- a **section ID** covers the whole section, and its badge sits under the
  heading;
- a **row anchor** covers that row, and its badge sits in the row's first cell;
- any **other anchor** covers the blocks of its area, or the one block
  `blockIndex` names, and its badge sits before the first of them.

Rules for the build:

- Emit only the markers to show: those for the current version. The page shows
  every marker it is given and does not compare versions.
- List the markers in document order. A marker before a heading uses the
  section's ID; a marker before a block uses the area's anchor and the block's
  `blockIndex`; `rows=` becomes one marker per row anchor.
- Leave the element out when there are no markers; the page treats a missing
  element as an empty list.
- Escape `</` as `<\/` inside the JSON.

A marker whose anchor is not in the page is listed under "Not placed" in the
panel and is not drawn in the text; the build should treat it as an error.
Malformed entries are skipped with a console warning.

The markers are written in the source as `<!-- changed v0.5.0[ feedback][
rows=A,B]: note -->` (see `tools/change_markers.py` and the Topic Reference
guidance). `build_guide.py` resolves each to its area and block from where it
sits, keeps those for the current version, and fails on one it cannot place.

## Comments

Comments are saved only in the reader's browser (local storage), so nothing is
sent anywhere. A reader can download their comments as JSON and load other
people's files to see everyone's comments together; loading merges by comment
ID. The name, load, download, and clear controls are in the panel's Comments
tab. Each comment records the document version, section, paragraph position,
the start of the paragraph's text, and any quoted selection, so it can be placed
again after the text changes. A comment that can no longer be placed is listed
in the panel under "Not placed."

`tools/import_guide_comments.py` turns one or more downloaded files into a dated
Markdown review record in the project's `review/` folder.

## Files

| File | Purpose |
|---|---|
| `aira.css` | AIRA Web theme stylesheet, copied from `immregistries/aira-web` version 0.1.13 (commit 330811d). Update it deliberately and note the version here and in the changelog. |
| `AIRA_2018Logo_BlueGreen_Hor.png` | AIRA logo, from the same aira-web release. |
| `guide.css` | Reading layout, annotations panel, and comment styles, composed on the AIRA Web classes. |
| `guide.js` | Section tracking, the annotations panel, change markers, and comments. No external libraries. |
| `mermaid/` | [Mermaid](https://github.com/mermaid-js/mermaid) 11.12.0 (`dist/mermaid.min.js` from the npm package) and its MIT license. The guide inlines it only when the document has diagrams, and `guide.js` starts once they are drawn. It is the version Quarto 1.10 bundles, so the guide and the Word document draw diagrams alike; update it deliberately with Quarto and note the version here and in the changelog. |

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
