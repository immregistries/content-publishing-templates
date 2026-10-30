# Topic Reference Skeleton

The starting point for a new Topic Reference project. Do not copy it by hand;
create a project with `tools/new_topic_reference.py`, which fills in the
project's names, renames the files that cannot be stored under their real names
here, generates the reading copy, and adds the shared templates as the
`process/` submodule:

```powershell
python tools/new_topic_reference.py ..\immunization-cds `
    --title "Immunization CDS (ImmDS + HALO)" --topic 1 `
    --topic-name "Immunization CDS (ImmDS + HALO)" --assembly ImmunizationCDS
```

See [the Topic Reference guidance](../../guidance/TopicReference.md) for what a
Topic Reference is and what to do after the project is created.

## Files

| Path | Purpose |
|---|---|
| `project/` | Every new project. `Project.qmd` is renamed for the project, and `_gitignore` and `_github/` become `.gitignore` and `.github/`. |
| `optional/presentation/` | Added with `--with presentation`: scripts to set up and build a review deck with the shared PowerPoint template. The brief and slide source are copied from `templates/product/` and `templates/powerpoint/`. |

Placeholders such as `{{TITLE}}` are replaced when a project is created.
Text the authors must write is marked with `CONFIRM` notes, which the content
check lists until they are resolved.

A Confluence product is not part of the skeleton yet. A project that publishes
Confluence pages adds a `products/confluence/` brief and manifest of its own.
