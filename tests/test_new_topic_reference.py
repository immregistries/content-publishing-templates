"""Tests for tools/new_topic_reference.py: public and private profiles."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "new_topic_reference.py"
PROFILES = ROOT / "templates" / "topic-reference" / "profiles"

PUBLIC_ONLY = [
    "LICENSE",
    "LICENSE-CONTENT.md",
    "CODE_OF_CONDUCT.md",
    ".github/workflows/publish-guide.yml",
]
PRIVATE_ONLY = ["INTERNAL-USE.md"]
# Phrases that belong only to a published, openly licensed project.
PUBLIC_PHRASES = [
    "github.io",
    "CC BY",
    "Apache",
    "developed in the open",
    "for community discussion",
    "published Topic Reference",
    "published page",
    "## Public repository",
    "publish-guide",
]


def create(target: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), str(target), "--no-git", "--title", "Sample Topic",
         "--topic", "7", "--topic-name", "Sample Topic", *extra],
        capture_output=True, text=True,
    )


def project_text(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file()
    }


class ProfileFiles(unittest.TestCase):
    def test_profiles_define_the_same_placeholders(self):
        names = {p: sorted(f.name for f in (PROFILES / p / "fragments").iterdir()) for p in ("public", "private")}
        self.assertEqual(names["public"], names["private"])


class GenerateTopicReference(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_visibility_is_required(self):
        result = create(self.base / "sample-topic")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--visibility", result.stderr)

    def test_private_requires_owner(self):
        target = self.base / "sample-topic"
        result = create(target, "--visibility", "private")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--owner", result.stdout + result.stderr)
        self.assertFalse(target.exists())

    def test_public_project(self):
        target = self.base / "sample-topic"
        result = create(target, "--visibility", "public", "--with", "presentation")
        self.assertEqual(0, result.returncode, result.stderr)
        files = project_text(target)
        for name in PUBLIC_ONLY:
            self.assertIn(name, files)
        for name in PRIVATE_ONLY:
            self.assertNotIn(name, files)
        self.assertIn("https://immregistries.github.io/sample-topic/latest/", files["README.md"])
        self.assertIn("## Public repository", files["AGENTS.md"])
        guide = json.loads(files["guide.json"])
        self.assertEqual("Content licensed CC BY 4.0", guide["license"])
        self.assertEqual(7, guide["interophubTopic"])

    def test_private_project(self):
        target = self.base / "sample-topic"
        result = create(target, "--visibility", "private", "--owner", "example-org", "--with", "presentation")
        self.assertEqual(0, result.returncode, result.stderr)
        files = project_text(target)
        for name in PUBLIC_ONLY:
            self.assertNotIn(name, files)
        for name in PRIVATE_ONLY:
            self.assertIn(name, files)
        for name, text in files.items():
            for phrase in PUBLIC_PHRASES:
                self.assertNotIn(phrase, text, f"{name} contains {phrase!r}")
        self.assertIn("## Private repository", files["AGENTS.md"])
        self.assertIn("Do not enable GitHub Pages", files["AGENTS.md"])
        self.assertIn("AIRA internal use only", files["README.md"])
        self.assertIn('--include "INTERNAL-USE.md"', files["validate.ps1"])
        self.assertIn('--include "INTERNAL-USE.md"', files[".github/workflows/validate.yml"])
        guide = json.loads(files["guide.json"])
        self.assertEqual("https://github.com/example-org/sample-topic", guide["repository"])
        self.assertEqual(7, guide["interophubTopic"])
        self.assertNotIn("comments", guide)
        self.assertIn("internal use only", guide["license"])


if __name__ == "__main__":
    unittest.main()
