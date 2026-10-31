"""Tests for tools/check_products.py against a throwaway Git project."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "check_products.py"


def git(root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.org", *args],
        cwd=root, check=True, capture_output=True,
    )


def run(root, *args):
    return subprocess.run(
        [sys.executable, str(TOOL), "--root", str(root), *args],
        capture_output=True, text=True,
    )


class CheckProductsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "content").mkdir()
        (self.root / "content" / "01-idea.md").write_text("# Idea\n\nText.\n", encoding="utf-8")
        (self.root / "Project.qmd").write_text("---\ntitle: T\n---\n", encoding="utf-8")
        product = self.root / "products" / "deck"
        product.mkdir(parents=True)
        (product / "manifest.yml").write_text(
            "product_id: deck\ncore_release: v0.1.0\n\nsources:\n"
            "  - path: ../../content/01-idea.md\n    revision: null\n",
            encoding="utf-8",
        )
        (product / "slides.json").write_text(
            json.dumps({"slides": [{"sources": ["content/01-idea.md"]}]}), encoding="utf-8"
        )
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "start")
        git(self.root, "tag", "v0.1.0")

    def tearDown(self):
        self.temp.cleanup()

    def test_current_product(self):
        result = run(self.root, "--fail-on-stale")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Current with the core.", result.stdout)

    def test_changed_core_needs_review(self):
        (self.root / "content" / "02-more.md").write_text("# More\n", encoding="utf-8")
        result = run(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NEEDS REVIEW", result.stdout)
        self.assertIn("added: content/02-more.md", result.stdout)
        self.assertEqual(run(self.root, "--fail-on-stale").returncode, 1)

    def test_renamed_source_is_missing(self):
        git(self.root, "mv", "content/01-idea.md", "content/02-idea.md")
        result = run(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("renamed: content/01-idea.md -> content/02-idea.md", result.stdout)
        self.assertIn("manifest.yml sources: ../../content/01-idea.md", result.stdout)
        self.assertIn("slides.json slide 1: content/01-idea.md", result.stdout)

    def test_unknown_release(self):
        manifest = self.root / "products" / "deck" / "manifest.yml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace("v0.1.0", "working-draft"), encoding="utf-8"
        )
        result = run(self.root)
        self.assertIn("release is not a Git tag or commit", result.stdout)


if __name__ == "__main__":
    unittest.main()
