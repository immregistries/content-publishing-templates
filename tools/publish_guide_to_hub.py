"""Publish a built guide to InteropHub, or save its build manifest there.

A hosted guide (guide.json "hosting": "interophub") is uploaded under one or
more labels; InteropHub reads the build manifest from the uploaded page:

    python process/tools/publish_guide_to_hub.py output/guide/index.html --label v0.4.0 --label latest

A guide hosted elsewhere, such as on GitHub Pages or shared by hand, is not
published until its build manifest is saved in InteropHub. --manifest-only
reads the manifest from the built guide and sends it on its own, with an
optional version label:

    python process/tools/publish_guide_to_hub.py output/guide/index.html --manifest-only --label v0.4.0

The hub comes from --hub, or from comments.hub in guide.json. The document key
comes from --document, or from guide.json: comments.document, then id. Both
modes need a personal
access token in INTEROPHUB_TOKEN and fail when the guide has no manifest.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit

LABEL = re.compile(r"^(?:latest|main|v\d+(?:\.\d+)*(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?)$")
DOCUMENT_KEY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SIZE = 20 * 1024 * 1024
MAX_MANIFEST_SIZE = 64 * 1024
MANIFEST_SCHEMA = 1
MANIFEST_PATTERN = re.compile(
    rb'<script type="application/json" id="guide-build-manifest">(.*?)</script>', re.DOTALL
)
ERRORS = {
    "invalid_field": "The server refused a field; check the document key, label, and guide file.",
    "invalid_request": "The server refused the build record; check that the guide was built by "
                       "this version of the templates and its manifest is under 64 KB.",
    "invalid_token": "The access token is missing, invalid, expired, or revoked.",
    "insufficient_scope": "The access token needs the topics:write scope.",
    "forbidden": "This account is not allowed to publish this guide.",
    "not_found": "InteropHub has no guide registered under this document key. Register the guide "
                 "in InteropHub, or check comments.document or id in guide.json.",
    "invalid_state": "This guide document is not set up for hosted publishing.",
    "document_inactive": "This guide document is inactive in InteropHub.",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("guide", help="Built self-contained HTML file.")
    parser.add_argument("--config", default="guide.json", help="Guide configuration file.")
    parser.add_argument(
        "--label", action="append", default=[],
        help="Label to upload; may be repeated. With --manifest-only, the optional version label to record.",
    )
    parser.add_argument(
        "--manifest-only", action="store_true",
        help="Save only the build manifest, for a guide hosted outside InteropHub.",
    )
    parser.add_argument("--hub", help="Hub base URL. Defaults to comments.hub in guide.json.")
    parser.add_argument("--document", help="InteropHub document key. Defaults to comments.document, then id, in guide.json.")
    parser.add_argument("--dry-run", action="store_true", help="Validate locally without sending anything.")
    return parser.parse_args()


def fail(message: str) -> int:
    print("Error: " + message, file=sys.stderr)
    return 1


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


def hub_target(args: argparse.Namespace, config: dict) -> tuple[str, str]:
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
        raise ValueError(
            "Give the document key with --document, or set comments.document or id in guide.json."
        )
    parsed = urlsplit(hub)
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("An http hub is allowed only on localhost.")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The hub must be an absolute http or https URL.")
    if not DOCUMENT_KEY.fullmatch(document):
        raise ValueError(f"Invalid document key: {document}")
    return hub.rstrip("/"), document


def error_message(error: urllib.error.HTTPError, fallback: str) -> str:
    try:
        body = json.loads(error.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        body = {}
    code = body.get("error", "request_failed") if isinstance(body, dict) else "request_failed"
    return f"{error.code} {code}. {ERRORS.get(code, fallback)}"


def send_manifest(hub: str, document: str, token: str, manifest: dict, label: str | None) -> int:
    body = {"label": label, "manifest": manifest} if label else {"manifest": manifest}
    url = f"{hub}/api/guide/{quote(document, safe='')}/builds"
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        print("Build manifest: " + error_message(error, "The server could not save the build manifest."), file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Build manifest: Could not reach the configured hub: {error.reason}", file=sys.stderr)
        return 1
    print(
        f"Build manifest saved: build {result.get('buildId')} of {result.get('documentKey')}, "
        f"process {result.get('processVersion')}, received {result.get('receivedAt')}."
    )
    return 0


def upload(hub: str, document: str, token: str, payload: bytes, labels: list[str]) -> int:
    failed = False
    for label in labels:
        url = f"{hub}/api/guide/{quote(document, safe='')}/versions/{quote(label, safe='')}"
        request = urllib.request.Request(url, data=payload, method="POST", headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "text/html",
        })
        try:
            with urllib.request.urlopen(request) as response:
                result = json.load(response)
                action = "created" if response.status == 201 else "replaced"
                print(f"{label}: {action}, {result['sizeBytes']} bytes, {result['viewUrl']}")
        except urllib.error.HTTPError as error:
            failed = True
            print(f"{label}: " + error_message(error, "The server could not publish this guide."), file=sys.stderr)
        except urllib.error.URLError as error:
            failed = True
            print(f"{label}: Could not reach the configured hub: {error.reason}", file=sys.stderr)
    return 1 if failed else 0


def main() -> int:
    args = arguments()
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        return fail(f"Could not read {args.config}: {error}")
    if args.manifest_only:
        if len(args.label) > 1:
            return fail("--manifest-only records at most one --label.")
    else:
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
        return fail(f"Invalid label: {invalid}")
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
    token = os.environ.get("INTEROPHUB_TOKEN")
    if not args.dry_run and not token:
        return fail("Set INTEROPHUB_TOKEN to a personal access token before publishing.")
    if args.dry_run:
        what = "build manifest" if args.manifest_only else f"{len(payload)} bytes, labels: {', '.join(args.label)}"
        print(f"Dry run passed: {guide} ({what}, process {manifest.get('processVersion')}). Nothing was sent.")
        return 0
    if args.manifest_only:
        return send_manifest(hub, document, token, manifest, args.label[0] if args.label else None)
    return upload(hub, document, token, payload, args.label)


if __name__ == "__main__":
    sys.exit(main())
