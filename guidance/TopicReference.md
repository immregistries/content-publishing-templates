# Topic References

A **Topic Reference** is the current, versioned statement of where an
InteropHub topic stands: its definitions, principles, diagrams, working
decisions, and open questions, in one document that people can read and refer
to in discussions and meetings, and that other tools can use.

It is the most common kind of content project built with these templates. The
same process and tools can be used for other kinds of documents.

A Topic Reference's visibility follows its topic's. A public topic's Topic
Reference is developed and published openly; a private topic's is kept in a
private repository and shared only with people who may see the topic. Both use
the same source, build, validation, release, review, and product model. See
[Visibility](#visibility).

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
- The InteropHub topic of a public Topic Reference links to it beside its other
  links. The link always points to the latest release,
  `https://<owner>.github.io/<id>/latest/`.
- The web guide links back to the topic ("Return to InteropHub").

## Reviewing comments in the guide

When connected comments are enabled, signed-in readers see each thread's review
state. A disposed comment also shows the server-provided disposition label, the
author's change note, and who disposed it. Closed threads are hidden initially;
readers can select **Show closed** to load them with their replies. Areas marked
for another look are highlighted and listed as **Flagged for review** in the
rail, with links back to the text.

Authors get controls permitted by the comment service. From the guide they can
set, change, or clear a disposition and its required change note; close or
reopen a thread; delete inappropriate comments or replies after an in-page
confirmation; and re-attach an orphaned thread by choosing one of the page's
anchor areas. They can also add, edit, and clear review flags. The service
checks every action again and reports when another person changed the thread
first.

## In terms of the process

A Topic Reference is a content project, as described in [the process](Process.md),
whose bounded purpose is one InteropHub topic:

- The Markdown in `content/` is the canonical source, and it builds the
  complete core document.
- The Topic Reference is that core document built as a
  [web guide](../templates/guide/README.md). A public one is published with
  GitHub Pages; a private one is built locally. The web guide is the format;
  the Topic Reference is what it presents.
- `CoreDocument.md` is the single-file reading copy on GitHub. Word and Quarto
  HTML builds are review copies.
- The [primary infographic](#primary-infographic), the topic at a glance, is
  built with the core document from `content/infographic.yml` and appears in
  the web guide and the Word document.
- Presentations, Confluence pages, and other copies are derived products, each
  with a brief and a manifest.

## What every Topic Reference contains

- **Status and scope** (`content/00-status-and-scope.md`): a short summary,
  purpose, and what the project covers and does not cover.
- **Related work** (`content/01-related-work.md`): related InteropHub topics and
  other efforts, linked rather than repeated. When it is short, make it a
  section of Status and Scope instead of its own chapter.
- **Topic sections** in reading order: definitions, principles, diagrams,
  examples, and whatever else the topic needs.
- **Working decisions and open questions** (`content/90-working-decisions.md`):
  each decision with an ID and its basis; each open question with the sources
  in tension and its status.
- **A primary infographic** (`content/infographic.yml`): the topic at a glance,
  each part referring to the section it summarizes. See
  [Primary infographic](#primary-infographic).
- **Status and version on the web guide**, and a return link to the topic.
- **A way to comment**, on the page itself, through GitHub issues, and in
  meetings, with every comment treated as a review input until it is
  adjudicated into `content/`.

A Topic Reference records the topic's knowledge, not how the project is run.
How Topic References are maintained, reviewed, and released is described once,
in this guidance and in each repository's `README.md` and `CONTRIBUTING.md`;
do not restate it in `content/` or record it as working decisions.

The Topic Reference is source, so it is concise: each fact is stated once and
linked from elsewhere, and the document has no more than about six top-level
chapters, including the appendix. See
[Conventions](Conventions.md#state-each-fact-once). Presentations and other
derived products may repeat and expand.

## Primary infographic

Every Topic Reference has one infographic that lays out the topic at a glance.
It is a primary output, like the web guide and the Word document: `build.ps1`
draws it on every build, the guide shows it above the first section, and the
Word document shows it before the first chapter. A copy of the image shared on
its own still says what it is.

### Anatomy

Every primary infographic has the same parts, so readers know where to look:

- the topic name, and its purpose in one sentence;
- three to six key ideas, with the relationships between them;
- the status (from `guide.json`), the version, and the build date;
- the InteropHub topic number, with its address for a public topic; and
- the notice from the guide footer, which for a private project is the
  internal-use notice.

`arrangement` places the key ideas as a `sequence`, a `cycle`, or a `set`
without changing the anatomy. Other layouts are for additional infographics,
which are derived products.

### The specification

`content/infographic.yml` is canonical source. It is reviewed and adjudicated
like the Markdown in `content/`, and the rendered files in `output/` are
generated. Its fields are listed in
[`tools/infographic.py`](../tools/infographic.py). The skeleton creates a
starter specification and a brief in `products/infographic/brief.yml`.

The infographic is a [sanctioned summary](Conventions.md#sanctioned-summaries):
its labels condense the core and add nothing to it.

- The purpose, each key idea, and each relationship has a `ref`: the heading ID
  or anchor in `content/` that it summarizes. In the guide, each part links to
  that section.
- It adds no claim, number, commitment, or change in certainty that the
  referenced sections do not state.
- When a referenced section changes, check the labels that refer to it.

The guide and the Word document state everything the image summarizes, so they
are its long text alternative; the specification's `alt` is the short one.

Generated artwork is not used by default, so every Topic Reference builds
without credentials and sends nothing to an image service. A project may add a
selected image as `artwork`, drawn behind the content. Artwork never carries
essential text.

### Building and checking

`build.ps1` runs `build_infographic.py` before `quarto render`, then
`insert_word_infographic.py` after it. The outputs are `output/infographic.svg`,
`.png`, and `.pdf`. Drawing them needs an installed Chrome or Edge, which runs
headless to measure the rendered text and export the PNG and PDF; set
`CHROME_PATH` to choose one. The guide draws the same figure without a browser,
so the publishing workflow needs none.

The content check fails when the specification is missing, a field is missing
or unknown, a `ref` does not resolve, named artwork is missing, or text does not
fit its box; the build also fails when the browser finds text that overflows.
`CONFIRM` text left from the starter specification is reported, not failed, so
a new Topic Reference builds while it is being written.

## Visibility

A project's visibility is chosen when it is created and must match its
InteropHub topic. Linking a private topic to a publicly readable page, or a
public topic to a private one, is a setup mistake.

| | Public | Private |
|---|---|---|
| Repository | Public | Private |
| Web guide | Published with GitHub Pages at `/main/`, each release, and `/latest/` | Built locally from `build.ps1`; not published |
| Comments | Local mode, or signed-in comments through InteropHub | Local mode |
| Linked from the InteropHub topic | Yes, through the topic's Topic Reference registration | Not yet |
| Licenses | CC BY 4.0 for content and Apache 2.0 for code | None; `INTERNAL-USE.md` restricts use to the organization |
| Contribution files | `CONTRIBUTING.md` for an open community, and a code of conduct | `CONTRIBUTING.md` for internal participants |
| `AGENTS.md` | Public-repository rules | Private-repository rules |

Everything else, including the content structure, build, validation, release
tags, review records, and products, is the same.

A private Topic Reference is not published, because GitHub Pages sites built
from private repositories can be publicly readable unless the hosting plan
restricts access. Publishing one to an access-controlled location, and
registering it with InteropHub, is not yet supported.

## Releases and status

- A release is a Git tag such as `v0.1.0`. In a public project, pushing the tag
  publishes the page at that version, `/v0.1.0/`, and at `/latest/`, and
  pushing to `main` publishes a preview at `/main/`. A private project's
  releases are tags only.
- The status shown on the page comes from `status` in `guide.json`, such as
  `Draft`. Change it only when the maintainers decide a release has a different
  status.
- Earlier releases stay at their own addresses. How a topic presents an earlier
  official release alongside a later working draft is not settled yet.

## Feedback

The guide has two comment modes. With no `comments` setting, or with
`"comments": {"mode": "local"}`, comments stay in the reader's browser until
they are downloaded; `tools/import_guide_comments.py` turns those files into a
dated review record. In `interophub` mode, the setting also supplies the hub URL
and document key. Readers sign in and comments live in the hub, not in the
repository. Issues, meeting notes, and other feedback still need an outcome in
the project's review record.

Named anchors in the Markdown divide the document into stable review areas.
They let a comment remain near its text as wording shifts and provide direct
links such as `#stable-name`; headings serve as anchors automatically. Content
before the first heading or named anchor belongs to the `document-start` area.
See [Review anchors](Conventions.md#review-anchors) for naming and placement.

## Starting a new Topic Reference

1. Create the project with the skeleton. Do not assemble one by hand:

   ```powershell
   python tools/new_topic_reference.py ..\<id> --visibility public --title "<Title>" `
       --topic <number> --topic-name "<InteropHub topic name>" --assembly <AssemblyName>
   ```

   `--visibility` is `public` or `private` and must match the topic. A private
   project also needs `--owner`, the owner of its private repository. The
   directory name becomes the project ID and the repository name. Add
   `--with presentation` for a review deck. The script fills in the names,
   generates `CoreDocument.md`, and adds these templates as `process/` at the
   latest release tag. It does not commit or push.
2. Resolve the `CONFIRM` notes, add the topic sections to `content/`, the
   assembly file, `content/README.md`, and `navLabels` in `guide.json`, and
   list the sources in `sources/README.md`. Replace the starter text in
   `content/infographic.yml` once the sections it refers to are written.
3. Run `build.ps1` (it needs Chrome or Edge for the infographic) and open
   `output/guide/index.html`. That page, not
   `output/<AssemblyName>.html`, is the Topic Reference.
4. Run `validate.ps1`.
5. For a public project, create the public GitHub repository, push, and set
   GitHub Pages to publish from the `gh-pages` branch. Tag the first release,
   then link the release's `/latest/` address from the InteropHub topic.
6. For a private project, create the private GitHub repository and push. Do
   not enable GitHub Pages. Tag releases as usual.

## Keeping projects in line

Every Topic Reference uses the same build and validation files, and every
Topic Reference with the same visibility uses the same publishing and
contribution files. When the skeleton changes, existing projects adopt the
change deliberately: move the `process/` pointer, compare the project's shared
files with `templates/topic-reference/project/` and
`templates/topic-reference/profiles/<visibility>/`, rebuild, review, and
commit.
