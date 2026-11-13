"""Report which derived products need review because their core has changed.

Run from a content project's root:

    python process/tools/check_products.py
    python process/tools/check_products.py --fail-on-stale

For each products/<id>/manifest.yml, the tool resolves the core release the
product was built from (canonical_source_revision, or else core_release when it
names a Git tag or commit) and lists the core files changed since then: the
Markdown in content/ and the Quarto assembly files at the root. It also checks
that every source the product cites, in its manifest, brief, and slides.json,
still exists.

Missing sources always fail. Stale products are reported, and fail only with
--fail-on-stale. Uses only the standard library and Git.

In a Workspace Topic Reference, which has no Git, each manifest records
core_built, the date (or date and time) the core was built, and core_location,
where the workspace is kept. A product needs review when a core file was
modified after core_built, judged by file dates. A private Standing Topic
Reference kept in a workspace works the same way, and its manifests also
record core_release, the version label of the core. Checks that need Git are
reported as not applicable, never as passed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

LIST_KEYS = {"sources", "allowed_sources"}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path, help="Content project root.")
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="Exit with an error when any product's core has changed since its release.",
    )
    return parser.parse_args()


def read_manifest(path: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Read the top-level scalars and source lists of a manifest or brief.

    Only the simple YAML used by the product templates is understood: top-level
    "key: value" lines, and lists of "- value" or "- path: value" items.
    """
    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if top:
            key, value = top.groups()
            current = key if key in LIST_KEYS and not value else None
            if current:
                lists[current] = []
            elif value:
                scalars[key] = value.strip("'\"")
            continue
        if current:
            item = re.match(r"^\s*-\s*(?:path:\s*)?(.+?)\s*$", line)
            if item:
                lists[current].append(item.group(1).strip("'\""))
            elif not line.startswith(" "):
                current = None
    return scalars, lists


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8"
    )


def resolve(root: Path, ref: str | None) -> str | None:
    if not ref or ref == "null":
        return None
    result = git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def core_paths(root: Path) -> list[str]:
    return ["content"] + sorted(path.name for path in root.glob("*.qmd"))


def changes_since(root: Path, commit: str) -> list[str]:
    result = git(root, "diff", "--name-status", "-M", commit, "--", *core_paths(root))
    if result.returncode != 0:
        raise SystemExit(f"git diff failed: {result.stderr.strip()}")
    changes = []
    for line in result.stdout.splitlines():
        status, *paths = line.split("\t")
        kind = {"A": "added", "D": "removed", "M": "changed"}.get(status[0], "renamed")
        changes.append(f"{kind}: {' -> '.join(paths)}")
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "--", *core_paths(root))
    changes.extend(f"added: {path}" for path in untracked.stdout.splitlines())
    return changes


def parse_built(value: str | None) -> datetime | None:
    """A manifest's core_built: a date, or a date and time, in ISO form."""
    if not value or value == "null":
        return None
    try:
        built = datetime.fromisoformat(value)
    except ValueError:
        return None
    # A bare date covers the whole day it names.
    if len(value) == 10:
        built += timedelta(days=1)
    return built


def changes_by_date(root: Path, built: datetime) -> list[str]:
    """Core files modified after the build, judged by file dates (no Git)."""
    changes = []
    for name in core_paths(root):
        path = root / name
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for file in files:
            if datetime.fromtimestamp(file.stat().st_mtime) > built:
                changes.append(f"changed: {file.relative_to(root).as_posix()}")
    return changes


def check_by_date(manifest: Path, root: Path) -> bool:
    """Report one product in a workspace; return True when it needs review."""
    scalars, _ = read_manifest(manifest)
    built_text = scalars.get("core_built")
    built = parse_built(built_text)
    location = scalars.get("core_location")
    release = scalars.get("core_release")
    print(f"{manifest.parent.name} ({'core release ' + release + ', ' if release else ''}"
          f"core built {built_text or 'not recorded'}{', ' + location if location else ''})")
    if built is None:
        print("  NEEDS REVIEW: record core_built, the date the core was built, in the manifest.")
        return True
    changes = changes_by_date(root, built)
    if changes:
        print(f"  NEEDS REVIEW: the core changed after {built_text}, by file dates:")
        for change in changes:
            print(f"    {change}")
        return True
    print("  Current with the core, by file dates.")
    return False


def missing_sources(root: Path, product: Path) -> list[str]:
    missing = []
    for name in ("manifest.yml", "brief.yml"):
        path = product / name
        if not path.is_file():
            continue
        _, lists = read_manifest(path)
        for key in LIST_KEYS:
            for source in lists.get(key, []):
                if not (product / source).resolve().is_file():
                    missing.append(f"{name} {key}: {source}")
    slides = product / "slides.json"
    if slides.is_file():
        for number, slide in enumerate(json.loads(slides.read_text(encoding="utf-8-sig"))["slides"], 1):
            for source in slide.get("sources", []):
                if not (root / source).is_file():
                    missing.append(f"slides.json slide {number}: {source}")
    return missing


def main() -> int:
    args = arguments()
    root = args.root.resolve()
    try:
        by_date = git(root, "rev-parse", "--git-dir").returncode != 0
    except OSError:
        by_date = True

    manifests = sorted(root.glob("products/*/manifest.yml"))
    if not manifests:
        print("No product manifests found.")
        return 0

    failed = False
    stale = 0
    if by_date:
        print("Not a Git repository: comparing core file dates with each product's core_built.")
        print("Removed core files cannot be detected this way.")
        print("Not applicable without Git: changes since a release tag or commit, and removed core files.")
    for manifest in manifests:
        product = manifest.parent
        if by_date:
            stale += check_by_date(manifest, root)
            missing = missing_sources(root, product)
            if missing:
                failed = True
                print("  MISSING SOURCES:")
                for item in missing:
                    print(f"    {item}")
            continue
        scalars, _ = read_manifest(manifest)
        release = scalars.get("core_release")
        commit = resolve(root, scalars.get("canonical_source_revision")) or resolve(root, release)
        print(f"{product.name} (core release {release or 'not recorded'})")

        if commit is None:
            stale += 1
            print("  NEEDS REVIEW: the release is not a Git tag or commit, so changes cannot be checked.")
            print("  Record canonical_source_revision or tag the core release.")
        else:
            changes = changes_since(root, commit)
            if changes:
                stale += 1
                print(f"  NEEDS REVIEW: the core changed since {commit[:7]}:")
                for change in changes:
                    print(f"    {change}")
            else:
                print("  Current with the core.")

        missing = missing_sources(root, product)
        if missing:
            failed = True
            print("  MISSING SOURCES:")
            for item in missing:
                print(f"    {item}")

    print(f"{len(manifests)} product(s); {stale} need review.")
    if failed:
        print("Some products cite sources that do not exist.", file=sys.stderr)
        return 1
    if stale and args.fail_on_stale:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
