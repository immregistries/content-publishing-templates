"""Tests for the primary infographic: specification reader, checks, layout, and Word placement."""

import copy
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import infographic  # noqa: E402
from headless_browser import find_browser  # noqa: E402

CONTENT = """# Overview

## Purpose

Text.

## First idea

## Second idea {#second}

## Third idea

<!-- anchor: fourth-anchor -->
"""

SPEC = {
    "layout": "topic-at-a-glance",
    "arrangement": "sequence",
    "title": "Sample Topic",
    "purpose": {"text": "Explain the sample topic in one sentence.", "ref": "purpose"},
    "ideas": [
        {"id": "one", "label": "First", "text": "The first idea.", "ref": "first-idea"},
        {"id": "two", "label": "Second", "text": "The second idea.", "ref": "second"},
        {"id": "three", "label": "Third", "ref": "third-idea"},
    ],
    "relationships": [
        {"from": "one", "to": "two", "label": "leads to", "ref": "first-idea"},
        {"from": "two", "to": "three", "ref": "fourth-anchor"},
    ],
    "alt": "Three ideas in sequence.",
}
TARGETS = {"overview", "purpose", "first-idea", "second", "third-idea", "fourth-anchor"}
CONFIG = {"status": "Draft", "interophubTopic": 7, "license": "Example license"}


def problems(spec, root=ROOT):
    report = infographic.check_spec(spec, root, TARGETS)
    result = infographic.layout(spec, "Draft", "v1.0.0", "2026-01-01", 7, "Notice")
    return report, result.errors


class ReadYaml(unittest.TestCase):
    def test_block_yaml_subset(self):
        text = """# comment
layout: topic-at-a-glance
title: "Quoted: title"
purpose:
  text: >-
    Folded text
    over lines.
  ref: purpose
ideas:
  - id: one
    label: Plain text that
      continues here
    ref: x # trailing comment
  - id: two
    label: 'It''s'
    ref: y
flags: []
topic_link: false
count: 3
"""
        data = infographic.load_yaml(text, "spec.yml")
        self.assertEqual("Quoted: title", data["title"])
        self.assertEqual("Folded text over lines.", data["purpose"]["text"])
        self.assertEqual("Plain text that continues here", data["ideas"][0]["label"])
        self.assertEqual("x", data["ideas"][0]["ref"])
        self.assertEqual("It's", data["ideas"][1]["label"])
        self.assertEqual([], data["flags"])
        self.assertIs(False, data["topic_link"])
        self.assertEqual(3, data["count"])

    def test_rejects_ambiguous_yaml(self):
        for text in ["a: b: c\n", "a: 1\na: 2\n", "a: [1, 2]\n", "a:\n  b: 1\n   c: 2\n"]:
            with self.assertRaises(infographic.SpecError, msg=text):
                infographic.load_yaml(text, "spec.yml")

    def test_product_briefs_are_readable(self):
        for brief in (ROOT / "templates" / "topic-reference" / "profiles").glob("*/products/infographic/brief.yml"):
            text = brief.read_text(encoding="utf-8").replace("{{TOPIC}}", "7")
            self.assertIsInstance(infographic.load_yaml(text, str(brief)), dict)


