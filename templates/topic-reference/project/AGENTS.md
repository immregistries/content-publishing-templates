# Repository Instructions

## What this repository is

- This is the Topic Reference for InteropHub topic {{TOPIC}},
  [{{TOPIC_NAME}}]({{TOPIC_URL}}): the current, versioned statement of the
  topic's definitions, principles, diagrams, working decisions, and open
  questions. See `process/guidance/TopicReference.md`.
- The published Topic Reference is the web guide, `output/guide/index.html`,
  built by `process/tools/build_guide.py` with the shared AIRA Web template and
  published to {{PAGES_URL}}latest/ by `.github/workflows/publish-guide.yml`.
  Do not write a separate HTML page, stylesheet, or site generator.
  `output/{{ASSEMBLY}}.html` is Quarto's review copy, not the published page.

## Public repository

- This repository is public. Everything committed here may be read, copied,
  and indexed by anyone.
- Do not commit private material: internal plans, funding or partner
  proposals, contact information, email, meeting recordings, unpublished
  partner data, credentials, or personal metadata in Office files.
- Source material in private working folders is not copied here. Draw on it by
  writing reviewed, public-safe prose in `content/`.

## Authority

- Markdown in `content/`, with `{{ASSEMBLY}}.qmd`, `_quarto.yml`, and cited
  assets, is the canonical source for the core document.
- `{{ASSEMBLY}}.qmd` defines section order. `CoreDocument.md` is generated;
  never edit it directly.
- Files in `output/` are generated artifacts, not source.
- Comments made on the web guide, in GitHub issues, in meetings, or on other
  copies are review inputs. Adjudicate accepted changes into `content/`.

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

- `process/` is a Git submodule of
  `immregistries/content-publishing-templates`, pinned to a release tag. Do not
  edit or copy files under it. Adopt changes by moving the pointer, rebuilding,
  reviewing the output, and committing.

## Validation

- After editing `content/` or `{{ASSEMBLY}}.qmd`, run
  `python process/tools/build_core_markdown.py --assembly {{ASSEMBLY}}.qmd`,
  then `validate.ps1`.
- Run `build.ps1` and open `output/guide/index.html` before any release.
- Review the `CONFIRM` list printed by the content check.
- Successful generation is a mechanical check, not editorial approval.
- Do not commit, push, tag, publish, or update InteropHub without explicit
  instruction.
