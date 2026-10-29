"""Give every table in a built Word document the template's table style.

Pandoc writes each table with its own "Table" style and cannot be told to use
another, so this replaces it after the build with a style from the reference
document (by default AIRA 2, style ID AIRA2).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path


DOCUMENT_PART = "word/document.xml"
STYLES_PART = "word/styles.xml"
TABLE_STYLE_PATTERN = re.compile(r'<w:tblStyle w:val="[^"]*"\s*/>')


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", help="Built Word document to update in place.")
    parser.add_argument(
        "--style-id",
        default="AIRA2",
        help="Table style ID from the reference document. Defaults to AIRA2.",
    )
    return parser.parse_args()


def main() -> int:
    args = arguments()
    path = Path(args.docx)

    with zipfile.ZipFile(path) as source:
        styles = source.read(STYLES_PART).decode("utf-8")
        if f'w:styleId="{args.style_id}"' not in styles:
            print(f"Table style {args.style_id} is not defined in {path}.")
            return 1

        document = source.read(DOCUMENT_PART).decode("utf-8")
        document, count = TABLE_STYLE_PATTERN.subn(
            f'<w:tblStyle w:val="{args.style_id}" />', document
        )

        handle, temporary = tempfile.mkstemp(suffix=".docx", dir=path.parent)
        os.close(handle)
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename == DOCUMENT_PART:
                    data = document.encode("utf-8")
                target.writestr(item, data)

    os.replace(temporary, path)
    print(f"Applied table style {args.style_id} to {count} tables in {path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
