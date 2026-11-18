import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import mock_hub

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "publish_guide_to_hub.py"
MANIFEST = {"schema": 1, "generator": "content-publishing-templates", "processVersion": "v0.21.0",
            "document": {"id": "document", "title": "Guide <one>"}, "checks": {"warnings": []}}


def guide_html(manifest=MANIFEST):
    script = ""
    if manifest is not None:
        text = json.dumps(manifest).replace("<", "\\u003c")
        script = f'<script type="application/json" id="guide-build-manifest">{text}</script>'
    return f"<!DOCTYPE html><html><head><title>Guide</title>{script}</head><body></body></html>"


class PublishGuideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = mock_hub.serve(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.author = "ihp_author_secret"; cls.reader = "ihp_reader_secret"
        user = {"userId": 9, "displayName": "Test Author", "organization": "Example"}
        cls.server.state.tokens[cls.author] = {"user": user, "isAuthor": True}
        cls.server.state.tokens[cls.reader] = {"user": {**user, "userId": 10}, "isAuthor": False}

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.guide = self.root / "index.html"; self.guide.write_text(guide_html(), encoding="utf-8")
        self.config = self.root / "guide.json"
        self.write_config("interophub")
        self.server.state.builds.clear(); self.server.state.active = True

    def tearDown(self): self.temp.cleanup()

    def write_config(self, hosting, comments=True):
        config = {"hosting": hosting}
        if comments:
            config["comments"] = {"mode": "interophub", "hub": self.base, "document": "document"}
        self.config.write_text(json.dumps(config))

    def run_tool(self, token, *args):
        env = os.environ.copy()
        if token is None: env.pop("INTEROPHUB_TOKEN", None)
        else: env["INTEROPHUB_TOKEN"] = token
        return subprocess.run([sys.executable, str(TOOL), str(self.guide), "--config", str(self.config), *args],
                              text=True, capture_output=True, env=env)

    def invoke(self, token=None, *extra):
        return self.run_tool(token, "--label", "latest", *extra)

    def builds(self, document="document"):
        return self.server.state.builds.get(document, [])

    def test_success_and_replacement(self):
        first = self.invoke(self.author); second = self.invoke(self.author)
        self.assertEqual((0, 0), (first.returncode, second.returncode))
        self.assertIn("created", first.stdout); self.assertIn("replaced", second.stdout)
        uploads = self.builds()
        self.assertEqual(["UPLOAD", "UPLOAD"], [build["source"] for build in uploads])
        self.assertEqual("v0.21.0", uploads[0]["processVersion"])
        self.assertEqual("Guide <one>", uploads[0]["manifest"]["document"]["title"])

    def test_reader_missing_token_and_wrong_hosting(self):
        self.assertIn("403 forbidden", self.invoke(self.reader).stderr)
        self.assertIn("INTEROPHUB_TOKEN", self.invoke().stderr)
        self.write_config("local"); self.assertIn("hosting", self.invoke(self.author).stderr)

    def test_dry_run_sends_nothing_and_never_prints_token(self):
        before = dict(self.server.state.versions.get("document", {}))
        result = self.invoke(self.author, "--dry-run")
        self.assertEqual(0, result.returncode); self.assertEqual(before, self.server.state.versions.get("document", {}))
        self.assertNotIn(self.author, result.stdout + result.stderr)
        failed = self.invoke("definitely-secret")
        self.assertNotIn("definitely-secret", failed.stdout + failed.stderr)

    def test_a_guide_without_a_manifest_is_not_published(self):
        self.guide.write_text(guide_html(None), encoding="utf-8")
        before = dict(self.server.state.versions.get("document", {}))
        for result in (self.invoke(self.author), self.invoke(self.author, "--dry-run"),
                       self.run_tool(self.author, "--manifest-only")):
            self.assertEqual(1, result.returncode)
            self.assertIn("no build manifest", result.stderr)
        self.assertEqual(before, self.server.state.versions.get("document", {}))
        self.assertEqual([], self.builds())

    def test_an_unreadable_manifest_is_refused(self):
        self.guide.write_text(guide_html({"schema": 2}), encoding="utf-8")
        self.assertIn("not schema 1", self.invoke(self.author).stderr)
        self.guide.write_text(guide_html(None).replace(
            "</head>", '<script type="application/json" id="guide-build-manifest">{oops</script></head>'), encoding="utf-8")
        self.assertIn("not valid JSON", self.invoke(self.author).stderr)

    def test_manifest_only_saves_the_manifest_with_its_label(self):
        result = self.run_tool(self.author, "--manifest-only", "--label", "v0.4.0")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Build manifest saved: build", result.stdout)
        self.assertIn("process v0.21.0", result.stdout)
        [build] = self.builds()
        self.assertEqual(("MANIFEST", "v0.4.0"), (build["source"], build["label"]))
        self.assertEqual(MANIFEST, build["manifest"])
        self.assertEqual({}, self.server.state.versions.get("unused", {}))

    def test_manifest_only_for_a_guide_hosted_elsewhere(self):
        # A public guide on GitHub Pages with local comments names its hub and document.
        self.write_config("github-pages", comments=False)
        missing = self.run_tool(self.author, "--manifest-only")
        self.assertEqual(1, missing.returncode); self.assertIn("--hub", missing.stderr)
        no_key = self.run_tool(self.author, "--manifest-only", "--hub", self.base)
        self.assertEqual(1, no_key.returncode); self.assertIn("--document", no_key.stderr)
        # With no comments.document, the document key is the project id in guide.json.
        self.config.write_text(json.dumps({"id": "external-document", "hosting": "github-pages"}))
        by_id = self.run_tool(self.author, "--manifest-only", "--hub", self.base, "--label", "v0.1.0")
        self.assertEqual(0, by_id.returncode, by_id.stderr)
        self.assertEqual("v0.1.0", self.builds("external-document")[-1]["label"])
        # comments.document wins over id, and --document over both.
        self.config.write_text(json.dumps({"id": "external-document", "hosting": "github-pages",
                                           "comments": {"mode": "interophub", "hub": self.base, "document": "document"}}))
        self.assertEqual(0, self.run_tool(self.author, "--manifest-only").returncode)
        self.assertEqual(1, len(self.builds("document")))
        self.write_config("github-pages", comments=False)
        result = self.run_tool(self.author, "--manifest-only", "--label", "main",
                               "--hub", self.base + "/", "--document", "external-document")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["MANIFEST", "MANIFEST"], [build["source"] for build in self.builds("external-document")])
        self.assertEqual("main", self.builds("external-document")[-1]["label"])
        unlabeled = self.run_tool(self.author, "--manifest-only", "--hub", self.base, "--document", "external-document")
        self.assertEqual(0, unlabeled.returncode, unlabeled.stderr)
        self.assertIsNone(self.builds("external-document")[-1]["label"])

    def test_manifest_only_errors_are_explained(self):
        cases = [
            (self.reader, ["--document", "document"], "403 forbidden"),
            (self.author, ["--document", "no-such-guide"], "404 not_found"),
            ("not-a-token", ["--document", "document"], "401 invalid_token"),
        ]
        for token, extra, expected in cases:
            result = self.run_tool(token, "--manifest-only", *extra)
            self.assertEqual(1, result.returncode); self.assertIn(expected, result.stderr)
        self.server.state.active = False
        inactive = self.run_tool(self.author, "--manifest-only")
        self.assertIn("409 document_inactive", inactive.stderr)
        self.assertIn(mock_hub_message("document_inactive"), inactive.stderr)
        self.assertEqual(1, self.run_tool(None, "--manifest-only").returncode)
        self.assertIn("at most one", self.run_tool(self.author, "--manifest-only", "--label", "v1", "--label", "latest").stderr)
        self.assertEqual([], self.builds())

    def test_manifest_only_dry_run_sends_nothing(self):
        result = self.run_tool(self.author, "--manifest-only", "--dry-run")
        self.assertEqual(0, result.returncode); self.assertIn("build manifest", result.stdout)
        self.assertEqual([], self.builds())


