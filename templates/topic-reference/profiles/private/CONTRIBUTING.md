# Contributing

{{TITLE}} is AIRA internal working material; see
[INTERNAL-USE.md](INTERNAL-USE.md). Questions, objections, examples, and
proposed wording from AIRA staff and authorized collaborators are welcome.

## Ways to take part

- **Open an issue** in this repository to raise a question, challenge a
  working decision, or share an experience. Issue templates are provided for
  general feedback and for proposing or challenging a working decision.
- **Join the discussion** on InteropHub,
  [{{TOPIC_NAME}}, topic {{TOPIC}}]({{TOPIC_URL}}), which is visible only to
  people who may see the topic.
- **Comment on the Topic Reference.** Build it and open
  `output/guide/index.html`. Comments stay in your browser until you download
  them. Share the downloaded file with the maintainers, for example by
  attaching it to an issue.
- **Propose a change** with a pull request against the Markdown in `content/`.
  Explain the reasoning in the pull request description. Substantive changes
  are usually easier to agree on in an issue first.

## How changes are decided

The maintainers consider feedback, discuss it where needed, and record the
outcome in `content/90-working-decisions.md`. A working decision is the
current position for discussion, and it can be revisited.

## Pull request checklist

- Edit files in `content/`, not `CoreDocument.md` or anything under `process/`.
- Regenerate the reading copy:
  `python process/tools/build_core_markdown.py --assembly {{ASSEMBLY}}.qmd`.
- Run `validate.ps1`, or let GitHub Actions run the same checks.
- Do not include credentials, personal health information, or other personal
  information.

Contributions become part of this repository's internal working material and
are covered by [INTERNAL-USE.md](INTERNAL-USE.md).
