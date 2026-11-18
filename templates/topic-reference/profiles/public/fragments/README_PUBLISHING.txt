Pushing to `main` publishes the guide at {{PAGES_URL}}main/. Pushing a release
tag such as `v0.1.0` publishes it at that version and at
{{PAGES_URL}}latest/.

After each deploy, the workflow saves the guide's build manifest in InteropHub
with the `INTEROPHUB_TOKEN` repository secret, a personal access token with
`topics:write`. A guide is not published until its manifest is saved, so the
workflow fails without the secret.

To create the token and set up as an author, see InteropHub's
[help page for authors]({{HUB_URL}}/help/topic-reference-authors). Check the
token with
`python process/tools/publish_guide_to_hub.py --check-token --hub {{HUB_URL}}`.
Choose how InteropHub shows each release, such as making it the Current
version with comments limited to it, on the topic's guide settings page or
with `publish_guide_to_hub.py --settings-only --hub {{HUB_URL}} --label v0.1.0
--display current --comment-mode release`. `AGENTS.md` lists the steps an
AI agent may take and those it must leave to the author.
