"""Tests for how the web guide prepares the core document's Markdown."""

import base64
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_guide  # noqa: E402

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class PreparedMarkdownTests(unittest.TestCase):
    def test_local_images_are_embedded_and_other_files_link_to_the_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            content = root / "content"
            (content / "images").mkdir(parents=True)
            (content / "images" / "figure.png").write_bytes(PNG)
            (content / "notes.txt").write_text("notes", encoding="utf-8")
            chapter = content / "01-chapter.md"
            chapter.write_text(
                "# Chapter\n\n![A figure](images/figure.png)\n\n[Notes](notes.txt)\n",
                encoding="utf-8",
            )

            markdown = build_guide.prepared_markdown(
                root, [chapter], "https://github.com/example/project", "main"
            )

        self.assertIn("![A figure](data:image/png;base64,", markdown)
        self.assertIn("[Notes](https://github.com/example/project/blob/main/content/notes.txt)", markdown)


if __name__ == "__main__":
    unittest.main()