class CheckSpec(unittest.TestCase):
    def test_valid_spec(self):
        report, layout_errors = problems(SPEC)
        self.assertEqual([], report.errors)
        self.assertEqual([], report.warnings)
        self.assertEqual([], layout_errors)

    def test_unresolved_reference_fails(self):
        spec = copy.deepcopy(SPEC)
        spec["ideas"][0]["ref"] = "missing-heading"
        spec["relationships"][0]["ref"] = None
        report, _ = problems(spec)
        text = "\n".join(report.errors)
        self.assertIn("'missing-heading' does not match", text)
        self.assertIn("relationship 1 needs a ref", text)

    def test_missing_alt_purpose_and_ideas_fail(self):
        spec = copy.deepcopy(SPEC)
        del spec["alt"]
        del spec["purpose"]
        spec["ideas"] = spec["ideas"][:2]
        report, _ = problems(spec)
        text = "\n".join(report.errors)
        self.assertIn("alt is required", text)
        self.assertIn("purpose needs text and a ref", text)
        self.assertIn("ideas must list 3 to 6", text)

    def test_missing_artwork_fails(self):
        spec = copy.deepcopy(SPEC)
        spec["artwork"] = {"file": "content/assets/missing.png"}
        report, _ = problems(spec)
        self.assertIn("artwork file content/assets/missing.png does not exist", "\n".join(report.errors))

    def test_relationship_errors(self):
        spec = copy.deepcopy(SPEC)
        spec["relationships"].append({"from": "two", "to": "one", "ref": "second"})
        spec["relationships"].append({"from": "one", "to": "nobody", "ref": "second"})
        report, _ = problems(spec)
        text = "\n".join(report.errors)
        self.assertIn("repeats a pair", text)
        self.assertIn("'nobody' is not an idea id", text)

    def test_starter_text_warns(self):
        spec = copy.deepcopy(SPEC)
        spec["alt"] = "CONFIRM: describe it."
        report, _ = problems(spec)
        self.assertEqual([], report.errors)
        self.assertEqual(1, len(report.warnings))
        self.assertIn("alt", report.warnings[0])

    def test_overflow_fails(self):
        spec = copy.deepcopy(SPEC)
        spec["ideas"][0]["text"] = "A very long description that goes on. " * 20
        spec["title"] = "An extremely long topic title that cannot possibly fit on two lines " * 2
        spec["relationships"][0]["label"] = "Incomprehensibilities-everywhere-unbroken"
        _, errors = problems(spec)
        text = "\n".join(errors)
        self.assertIn("title needs", text)
        self.assertIn("label 'Incomprehensibilities", text)

    def test_arrow_across_an_idea_fails(self):
        spec = copy.deepcopy(SPEC)
        spec["relationships"] = [{"from": "one", "to": "three", "ref": "second"}]
        _, errors = problems(spec)
        self.assertIn("crosses idea 'two'", "\n".join(errors))

    def test_every_arrangement_and_size_lays_out(self):
        for arrangement in sorted(infographic.ARRANGEMENTS):
            for count in range(3, 7):
                ideas = [{"id": f"i{n}", "label": f"Idea {n}", "text": "A short sentence.", "ref": "purpose"}
                         for n in range(count)]
                relationships = []
                if arrangement != "set":
                    order = list(range(count)) + ([0] if arrangement == "cycle" else [])
                    relationships = [{"from": f"i{a}", "to": f"i{b}", "label": "then", "ref": "purpose"}
                                     for a, b in zip(order, order[1:])]
                spec = dict(SPEC, arrangement=arrangement, ideas=ideas, relationships=relationships)
                report, errors = problems(spec)
                self.assertEqual([], report.errors, (arrangement, count))
                self.assertEqual([], errors, (arrangement, count))


