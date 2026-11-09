# Repository Instructions

## What this repository is

{{PROJECT_IDENTITY}}
{{GUIDE_ROLE}}

{{REPOSITORY_RULES}}

## Authority

- Markdown in `content/`, with `{{ASSEMBLY}}.qmd`, `_quarto.yml`, and cited
  assets, is the canonical source for the core document.
- `content/infographic.yml` is the canonical source of the primary
  infographic. Each label condenses the section its `ref` names and adds
  nothing to it; when a section changes, check the labels that refer to it.
- `{{ASSEMBLY}}.qmd` defines section order. `CoreDocument.md` is generated;
  never edit it directly.
- Files in `output/` are generated artifacts, not source.
- Comments made on the web guide, in GitHub issues, in meetings, or on other
  copies are review inputs. Adjudicate accepted changes into `content/`.

## Writing the source

- Keep the source concise. State each fact, rule, code, and decision in one
  place and link to it from elsewhere. Do not restate tables in prose, add
  recaps, or repeat the open-questions table in a section.
- Keep the document to about six top-level chapters, including the appendix.
  Merge short or related chapters and use second-level headings within them.
- These limits apply to `content/` only. Derived products may repeat and
  expand as their audience needs.

## Status and certainty

- Until a maintainer releases a version as final, this is a working draft.
  Never describe it, or any part of it, as a standard, approved, balloted,
  adopted, or final unless a maintainer has said so.
- Working decisions are current positions for discussion. Record each in
  `content/90-working-decisions.md` with its basis.
- Do not silently introduce a new claim, decision, commitment, number, owner,
  date, or change in certainty. Mark it with `<!-- CONFIRM: ... -->` beside the
  affected text for human resolution.
- When sources conflict, record an open question rather than choosing silently.
  Later sources are not automatically more authoritative.

## Project boundaries

<!-- CONFIRM: State what this topic owns, what belongs to related topics or
projects, and any rules specific to this subject. -->

- Do not create clinical policy or silently settle open design questions.

## Shared templates

{{SHARED_TEMPLATES_RULE}}

## Validation

- After editing `content/` or `{{ASSEMBLY}}.qmd`, run
  `python process/tools/build_core_markdown.py --assembly {{ASSEMBLY}}.qmd`,
  then `validate.ps1`.
- Run `build.ps1` and open `output/guide/index.html` before any release.
- Review the `CONFIRM` list printed by the content check.
- Successful generation is a mechanical check, not editorial approval.
- Do not commit, push, tag, publish, or update InteropHub without explicit
  instruction.
