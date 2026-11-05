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


DIAGRAM = '```{mermaid}\nflowchart LR\n  A["<b>One</b><br/>two"] -->|"a & b"| B\n```\n'


class MermaidTests(unittest.TestCase):
    def test_braced_fences_become_plain_and_the_diagram_is_unchanged(self):
        text = "Before.\n\n" + DIAGRAM.replace("\n", "\r\n") + "\nAfter.\n"
        converted = build_guide.plain_mermaid_fences(text)
        self.assertEqual(converted, text.replace("```{mermaid}", "```mermaid"))

    def test_fences_inside_other_code_are_left_alone(self):
        text = "````markdown\n" + DIAGRAM + "````\n"
        self.assertEqual(build_guide.plain_mermaid_fences(text), text)

    def test_diagram_becomes_a_commentable_block_with_its_text(self):
        body = build_guide.body_html(build_guide.plain_mermaid_fences(DIAGRAM))
        self.assertIn('<div class="guide-diagram" data-anchor="document-start" data-block-index="0">', body)
        self.assertIn('<pre class="mermaid">flowchart LR', body)
        self.assertIn("&lt;b&gt;One&lt;/b&gt;&lt;br/&gt;two", body)
        self.assertNotIn("<code>", body)

    def test_library_is_inlined_only_when_there_are_diagrams(self):
        self.assertEqual(build_guide.diagram_scripts("<p>No diagrams.</p>"), "")
        scripts = build_guide.diagram_scripts('<pre class="mermaid">flowchart LR</pre>')
        self.assertIn("window.guideDiagramsReady", scripts)
        self.assertIn("mermaid.initialize", scripts)

    def test_ids_inside_scripts_are_not_page_ids(self):
        document = '<p id="a"></p><script>x = \'<g id="a"></g>\';</script>'
        self.assertEqual(build_guide.duplicate_ids(document), [])
        self.assertEqual(build_guide.duplicate_ids(document + '<p id="a"></p>'), ["a"])


if __name__ == "__main__":
    unittest.main()
