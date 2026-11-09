"""Install or refresh the shared templates in a Workspace Topic Reference.

A Standing Topic Reference uses this repository as a Git submodule at
process/. A Workspace Topic Reference is kept in a shared folder without Git,
so it gets a plain copy instead: the tools, templates, and guidance at a named
commit or tag, with PROCESS-VERSION.txt recording which. Run from anywhere to
refresh a workspace's copy:

    python tools/workspace_process.py "<workspace folder>"
    python tools/workspace_process.py "<workspace folder>" --ref v0.14.0

The copy is taken from this repository's Git history with git archive, so
uncommitted changes here are never copied. An existing process/ folder is
replaced only when it has a PROCESS-VERSION.txt, so a folder that was not
installed by this tool is never deleted.
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# What a project uses at build time, with the license and the record of changes.
CONTENTS = ["tools", "templates", "guidance", "requirements-pptx.txt", "README.md", "LICENSE", "CHANGELOG.md"]
VERSION_FILE = "PROCESS-VERSION.txt"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, check=False)


def latest_tag() -> str:
    result = git("describe", "--tags", "--abbrev=0")
    if result.returncode != 0:
        raise SystemExit("No release tag found; give --ref.")
    return result.stdout.decode().strip()


def install(workspace: Path, ref: str | None = None) -> str:
    """Copy the shared templates at ref into workspace/process/; return a description."""
    ref = ref or latest_tag()
    commit = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if commit.returncode != 0:
        raise SystemExit(f"{ref} is not a commit or tag in {REPO_ROOT}.")
    commit_id = commit.stdout.decode().strip()
    archive = git("archive", "--format=tar", commit_id, "--", *CONTENTS)
    if archive.returncode != 0:
        raise SystemExit(f"git archive failed:\n{archive.stderr.decode().strip()}")

    target = workspace / "process"
    if target.exists():
        if not (target / VERSION_FILE).is_file():
            raise SystemExit(f"{target} exists but was not installed by this tool; not replacing it.")
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(target, filter="data")
        else:  # Python before 3.12; git archive output has no unsafe members.
            tar.extractall(target)

    description = ref if ref == commit_id else f"{ref} ({commit_id[:12]})"
    (target / VERSION_FILE).write_text(
        "Shared templates for a Workspace Topic Reference: a copy, not a Git submodule.\n"
        f"Source: content-publishing-templates {description}\n"
        f"Commit: {commit_id}\n"
        f"Installed: {date.today().isoformat()}\n"
        "Do not edit these files. Refresh them with tools/workspace_process.py from a\n"
        "checkout of content-publishing-templates.\n",
        encoding="utf-8",
        newline="\n",
    )
    return description


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path, help="Workspace Topic Reference folder.")
    parser.add_argument("--ref", help="Tag or commit to copy. Defaults to the latest release tag.")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not (workspace / "guide.json").is_file():
        raise SystemExit(f"{workspace} has no guide.json; is it a Topic Reference?")
    print(f"Installed process/ at {install(workspace, args.ref)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
