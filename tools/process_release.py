"""The shared templates' own release: its version and the release registry.

VERSION, at the root of this repository, holds the current release label, such
as v0.21.0. process-releases.json lists every release, newest first, each with
its date, its upgrade impact, and a one-sentence summary. build_guide.py copies
both into each guide's build manifest, which is how InteropHub learns which
releases exist and how much work moving to each one is.

Run from this repository to check that VERSION, the registry, and CHANGELOG.md
agree:

    python tools/process_release.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROCESS_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = "VERSION"
REGISTRY_FILE = "process-releases.json"
CHANGELOG_FILE = "CHANGELOG.md"
# A copy of these templates made by workspace_process.py records its commit here.
COPY_RECORD_FILE = "PROCESS-VERSION.txt"
UPGRADE_IMPACTS = ("rebuild", "config", "content")
RELEASE_KEYS = ("version", "date", "upgradeImpact", "summary")
VERSION_PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CHANGELOG_HEADING = re.compile(r"^## (v\S+)\s*$", re.MULTILINE)
IMPACT_LINE = re.compile(r"^\*\*Upgrade impact:\*\*\s*`?([A-Za-z]+)`?", re.MULTILINE)


def version_key(version: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if not match:
        raise ValueError(version)
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def read_version(root: Path = PROCESS_ROOT) -> str:
    path = root / VERSION_FILE
    if not path.is_file():
        raise RuntimeError(f"The shared templates have no {VERSION_FILE} file.")
    return path.read_text(encoding="utf-8").strip()


def read_registry(root: Path = PROCESS_ROOT) -> list[dict]:
    path = root / REGISTRY_FILE
    if not path.is_file():
        raise RuntimeError(f"The shared templates have no {REGISTRY_FILE} file.")
    registry = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(registry, list):
        raise RuntimeError(f"{REGISTRY_FILE} must be a list of releases.")
    return registry


def process_commit(root: Path = PROCESS_ROOT) -> str | None:
    """The short commit of these templates, or None when it cannot be known.

    In a project, process/ is a Git submodule. In a workspace it is a copy whose
    PROCESS-VERSION.txt names the commit. A folder that is not its own Git
    repository is never reported with the commit of a repository around it.
    """
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=root,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if top and Path(top).resolve() == root.resolve():
            return subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"], cwd=root,
                capture_output=True, text=True, check=True,
            ).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        pass
    record = root / COPY_RECORD_FILE
    if record.is_file():
        match = re.search(r"^Commit:\s*([0-9a-f]{7,40})\s*$", record.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            return match.group(1)[:7]
    return None


def registry_problems(registry: list) -> list[str]:
    problems = []
    previous: dict | None = None
    seen: set[str] = set()
    for index, release in enumerate(registry):
        where = f"{REGISTRY_FILE} entry {index + 1}"
        if not isinstance(release, dict):
            problems.append(f"{where} is not an object")
            continue
        version = release.get("version")
        where = f"{REGISTRY_FILE} {version or f'entry {index + 1}'}"
        if set(release) != set(RELEASE_KEYS):
            problems.append(f"{where} must have exactly the keys {', '.join(RELEASE_KEYS)}")
        if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
            problems.append(f"{where}: version must look like v0.21.0")
            continue
        if version in seen:
            problems.append(f"{where} is listed twice")
        seen.add(version)
        if not isinstance(release.get("date"), str) or not DATE_PATTERN.fullmatch(release["date"]):
            problems.append(f"{where}: date must be written as 2026-01-31")
        if release.get("upgradeImpact") not in UPGRADE_IMPACTS:
            problems.append(
                f"{where}: upgradeImpact {release.get('upgradeImpact')!r} must be one of "
                f"{', '.join(UPGRADE_IMPACTS)}"
            )
        if not isinstance(release.get("summary"), str) or not release["summary"].strip():
            problems.append(f"{where}: summary is required")
        if previous is not None and VERSION_PATTERN.fullmatch(previous.get("version", "")):
            if version_key(version) >= version_key(previous["version"]):
                problems.append(f"{where} must come after {previous['version']}; list releases newest first")
            elif str(release.get("date", "")) > str(previous.get("date", "")):
                problems.append(f"{where} is dated after the newer {previous['version']}")
        previous = release
    return problems


def changelog_sections(text: str) -> list[tuple[str, str]]:
    """(version, body) for each release heading in CHANGELOG.md, in order."""
    matches = list(CHANGELOG_HEADING.finditer(text))
    return [
        (match.group(1), text[match.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)])
        for i, match in enumerate(matches)
    ]


def release_problems(root: Path = PROCESS_ROOT) -> list[str]:
    """Disagreements between VERSION, the registry, and CHANGELOG.md."""
    problems = []
    try:
        version = read_version(root)
        registry = read_registry(root)
    except (RuntimeError, json.JSONDecodeError) as error:
        return [str(error)]
    if not VERSION_PATTERN.fullmatch(version):
        problems.append(f"{VERSION_FILE} holds {version!r}; it must be a release label such as v0.21.0")
    if not registry:
        return problems + [f"{REGISTRY_FILE} lists no releases"]
    problems.extend(registry_problems(registry))
    top = registry[0].get("version") if isinstance(registry[0], dict) else None
    if top != version:
        problems.append(f"{VERSION_FILE} is {version} but the newest entry in {REGISTRY_FILE} is {top}")

    changelog = root / CHANGELOG_FILE
    if not changelog.is_file():
        return problems + [f"{CHANGELOG_FILE} is missing"]
    sections = changelog_sections(changelog.read_text(encoding="utf-8"))
    if not sections:
        return problems + [f"{CHANGELOG_FILE} has no release headings such as '## {version}'"]
    if sections[0][0] != version:
        problems.append(f"{VERSION_FILE} is {version} but the newest {CHANGELOG_FILE} heading is {sections[0][0]}")
    listed = [release.get("version") for release in registry if isinstance(release, dict)]
    headed = [heading for heading, _ in sections]
    if listed != headed:
        missing = [heading for heading in headed if heading not in listed]
        extra = [entry for entry in listed if entry not in headed]
        detail = []
        if missing:
            detail.append(f"not in the registry: {', '.join(missing)}")
        if extra:
            detail.append(f"not in the changelog: {', '.join(str(entry) for entry in extra)}")
        problems.append(
            f"{REGISTRY_FILE} and {CHANGELOG_FILE} must list the same releases in the same order"
            + (f" ({'; '.join(detail)})" if detail else "")
        )
    impacts = {release.get("version"): release.get("upgradeImpact") for release in registry if isinstance(release, dict)}
    for index, (heading, body) in enumerate(sections):
        match = IMPACT_LINE.search(body)
        if match is None:
            if index == 0:
                problems.append(f"{CHANGELOG_FILE} {heading} needs an '**Upgrade impact:**' line")
            continue
        impact = match.group(1)
        if impact not in UPGRADE_IMPACTS:
            problems.append(f"{CHANGELOG_FILE} {heading}: upgrade impact {impact!r} must be one of {', '.join(UPGRADE_IMPACTS)}")
        elif heading in impacts and impacts[heading] != impact:
            problems.append(
                f"{CHANGELOG_FILE} {heading} says upgrade impact {impact} but {REGISTRY_FILE} says {impacts[heading]}"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(PROCESS_ROOT), help="Root of the shared templates.")
    args = parser.parse_args()
    problems = release_problems(Path(args.root))
    if problems:
        print(f"{len(problems)} release record problem(s):")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"Release records agree on {read_version(Path(args.root))}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
