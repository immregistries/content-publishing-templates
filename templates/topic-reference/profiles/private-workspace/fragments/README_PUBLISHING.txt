Publish by uploading the built guide, `output/guide/index.html`, to the
topic's private hosting in InteropHub, labeled with the `version` in
`guide.json` and as `latest`. Raise `version` (for example from `v0.1.0` to
`v0.2.0`) before each upload, so readers and InteropHub can tell the versions
apart. Uploads are made by hand on InteropHub for now;
`process/tools/publish_guide_to_hub.py` uploads with a personal access token
where the hub allows it. Share the guide in no other way; see
[INTERNAL-USE.md](INTERNAL-USE.md).
