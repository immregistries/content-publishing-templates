import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
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


class HubToolCase(unittest.TestCase):
    """A mock hub, a guide, and its guide.json, for running the tool."""

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
        self.server.state.versions.clear(); self.server.state.labels.clear()

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

    def labels(self):
        return self.server.state.labels.get("document", {})


class PublishGuideTest(HubToolCase):
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

    def test_labels_follow_interophubs_pattern(self):
        for label in ("latest", "main", "v1", "v1.2.0", "v1.2.0-rc.1", "v0.3.0-panelprototype"):
            result = self.run_tool(self.author, "--label", label, "--dry-run")
            self.assertEqual(0, result.returncode, (label, result.stderr))
        for label in ("v1.2.0-rc-1", "panel-prototype", "v1.2.0-", "1.2.0", "v1.2.0-.1"):
            result = self.run_tool(self.author, "--label", label, "--dry-run")
            self.assertEqual(1, result.returncode, label)
            self.assertIn("Invalid label", result.stderr)

    def test_publish_a_release_and_make_it_current_in_release_mode(self):
        self.server.state.labels.clear()
        result = self.run_tool(self.author, "--label", "v0.4.0", "--label", "latest",
                               "--display", "current", "--comment-mode", "release")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("v0.4.0: created", result.stdout)
        self.assertIn("v0.4.0: display current, comments release.", result.stdout)
        self.assertEqual(("current", "release"), (self.labels()["v0.4.0"]["display"], self.labels()["v0.4.0"]["commentMode"]))
        self.assertNotIn("latest", self.labels())
        # The next release becomes Current; InteropHub demotes the previous one to Listed.
        result = self.run_tool(self.author, "--label", "v0.5.0", "--display", "current")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("v0.5.0: display current, comments open; v0.4.0 is now listed.", result.stdout)
        self.assertEqual("listed", self.labels()["v0.4.0"]["display"])

    def test_manifest_only_then_label_settings(self):
        self.server.state.labels.clear()
        self.write_config("github-pages")
        result = self.run_tool(self.author, "--manifest-only", "--label", "v0.6.0", "--comment-mode", "closed")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Build manifest saved", result.stdout)
        self.assertIn("v0.6.0: display unlisted, comments closed.", result.stdout)
        self.assertEqual("closed", self.labels()["v0.6.0"]["commentMode"])

    def test_label_settings_errors(self):
        self.server.state.labels.clear()
        no_label = self.run_tool(self.author, "--manifest-only", "--display", "current")
        self.assertEqual(1, no_label.returncode); self.assertIn("give one", no_label.stderr)
        self.assertEqual([], self.builds())
        # A failed upload sends no settings.
        reader = self.run_tool(self.reader, "--label", "v0.7.0", "--display", "current")
        self.assertEqual(1, reader.returncode); self.assertIn("403 forbidden", reader.stderr)
        self.assertEqual({}, self.labels())
        # A token without topics:write can upload here but not change labels.
        narrow = "ihp_comments_only"
        self.server.state.tokens[narrow] = {"user": {"userId": 9, "displayName": "Test Author"}, "isAuthor": True, "scopes": ["comments"]}
        scoped = self.run_tool(narrow, "--label", "v0.7.0", "--comment-mode", "release")
        self.assertEqual(1, scoped.returncode)
        self.assertIn("v0.7.0: created", scoped.stdout)
        self.assertIn("v0.7.0 settings: 403 insufficient_scope", scoped.stderr)
        self.assertEqual({}, self.labels())
        dry = self.run_tool(self.author, "--label", "v0.8.0", "--display", "listed", "--dry-run")
        self.assertEqual(0, dry.returncode)
        self.assertIn("then v0.8.0: display listed, comments unchanged", dry.stdout)
        self.assertNotIn("v0.8.0", self.server.state.versions.get("document", {}))
        bad = self.run_tool(self.author, "--label", "v0.8.0", "--display", "shown")
        self.assertEqual(2, bad.returncode); self.assertIn("invalid choice", bad.stderr)


