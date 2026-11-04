# {{TITLE}}

{{STATUS_NOTICE}}

<!-- CONFIRM: In one or two paragraphs, say what this topic is and why it
matters. -->

This repository is the Topic Reference for
[{{TOPIC_NAME}}, InteropHub topic {{TOPIC}}]({{TOPIC_URL}}). It records where
the topic currently stands: its definitions, principles, diagrams, working
decisions, and open questions.

## Start here

{{README_READ}}
2. See the [working decisions and open questions](content/90-working-decisions.md).
3. Read [how to contribute](CONTRIBUTING.md).

## What belongs here, and what does not

<!-- CONFIRM: State what this project covers and what belongs to related
topics or projects. -->

{{README_COORDINATION}}
[{{TOPIC_NAME}}, topic {{TOPIC}}]({{TOPIC_URL}}). Meetings, agendas, and
discussion notes are tracked there.

## Build

Initialize the shared templates after cloning:

```powershell
git submodule update --init
```

Then build the reading copy, Word and HTML review copies, and the web guide in
`output/`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Validate source and generated files:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\validate.ps1
```

{{README_PUBLISHING}}

## Repository structure

```text
content/            canonical Markdown for the core document
products/           derived products, including the web guide
review/             review inputs awaiting adjudication
sources/            list of source material and how it is used
process/            submodule: shared public templates and tools
output/             generated files; not committed
{{ASSEMBLY}}.qmd    assembly authority for section order
CoreDocument.md     generated single-file reading copy
guide.json          web guide settings
```
