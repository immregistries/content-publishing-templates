"""Tests that VERSION, process-releases.json, and CHANGELOG.md must agree."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import process_release  # noqa: E402

REGISTRY = [
    {"version": "v0.3.0", "date": "2026-02-01", "upgradeImpact": "rebuild", "summary": "Third."},
    {"version": "v0.2.0", "date": "2026-01-15", "upgradeImpact": "content", "summary": "Second."},
    {"version": "v0.1.0", "date": "2026-01-01", "upgradeImpact": "config", "summary": "First."},
]
CHANGELOG = (
    "# Changelog\n\n## v0.3.0\n\n- Third.\n\n**Upgrade impact:** rebuild\n\n"
    "## v0.2.0\n\n- Second.\n\n**Upgrade impact:** content\n\n## v0.1.0\n\n- First.\n"
)


class ReleaseRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.write("v0.3.0\n", REGISTRY, CHANGELOG)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, version, registry, changelog):
        (self.root / "VERSION").write_text(version, encoding="utf-8")
        (self.root / "process-releases.json").write_text(json.dumps(registry), encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

    def problems(self):
        return "\n".join(process_release.release_problems(self.root))

    def test_records_that_agree_pass(self):
        self.assertEqual("", self.problems())

    def test_this_repository_agrees(self):
        self.assertEqual([], process_release.release_problems(ROOT))
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "process_release.py")],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout)

    def test_version_must_match_the_registry_and_changelog(self):
        self.write("v0.4.0\n", REGISTRY, CHANGELOG)
        problems = self.problems()
        self.assertIn("VERSION is v0.4.0 but the newest entry", problems)
        self.assertIn("newest CHANGELOG.md heading is v0.3.0", problems)
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "process_release.py"), "--root", str(self.root)],
                                capture_output=True, text=True)
        self.assertEqual(1, result.returncode)

    def test_the_registry_and_changelog_list_the_same_releases(self):
        self.write("v0.3.0\n", REGISTRY[:2], CHANGELOG)
        self.assertIn("not in the registry: v0.1.0", self.problems())
        self.write("v0.3.0\n", [REGISTRY[0], REGISTRY[2], REGISTRY[1]], CHANGELOG)
        self.assertIn("newest first", self.problems())

    def test_impacts_must_be_valid_and_match(self):
        bad = [dict(REGISTRY[0], upgradeImpact="minor")] + REGISTRY[1:]
        self.write("v0.3.0\n", bad, CHANGELOG)
        self.assertIn("upgradeImpact 'minor' must be one of rebuild, config, content", self.problems())
        self.write("v0.3.0\n", REGISTRY, CHANGELOG.replace("**Upgrade impact:** content", "**Upgrade impact:** rebuild"))
        self.assertIn("v0.2.0 says upgrade impact rebuild but process-releases.json says content", self.problems())
        self.write("v0.3.0\n", REGISTRY, CHANGELOG.replace("**Upgrade impact:** rebuild", "**Upgrade impact:** huge"))
        self.assertIn("upgrade impact 'huge' must be one of", self.problems())

    def test_the_newest_changelog_entry_states_its_impact(self):
        self.write("v0.3.0\n", REGISTRY, CHANGELOG.replace("\n**Upgrade impact:** rebuild\n", ""))
        self.assertIn("v0.3.0 needs an '**Upgrade impact:**' line", self.problems())

    def test_entries_are_complete(self):
        incomplete = [{"version": "v0.3.0", "date": "Feb 1", "upgradeImpact": "rebuild"}] + REGISTRY[1:]
        self.write("v0.3.0\n", incomplete, CHANGELOG)
        problems = self.problems()
        self.assertIn("must have exactly the keys", problems)
        self.assertIn("date must be written as", problems)
        self.assertIn("summary is required", problems)


if __name__ == "__main__":
    unittest.main()
