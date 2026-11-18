"""Publish a built guide to InteropHub, or save its build manifest there.

Check the token first. --check-token asks InteropHub who the token in
INTEROPHUB_TOKEN acts as, what it may do, when it expires, and whether this
guide is among the guides the account can publish:

    python process/tools/publish_guide_to_hub.py --check-token

A hosted guide (guide.json "hosting": "interophub") is uploaded under one or
more labels; InteropHub reads the build manifest from the uploaded page:

    python process/tools/publish_guide_to_hub.py output/guide/index.html --label v0.4.0 --label latest

A guide hosted elsewhere, such as on GitHub Pages or shared by hand, is not
published until its build manifest is saved in InteropHub. --manifest-only
reads the manifest from the built guide and sends it on its own, with an
optional version label:

    python process/tools/publish_guide_to_hub.py output/guide/index.html --manifest-only --label v0.4.0

--display and --comment-mode then set the first label's display state and
comment mode in InteropHub, so one command can publish a release and make it
the Current version with comments limited to this release:

    python process/tools/publish_guide_to_hub.py output/guide/index.html --label v0.4.0 --label latest --display current --comment-mode release

--settings-only sets them for a label that is already published, such as one
a workflow published, and sends no guide:

    python process/tools/publish_guide_to_hub.py --settings-only --label v0.4.0 --display current --comment-mode release

The hub comes from --hub, or from comments.hub in guide.json. The document key
comes from --document, or from guide.json: comments.document, then id. Every
mode needs a personal access token in INTEROPHUB_TOKEN (with topics:write to
publish or change labels). The tool never prints the token. Publishing fails
when the guide has no manifest. Each error from InteropHub is explained, with
the link to its entry on the hub's help page for authors.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

# InteropHub's label pattern (GuideHtmlRules): after the first suffix character,
# only letters, digits, and dots, so v1.2.0-rc.1 is valid and v1.2.0-rc-1 is not.
LABEL = re.compile(r"^(?:latest|main|v[0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9][A-Za-z0-9.]*)?)$")
DISPLAYS = ("current", "listed", "unlisted", "authors_only", "retired")
COMMENT_MODES = ("open", "release", "closed")
DOCUMENT_KEY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SIZE = 20 * 1024 * 1024
MAX_MANIFEST_SIZE = 64 * 1024
MANIFEST_SCHEMA = 1
MANIFEST_PATTERN = re.compile(
    rb'<script type="application/json" id="guide-build-manifest">(.*?)</script>', re.DOTALL
)
# The public help page for authors and their agents. Its anchors are part of
# InteropHub's API contract (2.1).
HELP_PAGE = "/help/topic-reference-authors"
TOKEN_VARIABLE = "INTEROPHUB_TOKEN"
EXPIRY_WARNING_DAYS = 14
# Plain explanations of InteropHub's error codes, saying what to do next.
# {scope} is the scope InteropHub names in requiredScope.
ERRORS = {
    "invalid_field": "The server refused a field; check the document key, label, and guide file.",
    "invalid_request": "The server refused the build record; check that the guide was built by "
                       "this version of the templates and its manifest is under 64 KB.",
    "invalid_token": f"The token in {TOKEN_VARIABLE} is missing, invalid, expired, or revoked. "
                     f"Ask the author to create a new personal access token and set it as "
                     f"{TOKEN_VARIABLE} themselves.",
    "insufficient_scope": "The token lacks the {scope} scope. Ask the author to create a personal "
                          "access token with the Author preset (comments and topics:write) and set "
                          f"it as {TOKEN_VARIABLE}.",
    "forbidden": "This account must be an editor of the guide's topic to do this. Ask the author "
                 "to become a topic editor: the topic's champions or its space admin can add them.",
    "comments_closed": "Comments are closed on this version: its comment mode is closed. A topic "
                       "editor can change it with --comment-mode open or release, or on the "
                       "guide settings page in InteropHub.",
    "not_found": "InteropHub has no guide registered under this document key. Register the guide "
                 "in InteropHub, or check comments.document or id in guide.json.",
    "invalid_state": "This guide document is not set up for hosted publishing. A guide hosted "
                     "elsewhere saves its build manifest with --manifest-only.",
    "document_inactive": "This guide document is inactive in InteropHub.",
    "server_error": "InteropHub could not complete the request. Try again later; if it fails "
                    "again, report the time in UTC and the endpoint to the hub's administrators.",
}


class HubError(Exception):
    """A failed InteropHub request. str() is the explanation to print."""

    def __init__(self, text: str, status: int | None = None, code: str | None = None):
        super().__init__(text)
        self.status = status
        self.code = code


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "guide", nargs="?",
        help="Built self-contained HTML file. Not used with --check-token or --settings-only.",
    )
    parser.add_argument("--config", default="guide.json", help="Guide configuration file.")
    parser.add_argument(
        "--label", action="append", default=[],
        help="Label to upload; may be repeated. With --manifest-only, the optional version label to record.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--manifest-only", action="store_true",
        help="Save only the build manifest, for a guide hosted outside InteropHub.",
    )
    mode.add_argument(
        "--check-token", action="store_true",
        help=f"Report who the token in {TOKEN_VARIABLE} acts as, its scopes and expiry, and whether "
             "it can publish this guide. Sends nothing else.",
    )
    mode.add_argument(
        "--settings-only", action="store_true",
        help="Only set the --label's --display and --comment-mode; publish nothing.",
    )
    parser.add_argument("--hub", help="Hub base URL. Defaults to comments.hub in guide.json.")
    parser.add_argument("--document", help="InteropHub document key. Defaults to comments.document, then id, in guide.json.")
    parser.add_argument(
        "--display", choices=DISPLAYS,
        help="After publishing, set the first label's display state in InteropHub.",
    )
    parser.add_argument(
        "--comment-mode", choices=COMMENT_MODES,
        help="After publishing, set the first label's comment mode in InteropHub.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate locally without sending anything.")
    return parser.parse_args()


def fail(message: str) -> int:
    print("Error: " + message, file=sys.stderr)
    return 1


def help_link(hub: str, anchor: str) -> str:
    return f"{hub}{HELP_PAGE}#{anchor}"


def missing_token(hub: str) -> str:
    return (
        f"{TOKEN_VARIABLE} is not set. Only the author can create a token. Ask them: \"Please "
        f"create a personal access token on your InteropHub account page ({hub}/account, Access "
        f"tokens) with the Author preset. Set it as the {TOKEN_VARIABLE} environment variable "
        "yourself, then start me again from a new terminal. Please don't paste the token into "
        "this chat.\" A workflow "
        f"reads it from the {TOKEN_VARIABLE} repository secret instead.\n"
        f"  Help: {help_link(hub, 'create-a-token')}"
    )


def read_manifest(payload: bytes) -> dict:
    """The guide's build manifest. Raises ValueError when it is missing or unusable."""
    match = MANIFEST_PATTERN.search(payload)
    if not match:
        raise ValueError(
            "The guide has no build manifest. Build it with content-publishing-templates "
            "v0.21.0 or later; a guide is not published until its manifest is saved."
        )
    if len(match.group(1)) > MAX_MANIFEST_SIZE:
        raise ValueError("The guide's build manifest is larger than 64 KB.")
    try:
        manifest = json.loads(match.group(1).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"The guide's build manifest is not valid JSON: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"The guide's build manifest is not schema {MANIFEST_SCHEMA}.")
    return manifest


def hub_target(args: argparse.Namespace, config: dict, need_document: bool = True) -> tuple[str, str | None]:
    """The hub base URL and document key. Raises ValueError when they are unusable."""
    comments = config.get("comments") if isinstance(config.get("comments"), dict) else {}
    from_comments = comments.get("mode") == "interophub"
    hub = args.hub or (comments.get("hub") if from_comments else None)
    # The document key is set in one place, guide.json: comments.document when
    # the guide uses InteropHub comments, otherwise the project id.
    document = args.document or (comments.get("document") if from_comments else None) or config.get("id")
    if not isinstance(hub, str):
        raise ValueError("Give the hub with --hub, or set comments.hub in guide.json.")
    if not isinstance(document, str):
        if need_document:
            raise ValueError(
                "Give the document key with --document, or set comments.document or id in guide.json."
            )
        document = None
    parsed = urlsplit(hub)
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("An http hub is allowed only on localhost.")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The hub must be an absolute http or https URL.")
    if document is not None and not DOCUMENT_KEY.fullmatch(document):
        raise ValueError(f"Invalid document key: {document}")
    return hub.rstrip("/"), document


def json_body(raw: bytes, content_type: str) -> dict | None:
    """The response as a JSON object, or None when it is not InteropHub's JSON."""
    if content_type == "text/html" or raw.lstrip()[:1] == b"<":
        return None
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return body if isinstance(body, dict) else None


def not_json(hub: str, status: int, method: str, path: str) -> HubError:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return HubError(
        f"{status} from {method} {path}, as an HTML page instead of InteropHub's JSON. Something "
        "in front of InteropHub, such as a firewall, stopped the request before it reached the "
        f"hub. Ask the author to report the status ({status}), the time ({stamp}), and the "
        f"endpoint ({method} {hub}{path}) to the hub's administrators.\n"
        f"  Help: {help_link(hub, 'troubleshooting-html-response')}",
        status=status, code="html_response",
    )


def explain(status: int, body: dict, fallback: str, overrides: dict[str, str] | None = None) -> HubError:
    code = body.get("error") if isinstance(body.get("error"), str) else "request_failed"
    explanation = (overrides or {}).get(code) or ERRORS.get(code, fallback)
    if code == "insufficient_scope":
        scope = body.get("requiredScope") if isinstance(body.get("requiredScope"), str) else "topics:write"
        explanation = explanation.format(scope=scope)
    lines = [f"{status} {code}. {explanation}"]
    message = body.get("message")
    if isinstance(message, str) and message.strip():
        lines.append(f"  InteropHub: {message.strip()}")
    # Older hubs send no help link; the help page anchors are InteropHub's.
    if isinstance(body.get("help"), str):
        lines.append(f"  Help: {body['help']}")
    return HubError("\n".join(lines), status=status, code=code)


def call(hub: str, method: str, path: str, token: str, data: bytes | None = None,
         content_type: str | None = None, fallback: str = "The request failed.",
         overrides: dict[str, str] | None = None) -> tuple[int, dict]:
    """Send one request to the hub. Returns the status and JSON body, or raises HubError."""
    headers = {"Authorization": "Bearer " + token}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(hub + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            status, raw, kind = response.status, response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        with error:
            status, raw, kind = error.code, error.read(), error.headers.get_content_type()
        body = json_body(raw, kind)
        if body is None:
            raise not_json(hub, status, method, path) from None
        raise explain(status, body, fallback, overrides) from None
    except urllib.error.URLError as error:
        raise HubError(f"Could not reach the configured hub: {error.reason}") from None
    body = json_body(raw, kind)
    if body is None:
        raise not_json(hub, status, method, path)
    return status, body


def token_info(hub: str, token: str) -> dict:
    """GET /api/token (contract 3.7). Raises HubError."""
    return call(hub, "GET", "/api/token", token, fallback="InteropHub could not describe the token.")[1]


def expiry_warning(hub: str, info: dict) -> str | None:
    days = info.get("expiresInDays")
    if not isinstance(days, int) or isinstance(days, bool) or days > EXPIRY_WARNING_DAYS:
        return None
    when = "today" if days <= 0 else "in 1 day" if days == 1 else f"in {days} days"
    return (
        f"Warning: the token in {TOKEN_VARIABLE} expires {when} ({info.get('expiresAt')}). Ask the "
        f"author to create a new one before then and set it as {TOKEN_VARIABLE} (and as the "
        f"repository secret, if a workflow uses it).\n  Help: {help_link(hub, 'create-a-token')}"
    )


def warn_if_expiring(hub: str, token: str) -> None:
    """Warn before publishing when the token expires soon. A hub older than
    GET /api/token answers 404; that, and any other failure, is left to the
    publishing request itself to report."""
    try:
        info = token_info(hub, token)
    except HubError:
        return
    warning = expiry_warning(hub, info)
    if warning:
        print(warning, file=sys.stderr)


def check_token(hub: str, document: str | None, token: str) -> int:
    """Print who the token acts as and whether it can publish this guide."""
    try:
        info = token_info(hub, token)
    except HubError as error:
        if error.status == 404:
            # Whatever the body: an InteropHub release before GET /api/token.
            print("Token check: this hub does not offer GET /api/token yet (InteropHub 0.12.0 adds "
                  "it). Publishing still reports any token problem when it runs.", file=sys.stderr)
        else:
            print(f"Token check: {error}", file=sys.stderr)
        return 1
    user = info.get("user") if isinstance(info.get("user"), dict) else {}
    scopes = [scope for scope in info.get("scopes") or [] if isinstance(scope, str)]
    guides = [guide for guide in info.get("guides") or [] if isinstance(guide, dict)]
    print(f"Account: {user.get('displayName')} (user {user.get('userId')})")
    print(f"Token: {info.get('kind')} token \"{info.get('label')}\", scopes: {', '.join(scopes) or 'none'}")
    print(f"Expires: {info.get('expiresAt')} ({info.get('expiresInDays')} days left)")
    print("Guides this account can publish: "
          + (", ".join(str(guide.get("documentKey")) for guide in guides) or "none"))
    problems = []
    if "topics:write" not in scopes:
        problems.append(
            "This token cannot publish or change labels: it lacks topics:write. Ask the author to "
            "create a personal access token with the Author preset (comments and topics:write) and "
            f"set it as {TOKEN_VARIABLE}.\n  Help: {help_link(hub, 'create-a-token')}"
        )
    if document:
        guide = next((guide for guide in guides if guide.get("documentKey") == document), None)
        if guide:
            hosting = guide.get("hosting")
            how = "upload it with --label" if hosting == "HUB" else "save its manifest with --manifest-only"
            if not guide.get("canPublish"):
                how = "this token cannot publish it"
            print(f"This guide, {document}: registered, hosting {hosting}; {how}.")
        else:
            problems.append(
                f"This guide, {document}, is not among them. Either it is not registered in InteropHub "
                "under that key, or this account is not an editor of its topic. Ask the author to "
                "register the guide on the topic's guide settings page, or to become an editor of "
                "the topic: its champions or space admin can add them.\n"
                f"  Help: {help_link(hub, 'who-can-author')}"
            )
    else:
        print("This guide: no document key; give --document, or set comments.document or id in guide.json.")
    warning = expiry_warning(hub, info)
    for problem in problems:
        print(problem, file=sys.stderr)
    if warning:
        print(warning, file=sys.stderr)
    if isinstance(info.get("help"), str):
        print(f"Help for agents: {info['help']}")
    return 1 if problems else 0


def send_manifest(hub: str, document: str, token: str, manifest: dict, label: str | None) -> int:
    body = {"label": label, "manifest": manifest} if label else {"manifest": manifest}
    try:
        _, result = call(hub, "POST", f"/api/guide/{quote(document, safe='')}/builds", token,
                         json.dumps(body).encode("utf-8"), "application/json",
                         fallback="The server could not save the build manifest.")
    except HubError as error:
        print(f"Build manifest: {error}", file=sys.stderr)
        return 1
    print(
        f"Build manifest saved: build {result.get('buildId')} of {result.get('documentKey')}, "
        f"process {result.get('processVersion')}, received {result.get('receivedAt')}."
    )
    return 0


def set_label(hub: str, document: str, token: str, label: str, display: str | None, mode: str | None) -> int:
    """Set a label's display state and comment mode (contract 7.5). The label must
    already be known to InteropHub, so this runs after the upload or manifest."""
    body = {}
    if display:
        body["display"] = display
    if mode:
        body["commentMode"] = mode
    path = f"/api/guide/{quote(document, safe='')}/labels/{quote(label, safe='')}"
    overrides = {
        "not_found": f"InteropHub does not know the label {label} for this guide, or the guide "
                     "itself. Publish the label first.",
        "forbidden": "Only an editor of the guide's topic can change its labels. Ask the author to "
                     "become a topic editor: the topic's champions or its space admin can add them.",
    }
    try:
        _, result = call(hub, "PATCH", path, token, json.dumps(body).encode("utf-8"), "application/json",
                         fallback="The server could not change the label.", overrides=overrides)
    except HubError as error:
        print(f"{label} settings: {error}", file=sys.stderr)
        return 1
    line = f"{label}: display {result.get('display')}, comments {result.get('commentMode')}"
    demoted = result.get("demoted")
    if isinstance(demoted, dict):
        line += f"; {demoted.get('label')} is now {demoted.get('display')}"
    print(line + ".")
    return 0


def upload(hub: str, document: str, token: str, payload: bytes, labels: list[str]) -> int:
    failed = False
    for label in labels:
        try:
            status, result = call(hub, "POST", f"/api/guide/{quote(document, safe='')}/versions/{quote(label, safe='')}",
                                  token, payload, "text/html", fallback="The server could not publish this guide.")
        except HubError as error:
            failed = True
            print(f"{label}: {error}", file=sys.stderr)
            continue
        action = "created" if status == 201 else "replaced"
        print(f"{label}: {action}, {result.get('sizeBytes')} bytes, {result.get('viewUrl')}")
    return 1 if failed else 0


def read_config(args: argparse.Namespace) -> dict:
    """guide.json, or {} when checking the token or changing settings without one. Raises ValueError."""
    path = Path(args.config)
    if (args.check_token or args.settings_only) and not path.exists():
        return {}
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read {args.config}: {error}") from error
    if not isinstance(config, dict):
        raise ValueError(f"{args.config} is not a JSON object.")
    return config


def main() -> int:
    args = arguments()
    try:
        config = read_config(args)
    except ValueError as error:
        return fail(str(error))
    token = os.environ.get(TOKEN_VARIABLE)
    if args.check_token:
        try:
            hub, document = hub_target(args, config, need_document=False)
        except ValueError as error:
            return fail(str(error))
        if not token:
            return fail(missing_token(hub))
        return check_token(hub, document, token)

    if args.manifest_only:
        if len(args.label) > 1:
            return fail("--manifest-only records at most one --label.")
    elif not args.settings_only:
        if config.get("hosting", "github-pages") != "interophub":
            return fail(
                "guide.json hosting must be 'interophub' to publish to the hub. For a guide "
                "hosted elsewhere, save its build manifest with --manifest-only."
            )
        comments = config.get("comments")
        if not isinstance(comments, dict) or comments.get("mode") != "interophub":
            return fail("guide.json comments.mode must be 'interophub'.")
        if not args.label:
            return fail("Give at least one --label to upload.")
    try:
        hub, document = hub_target(args, config)
    except ValueError as error:
        return fail(str(error))
    invalid = next((label for label in args.label if not LABEL.fullmatch(label)), None)
    if invalid:
        return fail(
            f"Invalid label: {invalid}. Use latest, main, or a version such as v1.2.0 or "
            "v1.2.0-rc.1 (after the hyphen, only letters, digits, and dots)."
        )
    settings = bool(args.display or args.comment_mode)
    if args.settings_only and (not settings or len(args.label) != 1):
        return fail("--settings-only needs one --label and --display, --comment-mode, or both.")
    if settings and not args.label:
        return fail("--display and --comment-mode set the first --label; give one.")
    if args.settings_only:
        if args.guide:
            return fail("--settings-only sends no guide; leave out the guide file.")
        if args.dry_run:
            print(f"Dry run passed: {args.label[0]}: display {args.display or 'unchanged'}, "
                  f"comments {args.comment_mode or 'unchanged'}. Nothing was sent.")
            return 0
        if not token:
            return fail(missing_token(hub))
        return set_label(hub, document, token, args.label[0], args.display, args.comment_mode)

    if not args.guide:
        return fail("Give the built guide file, such as output/guide/index.html.")
    guide = Path(args.guide)
    try:
        payload = guide.read_bytes()
    except OSError as error:
        return fail(f"Could not read {guide}: {error}")
    if len(payload) > MAX_SIZE:
        return fail("The guide is larger than 20 MB.")
    try:
        manifest = read_manifest(payload)
    except ValueError as error:
        return fail(str(error))
    if args.dry_run:
        what = "build manifest" if args.manifest_only else f"{len(payload)} bytes, labels: {', '.join(args.label)}"
        if settings:
            what += f"; then {args.label[0]}: display {args.display or 'unchanged'}, comments {args.comment_mode or 'unchanged'}"
        print(f"Dry run passed: {guide} ({what}, process {manifest.get('processVersion')}). Nothing was sent.")
        return 0
    if not token:
        return fail(missing_token(hub))
    warn_if_expiring(hub, token)
    if args.manifest_only:
        result = send_manifest(hub, document, token, manifest, args.label[0] if args.label else None)
    else:
        result = upload(hub, document, token, payload, args.label)
    # Settings apply only once the label is published, so InteropHub knows it.
    if result == 0 and settings:
        result = set_label(hub, document, token, args.label[0], args.display, args.comment_mode)
    return result


if __name__ == "__main__":
    sys.exit(main())
