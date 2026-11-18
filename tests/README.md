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
