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
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
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
    if git(root, "rev-parse", "--git-dir").returncode != 0:
        raise SystemExit(f"{root} is not a Git repository.")

    manifests = sorted(root.glob("products/*/manifest.yml"))
    if not manifests:
        print("No product manifests found.")
        return 0

    failed = False
    stale = 0
    for manifest in manifests:
        product = manifest.parent
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
