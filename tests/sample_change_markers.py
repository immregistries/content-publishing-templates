"""Put sample change markers into a built guide, standing in for Workstream D.

The build will emit the markers itself once change markers are parsed from the
source. Until then, this adds or replaces the
<script type="application/json" id="guide-change-markers"> element in a built
guide so the annotations panel can be tried. The element and its fields are
described in templates/guide/README.md ("Change markers").

    python tests/sample_change_markers.py output/guide/index.html
    python tests/sample_change_markers.py guide.html --markers markers.json

Without --markers, the markers fit tests/fixture-project.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ELEMENT_ID = "guide-change-markers"
# Only an element whose content is a JSON list, ending at its own closing tag,
# so text that merely quotes the tag (as a comment might) is never matched.
ELEMENT_PATTERN = re.compile(
    r'<script type="application/json" id="guide-change-markers">\s*\[(?:(?!</script>)[\s\S])*\]\s*</script>\n?'
)
DATA_TAG = '<script type="application/json" id="guide-data">'
VERSION_PATTERN = re.compile(r'"version": "([^"]+)"')


def fixture_markers(version: str) -> list[dict]:
    """Both levels, on a section, a block area, one block, and two rows."""
    return [
        {"anchor": "summary", "version": version, "level": "changed",
         "note": "The summary now leads with what the fixture is for."},
        {"anchor": "fixture-introduction", "blockIndex": 1, "version": version, "level": "changed",
         "note": "Says how positions are counted within an area."},
        {"anchor": "review-item", "version": version, "level": "feedback",
         "note": "New review process. Tell us whether these steps match your program's practice."},
        {"anchor": "fx-1", "version": version, "level": "changed",
         "note": "Status wording updated after the October call."},
        {"anchor": "fx-2", "version": version, "level": "feedback",
         "note": "New row. Is a second review area needed here?"},
    ]


def marker_script(markers: list[dict]) -> str:
    # "</" cannot appear inside a script element.
    text = json.dumps(markers, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="{ELEMENT_ID}">{text}</script>\n'


def inject(document: str, markers: list[dict]) -> str:
    """Return the guide with exactly one change-marker element, before guide-data."""
    document = ELEMENT_PATTERN.sub("", document)
    if DATA_TAG not in document:
        raise ValueError("This is not a built guide: it has no guide-data element.")
    return document.replace(DATA_TAG, marker_script(markers) + DATA_TAG, 1)


def guide_version(document: str) -> str:
    data = document.split(DATA_TAG, 1)[1] if DATA_TAG in document else ""
    match = VERSION_PATTERN.search(data)
    return match.group(1) if match else "v0.0.0"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("guide", help="Built guide HTML file to change in place.")
    parser.add_argument("--markers", help="JSON file holding the list of markers.")
    args = parser.parse_args()
    path = Path(args.guide)
    document = path.read_text(encoding="utf-8")
    if args.markers:
        markers = json.loads(Path(args.markers).read_text(encoding="utf-8-sig"))
    else:
        markers = fixture_markers(guide_version(document))
    path.write_text(inject(document, markers), encoding="utf-8", newline="\n")
    print(f"Added {len(markers)} change markers to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
