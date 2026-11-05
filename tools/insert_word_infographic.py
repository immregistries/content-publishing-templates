"""Place the primary infographic at the start of a built Word document.

Run after quarto render and build_infographic.py, from the project root:

    python process/tools/insert_word_infographic.py output/Project.docx

The PNG (output/infographic.png by default) goes before the first Heading 1,
after the title and table of contents, at the full text width, with the
specification's alt text and a short caption. The document's own text is the
figure's long description. Running it again replaces the figure.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import infographic  # noqa: E402


DOCUMENT_PART = "word/document.xml"
RELS_PART = "word/_rels/document.xml.rels"
TYPES_PART = "[Content_Types].xml"
MEDIA_PART = "word/media/primary-infographic.png"
RELATIONSHIP_ID = "rIdPrimaryInfographic"
IMAGE_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
MARKER = "primary-infographic"
EMU_PER_TWIP = 635
CAPTION = ("At a glance. The sections that follow state in full everything this figure "
           "summarizes.")
NAMESPACES = {
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
FIGURE_PATTERN = re.compile(
    r'<w:p>(?:(?!</w:p>).)*?<w:bookmarkStart w:id="\d+" w:name="' + MARKER + r'"/>.*?'
    r'<w:bookmarkEnd w:id="\d+"/></w:p>', re.DOTALL
)
HEADING_PATTERN = re.compile(r'<w:p\b[^>]*>(?:(?!</w:p>).)*?<w:pStyle w:val="Heading1"\s*/>', re.DOTALL)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", help="Built Word document to update in place.")
    parser.add_argument("--image", default="output/infographic.png", help="Infographic PNG.")
    parser.add_argument("--spec", default=infographic.SPEC_PATH, help="Specification, for the alt text.")
    parser.add_argument("--root", default=".", help="Content project root.")
    return parser.parse_args()


def text_width_emu(document: str) -> int:
    size = re.search(r'<w:pgSz\b[^>]*\bw:w="(\d+)"', document)
    margins = re.search(r'<w:pgMar\b[^>]*>', document)
    width = int(size.group(1)) if size else 12240
    left = right = 1440
    if margins:
        left = int(re.search(r'w:left="(\d+)"', margins.group(0)).group(1))
        right = int(re.search(r'w:right="(\d+)"', margins.group(0)).group(1))
    return (width - left - right) * EMU_PER_TWIP


def figure_xml(alt: str, title: str, width: int, height: int, ids: tuple[int, int]) -> str:
    alt, title = html.escape(alt, quote=True), html.escape(title, quote=True)
    bookmark, drawing = ids
    picture = (
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="primary-infographic.png" descr="{alt}"/>'
        '<pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{RELATIONSHIP_ID}"/><a:stretch><a:fillRect/></a:stretch>'
        '</pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        f'<a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</pic:spPr></pic:pic>"
    )
    return (
        f'<w:p><w:pPr><w:pStyle w:val="Caption"/><w:keepNext/><w:jc w:val="center"/></w:pPr>'
        f'<w:bookmarkStart w:id="{bookmark}" w:name="{MARKER}"/>'
        f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{width}" cy="{height}"/><wp:docPr id="{drawing}" name="Primary infographic" '
        f'title="{title}" descr="{alt}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks '
        f'noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData '
        f'uri="http://schemas.openxmlformats.org/drawingml/2006/picture">{picture}</a:graphicData>'
        f'</a:graphic></wp:inline></w:drawing></w:r>'
        f'<w:r><w:br/><w:t xml:space="preserve">{html.escape(CAPTION)}</w:t></w:r>'
        f'<w:bookmarkEnd w:id="{bookmark}"/></w:p>'
    )


def main() -> int:
    args = arguments()
    root = Path(args.root).resolve()
    path = (root / args.docx) if not Path(args.docx).is_absolute() else Path(args.docx)
    image = root / args.image
    if not image.is_file():
        print(f"{image} is missing. Run build_infographic.py first.")
        return 1
    spec = infographic.load_spec(root / args.spec)
    alt = str(spec.get("alt") or "").strip()
    if not alt:
        print(f"{args.spec} has no alt text.")
        return 1
    title = f"{spec.get('title', '')}: topic at a glance"
    png = image.read_bytes()
    pixel_width, pixel_height = struct.unpack(">II", png[16:24])

    with zipfile.ZipFile(path) as source:
        document = source.read(DOCUMENT_PART).decode("utf-8")
        rels = source.read(RELS_PART).decode("utf-8")
        types = source.read(TYPES_PART).decode("utf-8")
        root_tag = re.search(r"<w:document\b[^>]*>", document).group(0)
        additions = "".join(f' xmlns:{prefix}="{uri}"' for prefix, uri in NAMESPACES.items()
                            if f"xmlns:{prefix}=" not in root_tag)
        if additions:
            document = document.replace(root_tag, root_tag[:-1] + additions + ">", 1)
        document = FIGURE_PATTERN.sub("", document)
        heading = HEADING_PATTERN.search(document)
        if not heading:
            print(f"{path} has no Heading 1 to place the infographic before.")
            return 1
        width = text_width_emu(document)
        height = round(width * pixel_height / pixel_width)
        used = [int(value) for value in re.findall(r'<wp:docPr id="(\d+)"', document)]
        used_bookmarks = [int(value) for value in re.findall(r'<w:bookmarkStart w:id="(\d+)"', document)]
        ids = (max(used_bookmarks, default=0) + 1, max(used, default=0) + 1)
        document = (document[:heading.start()] + figure_xml(alt, title, width, height, ids)
                    + document[heading.start():])
        if RELATIONSHIP_ID not in rels:
            rels = rels.replace(
                "</Relationships>",
                f'<Relationship Id="{RELATIONSHIP_ID}" Type="{IMAGE_TYPE}" '
                f'Target="media/primary-infographic.png"/></Relationships>',
            )
        if 'Extension="png"' not in types:
            types = types.replace(
                "</Types>", '<Default Extension="png" ContentType="image/png"/></Types>')

        handle, temporary = tempfile.mkstemp(suffix=".docx", dir=path.parent)
        os.close(handle)
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                if item.filename == MEDIA_PART:
                    continue
                data = source.read(item.filename)
                if item.filename == DOCUMENT_PART:
                    data = document.encode("utf-8")
                elif item.filename == RELS_PART:
                    data = rels.encode("utf-8")
                elif item.filename == TYPES_PART:
                    data = types.encode("utf-8")
                target.writestr(item, data)
            target.writestr(MEDIA_PART, png)

    os.replace(temporary, path)
    print(f"Placed the primary infographic in {path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
