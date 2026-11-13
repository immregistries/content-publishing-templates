"""Create a new Topic Reference project from the shared skeleton.

A Topic Reference is a content project whose bounded purpose is one topic. It
is one of two types (see guidance/TopicReference.md):

- A Standing Topic Reference is a lasting reference for an InteropHub topic,
  kept in Git with releases. --visibility is required and must match the
  topic. A public project is published with GitHub Pages under open licenses.
  A private project has no GitHub Pages workflow or open licenses, carries an
  internal-use notice, and needs --owner, the GitHub owner of its private
  repository. It defaults to --hosting local; --hosting interophub adds
  access-controlled publishing.

      python tools/new_topic_reference.py ../immunization-cds --visibility public \\
          --title "Immunization CDS (ImmDS + HALO)" --topic 1 \\
          --topic-name "Immunization CDS (ImmDS + HALO)" --assembly ImmunizationCDS

  A private Standing Topic Reference may instead be kept in a workspace
  (--kept-in workspace): a shared folder, such as a synced Dropbox folder,
  with no Git repository, published only by uploading its guide to
  InteropHub. It needs --hosting interophub, --hub, and --location, and takes
  no --owner. Its version label is set by hand in guide.json.

      python tools/new_topic_reference.py "<shared folder>/example-project" --visibility private \\
          --kept-in workspace --hosting interophub --hub https://informatics.immregistries.org/hub \\
          --title "Example Project" --topic 1 --topic-name "Example Project" \\
          --location "Team Dropbox/Example/Topic References/example-project"

- A Workspace Topic Reference is kept in a shared folder, such as a synced
  Dropbox folder, without Git, releases, or an InteropHub topic. --location
  names where it is kept, in a form every collaborator recognizes. The folder
  may already hold the working material it is made from, as long as no
  skeleton file would replace an existing file; --id gives the project ID when
  the folder name is not one.

      python tools/new_topic_reference.py "<shared folder>/Survey Idea" --type workspace \\
          --id survey-idea --title "Survey Idea" --location "Team Dropbox/Surveys/Survey Idea"

The project is created from templates/topic-reference/project/ and the files of
its profile in templates/topic-reference/profiles/<public|private|private-workspace|workspace>/.
Each file in the profile's fragments/ directory supplies the value of the
placeholder named after it. The reading copy is generated. Unless --no-git is
given, a Standing project becomes a Git repository with this repository added
as the process/ submodule at the latest release tag, and a project kept in a
workspace, of either type, gets a plain copy of this repository's tools and templates in process/ (see
tools/workspace_process.py). Nothing is committed or pushed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import workspace_process

REPO_ROOT = Path(__file__).resolve().parent.parent
SKELETON = REPO_ROOT / "templates" / "topic-reference"
TOKEN_PATTERN = re.compile(r"\{\{([A-Z_]+)\}\}")
RENAMES = {"_gitignore": ".gitignore", "_github": ".github"}
OPTIONS = ["presentation"]
TYPES = ["standing", "workspace"]
VISIBILITIES = ["public", "private"]
HOSTING = ["local", "interophub"]
KEPT_IN = ["git", "workspace"]
DEFAULT_SUBTITLES = {
    "public": "A Topic Reference for community discussion",
    "private": "A Topic Reference for internal discussion",
    "private-workspace": "A Topic Reference for internal discussion",
    "workspace": "A Workspace Topic Reference",
}
# Git and GitHub files a Workspace project, which has neither, does not get.
WORKSPACE_SKIP = ("_github", "_gitignore")
PUBLIC_OWNER = "immregistries"
INTEROPHUB_TOPIC_URL = "https://informatics.immregistries.org/hub/es/topic/{topic}"
TEMPLATES_URL = "https://github.com/immregistries/content-publishing-templates.git"
ID_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="Project directory. For a Standing project its name is the project ID.")
    parser.add_argument(
        "--type",
        choices=TYPES,
        default="standing",
        help="standing (the default): Git, releases, and an InteropHub topic. "
        "workspace: a shared folder without Git or an InteropHub topic.",
    )
    parser.add_argument(
        "--visibility",
        choices=VISIBILITIES,
        help="Standing projects only, and required for them; must match the InteropHub topic. "
        "Public projects are published with GitHub Pages; private projects are not.",
    )
    parser.add_argument(
        "--hosting", choices=HOSTING, default=None,
        help="Private Standing projects only: local (the default) or interophub.",
    )
    parser.add_argument("--hub", help="Hub base URL; required with --hosting interophub.")
    parser.add_argument(
        "--kept-in", choices=KEPT_IN, default="git",
        help="Standing projects: git (the default) or workspace. Workspace is only for a private "
        "project hosted in InteropHub; it has no Git repository.",
    )
    parser.add_argument("--title", required=True, help="Document title.")
    parser.add_argument("--subtitle", help="Document subtitle. Defaults to one for the type and visibility.")
    parser.add_argument("--topic", type=int, help="InteropHub topic number. Standing projects only.")
    parser.add_argument("--topic-name", help="InteropHub topic name. Standing projects only.")
    parser.add_argument(
        "--id",
        help="Project ID: lowercase words joined by hyphens. Defaults to the directory name.",
    )
    parser.add_argument(
        "--location",
        help="Required for a project kept in a workspace, of either type: where it is kept, "
        "such as \"Team Dropbox/Surveys/Survey Idea\". Recorded in its guide and product manifests.",
    )
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
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Do not set up process/: no Git repository or submodule, or for a workspace no copy.",
    )
    parser.add_argument("--process-url", default=TEMPLATES_URL, help="Submodule URL for process/.")
    parser.add_argument(
        "--process-ref", help="Release tag or commit for process/. Defaults to the latest tag here."
    )
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


def merge_into(staging: Path, target: Path) -> None:
    """Move the staged skeleton into an existing folder without replacing anything in it."""
    collisions = [
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_file() and (target / path.relative_to(staging)).exists()
    ]
    if collisions:
        raise SystemExit(
            f"{target} already has files the skeleton would replace: {', '.join(sorted(collisions))}. "
            "Move them, for example into sources/, and run again."
        )
    shutil.copytree(staging, target, dirs_exist_ok=True)


def check_text(name: str, value: str) -> None:
    if '"' in value:
        raise SystemExit(f"The {name} cannot contain double quotes.")


def location_values(args: argparse.Namespace) -> dict[str, str]:
    if not args.location or not args.location.strip():
        raise SystemExit("A Topic Reference kept in a workspace needs --location, where it is kept.")
    location = args.location.strip()
    return {"LOCATION": location, "LOCATION_JSON": json.dumps(location)}


def standing_values(args: argparse.Namespace, project_id: str) -> dict[str, str]:
    if args.visibility is None:
        raise SystemExit("A Standing Topic Reference needs --visibility, matching its InteropHub topic.")
    if args.topic is None or not args.topic_name:
        raise SystemExit("A Standing Topic Reference needs --topic and --topic-name.")
    check_text("topic name", args.topic_name)
    topic = {
        "TOPIC": str(args.topic),
        "TOPIC_NAME": args.topic_name,
        "TOPIC_URL": INTEROPHUB_TOPIC_URL.format(topic=args.topic),
    }
    if args.kept_in == "workspace":
        if args.visibility != "private" or args.hosting != "interophub":
            raise SystemExit(
                "Only a private Standing Topic Reference hosted in InteropHub can be kept in a "
                "workspace: use --visibility private --hosting interophub. Public ones are kept in Git."
            )
        if args.owner is not None:
            raise SystemExit("A Topic Reference kept in a workspace has no repository, so it takes no --owner.")
        # No REPOSITORY: a file that refers to one fails as an unknown placeholder.
        return {**topic, **location_values(args)}
    if args.location:
        raise SystemExit("--location is for Topic References kept in a workspace.")
    owner = args.owner
    if owner is None:
        if args.visibility == "private":
            raise SystemExit("A private Topic Reference needs --owner, the GitHub owner of its private repository.")
        owner = PUBLIC_OWNER
    if not re.fullmatch(r"[A-Za-z0-9]+(-[A-Za-z0-9]+)*", owner):
        raise SystemExit("--owner must be a GitHub user or organization name.")
    values = {**topic, "REPOSITORY": f"https://github.com/{owner}/{project_id}"}
    # Only public projects are published, so only they have a Pages address.
    # A private file that refers to one fails as an unknown placeholder.
    if args.visibility == "public":
        values["PAGES_URL"] = f"https://{owner}.github.io/{project_id}/"
    return values


def workspace_values(args: argparse.Namespace) -> dict[str, str]:
    for name, given in [("--visibility", args.visibility), ("--hosting", args.hosting), ("--hub", args.hub), ("--topic", args.topic),
                        ("--topic-name", args.topic_name), ("--owner", args.owner),
                        ("--kept-in", None if args.kept_in == "git" else args.kept_in)]:
        if given is not None:
            raise SystemExit(
                f"{name} is for Standing Topic References. A workspace has no InteropHub topic or "
                "repository until it is promoted."
            )
    # A workspace has no InteropHub topic; its own title names it on the infographic.
    # Files that link to a topic or repository fail as unknown placeholders.
    return {"TOPIC_NAME": args.title, **location_values(args)}


def main() -> int:
    args = arguments()
    workspace = args.type == "workspace"
    # Kept in a shared folder without Git: a Workspace, or a private Standing project kept in a workspace.
    in_workspace = workspace or args.kept_in == "workspace"
    target = Path(args.target).resolve()
    if target.exists() and any(target.iterdir()) and not in_workspace:
        raise SystemExit(f"{target} already exists and is not empty.")

    project_id = args.id or target.name
    if not ID_PATTERN.fullmatch(project_id):
        raise SystemExit(
            "The project ID must be lowercase words joined by hyphens. "
            + ("Give one with --id." if not args.id else "")
        )
    assembly = args.assembly or "".join(word.capitalize() for word in project_id.split("-"))
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", assembly):
        raise SystemExit("--assembly must be letters and digits, starting with a letter.")
    profile_name = "workspace" if workspace else (
        "private-workspace" if args.kept_in == "workspace" else args.visibility
    )
    if not workspace and args.visibility is None:
        raise SystemExit("A Standing Topic Reference needs --visibility, matching its InteropHub topic.")
    if args.hosting and (workspace or args.visibility != "private"):
        raise SystemExit("--hosting is only for a private Standing Topic Reference.")
    hosting = args.hosting or ("local" if args.visibility == "private" else None)
    if args.hub and hosting != "interophub":
        raise SystemExit("--hub is only used with --hosting interophub.")
    if hosting == "interophub":
        if not args.hub:
            raise SystemExit("--hosting interophub needs --hub, the hub base URL.")
        parsed_hub = urlsplit(args.hub)
        local_http = parsed_hub.scheme == "http" and parsed_hub.hostname in {"localhost", "127.0.0.1"}
        if not (parsed_hub.scheme == "https" or local_http) or not parsed_hub.netloc or parsed_hub.query or parsed_hub.fragment:
            raise SystemExit("--hub must be an absolute https URL, or http on localhost, without a query or fragment.")
    subtitle = args.subtitle or DEFAULT_SUBTITLES[profile_name]
    check_text("title", args.title)
    check_text("subtitle", subtitle)

    values = {"ID": project_id, "TITLE": args.title, "SUBTITLE": subtitle, "ASSEMBLY": assembly}
    values.update(workspace_values(args) if workspace else standing_values(args, project_id))
    profile = SKELETON / "profiles" / profile_name
    values.update(fragments(profile, values))

    with tempfile.TemporaryDirectory() as temp:
        staging = Path(temp) / project_id
        skip = WORKSPACE_SKIP if in_workspace else ()
        copy_tree(SKELETON / "project", staging, values, skip=skip)
        profile_skip = ["fragments", *skip]
        copy_tree(profile, staging, values, skip=tuple(profile_skip), overlay=True)
        if args.visibility == "private" and hosting == "local" and not in_workspace:
            (staging / ".github" / "workflows" / "publish-guide.yml").unlink()
        if args.visibility == "private":
            guide_path = staging / "guide.json"
            guide = json.loads(guide_path.read_text(encoding="utf-8"))
            guide["hosting"] = hosting
            if hosting == "interophub":
                guide["comments"] = {"mode": "interophub", "hub": args.hub.rstrip("/"), "document": project_id}
            else:
                guide["comments"] = {"mode": "local"}
            guide_path.write_text(json.dumps(guide, indent=2) + "\n", encoding="utf-8", newline="\n")
        if "presentation" in args.options:
            add_presentation(staging, values)
        target.mkdir(parents=True, exist_ok=True)
        merge_into(staging, target)

    run(
        [sys.executable, str(REPO_ROOT / "tools" / "build_core_markdown.py"),
         "--root", str(target), "--assembly", f"{assembly}.qmd"],
        target,
    )

    if in_workspace and not args.no_git:
        print(f"Copied the shared templates into process/ at {workspace_process.install(target, args.process_ref)}.")
    if args.kept_in == "workspace":
        print(f"Created the private Standing Topic Reference {project_id}, kept in a workspace, in {target}.")
        print("It has no Git repository. Next: resolve the CONFIRM notes, add topic sections to content/,")
        print("run build.ps1, and upload output/guide/index.html to the topic in InteropHub, labeled with")
        print("the version in guide.json and latest. See process/guidance/TopicReference.md.")
        return 0
    if workspace:
        print(f"Created the Workspace Topic Reference {project_id} in {target}.")
        print("Next: resolve the CONFIRM notes, list the working material in sources/README.md,")
        print("add sections to content/, run build.ps1, and open output/guide/index.html.")
        print("See process/guidance/TopicReference.md, 'Workspace Topic References'.")
        return 0

    if not args.no_git:
        ref = args.process_ref or run(["git", "describe", "--tags", "--abbrev=0"], REPO_ROOT)
        run(["git", "init", "--quiet", "-b", "main"], target)
        run(["git", "submodule", "add", "--quiet", args.process_url, "process"], target)
        run(["git", "-C", "process", "checkout", "--quiet", ref], target)
        run(["git", "add", "process"], target)
        print(f"Added process/ at {ref}.")

    print(f"Created the {args.visibility} Standing Topic Reference project in {target}.")
    print("Next: resolve the CONFIRM notes, add topic sections to content/, run build.ps1,")
    print("and open output/guide/index.html. See process/guidance/TopicReference.md.")
    if args.visibility == "private":
        if hosting == "interophub":
            print("This project publishes its guide to InteropHub. Add the INTEROPHUB_TOKEN repository secret.")
        else:
            print("This project is local only. Keep its repository private and do not enable GitHub Pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
