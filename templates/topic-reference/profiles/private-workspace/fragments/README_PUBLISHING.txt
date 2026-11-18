Publish by uploading the built guide, `output/guide/index.html`, to the
topic's private hosting in InteropHub, labeled with the `version` in
`guide.json` and as `latest`. Raise `version` (for example from `v0.1.0` to
`v0.2.0`) before each upload, so readers and InteropHub can tell the versions
apart. Uploads are made by hand on InteropHub for now;
`process/tools/publish_guide_to_hub.py` uploads with a personal access token
where the hub allows it. Share the guide in no other way; see
[INTERNAL-USE.md](INTERNAL-USE.md).

The upload carries the guide's build manifest, which InteropHub saves to show
the guide's status. A guide is not published until its manifest is saved, so
upload only a guide built by `build.ps1` with the current `process/`.

Uploading with the tool needs a personal access token in the
`INTEROPHUB_TOKEN` environment variable. To create it and set up as an
author, see InteropHub's
[help page for authors]({{HUB_URL}}/help/topic-reference-authors). Check it
with `python process/tools/publish_guide_to_hub.py --check-token`.
`--display` and `--comment-mode` choose how InteropHub shows a release, such
as making it the Current version with comments limited to it. `AGENTS.md`
lists the steps an AI agent may take and those it must leave to the author.