class TokenAndHelpTest(HubToolCase):
    """--check-token, the expiry warning, help links, and HTML answers (InteropHub contract 2, 2.1, 3.7)."""

    def setUp(self):
        super().setUp()
        self.server.state.firewall = False; self.server.state.token_endpoint = True
        self.addCleanup(setattr, self.server.state, "firewall", False)
        self.addCleanup(setattr, self.server.state, "token_endpoint", True)

    def token(self, name, days=None, scopes=None, author=True):
        record = {"user": {"userId": 9, "displayName": "Test Author"}, "isAuthor": author, "label": "laptop agent"}
        if days is not None:
            record["expiresAt"] = (datetime.now(timezone.utc) + timedelta(days=days, hours=-1)).isoformat(
                timespec="milliseconds").replace("+00:00", "Z")
        if scopes is not None: record["scopes"] = scopes
        self.server.state.tokens[name] = record
        return name

    def run_alone(self, token, *args):
        """The tool without a guide file, as --check-token and --settings-only run."""
        env = os.environ.copy()
        if token is None: env.pop("INTEROPHUB_TOKEN", None)
        else: env["INTEROPHUB_TOKEN"] = token
        return subprocess.run([sys.executable, str(TOOL), "--config", str(self.config), *args],
                              text=True, capture_output=True, env=env)

    def help(self, anchor):
        return f"{self.base}/help/topic-reference-authors#{anchor}"

    def assertSecret(self, result, *tokens):
        for token in tokens: self.assertNotIn(token, result.stdout + result.stderr)

    def test_check_token_reports_the_account_and_this_guide(self):
        result = self.run_alone(self.author, "--check-token")
        self.assertEqual(0, result.returncode, result.stderr)
        for expected in ("Account: Test Author (user 9)", "scopes: comments, topics:write", "(90 days left)",
                         "Guides this account can publish: document, external-document",
                         "This guide, document: registered, hosting HUB; upload it with --label.",
                         "Help for agents: " + self.help("if-you-are-an-agent")):
            self.assertIn(expected, result.stdout)
        self.assertEqual("", result.stderr); self.assertSecret(result, self.author)
        # A guide hosted elsewhere, named by its id, with the hub given on the command line.
        self.config.write_text(json.dumps({"id": "external-document", "hosting": "github-pages"}))
        external = self.run_alone(self.author, "--check-token", "--hub", self.base)
        self.assertEqual(0, external.returncode, external.stderr)
        self.assertIn("hosting EXTERNAL; save its manifest with --manifest-only", external.stdout)

    def test_check_token_needs_no_guide_json(self):
        self.config.unlink()
        result = self.run_alone(self.author, "--check-token", "--hub", self.base)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("This guide: no document key", result.stdout)
        self.assertIn("--hub", self.run_alone(self.author, "--check-token").stderr)

    def test_check_token_says_what_to_ask_the_author(self):
        reader = self.run_alone(self.reader, "--check-token")
        self.assertEqual(1, reader.returncode)
        self.assertIn("Guides this account can publish: none", reader.stdout)
        self.assertIn("This guide, document, is not among them", reader.stderr)
        self.assertIn(self.help("who-can-author"), reader.stderr)
        narrow = self.run_alone(self.token("ihp_narrow", scopes=["comments"]), "--check-token")
        self.assertEqual(1, narrow.returncode)
        self.assertIn("lacks topics:write", narrow.stderr); self.assertIn(self.help("create-a-token"), narrow.stderr)
        missing = self.run_alone(None, "--check-token")
        self.assertEqual(1, missing.returncode)
        self.assertIn("INTEROPHUB_TOKEN is not set", missing.stderr)
        self.assertIn("don't paste the token", missing.stderr); self.assertIn(self.help("create-a-token"), missing.stderr)
        bad = self.run_alone("ihp_not_a_real_token", "--check-token")
        self.assertEqual(1, bad.returncode); self.assertIn("401 invalid_token", bad.stderr)
        self.assertIn("Help: " + self.help("troubleshooting-invalid_token"), bad.stderr)
        expired = self.run_alone(self.token("ihp_expired", days=-1), "--check-token")
        self.assertIn("401 invalid_token", expired.stderr)
        self.assertSecret(reader, self.reader); self.assertSecret(bad, "ihp_not_a_real_token")

    def test_check_token_on_an_older_hub(self):
        self.server.state.token_endpoint = False
        result = self.run_alone(self.author, "--check-token")
        self.assertEqual(1, result.returncode)
        self.assertIn("does not offer GET /api/token", result.stderr)
        self.assertNotIn("firewall", result.stderr)

    def test_a_token_expiring_soon_is_warned_about_before_publishing(self):
        soon = self.token("ihp_soon", days=5)
        for result in (self.invoke(soon), self.run_tool(soon, "--manifest-only"), self.run_alone(soon, "--check-token")):
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("expires in 5 days", result.stderr); self.assertIn(self.help("create-a-token"), result.stderr)
            self.assertSecret(result, soon)
        later = self.token("ihp_later", days=15)
        self.assertNotIn("Warning", self.invoke(later).stderr)
        self.assertIn("expires in 1 day", self.invoke(self.token("ihp_tomorrow", days=1)).stderr)

    def test_an_older_hub_publishes_without_the_warning(self):
        self.server.state.token_endpoint = False
        result = self.invoke(self.token("ihp_soon_old_hub", days=3))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr); self.assertIn("latest: created", result.stdout)

    def test_errors_carry_an_explanation_and_the_help_link(self):
        reader = self.invoke(self.reader)
        self.assertIn("latest: 403 forbidden. This account must be an editor of the guide's topic", reader.stderr)
        self.assertIn('InteropHub: Your account must be an editor of the topic "Fixture topic"', reader.stderr)
        self.assertIn("Help: " + self.help("troubleshooting-forbidden"), reader.stderr)
        narrow = self.run_tool(self.token("ihp_comments", scopes=["comments"]), "--label", "v0.9.0", "--display", "listed")
        self.assertIn("v0.9.0 settings: 403 insufficient_scope. The token lacks the topics:write scope.", narrow.stderr)
        self.assertIn("Help: " + self.help("troubleshooting-insufficient_scope"), narrow.stderr)
        missing = self.run_tool(self.author, "--manifest-only", "--document", "no-such-guide")
        self.assertIn("Help: " + self.help("troubleshooting-not_found"), missing.stderr)
        no_token = self.invoke(None)
        self.assertIn("INTEROPHUB_TOKEN is not set", no_token.stderr); self.assertIn(self.help("create-a-token"), no_token.stderr)
        self.assertSecret(reader, self.reader)

    def test_newer_codes_are_explained(self):
        module = load_tool()
        closed = str(module.explain(403, {"error": "comments_closed", "help": "h"}, "fallback"))
        self.assertIn("403 comments_closed. Comments are closed on this version", closed); self.assertIn("Help: h", closed)
        scope = str(module.explain(403, {"error": "insufficient_scope", "requiredScope": "comments"}, "fallback"))
        self.assertIn("lacks the comments scope", scope); self.assertNotIn("Help:", scope)
        self.assertIn("editor of the guide's topic", str(module.explain(403, {"error": "forbidden"}, "fallback")))
        self.assertIn("500 request_failed. fallback", str(module.explain(500, {}, "fallback")))

    def test_an_html_answer_means_a_firewall(self):
        self.server.state.firewall = True
        for result in (self.invoke(self.author), self.run_tool(self.author, "--manifest-only"),
                       self.run_alone(self.author, "--check-token")):
            self.assertEqual(1, result.returncode)
            self.assertIn("403 from", result.stderr); self.assertIn("HTML page instead of InteropHub's JSON", result.stderr)
            self.assertIn("firewall", result.stderr); self.assertIn(self.help("troubleshooting-html-response"), result.stderr)
            self.assertSecret(result, self.author)
        self.assertIn("POST /api/guide/document/versions/latest", self.invoke(self.author).stderr)
        self.assertEqual([], self.builds())

    def test_settings_only_changes_a_published_label(self):
        self.assertEqual(0, self.run_tool(self.author, "--label", "v0.4.0").returncode)
        result = self.run_alone(self.author, "--settings-only", "--label", "v0.4.0", "--display", "current", "--comment-mode", "release")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("v0.4.0: display current, comments release.", result.stdout)
        self.assertEqual(1, len(self.builds()))
        # A public guide, published by its workflow, names the hub on the command line.
        self.config.write_text(json.dumps({"id": "document", "hosting": "github-pages"}))
        public = self.run_alone(self.author, "--settings-only", "--hub", self.base, "--label", "v0.4.0", "--display", "listed")
        self.assertEqual(0, public.returncode, public.stderr)
        unknown = self.run_alone(self.author, "--settings-only", "--hub", self.base, "--label", "v9.9.9", "--display", "listed")
        self.assertIn("does not know the label v9.9.9", unknown.stderr)
        for extra in ([], ["--label", "v0.4.0"], ["--display", "listed"],
                      ["--label", "v0.4.0", "--label", "latest", "--display", "listed"]):
            self.assertIn("--settings-only needs", self.run_alone(self.author, "--settings-only", "--hub", self.base, *extra).stderr)
        self.assertIn("leave out the guide", self.run_tool(self.author, "--settings-only", "--hub", self.base,
                                                           "--label", "v0.4.0", "--display", "listed").stderr)
        self.assertEqual(2, self.run_alone(self.author, "--settings-only", "--manifest-only").returncode)
        dry = self.run_alone(None, "--settings-only", "--hub", self.base, "--label", "v0.4.0", "--comment-mode", "closed", "--dry-run")
        self.assertEqual(0, dry.returncode); self.assertIn("Nothing was sent", dry.stdout)
        self.assertEqual("listed", self.labels()["v0.4.0"]["display"])

    def test_publishing_still_needs_the_guide(self):
        result = self.run_alone(self.author, "--label", "latest")
        self.assertEqual(1, result.returncode); self.assertIn("Give the built guide file", result.stderr)


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


def load_tool():
    import importlib.util  # noqa: PLC0415
    spec = importlib.util.spec_from_file_location("publish_guide_to_hub", TOOL)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def mock_hub_message(code):
    return load_tool().ERRORS[code]


if __name__ == "__main__": unittest.main()
