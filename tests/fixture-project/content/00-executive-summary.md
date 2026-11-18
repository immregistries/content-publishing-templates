# Executive Summary

::: {.status-notice}
**Status:** Test fixture for the shared tools. Nothing here is guidance.
:::

<!-- anchor: fixture-introduction -->

This fixture exercises the shared build and check tools. See the
[detail section](01-detail.md).

<!-- changed v0.2.0: Says how positions are counted within an area. -->

This second paragraph verifies positions within one anchor area.

This third paragraph supports legacy comment placement checks.

- The fixture also includes a commentable list.
- Its position follows the paragraphs in the same area.

The anchor syntax can be shown literally in fenced code:

```markdown
<!-- anchor: fixture-introduction -->
```

This summary is long enough to pass the length check without a warning. It
stands in for the one-page overview a Topic Reference gives a reader who reads
nothing else: what the topic is, why it matters, what the document decides,
and what is still open. The build places it first, above the chapters, with
the status banner above it, the list of what changed in this version after
it, then the primary infographic when there is one, and then the scope. None
of these parts has an entry in the section bar, and none counts as a chapter.
Comments, review flags, and change markers work here as they do anywhere else.
