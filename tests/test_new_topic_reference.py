"""Tests for tools/new_topic_reference.py: public and private profiles."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "new_topic_reference.py"
sys.path.insert(0, str(ROOT / "tools"))
from headless_browser import find_browser  # noqa: E402
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
        names = {p: sorted(f.name for f in (PROFILES / p / "fragments").iterdir())
                 for p in ("public", "private", "workspace")}
        self.assertEqual(names["public"], names["private"])
        self.assertEqual(names["public"], names["workspace"])


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
        self.assertEqual("local", guide["hosting"])
        self.assertEqual({"mode": "local"}, guide["comments"])
        self.assertIn("internal use only", guide["license"])

    def test_private_hosted_project(self):
        target = self.base / "sample-topic"
        result = create(target, "--visibility", "private", "--owner", "example-org", "--hosting", "interophub", "--hub", "https://example.test/hub")
        self.assertEqual(0, result.returncode, result.stderr)
        files = project_text(target)
        self.assertIn(".github/workflows/publish-guide.yml", files)
        guide = json.loads(files["guide.json"])
        self.assertEqual("interophub", guide["hosting"])
        self.assertEqual("interophub", guide["comments"]["mode"])
        self.assertEqual("sample-topic", guide["comments"]["document"])



def create_workspace(target: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), str(target), "--type", "workspace", "--title", "Sample Idea",
         "--location", "Team Dropbox/Ideas/Sample Idea", *extra],
        capture_output=True, text=True,
    )


class GenerateWorkspaceTopicReference(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_workspace_in_a_working_folder(self):
        target = self.base / "Sample Idea"
        target.mkdir()
        (target / "notes.txt").write_text("Working notes.\n", encoding="utf-8")
        result = create_workspace(target, "--id", "sample-idea", "--no-git")
        self.assertEqual(0, result.returncode, result.stderr)
        files = project_text(target)
        self.assertEqual("Working notes.\n", files["notes.txt"])
        for name in PUBLIC_ONLY + PRIVATE_ONLY + [".gitignore", ".github/workflows/validate.yml"]:
            self.assertNotIn(name, files)
        for name, text in files.items():
            for phrase in PUBLIC_PHRASES + ["InteropHub topic 7", "git submodule"]:
                self.assertNotIn(phrase, text, f"{name} contains {phrase!r}")
        guide = json.loads(files["guide.json"])
        self.assertEqual("workspace", guide["topicReferenceType"])
        self.assertEqual("Team Dropbox/Ideas/Sample Idea", guide["location"])
        self.assertNotIn("interophubTopic", guide)
        self.assertNotIn("repository", guide)
        self.assertIn("Workspace Topic Reference", files["AGENTS.md"])
        self.assertIn("Team Dropbox/Ideas/Sample Idea", files["sources/README.md"])

        built = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_guide.py"), "--root", str(target),
             "--assembly", "SampleIdea.qmd"], capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        html = (target / "output" / "guide" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Workspace build ", html)
        self.assertIn("Kept in Team Dropbox/Ideas/Sample Idea", html)
        self.assertNotIn("Return to InteropHub", html)

    def test_workspace_gets_a_copy_of_the_shared_templates(self):
        target = self.base / "sample-idea"
        result = create_workspace(target, "--process-ref", "HEAD")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((target / "process" / "tools" / "build_guide.py").is_file())
        self.assertFalse((target / "process" / "tests").exists())
        self.assertFalse((target / ".git").exists())
        self.assertIn("Commit: ", (target / "process" / "PROCESS-VERSION.txt").read_text(encoding="utf-8"))

    def test_workspace_does_not_replace_existing_files(self):
        target = self.base / "sample-idea"
        target.mkdir()
        (target / "README.md").write_text("Mine.\n", encoding="utf-8")
        result = create_workspace(target, "--no-git")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("README.md", result.stdout + result.stderr)
        self.assertEqual(["README.md"], [p.name for p in target.iterdir()])

    def test_workspace_rejects_topic_and_needs_location(self):
        result = create_workspace(self.base / "sample-idea", "--visibility", "private", "--no-git")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Standing", result.stderr)
        result = subprocess.run(
            [sys.executable, str(TOOL), str(self.base / "sample-idea"), "--type", "workspace",
             "--title", "Sample Idea", "--no-git"], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--location", result.stderr)

    def test_folder_name_that_is_not_an_id_needs_id(self):
        result = create_workspace(self.base / "Sample Idea", "--no-git")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--id", result.stderr)


class PrimaryInfographic(unittest.TestCase):
    """Both profiles create, check, and build a starter primary infographic."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def check(self, visibility: str, *extra: str) -> Path:
        target = self.base / f"sample-{visibility}"
        result = create(target, "--visibility", visibility, *extra)
        self.assertEqual(0, result.returncode, result.stderr)
        for name in ("content/infographic.yml", "products/infographic/brief.yml"):
            self.assertTrue((target / name).is_file(), name)
        self.assertIn("build_infographic.py", (target / "build.ps1").read_text(encoding="utf-8"))
        self.assertIn("insert_word_infographic.py", (target / "build.ps1").read_text(encoding="utf-8"))

        check = subprocess.run([sys.executable, str(ROOT / "tools" / "check_content.py"), "--root", str(target)],
                               capture_output=True, text=True)
        self.assertEqual(0, check.returncode, check.stdout)
        self.assertIn("content/infographic.yml:", check.stdout)
        self.assertIn("CONFIRM starter text", check.stdout)

        guide = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_guide.py"), "--root", str(target),
             "--assembly", "SamplePublic.qmd" if visibility == "public" else "SamplePrivate.qmd",
             "--version", "v0.1.0"], capture_output=True, text=True)
        self.assertEqual(0, guide.returncode, guide.stdout + guide.stderr)
        html = (target / "output" / "guide" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<figure class="guide-infographic" id="guide-infographic">', html)
        self.assertIn('href="#what-this-project-covers"', html)

        if find_browser():
            build = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "build_infographic.py"), "--root", str(target),
                 "--version", "v0.1.0"], capture_output=True, text=True)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            for suffix in ("svg", "png", "pdf"):
                self.assertTrue((target / "output" / f"infographic.{suffix}").is_file(), suffix)
        return target

    def test_public_infographic(self):
        target = self.check("public")
        svg = (target / "output" / "guide" / "index.html").read_text(encoding="utf-8")
        self.assertIn("https://informatics.immregistries.org/hub/es/topic/7", svg)
        self.assertIn("Content licensed CC BY 4.0", svg)

    def test_private_infographic(self):
        target = self.check("private", "--owner", "example-org")
        self.assertIn("topic_link: false", (target / "content" / "infographic.yml").read_text(encoding="utf-8"))
        html = (target / "output" / "guide" / "index.html").read_text(encoding="utf-8")
        figure = html[html.index('<figure class="guide-infographic"'):html.index("</figure>")]
        self.assertIn("AIRA internal use only", figure)
        self.assertNotIn("informatics.immregistries.org/hub/es/topic/7", figure)

    def test_unresolved_reference_fails_the_check(self):
        target = self.base / "sample-topic"
        self.assertEqual(0, create(target, "--visibility", "public").returncode)
        spec = target / "content" / "infographic.yml"
        spec.write_text(spec.read_text(encoding="utf-8").replace("ref: related-work", "ref: no-such-heading"),
                        encoding="utf-8")
        check = subprocess.run([sys.executable, str(ROOT / "tools" / "check_content.py"), "--root", str(target)],
                               capture_output=True, text=True)
        self.assertNotEqual(0, check.returncode)
        self.assertIn("'no-such-heading' does not match", check.stdout)

    def test_missing_specification_fails_the_check(self):
        target = self.base / "sample-topic"
        self.assertEqual(0, create(target, "--visibility", "public").returncode)
        (target / "content" / "infographic.yml").unlink()
        check = subprocess.run([sys.executable, str(ROOT / "tools" / "check_content.py"), "--root", str(target)],
                               capture_output=True, text=True)
        self.assertNotEqual(0, check.returncode)
        self.assertIn("content/infographic.yml is missing", check.stdout)


if __name__ == "__main__":
    unittest.main()
