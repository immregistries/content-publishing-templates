# Guide comment tests

The validation script starts the in-memory comments service automatically. To
run it by hand:

```powershell
python tests/mock_hub.py --port 8766 --allow-origin http://127.0.0.1:8765
```

Serve a built guide at the allowed origin (for example, with
`python -m http.server 8765`) and configure its `comments.hub` as
`http://127.0.0.1:8766`. The service keeps data in memory and provides test-only
routes under `/test/` for revoking tokens, deleting or closing comments, and
changing document visibility.


The service also takes build records as InteropHub does. `POST
/api/guide/{document}/builds` saves a build manifest sent on its own (the
documents `document` and `external-document` are registered), and each upload
to `/api/guide/{document}/versions/{label}` records the manifest read from the
uploaded guide, or why it could not be read. Tests read them from
`server.state.builds`.

## Annotations panel

`browser_check.py` drives headless Chrome or Edge against a guide built in
InteropHub comment mode and the mock service. Before it starts, it seeds the
service with comments, replies, a comment that cannot be placed, and review
flags (`mock_hub.seed_demo`). The change markers and the front section come
from the fixture's own source. `--local-guide` also checks a guide built in
local-comments mode, `--screenshots DIR` saves each tab at wide and narrow
widths, and `--quick` skips the 65-second refresh wait while developing.

To try the panel by hand against the fixture, after `validate.ps1` has made
`output/fixture-remote`, its InteropHub-mode copy:

```powershell
python tests/mock_hub.py --port 8766 --allow-origin http://127.0.0.1:8765 --seed-demo
python -m http.server 8765 --bind 127.0.0.1 --directory output/fixture-remote
```

Then open `http://127.0.0.1:8765/output/guide/`. Signing in through the mock
signs in as "Test Reader"; to sign in as the author, add `&user=Test%20Author`
to the mock's `/home` address when the browser reaches it.

The service's threads and replies carry `mine`, and `GET
/api/guide/{document}/review-flags?includeCleared=true` returns cleared flags,
as InteropHub does.

It also follows InteropHub's version rules: labels from uploads, build
reports, settings, and registered addresses; `pageUrl` and `label` on reads
(`labelPolicy`, `inScope`); `madeOnLabel` and `403 comments_closed` on writes;
and `GET` and `PATCH /api/guide/{document}/labels`. `--seed-demo --site
http://127.0.0.1:8765` adds three versions of the fixture guide: the copy at
`output/guide/` is `main` (Open), `output/release/` is `v0.2.0` (Current,
Release), and `output/closed/` is `v0.1.0` (Retired, Closed). Copy the built
guide into those two folders to try them. `/test/label?label=…&mode=…`
changes a label's mode directly.
