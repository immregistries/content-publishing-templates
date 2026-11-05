# Infographic assets

Openly licensed files used by `tools/infographic.py` to draw the primary
infographic. They are embedded in, or drawn into, every rendered image, so
only files that may be redistributed publicly belong here.

## Fonts

`fonts/` holds Open Sans, AIRA's brand typeface, regular (400) and bold (700),
latin subset, in WOFF format:

- Source: the `@fontsource/open-sans` npm package, version 5.1.0
  (`files/open-sans-latin-400-normal.woff`, `files/open-sans-latin-700-normal.woff`).
- License: SIL Open Font License 1.1, in [fonts/OFL.txt](fonts/OFL.txt).
  Copyright 2020 The Open Sans Project Authors.

The renderer embeds the files in each SVG under the family name
"Open Sans Infographic", so an SVG placed inline in the guide does not change
the page's own fonts. It reads the advance widths from the same files to wrap
text, so the layout and the browser's rendering agree. Characters outside the
latin subset are estimated, and the browser check catches any overflow.

## Icons

`icons/` holds a subset of [Lucide](https://lucide.dev) stroke icons, drawn on
a 24-unit grid:

- Source: the `lucide-static` npm package, version 0.460.0 (`icons/<name>.svg`).
- License: ISC, with portions under MIT from Feather, in
  [icons/LICENSE](icons/LICENSE).

Each file was reduced to its geometry: only `path`, `circle`, `rect`,
`line`, `polyline`, `polygon`, and `ellipse` elements and their geometry
attributes are kept, under a fixed `<svg>` wrapper. No scripts, styles, or
links are allowed.

To add an icon, take it from the same Lucide release, reduce it the same way,
and keep the file name. An idea in `content/infographic.yml` names an icon by
its file name without `.svg`; the content check rejects names not here.

Available icons: archive, book-open, building-2, calendar, circle-check,
circle-help, clipboard-check, compass, database, file-text, flag, git-branch,
globe, graduation-cap, handshake, layers, layout-grid, lightbulb, link,
list-checks, map, megaphone, message-square-text, messages-square, network,
package, pen-line, presentation, puzzle, recycle, repeat, rocket, scale,
search, settings, share-2, shield-check, target, users, workflow.
