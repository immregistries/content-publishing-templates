# {{TITLE}}

{{STATUS_NOTICE}}

<!-- CONFIRM: In one or two paragraphs, say what this topic is and why it
matters. -->

{{README_IDENTITY}}

## Start here

{{README_READ}}
2. See the [working decisions and open questions](content/90-working-decisions.md).
3. Read [how to contribute](CONTRIBUTING.md).

## What belongs here, and what does not

<!-- CONFIRM: State what this project covers and what belongs to related
topics or projects. -->

{{README_COORDINATION}}

## Build

{{README_BUILD_SETUP}}

Build the reading copy, Word and HTML review copies, and the web guide in
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
process/            {{PROCESS_ROLE}}
output/             generated files; not committed
{{ASSEMBLY}}.qmd    assembly authority for section order
CoreDocument.md     generated single-file reading copy
guide.json          web guide settings
```