class Arrangement(unittest.TestCase):
    def ideas(self, count, icon=None):
        return [dict({"id": f"i{n}", "label": f"Idea {n}", "text": "A short sentence.", "ref": "purpose"},
                     **({"icon": icon} if icon else {})) for n in range(count)]

    def test_four_idea_sequence_reads_left_to_right(self):
        result = infographic.layout(dict(SPEC, ideas=self.ideas(4), relationships=[]), "Draft", None,
                                    "2026-01-01", 7, None)
        boxes = [card.box for card in result.cards]
        self.assertEqual(1, len({round(box.y) for box in boxes}))
        self.assertEqual(sorted(box.x for box in boxes), [box.x for box in boxes])

    def test_four_idea_cycle_is_a_loop(self):
        result = infographic.layout(dict(SPEC, arrangement="cycle", ideas=self.ideas(4), relationships=[]),
                                    "Draft", None, "2026-01-01", 7, None)
        (a, b, c, d) = [card.box for card in result.cards]
        self.assertEqual((a.y, c.y), (b.y, d.y))
        self.assertLess(a.y, c.y)
        self.assertEqual((a.x, b.x), (d.x, c.x))

    def test_sequence_and_cycle_are_numbered_and_set_is_not(self):
        for arrangement, expected in (("sequence", [1, 2, 3]), ("cycle", [1, 2, 3]), ("set", [None] * 3)):
            result = infographic.layout(dict(SPEC, arrangement=arrangement, relationships=[]), "Draft", None,
                                        "2026-01-01", 7, None)
            self.assertEqual(expected, [card.number for card in result.cards], arrangement)

    def test_icons_are_checked_and_drawn(self):
        report = infographic.check_spec(dict(SPEC, ideas=self.ideas(3, "no-such-icon")), ROOT, TARGETS)
        self.assertIn("icon 'no-such-icon' is not in", " ".join(report.errors))
        spec = dict(SPEC, arrangement="sequence", ideas=self.ideas(4, "users"), relationships=[])
        self.assertEqual([], infographic.check_spec(spec, ROOT, TARGETS).errors)
        result = infographic.layout(spec, "Draft", None, "2026-01-01", 7, None)
        self.assertEqual([], result.errors)
        svg = infographic.render_svg(result, ROOT)
        self.assertEqual(4, svg.count('class="ig-icon"'))
        self.assertEqual(4, svg.count('class="ig-number"'))

    def test_vendored_assets_have_licenses(self):
        assets = ROOT / "templates" / "infographic"
        self.assertTrue((assets / "fonts" / "OFL.txt").is_file())
        self.assertTrue((assets / "icons" / "LICENSE").is_file())
        self.assertGreater(len(infographic.icon_names()), 20)
        for name in infographic.icon_names():
            self.assertNotIn("<script", (assets / "icons" / f"{name}.svg").read_text(encoding="utf-8"))

    def test_open_sans_metrics(self):
        self.assertGreater(infographic.text_width("Wording", 20, 700), infographic.text_width("Wording", 20))
        self.assertAlmostEqual(infographic.text_width("a", 1000), infographic.advance_widths(400)["a"])


class ReleaseLabel(unittest.TestCase):
    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.org", *args],
                       cwd=self.root, check=True, capture_output=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        (self.root / "file.txt").write_text("one", encoding="utf-8")
        self.git("add", "file.txt")
        self.git("commit", "-q", "-m", "first")

    def tearDown(self):
        self.temp.cleanup()

    def test_only_an_exact_clean_tag_is_drawn(self):
        self.assertIsNone(infographic.release_label(self.root))
        self.git("tag", "v1.2.0")
        self.assertEqual("v1.2.0", infographic.release_label(self.root))
        self.assertEqual("v1.2.0", infographic.release_label(self.root, "v1.2.0"))
        self.assertIsNone(infographic.release_label(self.root, "v1.2.0-3-gabc1234"))
        (self.root / "file.txt").write_text("changed", encoding="utf-8")
        self.assertIsNone(infographic.release_label(self.root))
        self.git("commit", "-q", "-am", "second")
        self.assertIsNone(infographic.release_label(self.root))

    def test_a_non_release_tag_is_not_drawn(self):
        self.git("tag", "draft-for-review")
        self.assertIsNone(infographic.release_label(self.root))


