"""Upload a self-contained guide to its configured private host."""
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
MAX_SIZE = 20 * 1024 * 1024
ERRORS = {
    "invalid_field": "The server refused a field; check the document key, label, and guide file.",
    "invalid_token": "The access token is missing, invalid, expired, or revoked.",
    "insufficient_scope": "The access token needs the topics:write scope.",
    "forbidden": "This account is not allowed to publish this guide.",
    "not_found": "The configured guide document was not found.",
    "invalid_state": "This guide document is not set up for hosted publishing.",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("guide", help="Built self-contained HTML file.")
    parser.add_argument("--config", default="guide.json", help="Guide configuration file.")
    parser.add_argument("--label", action="append", required=True, help="Label to upload; may be repeated.")
    parser.add_argument("--dry-run", action="store_true", help="Validate locally without sending anything.")
    return parser.parse_args()


def fail(message: str) -> int:
    print("Error: " + message, file=sys.stderr)
    return 1


def main() -> int:
    args = arguments()
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        return fail(f"Could not read {args.config}: {error}")
    if config.get("hosting", "github-pages") != "interophub":
        return fail("guide.json hosting must be 'interophub' to publish to the hub.")
    comments = config.get("comments")
    if not isinstance(comments, dict) or comments.get("mode") != "interophub":
        return fail("guide.json comments.mode must be 'interophub'.")
    hub, document = comments.get("hub"), comments.get("document")
    if not isinstance(hub, str) or not isinstance(document, str):
        return fail("guide.json comments.hub and comments.document are required.")
    parsed = urlsplit(hub)
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        return fail("An http hub is allowed only on localhost.")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return fail("comments.hub must be an absolute http or https URL.")
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
    token = os.environ.get("INTEROPHUB_TOKEN")
    if not args.dry_run and not token:
        return fail("Set INTEROPHUB_TOKEN to a personal access token before publishing.")
    if args.dry_run:
        print(f"Dry run passed: {guide} ({len(payload)} bytes), labels: {', '.join(args.label)}. Nothing was sent.")
        return 0
    failed = False
    for label in args.label:
        url = f"{hub.rstrip('/')}/api/guide/{quote(document, safe='')}/versions/{quote(label, safe='')}"
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
            try:
                body = json.loads(error.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                body = {}
            code = body.get("error", "request_failed")
            explanation = ERRORS.get(code, "The server could not publish this guide.")
            print(f"{label}: {error.code} {code}. {explanation}", file=sys.stderr)
        except urllib.error.URLError as error:
            failed = True
            print(f"{label}: Could not reach the configured hub: {error.reason}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
