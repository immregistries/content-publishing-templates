"""Change markers (Workstream D) and the front section (Workstream C)."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_core_markdown  # noqa: E402
import change_markers  # noqa: E402
import check_content  # noqa: E402
import front_section  # noqa: E402

FIXTURE = ROOT / "tests" / "fixture-project"
TOOLS = ROOT / "tools"


def problems_of(text):
    return [problem for _, problem in change_markers.parse(text)[1]]


class ParseMarkers(unittest.TestCase):
    def test_block_heading_and_rows(self):
        text = (
            "<!-- changed v0.5.0: Before a paragraph. -->\n\nA paragraph.\n\n"
            "<!-- changed v0.5.0 feedback: Before a heading,\nover two lines. -->\n\n## Heading\n\n"
            "<!-- row-anchors -->\n<!-- changed v0.5.0 rows=OQ-13,OQ-14: Two rows. -->\n\n"
            "| ID | Text |\n|---|---|\n| OQ-13 | a |\n| OQ-14 | b |\n"
        )
        markers, problems = change_markers.parse(text)
        self.assertEqual([], problems)
        self.assertEqual(["block", "heading", "row-table"], [marker.covers for marker in markers])
        self.assertEqual("Before a heading, over two lines.", markers[1].note)
        self.assertEqual(["changed", "feedback", "changed"], [marker.level for marker in markers])
        self.assertEqual((["oq-13", "oq-14"], ["OQ-13", "OQ-14"]), (markers[2].rows, markers[2].row_labels))
        self.assertEqual("Changed in v0.5.0 (OQ-13, OQ-14)", markers[2].label())

    def test_markers_inside_code_are_text(self):
        self.assertEqual(([], []), change_markers.parse("```\n<!-- changed v0.5.0: shown as code -->\n```\n"))

    def test_errors(self):
        long_note = "x" * 301
        cases = {
            "<!-- changed 0.5: note -->\n\nText.\n": "not a release label",
            "<!-- changed v0.5.0 -->\n\nText.\n": "malformed",
            "<!-- changed v0.5.0:   -->\n\nText.\n": "needs a note",
            f"<!-- changed v0.5.0: {long_note} -->\n\nText.\n": "limit is 300",
            "<!-- changed v0.5.0: a <b>note</b> -->\n\nText.\n": "plain text",
            "Text.\n\n<!-- changed v0.5.0: nothing follows -->\n": "followed by the block",
            "<!-- changed v0.5.0 rows=A: no table -->\n\nText.\n": "only for a table with row anchors",
            "<!-- row-anchors -->\n<!-- changed v0.5.0: no rows -->\n\n| ID |\n|---|\n| A |\n": "must name its rows",
            "<!-- row-anchors -->\n<!-- changed v0.5.0 rows=B: missing -->\n\n| ID |\n|---|\n| A |\n": "not a row of the table",
        }
        for text, expected in cases.items():
            with self.subTest(expected=expected):
                found = problems_of(text)
                self.assertEqual(1, len(found), found)
                self.assertIn(expected, found[0])


class CurrentVersion(unittest.TestCase):
    def test_versions_compare_and_step(self):
        self.assertEqual("v0.3.1", change_markers.next_version("v0.3.0"))
        self.assertEqual("v1.0.1", change_markers.next_version("v1"))
        self.assertGreater(change_markers.version_key("v0.10.0"), change_markers.version_key("v0.9.9"))

    def test_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual("v0.5.0", change_markers.current_version(root, "v0.5.0", {}))
            self.assertIsNone(change_markers.current_version(root, "main", {}))
            workspace = {"keptIn": "workspace", "version": "v0.4.0"}
            self.assertEqual("v0.4.0", change_markers.current_version(root, "main", workspace))
            self.assertIsNone(change_markers.current_version(root, None, {"topicReferenceType": "workspace"}))

    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_newest_tag_plus_one_and_a_release_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=T", *args],
                               cwd=root, check=True, capture_output=True)

            git("init", "-q")
            (root / "a.txt").write_text("a")
            git("add", "a.txt"); git("commit", "-qm", "first"); git("tag", "v0.3.0")
            self.assertEqual("v0.3.0", change_markers.current_version(root, "v0.3.0-0-gabc", {}))
            (root / "a.txt").write_text("b")
            git("commit", "-qam", "second")
            self.assertEqual("v0.3.1", change_markers.current_version(root, "main", {}))
            # A folder inside a repository is not a project of its own.
            (root / "sub").mkdir()
            self.assertIsNone(change_markers.current_version(root / "sub", "main", {}))


class ReadingCopy(unittest.TestCase):
    def test_shown_markers_are_quoted_and_old_ones_leave_no_gap(self):
        text = ("Intro.\n\n<!-- changed v0.5.0 feedback: New rule. -->\nThe rule.\n\n"
                "<!-- changed v0.4.0: Old change. -->\n\nAfter.\n")
        result = change_markers.replace_for_reading_copy(text, "v0.5.0")
        self.assertEqual("Intro.\n\n> **Changed in v0.5.0, feedback wanted:** New rule.\n\nThe rule.\n\nAfter.\n", result)

    def test_the_fixture_reading_copy_lists_what_changed_and_quotes_the_notice(self):
        text = (FIXTURE / "CoreDocument.md").read_text(encoding="utf-8")
        self.assertIn("> **Status:** Test fixture", text)
        self.assertNotIn(":::", text)
        listing = text[text.index("# What changed in v0.2.0"):text.index("# Scope")]
        items = [line for line in listing.splitlines() if line.startswith("- ")]
        self.assertEqual(5, len(items))
        self.assertTrue(items[0].endswith("*(feedback wanted)*") and items[1].endswith("*(feedback wanted)*"))
        self.assertLess(text.index("# Executive Summary"), text.index("# What changed"))


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


SCOPE = ("# Scope\n\nPurpose.\n\n## In scope\n\n- One.\n\n## Out of scope\n\n"
         "- Two, in [another topic](https://example.org/).\n- Three (not covered by any current topic).\n")


class FrontChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def codes(self, topic_reference=True):
        report = front_section.check(self.root, topic_reference)
        return sorted((finding.code, finding.error) for finding in report.findings)

    def summary(self, words):
        write(self.root, front_section.SUMMARY_PATH,
              "# Executive Summary\n\n::: {.status-notice}\n**Status:** not counted at all here\n:::\n\n"
              "<!-- CONFIRM: not counted -->\n\n" + " ".join(["word"] * words) + "\n")

    def test_word_count_leaves_out_heading_notice_comments_and_links(self):
        text = ("# Executive Summary\n\n::: {.status-notice}\nNot counted.\n:::\n\n<!-- hidden words -->\n"
                "A [linked phrase](https://example.org/long/path) and v0.5.0 count.\n\n- one item\n")
        self.assertEqual(8, front_section.summary_words(text))

    def test_missing_files_only_in_a_topic_reference(self):
        self.assertEqual([("SCOPE_MISSING", True), ("SUMMARY_MISSING", True)], self.codes())
        self.assertEqual([], self.codes(topic_reference=False))

    def test_length_limits(self):
        write(self.root, front_section.SCOPE_PATH, SCOPE)
        for words, expected in ((149, [("SUMMARY_SHORT", False)]), (150, []), (550, []),
                                (551, [("SUMMARY_LONG", False)]), (651, [("SUMMARY_LONG", True)])):
            with self.subTest(words=words):
                self.summary(words)
                self.assertEqual(expected, self.codes())

    def test_scope_rules(self):
        self.summary(200)
        write(self.root, front_section.SCOPE_PATH,
              "# Scope\n\n## In scope\n\n## Out of scope\n\n- Unlinked.\n\n## Background\n\n- No.\n")
        self.assertEqual([("SCOPE_HEADING", True), ("SCOPE_OUT_UNLINKED", False), ("SCOPE_SECTION", True)],
                         self.codes())
        write(self.root, front_section.SCOPE_PATH, SCOPE + "\n## Not yet decided\n\n- Maybe.\n")
        self.assertEqual([], self.codes())

    def test_the_retired_file_is_an_error_with_migration_steps(self):
        self.summary(200)
        write(self.root, front_section.SCOPE_PATH, SCOPE)
        write(self.root, front_section.RETIRED_PATH, "# Status and Scope\n")
        report = front_section.check(self.root, True)
        self.assertEqual(["RETIRED_STATUS_AND_SCOPE"], [finding.code for finding in report.errors])
        self.assertIn("00-executive-summary.md", report.errors[0].message)

    def test_content_check_reports_codes(self):
        self.summary(100)
        write(self.root, front_section.SCOPE_PATH, SCOPE)
        write(self.root, "guide.json", json.dumps({"documentType": "Topic Reference"}))
        report = check_content.run_checks(self.root)
        self.assertIn("SUMMARY_SHORT", [warning["code"] for warning in report.coded_warnings])


def build(root, *extra, output="out.html"):
    return subprocess.run(
        [sys.executable, str(TOOLS / "build_guide.py"), "--root", str(root), "--assembly", "Example.qmd",
         "--output", output, *extra], capture_output=True, text=True, encoding="utf-8")


class GuideBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / "project"
        shutil.copytree(FIXTURE, cls.root)
        result = build(cls.root, "--version", "v0.2.0")
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.page = (cls.root / "out.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_markers_are_placed_on_their_areas(self):
        markers = json.loads(re.search(r'id="guide-change-markers">(.*?)</script>', self.page).group(1))
        self.assertEqual([
            {"anchor": "fixture-introduction", "blockIndex": 1, "version": "v0.2.0", "level": "changed"},
            {"anchor": "detail", "version": "v0.2.0", "level": "changed"},
            {"anchor": "review-item", "blockIndex": 0, "version": "v0.2.0", "level": "feedback"},
            {"anchor": "fx-1", "version": "v0.2.0", "level": "changed"},
            {"anchor": "fx-2", "version": "v0.2.0", "level": "feedback"},
        ], [{key: value for key, value in marker.items() if key != "note"} for marker in markers])
        self.assertNotIn("guide-change-slot", self.page)
        self.assertIn('<tr id="fx-1" class="guide-row-block"', self.page)

    def test_front_section_order_and_navigation(self):
        body = self.page[self.page.index('id="guide-content"'):]
        order = [body.index(text) for text in (
            'class="status-notice guide-status-banner"', 'id="executive-summary"', 'id="guide-what-changed"',
            'id="scope"', 'id="detail"')]
        self.assertEqual(sorted(order), order)
        nav = re.search(r'<nav class="aira-context-nav"[^>]*>(.*?)</nav>', self.page, re.DOTALL).group(1)
        self.assertNotIn("executive-summary", nav)
        self.assertNotIn('href="#scope"', nav)
        self.assertIn('"front": [{"id": "executive-summary"', self.page)
        self.assertIn("guide-scope-card--in", self.page)
        self.assertIn("guide-scope-card--undecided", self.page)
        listing = body[body.index('id="guide-what-changed"'):body.index('id="scope"')]
        levels = re.findall(r"guide-what-changed__level(?:--feedback)?\">([^<]+)<", listing)
        self.assertEqual(["Feedback wanted", "Feedback wanted", "Changed", "Changed", "Changed"], levels)

    def test_manifest_counts_markers_once(self):
        manifest = json.loads(re.search(r'id="guide-build-manifest">(.*?)</script>', self.page).group(1))
        self.assertEqual((5, 2, True, True), (manifest["structure"]["changeMarkers"],
                                              manifest["structure"]["feedbackMarkers"],
                                              manifest["structure"]["hasExecutiveSummary"],
                                              manifest["structure"]["hasScope"]))

    def test_old_markers_are_left_out(self):
        result = build(self.root, "--version", "v0.3.0", output="later.html")
        self.assertEqual(0, result.returncode, result.stderr)
        page = (self.root / "later.html").read_text(encoding="utf-8")
        self.assertNotIn('id="guide-change-markers"', page)
        self.assertNotIn('id="guide-what-changed"', page)

    def test_bad_markers_and_front_errors_fail_the_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            shutil.copytree(FIXTURE, root)
            detail = root / "content" / "01-detail.md"
            original = detail.read_text(encoding="utf-8")
            detail.write_text(original.replace("rows=FX-1", "rows=FX-9"), encoding="utf-8")
            result = build(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("FX-9, not a row of the table", result.stderr)
            detail.write_text(original + "\n<!-- changed v0.2.0: Nothing after this. -->\n", encoding="utf-8")
            self.assertIn("followed by the block", build(root).stderr)
            detail.write_text(original, encoding="utf-8")
            summary = root / "content" / "00-executive-summary.md"
            summary.write_text(summary.read_text(encoding="utf-8") + " word" * 700, encoding="utf-8")
            result = build(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("[SUMMARY_LONG]", result.stderr)


def minimal_docx(path, scope_bookmark="inside"):
    """A Word document with an Executive Summary and a Scope heading. Pandoc bookmarks
    a heading inside its paragraph; Quarto writes the bookmark just before it."""
    heading = '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>{bookmark}<w:r><w:t>{text}</w:t></w:r></w:p>'
    scope = '<w:bookmarkStart w:id="2" w:name="scope" />'
    body = (heading.format(bookmark='<w:bookmarkStart w:id="1" w:name="executive-summary"/><w:bookmarkEnd w:id="1"/>',
                           text="Executive Summary")
            + "<w:p><w:r><w:t>Summary text.</w:t></w:r></w:p>"
            + (scope if scope_bookmark == "before" else "")
            + heading.format(bookmark=scope if scope_bookmark == "inside" else "", text="Scope")
            + ('<w:bookmarkEnd w:id="2" />' if scope_bookmark else ""))
    document = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body>' + body + "<w:sectPr/></w:body></w:document>")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels",
                         '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>')
        archive.writestr("[Content_Types].xml",
                         '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')


class WordInfographic(unittest.TestCase):
    def test_the_infographic_goes_before_the_scope_heading(self):
        source = ROOT / "templates" / "topic-reference" / "project" / "content" / "infographic.yml"
        png = ROOT / "templates" / "guide" / "AIRA_2018Logo_BlueGreen_Hor.png"
        for has_scope, before in (("inside", "Scope"), ("before", "Scope"), (None, "Executive Summary")):
            with tempfile.TemporaryDirectory() as directory, self.subTest(has_scope=has_scope):
                root = Path(directory)
                write(root, "content/infographic.yml",
                      source.read_text(encoding="utf-8").replace("{{TOPIC_NAME}}", "Sample")
                      .replace("{{INFOGRAPHIC_TOPIC_LINK}}", "none"))
                (root / "output").mkdir()
                shutil.copy(png, root / "output" / "infographic.png")
                minimal_docx(root / "doc.docx", has_scope)
                result = subprocess.run([sys.executable, str(TOOLS / "insert_word_infographic.py"), "doc.docx",
                                         "--root", str(root)], capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                document = zipfile.ZipFile(root / "doc.docx").read("word/document.xml").decode("utf-8")
                figure = document.index('w:name="primary-infographic"')
                self.assertLess(figure, document.index(f"<w:t>{before}</w:t>"))
                if has_scope:
                    self.assertGreater(figure, document.index("Summary text."))
                if has_scope == "before":
                    # The figure stays out of the Scope's bookmark.
                    self.assertLess(figure, document.index('w:name="scope"'))


@unittest.skipUnless(shutil.which("quarto"), "Quarto is not installed")
class WordFilter(unittest.TestCase):
    """The Lua filter shows markers for the current version, the What changed list, and the Scope table."""

    def test_render(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            shutil.copytree(FIXTURE, root)
            (root / "_quarto.yml").write_text(
                "project:\n  type: default\n  output-dir: output\n  render:\n    - Example.qmd\n"
                "format:\n  docx:\n    reference-doc: " + (ROOT / "templates/word/aira-reference-document.docx").as_posix()
                + "\n    filters:\n      - " + (ROOT / "templates/word/topic-reference.lua").as_posix() + "\n",
                encoding="utf-8")
            for version, notes in (("v0.2.0", 5), ("v0.3.0", 0)):
                result = subprocess.run(["quarto", "render", "-M", f"change-version:{version}"], cwd=root,
                                        capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr[-2000:])
                document = zipfile.ZipFile(root / "output" / "Example.docx").read("word/document.xml").decode("utf-8")
                text = re.sub(r"<[^>]+>", "", re.sub(r"<w:p\b", "\n<w:p", document))
                self.assertEqual(notes, text.count("Changed in v0.2.0"), version)
                self.assertEqual(bool(notes), "What changed in v0.2.0" in text)
                self.assertIn('w:val="StatusNotice"', document)
                self.assertIn("w:gridSpan", document)
                self.assertNotIn("&lt;!-- changed", document)
                if notes:
                    self.assertIn("Feedback wanted. Changed in v0.2.0 (FX-2)", text)


if __name__ == "__main__":
    unittest.main()
