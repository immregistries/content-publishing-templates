# Topic References

A **Topic Reference** is the current statement of where a topic stands: its
definitions, principles, diagrams, working decisions, and open questions, in
one document that people can read and refer to in discussions and meetings,
and that other tools can use.

It is the most common kind of content project built with these templates. The
same process and tools can be used for other kinds of documents.

A Topic Reference is one of two types, described in
[Workspace and Standing Topic References](#workspace-and-standing-topic-references).
A **Standing Topic Reference** is a lasting, versioned reference for an
InteropHub topic. A **Workspace Topic Reference** is kept in a shared folder
while a topic is still taking shape, without Git, releases, or an InteropHub
topic.

A Standing Topic Reference's visibility follows its topic's. A public topic's
Topic Reference is developed and published openly; a private topic's is kept
in a private repository, or in a shared workspace with no repository, and
shared only with people who may see the topic. Both use the same source,
build, validation, review, and product model. See [Visibility](#visibility)
and [Where a Standing Topic Reference is kept](#where-a-standing-topic-reference-is-kept).

## Workspace and Standing Topic References

The pattern is useful before a topic is settled, so work often moves through
three stages:

1. A **working folder** of notes, drafts, and documents. It is source
   material, not a Topic Reference.
2. A **Workspace Topic Reference**, made in or beside that folder, with a
   bounded purpose, canonical Markdown, and one complete core document.
3. A **Standing Topic Reference**, if the work becomes a lasting reference for
   an InteropHub topic.

| | Workspace | Standing |
|---|---|---|
| InteropHub topic | None | One, which the guide links back to |
| Kept in | A shared folder, such as a synced Dropbox folder | A Git repository, public or private; or, for a private topic, a shared folder |
| Shared templates | A copy in `process/`, recorded in `process/PROCESS-VERSION.txt` | The `process/` Git submodule at a release tag; a copy when kept in a shared folder |
| Identifies a build by | Its build date; the guide shows "Workspace build" and the date | A release tag such as `v0.1.0`; when kept in a shared folder, the same kind of label set in `guide.json` |
| Products record | `core_built` and `core_location` | `core_release`; when kept in a shared folder, also `core_built` and `core_location` |
| Stale products found by | File dates after `core_built` | Git changes since the release; file dates when kept in a shared folder |
| Review | Downloaded guide comments, meeting notes, and document comments, in `review/` | The same, plus issues in a repository and signed-in comments when hosted |

What makes a Topic Reference Standing is that it is attached to an InteropHub
topic as a lasting reference with a named Author, not where its files are
kept. Both types share the content model: one bounded purpose, one canonical
source, one complete core document, and products traceable to it. The names
describe permanence, not approval. Either type can hold draft or settled
material, and the status shown on the page is set separately. Visibility is
also separate: a Workspace's access follows the rules of the folder it is kept
in.

Promotion from Workspace to Standing is a deliberate decision, not something
that happens because a workspace has lasted. See
[Promoting a Workspace Topic Reference](#promoting-a-workspace-topic-reference).

### Where a Standing Topic Reference is kept

Where a Standing Topic Reference is kept is a separate choice from its type
and its visibility. A public one is kept in Git, because public topics are
developed openly and published with GitHub Pages and releases. A private one
is kept in Git, or in a shared workspace such as a synced Dropbox folder with
no repository at all.

| Type | Kept in | Visibility | Guide hosting |
|---|---|---|---|
| Workspace | Shared folder | Follows the folder's access | Built locally |
| Standing | Git | Public | GitHub Pages |
| Standing | Git | Private | Built locally, or InteropHub |
| Standing | Shared folder | Private | InteropHub only |

A public Standing Topic Reference is never kept in a shared folder.

Keep a private one in a shared folder when its material sits beside sensitive
working sources that must not travel further, its readers are a defined group
reached through a private InteropHub topic, it serves a bounded project rather
than an ongoing community standard, and its contributors already work in the
folder and do not need branch-based review. A repository would be one more
place the material exists, with its own access list, clones, hosting copy,
and permanent history. Keep it in Git when several people edit at once and
need history and review, when releases must be reproducible, or when it may
become public.

A Standing Topic Reference kept in a shared folder has everything a Workspace
has, and also:

- **Its topic.** `guide.json` names the topic in `interophubTopic`, sets
  `"keptIn": "workspace"` and `location`, and uses `interophub` hosting and
  comments with a document key.
- **An Author** named in `README.md`.
- **A version label without Git.** `version` in `guide.json`, such as
  `v0.1.0`, is set by hand and raised before each upload. The guide shows it
  with the build date. Each upload is labeled with that version and `latest`,
  so the published history is kept in InteropHub even though the folder has
  no source history.
- **A source boundary.** Working material is listed by title, date, and status
  in `sources/README.md` and is not copied into `content/`. Keep Topic
  References in their own folder, apart from raw working material, so the
  folder structure shows the boundary.
- **Portable output.** The built guide is self-contained and has no local
  paths or links to files outside the project.
- **No repository, by design.** `README.md` says so, so a later maintainer
  does not "fix" it by creating one.

Dropbox version history allows recovery from a bad edit, and conflict copies
show when two people edited one file at once; have one person edit a chapter
at a time. Validation runs without Git and reports checks that need Git as not
applicable, never as passed.

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

- A topic has at most one Standing Topic Reference, and a Standing Topic
  Reference belongs to one topic. Related topics are linked, not merged. A
  Workspace Topic Reference has no topic until it is promoted.
- The InteropHub topic of a public Topic Reference links to it beside its other
  links. The link always points to the latest release,
  `https://<owner>.github.io/<id>/latest/`.
- The web guide links back to the topic ("Return to InteropHub").

## Reviewing comments in the guide

When connected comments are enabled, signed-in readers see each thread's review
state. A disposed comment also shows the server-provided disposition label, the
author's change note, and who disposed it. Closed threads are hidden initially;
readers can select **Show closed** to load them with their replies.

Review flags are how authors point readers, and each other, to an area that
needs attention. A flagged area starts with a purple **Review** badge showing
the start of the note, and a purple bar runs down its left side; a flagged
table row has the bar and a small badge in its first cell. Hovering over or
selecting the badge shows the whole note, who flagged it, and when. Section
links with flagged areas carry a purple dot, and the comments panel lists the
flags first, under **Review flags**, with links to each. Everyone signed in
sees flags.

Authors get controls permitted by the comment service. From the guide they can
set, change, or clear a disposition and its required change note; close or
reopen a thread; delete inappropriate comments or replies after an in-page
confirmation; and re-attach an orphaned thread by choosing one of the page's
anchor areas. They flag an area with the flag button that appears under the
comment button on hover, and edit or clear a flag from its badge or from the
panel list. The service
checks every action again and reports when another person changed the thread
first.

## In terms of the process

A Topic Reference is a content project, as described in [the process](Process.md),
whose bounded purpose is one topic:

- The Markdown in `content/` is the canonical source, and it builds the
  complete core document.
- The Topic Reference is that core document built as a
  [web guide](../templates/guide/README.md). A public one is published with
  GitHub Pages; a private one is built locally or hosted in InteropHub; a
  Workspace one is built in its folder. The web guide is the format; the Topic
  Reference is what it presents.
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
linked from elsewhere, and the document has six to seven chapters, not
counting appendices. See
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
- the status (from `guide.json`) and the build date, and the release tag only
  when the build is exactly on a clean tag;
- the InteropHub topic number, with its address for a public topic; and
- the notice from the guide footer, which for a private project is the
  restricted-use notice.

`arrangement` places the key ideas as a `sequence`, a `cycle`, or a `set`
without changing the anatomy. A sequence of three or four ideas reads left to
right in one row; longer sequences wrap into two rows. A cycle of four is a
two-by-two loop. Ideas in a sequence or cycle are numbered; ideas in a set are
not, because their order carries no meaning. Other layouts are for additional
infographics, which are derived products.

Each idea may name an `icon` from the openly licensed set in
[`templates/infographic/icons/`](../templates/infographic/README.md). Text is set
in Open Sans, AIRA's brand typeface, embedded in the image so it looks the same
everywhere.

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

A git describe string, a branch name, or a build from a changed working tree
never appears on the image: the tag is drawn only when the build is exactly on
it with no uncommitted changes.

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

A Standing project's visibility is chosen when it is created and must match
its InteropHub topic. A Workspace project has no visibility setting; access
follows the rules of the folder it is kept in. Linking a private topic to a publicly readable page, or a
public topic to a private one, is a setup mistake.

A private Topic Reference's readers are the people who may see its topic.
They may be one organization's staff, or may include partner organizations
given access to the topic. Its restricted-use notice, `INTERNAL-USE.md`, ties
access to the topic rather than to an organization, so the same notice fits
both, and `content/` holds only what every reader of the topic may see.

| | Public | Private |
|---|---|---|
| Repository | Public | Private, or none when kept in a shared folder |
| Web guide | Published with GitHub Pages at `/main/`, each release, and `/latest/` | Built locally, or hosted in InteropHub for signed-in topic readers; hosted only in InteropHub when kept in a shared folder |
| Comments | Local mode, or signed-in comments through InteropHub | Local mode, or signed-in comments when hosted in InteropHub |
| Linked from the InteropHub topic | Yes, through the topic's Topic Reference registration | Not yet |
| Licenses | CC BY 4.0 for content and Apache 2.0 for code | None; `INTERNAL-USE.md` restricts use to readers of the topic |
| Contribution files | `CONTRIBUTING.md` for an open community, and a code of conduct | `CONTRIBUTING.md` for people who may see the topic |
| `AGENTS.md` | Public-repository rules | Private-repository rules, or rules for a project kept without a repository |

Everything else, including the content structure, build, validation, review
records, and products, is the same. A private project kept in a shared folder
identifies its versions by the label in `guide.json` instead of tags; see
[Where a Standing Topic Reference is kept](#where-a-standing-topic-reference-is-kept).

### Guide hosting

`hosting` in `guide.json` chooses one of three modes. `local` keeps the built
file on the author's machine and normally uses local browser comments.
`github-pages` publishes a public guide and is the default when `hosting` is
absent, preserving existing projects. `interophub` uploads the guide for
signed-in readers who can view its topic; it requires InteropHub comments plus
`comments.hub` and `comments.document`. Hosted guides need no change to
`guide.js`: they use the same comment API and sign-in flow.

For hosted publishing, create a personal access token with `topics:write` on
the hub account page and save it as the repository secret `INTEROPHUB_TOKEN`.
The private workflow uploads `main` on a push to main, and uploads both the tag
and `latest` for a `vX.Y.Z` tag. To publish manually:

```powershell
$env:INTEROPHUB_TOKEN = "<personal access token>"
python process/tools/publish_guide_to_hub.py output/guide/index.html `
    --label v0.4.0 --label latest
```

A project kept in a shared folder has no repository, secret, or workflow. Its
Author uploads the built guide by hand from the topic in InteropHub, labeled
with the `version` in `guide.json` and as `latest`, or runs the same command
with a personal access token where the hub allows scripted upload.

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
- A Workspace Topic Reference has no releases. Its guide shows the date it was
  built, and each product's manifest records `core_built`, the date the core
  was built, and `core_location`, where the workspace is kept.
  `tools/check_products.py` reports a product for review when a core file was
  modified after that date. Releases begin when the workspace is promoted.
- A private Standing Topic Reference kept in a shared folder has no tags. Its
  version label is `version` in `guide.json`, such as `v0.1.0`, set by hand
  and raised before each upload to InteropHub. Its guide shows that label and
  the build date. Each product's manifest records the label as
  `core_release`, with `core_built` and `core_location`, and
  `tools/check_products.py` compares file dates as it does for a Workspace,
  reporting the checks that need Git as not applicable.

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
The working decisions and open questions tables should use row anchors, so
each decision or question can be commented on, linked, and flagged on its own.
See [Review anchors](Conventions.md#review-anchors) for naming and placement.

## Starting a new Topic Reference

Choose the type first. Start a Workspace when the topic is still taking shape
in a shared folder; start a Standing project when there is an InteropHub topic
and the work is meant to last.

### Starting a Standing Topic Reference

1. Create the project with the skeleton. Do not assemble one by hand:

   ```powershell
   python tools/new_topic_reference.py ..\<id> --visibility public --title "<Title>" `
       --topic <number> --topic-name "<InteropHub topic name>" --assembly <AssemblyName>
   ```

   `--visibility` is `public` or `private` and must match the topic. A private
   project also needs `--owner`, the owner of its private repository. The
   optional `--hosting interophub --hub "<hub base URL>"` makes a private guide
   hosted; otherwise it defaults to `--hosting local`. These options apply only
   to private Standing projects. To keep a private project in a shared folder
   instead of Git, see the next section. The
   directory name becomes the project ID and the repository name. Add
   `--with presentation` for a review deck, and `--with ideas` for an ideas
   register (see [Ideas](Conventions.md#ideas)). The script fills in the names,
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
   not enable GitHub Pages. For hosted mode, add `INTEROPHUB_TOKEN`; for local
   mode there is no publishing workflow. Tag releases as usual.

### Starting a private Standing Topic Reference kept in a shared folder

1. Create the project with the skeleton, in its own folder apart from the
   working material:

   ```powershell
   python tools/new_topic_reference.py "<shared folder>\<id>" --visibility private `
       --kept-in workspace --hosting interophub --hub "<hub base URL>" `
       --title "<Title>" --topic <number> --topic-name "<InteropHub topic name>" `
       --location "<where the folder is kept>"
   ```

   It takes no `--owner` and creates no Git repository. It copies these
   templates into `process/` as for a Workspace, and sets `keptIn`,
   `location`, `version` (`v0.1.0`), and InteropHub hosting and comments in
   `guide.json`, with the project ID as the document key.
2. Name the Author in `README.md`, list the working material in
   `sources/README.md`, resolve the `CONFIRM` notes, and write the sections.
3. Run `build.ps1` and `validate.ps1`, and open `output/guide/index.html`.
4. Upload the guide to the topic in InteropHub, labeled with the version and
   as `latest`. Sign in on the hosted page, add a test comment, and withdraw
   it.

### Starting a Workspace Topic Reference

1. Create the workspace with the skeleton, in the working folder or in a new
   folder beside it:

   ```powershell
   python tools/new_topic_reference.py "<shared folder>\<Working Folder>" --type workspace `
       --id <id> --title "<Title>" --location "<where the folder is kept>"
   ```

   `--location` names the folder in a form every collaborator recognizes, such
   as its path within a shared Dropbox, not one person's local path. `--id` is
   the project ID when the folder name is not lowercase words joined by
   hyphens. The working folder may already hold its notes and documents; the
   script stops without changing anything if a skeleton file would replace
   one. It copies these templates into `process/` at the latest release tag
   (`--process-ref` chooses another) and does not create a Git repository.
2. List the working folder's notes and documents in `sources/README.md`.
   They stay where they are and are not canonical source.
3. Resolve the `CONFIRM` notes and write the sections, as for a Standing
   project. Run `build.ps1` and `validate.ps1`, and open
   `output/guide/index.html`.
4. Share the built guide and other products according to the rules of the
   folder. When a product is made, record `core_built` and `core_location` in
   its manifest.

### Promoting a Workspace Topic Reference

Promote a workspace when it has, or belongs to, an InteropHub topic and is to
be kept as a lasting reference. Before promoting it, confirm the topic and its
visibility, name the Author who will maintain it, and decide where it will be
kept. A private one may stay in its shared folder and be promoted in place; a
public one, or one that needs Git, moves into a repository.

#### In place, for a private topic kept in a shared folder

1. Confirm that the topic is private and that the folder holds only the Topic
   Reference, apart from raw working material.
2. In `guide.json`, remove `topicReferenceType`, keep `location`, and add
   `"interophubTopic": <number>`, `"keptIn": "workspace"`,
   `"version": "v0.1.0"`, `"hosting": "interophub"`, and
   `"comments": {"mode": "interophub", "hub": "<hub base URL>", "document": "<id>"}`.
   Set `license` to the restricted-use notice,
   `Restricted to readers of InteropHub topic <number>; not for further distribution`.
3. Compare `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, the status lines in
   `content/`, `products/`, and `review/README.md` with a project made by
   `new_topic_reference.py --kept-in workspace` in a scratch folder, take its
   wording, and add its `INTERNAL-USE.md`. Name the Author in `README.md`.
4. Record `core_release`, `core_built`, and `core_location` in the manifests
   of products kept from the workspace.
5. Build, validate, and upload the guide to the topic in InteropHub, labeled
   with the version and as `latest`.

#### Into Git

1. Create a Standing project with the skeleton, as above. Do not convert the
   workspace folder in place. A project kept in a shared folder that moves
   into Git later follows the same steps.
2. Copy the canonical content, `content/infographic.yml`, cited assets, and
   the review records that are still open, keeping heading IDs and review
   anchors so comments stay attached.
3. Adjudicate what is current, obsolete, sensitive, or outside the topic.
   Working material stays out of the repository and is listed in
   `sources/README.md`.
4. Build, validate, and review, then tag the first release. Products kept from
   the workspace are rebuilt from that release and their manifests updated to
   cite it.
5. Mark the workspace as superseded in its `README.md`, with a link to the
   Standing project, and keep or remove it according to the folder's rules.

## Keeping projects in line

Every Topic Reference uses the same build and validation files, and every
Topic Reference with the same visibility uses the same publishing and
contribution files. When the skeleton changes, existing projects adopt the
change deliberately: move the `process/` pointer, compare the project's shared
files with `templates/topic-reference/project/` and
`templates/topic-reference/profiles/<visibility>/`, rebuild, review, and
commit.

A Workspace, or a private Standing project kept in a shared folder (profile
`private-workspace`), adopts a change by refreshing its copy with
`python tools/workspace_process.py "<workspace folder>"` from a checkout of
this repository, comparing its shared files with
`templates/topic-reference/project/` and
`templates/topic-reference/profiles/workspace/` or
`templates/topic-reference/profiles/private-workspace/`, rebuilding, and reviewing.
