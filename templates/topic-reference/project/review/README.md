# Review Inputs

Feedback arrives as GitHub issues, comments on the published Topic Reference,
meeting discussion, and comments on generated Word or HTML documents. None of
it changes the Topic Reference until it is adjudicated into `content/`.

- **GitHub issues** are the preferred record. Link the issue from the working
  decision or content change it produced.
- **InteropHub discussion notes and meeting feedback** are summarized as a
  GitHub issue, or, when several points arrive together, in a dated file here
  such as `2026-11-15-community-call.md`. Record the substance and source, not
  personal details.
- **Comments made on the web guide** are downloaded as JSON and turned into a
  dated review record with
  `python process/tools/import_guide_comments.py <files>`.
- **Comments in generated documents** are transcribed the same way. Do not edit
  the generated document as if it were source.

When a review input is resolved, note the outcome: accepted into `content/`,
recorded as a working decision, kept as an open question, or declined with a
reason.
