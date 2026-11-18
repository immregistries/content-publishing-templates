Check `hosting` in `guide.json`. With `local`, share the built guide only with
people who may see the topic. With `interophub`, the publishing workflow uploads
the guide to access-controlled version URLs. Never enable GitHub Pages; see
[INTERNAL-USE.md](INTERNAL-USE.md).

A guide is not published until InteropHub has saved its build manifest. A
hosted upload carries it. For a local guide, save it when you release with
`process/tools/publish_guide_to_hub.py output/guide/index.html --manifest-only`;
see `process/guidance/TopicReference.md`.

Publishing uses a personal access token in `INTEROPHUB_TOKEN`: the repository
secret for the workflow, or an environment variable when publishing by hand.
To create it and set up as an author, see InteropHub's
[help page for authors]({{HUB_URL}}/help/topic-reference-authors). Check it
with
`python process/tools/publish_guide_to_hub.py --check-token --hub {{HUB_URL}}`.
`--display` and `--comment-mode` choose how InteropHub shows a release, such
as making it the Current version with comments limited to it. `AGENTS.md`
lists the steps an AI agent may take and those it must leave to the author.
