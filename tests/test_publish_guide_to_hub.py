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
        self.guide = self.root / "index.html"; self.guide.write_text("<!DOCTYPE html><title>Guide</title>")
        self.config = self.root / "guide.json"
        self.write_config("interophub")

    def tearDown(self): self.temp.cleanup()

    def write_config(self, hosting):
        self.config.write_text(json.dumps({"hosting": hosting, "comments": {"mode": "interophub", "hub": self.base, "document": "document"}}))

    def invoke(self, token=None, *extra):
        env = os.environ.copy()
        if token is None: env.pop("INTEROPHUB_TOKEN", None)
        else: env["INTEROPHUB_TOKEN"] = token
        return subprocess.run([sys.executable, str(TOOL), str(self.guide), "--config", str(self.config), "--label", "latest", *extra], text=True, capture_output=True, env=env)

    def test_success_and_replacement(self):
        first = self.invoke(self.author); second = self.invoke(self.author)
        self.assertEqual((0, 0), (first.returncode, second.returncode))
        self.assertIn("created", first.stdout); self.assertIn("replaced", second.stdout)

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


if __name__ == "__main__": unittest.main()
