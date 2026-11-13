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


class HostingConfigTests(unittest.TestCase):
    def test_defaults_and_rules(self):
        self.assertEqual("github-pages", build_guide.hosting_config({}))
        self.assertEqual("github-pages", build_guide.hosting_config({"hosting": "github-pages"}))
        hosted = {"hosting": "interophub", "comments": {"mode": "interophub", "hub": "https://example.test/hub", "document": "sample-guide"}}
        self.assertEqual("interophub", build_guide.hosting_config(hosted))
        for invalid in ({"hosting": "other"}, {"hosting": "interophub"},
                        {"hosting": "interophub", "comments": {"mode": "local"}}):
            with self.assertRaises(RuntimeError):
                build_guide.hosting_config(invalid)


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


ROW_TABLE = (
    "# Chapter {#chapter}\n\n<!-- anchor: intro -->\n\nBefore.\n\n<!-- row-anchors -->\n\n"
    "| ID | Question |\n|---|---|\n| **OQ-1** | First |\n| [WD-2](x.md) | Second |\n\nAfter.\n"
)


class RowAnchorTests(unittest.TestCase):
    def test_each_row_is_a_review_area_named_from_its_first_cell(self):
        body = build_guide.body_html(build_guide.replace_anchors(ROW_TABLE))
        self.assertIn(
            '<tr id="oq-1" class="guide-row-block" data-guide-anchor="oq-1" '
            'data-anchor="oq-1" data-block-index="0">',
            body,
        )
        self.assertIn('<tr id="wd-2" class="guide-row-block"', body)
        self.assertIn('<div class="aira-table-wrap guide-row-table"><table', body)
        self.assertNotIn("guide-row-anchors", body)
        self.assertIn('<p data-anchor="intro" data-block-index="1">After.</p>', body)

    def test_tables_with_column_widths_are_styled_and_take_row_anchors(self):
        wide = (
            "<!-- row-anchors -->\n\n| ID | Question | Context | Status |\n"
            "|---|-----------|-----------|-----|\n"
            "| OQ-1 | " + "A long question that makes pandoc keep the column widths. " * 3
            + "| Context | Open |\n"
        )
        body = build_guide.body_html(build_guide.replace_anchors(wide))
        self.assertIn('<table class="aira-table" style="width:100%;">', body)
        self.assertIn('<tr id="oq-1" class="guide-row-block"', body)

    def test_other_tables_stay_one_block(self):
        body = build_guide.body_html("| A |\n|---|\n| OQ-1 |\n")
        self.assertIn('<div class="aira-table-wrap" data-anchor="document-start" data-block-index="0">', body)
        self.assertNotIn("guide-row-block", body)

    def test_a_directive_without_a_table_or_with_an_unusable_name_fails(self):
        with self.assertRaises(RuntimeError):
            build_guide.body_html(build_guide.replace_anchors("<!-- row-anchors -->\n\nText.\n"))
        with self.assertRaises(RuntimeError):
            build_guide.body_html(
                build_guide.replace_anchors("<!-- row-anchors -->\n\n| A |\n|---|\n| guide-x |\n")
            )

    def test_markdown_rows_give_the_same_names(self):
        import build_core_markdown  # noqa: PLC0415

        names, problems = build_core_markdown.row_anchors(ROW_TABLE)
        self.assertEqual([name for name, _ in names], ["oq-1", "wd-2"])
        self.assertEqual(problems, [])
        self.assertNotIn("row-anchors", build_core_markdown.strip_anchors(ROW_TABLE))


def sections_body(chapters: int, appendices: int) -> str:
    parts = [
        f'<section id="chapter-{n}" class="level2"><h2>Chapter {n}</h2></section>'
        for n in range(1, chapters + 1)
    ]
    parts += [
        f'<section id="appendix-{n}" class="level2"><h2>Appendix {n}: Extra</h2></section>'
        for n in range(1, appendices + 1)
    ]
    return "\n".join(parts)


class AppendixTests(unittest.TestCase):
    def test_seven_chapters_and_two_appendices_take_eight_links_without_a_warning(self):
        sections = build_guide.guide_sections(sections_body(7, 2), {"appendix-1": "Ideas"})
        nav = build_guide.section_nav(sections)
        self.assertEqual(nav.count("<a "), 8)
        self.assertIn('<a href="#appendix-1" data-guide-sections="appendix-1 appendix-2">Appendices</a>', nav)
        self.assertEqual(build_guide.chapter_warnings(sections), [])
        self.assertEqual(
            build_guide.appendix_list(sections),
            [{"id": "appendix-1", "label": "Ideas"}, {"id": "appendix-2", "label": "Appendix 2: Extra"}],
        )

    def test_a_single_appendix_keeps_its_own_link(self):
        sections = build_guide.guide_sections(sections_body(3, 1), {"appendix-1": "Decisions"})
        nav = build_guide.section_nav(sections)
        self.assertIn('<a href="#appendix-1">Decisions</a>', nav)
        self.assertNotIn("Appendices", nav)
        self.assertEqual(build_guide.appendix_list(sections), [])

    def test_eight_chapters_warn(self):
        warnings = build_guide.chapter_warnings(build_guide.guide_sections(sections_body(8, 2), {}))
        self.assertEqual(len(warnings), 1)
        self.assertIn("8 chapters, not counting appendices", warnings[0])

    def test_a_chapter_after_an_appendix_warns(self):
        body = sections_body(2, 1) + '\n<section id="late" class="level2"><h2>Late</h2></section>'
        warnings = build_guide.chapter_warnings(build_guide.guide_sections(body, {}))
        self.assertEqual(len(warnings), 1)
        self.assertIn("Late comes after an appendix", warnings[0])

    def test_appendices_are_listed_in_the_guide_data(self):
        sections = build_guide.guide_sections(sections_body(2, 2), {})
        document = build_guide.page(
            "Title", None, {}, "v1.0.0", build_guide.section_nav(sections), sections_body(2, 2), "",
            build_guide.appendix_list(sections),
        )
        self.assertIn('"appendices": [{"id": "appendix-1"', document)

    def test_collecting_ideas_has_its_own_tag(self):
        document = build_guide.page("Title", None, {"status": "Collecting ideas"}, "v1.0.0", "", "", "")
        self.assertIn('aira-tag--outline guide-status-tag">COLLECTING IDEAS', document)


if __name__ == "__main__":
    unittest.main()
