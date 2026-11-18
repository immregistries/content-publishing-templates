"""Tests for how the web guide prepares the core document's Markdown."""

import base64
import json
import re
import shutil
import subprocess
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


FIXTURE = ROOT / "tests" / "fixture-project"
MANIFEST_PATTERN = re.compile(
    r'<script type="application/json" id="guide-build-manifest">(.*?)</script>', re.DOTALL
)
WARNING_CODES = {
    "CHAPTER_COUNT", "APPENDIX_ORDER", "CONFIRM_OPEN", "SUMMARY_MISSING", "SUMMARY_LONG",
    "SUMMARY_SHORT", "SCOPE_MISSING", "SCOPE_OUT_UNLINKED", "STALE_CHANGE_MARKER",
    "RETIRED_STATUS_AND_SCOPE", "INFOGRAPHIC_WARNING",
}
ABSOLUTE_PATH = re.compile(r"(?:^|[\s\"'(])(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|tmp|var|mnt|private)/)")


def build_fixture(root: Path, output: Path, *extra: str) -> str:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_guide.py"), "--root", str(root),
         "--assembly", "Example.qmd", "--output", str(output), *extra],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    return output.read_text(encoding="utf-8")


def manifest_of(document: str) -> dict:
    head = document[: document.index("</head>")]
    match = MANIFEST_PATTERN.search(head)
    if not match:
        raise AssertionError("The guide has no build manifest in its <head>.")
    return json.loads(match.group(1))


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.document = build_fixture(FIXTURE, Path(cls.temp.name) / "guide.html", "--version", "v1.2.3")
        cls.manifest = manifest_of(cls.document)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_the_manifest_matches_schema_1(self):
        manifest = self.manifest
        self.assertEqual(1, manifest["schema"])
        self.assertEqual("content-publishing-templates", manifest["generator"])
        import process_release  # noqa: PLC0415

        self.assertEqual(process_release.read_version(), manifest["processVersion"])
        self.assertEqual(process_release.read_registry(), manifest["processReleases"])
        self.assertEqual(
            {"schema", "generator", "processVersion", "processCommit", "processReleases",
             "document", "build", "structure", "checks"} - ({"processCommit"} - set(manifest)),
            set(manifest),
        )
        self.assertEqual({
            "id": "example-core-document", "title": "Example Core Document", "status": "Draft",
            "version": "v1.2.3", "keptIn": "git", "visibility": "public", "hosting": "github-pages",
            "interophubTopic": 7,
        }, manifest["document"])
        build = manifest["build"]
        self.assertRegex(build["builtAt"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertLessEqual({"builtAt", "python"}, set(build))
        self.assertLessEqual(set(build), {"builtAt", "sourceCommit", "sourceDirty", "python", "pandoc"})
        # This release knows chapters, appendices, and the infographic, and leaves
        # out what it cannot know rather than reporting it as false.
        self.assertEqual({"chapters": 2, "appendices": 0, "hasInfographic": False}, manifest["structure"])
        self.assertEqual(1, manifest["checks"]["confirmOpen"])
        self.assertNotIn("openIdeas", manifest["checks"])

    def test_warnings_have_stable_codes_and_no_hidden_text(self):
        warnings = self.manifest["checks"]["warnings"]
        self.assertTrue(warnings)
        for warning in warnings:
            self.assertIn(warning["code"], WARNING_CODES)
            self.assertLessEqual(set(warning), {"code", "message", "file"})
            self.assertTrue(warning["message"])
        confirm = next(warning for warning in warnings if warning["code"] == "CONFIRM_OPEN")
        self.assertEqual("content/01-detail.md", confirm["file"])
        # The CONFIRM note is a hidden comment for authors; its text stays out.
        self.assertNotIn("Fixture CONFIRM note", json.dumps(self.manifest))

    def test_the_manifest_holds_no_absolute_paths_or_locations(self):
        text = json.dumps(self.manifest)
        self.assertNotIn(str(ROOT), text)
        self.assertNotIn(str(ROOT).replace("\\", "/"), text)
        self.assertNotIn(str(Path(self.temp.name)), text)
        for value in strings(self.manifest):
            self.assertIsNone(ABSOLUTE_PATH.search(value), value)

    def test_coded_section_warnings_name_the_assembly(self):
        warnings = build_guide.section_warnings(
            build_guide.guide_sections(sections_body(8, 1) + '\n<section id="late" class="level2"><h2>Late</h2></section>', {}),
            "Project.qmd",
        )
        self.assertEqual(["CHAPTER_COUNT", "APPENDIX_ORDER"], [warning["code"] for warning in warnings])
        self.assertEqual({"Project.qmd"}, {warning["file"] for warning in warnings})

    def test_script_text_is_escaped(self):
        script = build_guide.manifest_script({"schema": 1, "title": "</script><b>x</b>"})
        inner = script[script.index(">") + 1: script.rindex("</script>")]
        self.assertNotIn("<", inner)
        self.assertEqual("</script><b>x</b>", json.loads(inner)["title"])

    def test_a_workspace_guide_has_no_source_commit_or_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            shutil.copytree(FIXTURE, root)
            config = json.loads((root / "guide.json").read_text(encoding="utf-8"))
            config.update({"topicReferenceType": "workspace", "location": "Shared Folder/Secret Place"})
            config.pop("repository")
            (root / "guide.json").write_text(json.dumps(config), encoding="utf-8")
            manifest = manifest_of(build_fixture(root, root / "output" / "index.html"))
        self.assertNotIn("sourceCommit", manifest["build"])
        self.assertNotIn("sourceDirty", manifest["build"])
        self.assertEqual("workspace", manifest["document"]["keptIn"])
        self.assertNotIn("Secret Place", json.dumps(manifest))

    def test_outside_git_the_source_state_is_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual({}, build_guide.source_state(Path(directory), "git"))
        self.assertEqual({}, build_guide.source_state(ROOT, "workspace"))
        state = build_guide.source_state(ROOT, "git")
        self.assertEqual({"sourceCommit", "sourceDirty"}, set(state))

    def test_visibility_comes_from_the_settings(self):
        self.assertEqual("public", build_guide.visibility({}, "github-pages"))
        self.assertEqual("private", build_guide.visibility({}, "interophub"))
        self.assertIsNone(build_guide.visibility({}, "local"))
        self.assertEqual("private", build_guide.visibility({"visibility": "private"}, "local"))


if __name__ == "__main__":
    unittest.main()