class Render(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "content").mkdir()
        (self.root / "content" / "00-overview.md").write_text(CONTENT, encoding="utf-8")
        lines = """layout: topic-at-a-glance
arrangement: sequence
title: Sample <Topic> & more
purpose:
  text: Explain the sample topic in one sentence.
  ref: purpose
ideas:
  - id: one
    label: First
    ref: first-idea
  - id: two
    label: Second
    ref: second
  - id: three
    label: Third
    ref: third-idea
relationships:
  - from: one
    to: two
    label: leads to
    ref: first-idea
alt: Three ideas in sequence.
topic_link: false
"""
        (self.root / "content" / "infographic.yml").write_text(lines, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_svg_contents(self):
        svg, report = infographic.build(self.root, CONFIG, "v1.2.3", "2026-01-01")
        self.assertEqual([], report.errors)
        self.assertIn("Sample &lt;Topic&gt; &amp; more", svg)
        self.assertIn("DRAFT", svg)
        self.assertIn("Release v1.2.3", svg)
        self.assertIn("Open Sans Infographic", svg)
        self.assertIn("data:font/woff;base64,", svg)
        self.assertIn("Built 2026-01-01", svg)
        self.assertIn("InteropHub topic 7<", svg)
        self.assertNotIn("informatics.immregistries.org", svg)
        self.assertIn("Example license", svg)
        self.assertIn('role="img"', svg)
        self.assertNotIn('href="#', svg)

    def test_guide_svg_links_each_part(self):
        svg, _ = infographic.build(self.root, CONFIG, "v1", "2026-01-01", links=True, id_prefix="g")
        for ref in ("purpose", "first-idea", "second", "third-idea"):
            self.assertIn(f'href="#{ref}"', svg)
        self.assertIn('id="g-arrow"', svg)

    def test_topic_link_and_notice_override(self):
        spec_path = self.root / "content" / "infographic.yml"
        spec_path.write_text(spec_path.read_text(encoding="utf-8").replace("topic_link: false", "notice: Custom notice"), encoding="utf-8")
        svg, _ = infographic.build(self.root, CONFIG, "v1", "2026-01-01")
        self.assertIn("https://informatics.immregistries.org/hub/es/topic/7", svg)
        self.assertIn("Custom notice", svg)
        self.assertNotIn("Example license", svg)

    def test_artwork_is_layered_under_the_content(self):
        assets = self.root / "content" / "assets"
        assets.mkdir()
        shutil.copyfile(infographic.LOGO, assets / "art.png")
        spec_path = self.root / "content" / "infographic.yml"
        spec_path.write_text(spec_path.read_text(encoding="utf-8") + "artwork:\n  file: content/assets/art.png\n  opacity: 0.2\n")
        svg, report = infographic.build(self.root, CONFIG, "v1", "2026-01-01")
        self.assertEqual([], report.errors)
        self.assertLess(svg.index('class="ig-artwork"'), svg.index('class="ig-card"'))
        self.assertIn('opacity="0.2"', svg)

    @unittest.skipUnless(find_browser(), "Chrome or Edge is not installed")
    def test_browser_export_and_word_placement(self):
        (self.root / "guide.json").write_text('{"status": "Review", "interophubTopic": 7}')
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_infographic.py"), "--root", str(self.root),
             ], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        png = (self.root / "output" / "infographic.png").read_bytes()
        self.assertEqual(b"\x89PNG", png[:4])
        self.assertTrue((self.root / "output" / "infographic.pdf").read_bytes().startswith(b"%PDF"))

        docx = self.root / "output" / "Sample.docx"
        with zipfile.ZipFile(docx, "w") as archive:
            archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
            archive.writestr("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>')
            archive.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr></w:p><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr></w:p><w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>')
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "insert_word_infographic.py"), str(docx),
                 "--root", str(self.root)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        with zipfile.ZipFile(docx) as archive:
            document = archive.read("word/document.xml").decode()
            self.assertEqual(1, document.count("<w:drawing>"))
            self.assertIn('descr="Three ideas in sequence."', document)
            self.assertLess(document.index("<w:drawing>"), document.index('w:val="Heading1"'))
            self.assertIn("xmlns:wp=", document)
            self.assertIn('Extension="png"', archive.read("[Content_Types].xml").decode())
            self.assertIn("rIdPrimaryInfographic", archive.read("word/_rels/document.xml.rels").decode())
            self.assertEqual(png, archive.read("word/media/primary-infographic.png"))

    @unittest.skipUnless(find_browser(), "Chrome or Edge is not installed")
    def test_browser_reports_overflow_the_estimate_misses(self):
        spec_path = self.root / "content" / "infographic.yml"
        # Characters outside the metrics table are estimated; wide CJK text renders wider.
        spec_path.write_text(spec_path.read_text(encoding="utf-8").replace("label: First", "label: " + "\u5bec" * 15), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_infographic.py"), "--root", str(self.root),
             ], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("renders", result.stdout)


if __name__ == "__main__":
    unittest.main()
