# Content Publishing Templates

Shared, public templates and tools for source-first content projects: documents
whose authoritative source is Markdown, built into a complete core document and
reused in derived products such as presentations and web pages.

This repository is the public counterpart of AIRA's internal content publishing
process. It holds only what public projects need to build, and it may evolve
independently of the internal version.

> **Status:** Early and evolving. The templates currently carry AIRA branding.
> Whether public community projects should keep that branding or diverge is an
> open decision.

## What is here

```text
guidance/          the process and the conventions content projects follow
templates/word/    Word reference document for Quarto builds (AIRA styles)
templates/product/ starting points for content modules, product briefs, and manifests
tools/             build and validation tools shared by content projects
tests/             a minimal fixture project used to test the tools
```

Start with [the process](guidance/Process.md) and
[the conventions](guidance/Conventions.md).

## Use in a content project

Add this repository as a Git submodule at `process/`, pinned to a release tag:

```powershell
git submodule add https://github.com/immregistries/content-publishing-templates.git process
git -C process checkout v0.1.0
```

Clone a project that uses it with `git clone --recurse-submodules`, or run
`git submodule update --init` in an existing clone. A change here reaches a
project only when that project moves its pointer, rebuilds, reviews the output,
and commits. Do not edit or copy files under `process/` from within a project.

The project's `_quarto.yml` uses the Word reference document:

```yaml
format:
  docx:
    reference-doc: process/templates/word/aira-reference-document.docx
```

From the project root, the shared tools are run as:

```powershell
# Generate, or verify, the single-file GitHub reading copy, CoreDocument.md.
# The title and subtitle come from the assembly file's front matter.
python process/tools/build_core_markdown.py --assembly Project.qmd
python process/tools/build_core_markdown.py --assembly Project.qmd --check

# Check maintained Markdown for broken links, placeholders, and CONFIRM notes.
python process/tools/check_content.py

# After quarto render, give every Word table the template's table style.
python process/tools/apply_word_table_style.py output/Project.docx
```

Building Word and HTML output requires [Quarto](https://quarto.org/). The tools
require Python 3.12 or later and no other packages.

## Releases

Projects pin to tags such as `v0.1.0`. Changes to a template's appearance or to
a tool's behavior get a new tag and a note in [CHANGELOG.md](CHANGELOG.md).

## License

- Tools and other code are licensed under the [Apache License 2.0](LICENSE).
- Guidance and template text are licensed under
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The licenses do not grant rights to use the AIRA name or brand to represent a
  document as an AIRA publication.
