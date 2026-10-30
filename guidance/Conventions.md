# Conventions

These conventions are the initial working rules. They are intentionally small
and are expected to change as projects test them.

## 1. Project and core-document boundary

1. A project has one primary goal and one bounded body of knowledge.
2. The canonical Markdown source must collectively build one complete core
   document.
3. Substantive project knowledge must have a place in the core document: main
   text, appendix, footnote, or referenced evidence.
4. If a body of knowledge cannot be deployed as one coherent core document, it
   should normally be treated as more than one project.

## 2. Source, releases, and outputs

1. Markdown, referenced assets, citations, and build configuration are the
   authoritative source.
2. The complete document built from that source is the core document.
3. A numbered or tagged build of the core is a core release.
4. DOCX, PDF, and generated HTML are release artifacts; PPTX, briefs, and
   audience-specific webpages are normally derived products.
5. Comments and tracked changes in an artifact are review inputs, not final
   adjudication. Accepted changes go into canonical Markdown.
6. Do not make an output file the only location of a substantive correction.
7. Preserve source history in version control when the project is under version
   control.

## 3. Folder responsibilities

A content project should distinguish these responsibilities, even if it
combines some folders:

```text
content/          canonical Markdown source and assets for the core document
core/             assembly file and core-document configuration
briefs/           product specifications
products/         product-specific source, outlines, and manifests
templates/        organizational Word, web, and PowerPoint templates
tools/            build and validation scripts
output/           core release artifacts and derived deliverables
```

In current projects, `content/` holds the canonical source, a Quarto assembly
file at the root defines section order, and `products/` holds briefs, product
sources, and manifests together. Shared templates and tools come from this
repository at `process/`. Generated files go in `output/` and are not canonical
source.

## 4. File naming and releases

- Use descriptive mixed-case names for reader-facing Markdown documents and
  lowercase hyphenated names for machine-oriented files and product IDs.
- Retain `README.md` as the conventional repository entry point.
- Give briefs and products stable identifiers, such as
  `implementer-overview-10-slide`.
- Include audience or purpose in product names, not merely `presentation-1`.
- Put dates or version numbers in manifests and releases rather than creating a
  chain of names such as `final-final-v2`.
- Record the core release in every derived-product manifest.

## 5. Content modules

A content module should:

- cover one coherent idea;
- be understandable without relying on unexplained prose from another file;
- distinguish evidence from interpretation;
- retain citations close to the claims they support;
- state important limits, uncertainty, or scope;
- avoid product-specific openings, conclusions, and transitions where
  practical;
- use stable headings and plain language.

Every content module must have an intended location in the complete core
document. Modules organize the canonical source; they do not replace the core
with a free-standing knowledge library.

## 6. Product briefs

- A brief is required before a product is assembled.
- State the desired audience outcome, not only the topic.
- Treat length as a constraint, not a target that must be filled.
- Specify assumed knowledge to prevent both unexplained jargon and unnecessary
  background.
- List exclusions when omission is important or sensitive.
- Identify the core release and source files the product may draw from.
- Separate substantive content from product-specific delivery context.
- Record assumptions when the requester has not supplied a field.

## 7. Presentations

- Each slide has one primary communication job.
- Use assertion-style titles when practical.
- Start by building the argument, not by decorating slides.
- Keep delivery detail in speaker notes rather than shrinking text.
- Prefer an existing source diagram; describe a new visual before creating it.
- Do not invent quantitative graphics when the source does not support them.
- A short deck may omit nuance, but it may not reverse or overstate the source.
- Use a small approved set of named layouts from the organizational template.
- Generated slides must remain editable.
- Rapid presentations use a controlled starter PPTX derived from the original
  organizational template; the original remains the visual authority.
- Use real title, content, and picture placeholders rather than relying on
  agents to infer arbitrary text-box roles.
- Maintain one specimen slide for each supported layout during validation.
- Substantive innovation must flow through canonical Markdown before it becomes
  established project knowledge.

## 8. AI-assisted assembly

AI may:

- select and order relevant source material;
- summarize or restate it for the named audience;
- propose titles, transitions, speaker notes, and visuals;
- identify conflicts, repetition, and missing support;
- perform consistency and completeness checks.

AI must not silently:

- add a factual claim unsupported by the allowed source;
- turn a possibility or leaning into an organizational decision;
- create a commitment, sponsor, deadline, budget, or policy position;
- remove a limitation that materially changes a claim;
- fabricate a citation, quotation, result, or source;
- present draft material as approved.

New claims may be proposed, but they must be visibly marked for human review and
then added to maintained source if accepted.

## 9. Traceability

- Every derived product names its core release and source files.
- Every product has a manifest before release.
- Direct quotations retain an exact source location.
- Material numbers, dates, and named findings remain traceable to evidence.
- Product-only assertions are labeled until incorporated into common source.
- When source changes materially, affected products are reviewed.

## 10. Status and review

- Draft source can be used for experimentation but not silently represented as
  approved.
- Generated products remain drafts until a human approves them for a named use.
- Approval is contextual: internal discussion approval is not public-release
  approval.
- Unresolved placeholders must remain visible or cause a check to fail.
- Review inputs received in generated artifacts have no authoritative effect
  until adjudicated in canonical source or recorded as delivery context.

### Review anchors

- Write an anchor on a line by itself between Markdown blocks, in the form
  `<!-- anchor: stable-name -->`.
- Use lowercase letters and digits separated by single hyphens. Names must be
  unique across the complete document and must not duplicate a heading ID.
- Do not use `document-start` or a name beginning with `comment-` or `guide-`.
  Those names are reserved for the initial document area, comment deep links,
  and elements supplied by the web guide.
- Place anchors sparingly at natural review points; do not add one before every
  paragraph.
- Keep names stable when nearby wording changes or content moves.
- Agents that edit or reorganize canonical content maintain the anchors as part
  of the edit.

## 11. Edge-to-core feedback

- Derived products may expose missing ideas, better formulations, or new
  implications.
- Decide whether each innovation changes core knowledge or only delivery
  context.
- Core changes are made in canonical Markdown and included in a new build or
  release.
- Affected derivatives are reviewed or regenerated after a core change.
- Do not allow an improved presentation to become a competing source of truth.

## 12. Portability

- Use relative paths within a project wherever practical.
- Do not embed secrets, personal machine configuration, or private URLs.
- Keep project-specific examples clearly identified as examples.
- Maintain a README that explains dependencies and migration steps.
- Consume shared templates and tools from this repository as a pinned Git
  submodule at `process/`; do not copy them into projects. Update the pointer
  deliberately and review the rebuilt output.
- Keep project-specific content in the project, not in this reusable
  repository.


## 13. Terms

- **Topic Reference:** a content project whose bounded purpose is one
  InteropHub topic, and the published document it produces. Use this name for
  the document in links, on its page, and in project files. See
  [Topic References](TopicReference.md).
- **Web guide:** the single-page HTML format built by `tools/build_guide.py`.
  A Topic Reference is published as a web guide; other core documents may be
  too.
- Do not call a Topic Reference a guide, an implementation guide, a working
  guide, or a standard.
