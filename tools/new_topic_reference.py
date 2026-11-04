"""Create a new Topic Reference project from the shared skeleton.

A Topic Reference is a content project whose bounded purpose is one InteropHub
topic. See guidance/TopicReference.md. Run from anywhere:

    python tools/new_topic_reference.py ../immunization-cds --visibility public \\
        --title "Immunization CDS (ImmDS + HALO)" --topic 1 \\
        --topic-name "Immunization CDS (ImmDS + HALO)" --assembly ImmunizationCDS

--visibility is required and must match the InteropHub topic. A public project
is published with GitHub Pages under open licenses. A private project has no
publishing workflow or open licenses, carries an internal-use notice, and needs
--owner, the GitHub owner of its private repository.

The project is created from templates/topic-reference/project/ and the files of
its profile in templates/topic-reference/profiles/<visibility>/. Each file in
the profile's fragments/ directory supplies the value of the placeholder named
after it. The reading copy is generated and, unless --no-git is given, the
project becomes a Git repository with this repository added as the process/
submodule at the latest release tag. Nothing is committed or pushed.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SKELETON = REPO_ROOT / "templates" / "topic-reference"
TOKEN_PATTERN = re.compile(r"\{\{([A-Z_]+)\}\}")
RENAMES = {"_gitignore": ".gitignore", "_github": ".github"}
OPTIONS = ["presentation"]
VISIBILITIES = ["public", "private"]
DEFAULT_SUBTITLES = {
    "public": "A Topic Reference for community discussion",
    "private": "A Topic Reference for internal discussion",
}
PUBLIC_OWNER = "immregistries"
INTEROPHUB_TOPIC_URL = "https://informatics.immregistries.org/hub/es/topic/{topic}"
TEMPLATES_URL = "https://github.com/immregistries/content-publishing-templates.git"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="New project directory; its name is the project ID.")
    parser.add_argument(
        "--visibility",
        required=True,
        choices=VISIBILITIES,
        help="Must match the InteropHub topic. Public projects are published with GitHub Pages; "
        "private projects are built only.",
    )
    parser.add_argument("--title", required=True, help="Document title.")
    parser.add_argument("--subtitle", help="Document subtitle. Defaults to one for the visibility.")
    parser.add_argument("--topic", required=True, type=int, help="InteropHub topic number.")
    parser.add_argument("--topic-name", required=True, help="InteropHub topic name.")
    parser.add_argument(
        "--assembly",
        help="Assembly file name without .qmd, such as ImmunizationCDS. "
        "Defaults to the project ID in CamelCase.",
    )
    parser.add_argument(
        "--owner",
        help=f"GitHub owner of the new repository. Defaults to {PUBLIC_OWNER} for public projects; "
        "required for private projects.",
    )
    parser.add_argument(
        "--with",
        dest="options",
        action="append",
        choices=OPTIONS,
        default=[],
        help="Optional product to include. May be repeated.",
    )
    parser.add_argument("--no-git", action="store_true", help="Do not initialize Git or add the submodule.")
    parser.add_argument("--process-url", default=TEMPLATES_URL, help="Submodule URL for process/.")
    parser.add_argument("--process-ref", help="Release tag for process/. Defaults to the latest tag here.")
    return parser.parse_args()


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(command)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def substitute(text: str, values: dict[str, str]) -> str:
    return TOKEN_PATTERN.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def fragments(profile: Path, values: dict[str, str]) -> dict[str, str]:
    """Placeholder values from the profile's fragments/, one file per placeholder."""
    result = {}
    for path in sorted((profile / "fragments").glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        result[path.stem] = substitute(text[:-1] if text.endswith("\n") else text, values)
    return result


def copy_tree(
    source: Path, target: Path, values: dict[str, str], skip: tuple[str, ...] = (), overlay: bool = False
) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_dir() or path.relative_to(source).parts[0] in skip:
            continue
        parts = [RENAMES.get(part, part) for part in path.relative_to(source).parts]
        if parts[-1] == "Project.qmd":
            parts[-1] = values["ASSEMBLY"] + ".qmd"
        destination = target.joinpath(*parts)
        if overlay and destination.exists():
            raise SystemExit(f"{path} would replace a file from the shared skeleton.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            destination.write_bytes(data)
            continue
        text = substitute(text, values)
        unresolved = sorted(set(TOKEN_PATTERN.findall(text)))
        if unresolved:
            raise SystemExit(f"{path} has unknown placeholders: {', '.join(unresolved)}")
        destination.write_bytes(text.encode("utf-8"))


def add_presentation(target: Path, values: dict[str, str]) -> None:
    copy_tree(SKELETON / "optional" / "presentation", target, values)
    product = target / "products" / "presentation"
    product.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / "templates" / "product" / "product-brief.yml", product / "brief.yml")
    readme = target / "products" / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "| [presentation/](presentation/brief.yml) | A review deck built with the shared PowerPoint template |\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    args = arguments()
    target = Path(args.target).resolve()
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"{target} already exists and is not empty.")

    project_id = target.name
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", project_id):
        raise SystemExit("The project directory name must be lowercase words joined by hyphens.")
    assembly = args.assembly or "".join(word.capitalize() for word in project_id.split("-"))
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", assembly):
        raise SystemExit("--assembly must be letters and digits, starting with a letter.")
    subtitle = args.subtitle or DEFAULT_SUBTITLES[args.visibility]
    for name, value in [("title", args.title), ("subtitle", subtitle)]:
        if '"' in value:
            raise SystemExit(f"The {name} cannot contain double quotes.")
    owner = args.owner
    if owner is None:
        if args.visibility == "private":
            raise SystemExit("A private Topic Reference needs --owner, the GitHub owner of its private repository.")
        owner = PUBLIC_OWNER
    if not re.fullmatch(r"[A-Za-z0-9]+(-[A-Za-z0-9]+)*", owner):
        raise SystemExit("--owner must be a GitHub user or organization name.")

    values = {
        "ID": project_id,
        "TITLE": args.title,
        "SUBTITLE": subtitle,
        "TOPIC": str(args.topic),
        "TOPIC_NAME": args.topic_name,
        "TOPIC_URL": INTEROPHUB_TOPIC_URL.format(topic=args.topic),
        "ASSEMBLY": assembly,
        "REPOSITORY": f"https://github.com/{owner}/{project_id}",
    }
    # Only public projects are published, so only they have a Pages address.
    # A private file that refers to one fails as an unknown placeholder.
    if args.visibility == "public":
        values["PAGES_URL"] = f"https://{owner}.github.io/{project_id}/"
    profile = SKELETON / "profiles" / args.visibility
    values.update(fragments(profile, values))

    target.mkdir(parents=True, exist_ok=True)
    copy_tree(SKELETON / "project", target, values)
    copy_tree(profile, target, values, skip=("fragments",), overlay=True)
    if "presentation" in args.options:
        add_presentation(target, values)

    run(
        [sys.executable, str(REPO_ROOT / "tools" / "build_core_markdown.py"),
         "--root", str(target), "--assembly", f"{assembly}.qmd"],
        target,
    )

    if not args.no_git:
        ref = args.process_ref or run(["git", "describe", "--tags", "--abbrev=0"], REPO_ROOT)
        run(["git", "init", "--quiet", "-b", "main"], target)
        run(["git", "submodule", "add", "--quiet", args.process_url, "process"], target)
        run(["git", "-C", "process", "checkout", "--quiet", ref], target)
        run(["git", "add", "process"], target)
        print(f"Added process/ at {ref}.")

    print(f"Created the {args.visibility} Topic Reference project in {target}.")
    print("Next: resolve the CONFIRM notes, add topic sections to content/, run build.ps1,")
    print("and open output/guide/index.html. See process/guidance/TopicReference.md.")
    if args.visibility == "private":
        print("This project is not published. Keep its repository private and do not enable GitHub Pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