class MockBuildsEndpointTest(unittest.TestCase):
    """The mock refuses what InteropHub's builds endpoint refuses."""

    @classmethod
    def setUpClass(cls):
        cls.server = mock_hub.serve(0)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server.state.tokens["author"] = {"user": {"userId": 1, "displayName": "A"}, "isAuthor": True}

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def post(self, body: bytes, content_type="application/json"):
        import urllib.error, urllib.request  # noqa: E401, PLC0415
        request = urllib.request.Request(f"{self.base}/api/guide/document/builds", data=body, method="POST",
                                         headers={"Authorization": "Bearer author", "Content-Type": content_type})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def test_invalid_requests(self):
        for body in (b"{oops", b"{}", json.dumps({"manifest": {"schema": 2}}).encode(),
                     json.dumps({"manifest": {"schema": 1, "pad": "x" * 70000}}).encode()):
            self.assertEqual((400, "invalid_request"), (lambda r: (r[0], r[1]["error"]))(self.post(body)))

    def test_created(self):
        status, body = self.post(json.dumps({"label": "v1.0.0", "manifest": MANIFEST}).encode())
        self.assertEqual(201, status)
        self.assertEqual({"buildId", "documentKey", "processVersion", "receivedAt"}, set(body))
        self.assertEqual(("document", "v0.21.0"), (body["documentKey"], body["processVersion"]))


def mock_hub_message(code):
    import importlib.util  # noqa: PLC0415
    spec = importlib.util.spec_from_file_location("publish_guide_to_hub", TOOL)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.ERRORS[code]


if __name__ == "__main__": unittest.main()
