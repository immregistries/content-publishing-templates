# Topic References

A **Topic Reference** is the current, versioned statement of where an
InteropHub topic stands: its definitions, principles, diagrams, working
decisions, and open questions, in one document that people can read and refer
to in discussions and meetings, and that other tools can use.

It is the most common kind of content project built with these templates. The
same process and tools can be used for other kinds of documents.

## What a Topic Reference is not

- **Not a standard or a final decision by default.** Each release states its own
  status. Most releases are working drafts for community discussion; a release
  may be marked final when the community and maintainers say so.
- **Not an implementation guide.** HL7 implementation guides and other
  specifications are separate artifacts. A Topic Reference may explain their
  intent and link to them, but does not replace them.
- **Not the InteropHub topic.** Meetings, agendas, discussion notes, and
  followers stay on InteropHub. The topic's Overview introduces the topic; the
  Topic Reference is the document the topic works on.
- **Not a Confluence page.** Pages made for Confluence or elsewhere are copies
  built from the Topic Reference's source and are not edited on their own.

## How it relates to its InteropHub topic

- A topic has at most one Topic Reference, and a Topic Reference belongs to one
  topic. Related topics are linked, not merged.
- The InteropHub topic links to the Topic Reference beside its other links. The
  link always points to the latest release, `https://<owner>.github.io/<id>/latest/`.
- The published page links back to the topic ("Return to InteropHub").

## In terms of the process

A Topic Reference is a content project, as described in [the process](Process.md),
whose bounded purpose is one InteropHub topic:

- The Markdown in `content/` is the canonical source, and it builds the
  complete core document.
- The published Topic Reference is that core document built as a
  [web guide](../templates/guide/README.md) and published with GitHub Pages.
  The web guide is the format; the Topic Reference is what it publishes.
- `CoreDocument.md` is the single-file reading copy on GitHub. Word and Quarto
  HTML builds are review copies.
- Presentations, Confluence pages, and other copies are derived products, each
  with a brief and a manifest.

## What every Topic Reference contains

- **Status and scope** (`content/00-status-and-scope.md`): a short summary,
  purpose, what the project covers and does not cover, and how it is
  maintained.
- **Related work** (`content/01-related-work.md`): related InteropHub topics and
  other efforts, linked rather than repeated.
- **Topic sections** in reading order: definitions, principles, diagrams,
  examples, and whatever else the topic needs.
- **Working decisions and open questions** (`content/90-working-decisions.md`):
  each decision with an ID and its basis; each open question with the sources
  in tension and its status.
- **Status and version on the published page**, and a return link to the topic.
- **A way to comment**, on the page itself, through GitHub issues, and in
  meetings, with every comment treated as a review input until it is
  adjudicated into `content/`.

## Releases and status

- A release is a Git tag such as `v0.1.0`. Pushing the tag publishes the page at
  that version, `/v0.1.0/`, and at `/latest/`. Pushing to `main` publishes a
  preview at `/main/`.
- The status shown on the page comes from `status` in `guide.json`, such as
  `Draft`. Change it only when the maintainers decide a release has a different
  status.
- Earlier releases stay at their own addresses. How a topic presents an earlier
  official release alongside a later working draft is not settled yet.

## Feedback

Comments made on the published page stay in the reader's browser until they are
downloaded. Downloaded files are turned into a dated review record with
`tools/import_guide_comments.py`. Issues, meeting notes, and other feedback are
recorded the same way, and each outcome is noted: accepted into `content/`,
recorded as a working decision, kept as an open question, or declined with a
reason.

Named anchors in the Markdown divide the document into stable review areas.
They let a comment remain near its text as wording shifts and provide direct
links such as `#stable-name`; headings serve as anchors automatically. Content
before the first heading or named anchor belongs to the `document-start` area.
See [Review anchors](Conventions.md#review-anchors) for naming and placement.

## Starting a new Topic Reference

1. Create the project with the skeleton. Do not assemble one by hand:

   ```powershell
   python tools/new_topic_reference.py ..\<id> --title "<Title>" `
       --topic <number> --topic-name "<InteropHub topic name>" --assembly <AssemblyName>
   ```

   The directory name becomes the project ID and the repository name. Add
   `--with presentation` for a review deck. The script fills in the names,
   generates `CoreDocument.md`, and adds these templates as `process/` at the
   latest release tag. It does not commit or push.
2. Resolve the `CONFIRM` notes, add the topic sections to `content/`, the
   assembly file, `content/README.md`, and `navLabels` in `guide.json`, and
   list the sources in `sources/README.md`.
3. Run `build.ps1` and open `output/guide/index.html`. That page, not
   `output/<AssemblyName>.html`, is the Topic Reference.
4. Run `validate.ps1`.
5. Create the public GitHub repository, push, and set GitHub Pages to publish
   from the `gh-pages` branch.
6. Tag the first release, then link the release's `/latest/` address from the
   InteropHub topic.

## Keeping projects in line

Every Topic Reference uses the same build, validation, and publishing files.
When the skeleton changes, existing projects adopt the change deliberately:
move the `process/` pointer, compare the project's shared files with
`templates/topic-reference/project/`, rebuild, review, and commit.
