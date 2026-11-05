"""Build a Topic Reference's primary infographic as SVG, PNG, and PDF.

Run from the content project's root, before quarto render and build_guide.py:

    python process/tools/build_infographic.py

The specification is content/infographic.yml (see tools/infographic.py for
its fields). The status comes from guide.json, the version from --version or
git describe, and the date is today's. The outputs are output/infographic.svg,
output/infographic.png, and output/infographic.pdf.

An installed Chrome or Edge, run headless, measures the rendered text and
exports the PNG and PDF; no network access or credentials are used. Text that
overflows its box in the browser fails the build, as does anything that fails
the specification checks. Use --browser, or set CHROME_PATH, to choose the
browser.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import infographic  # noqa: E402
from build_guide import git_version  # noqa: E402
from headless_browser import BrowserError, HeadlessBrowser, find_browser  # noqa: E402


MEASURE = r"""
(() => {
  const problems = [];
  const describe = (node) => (node.closest('[data-name]') || {dataset: {}}).dataset.name || 'text';
  for (const group of document.querySelectorAll('g.ig-text')) {
    const [x, , w] = group.dataset.box.split(' ').map(Number);
    for (const text of group.querySelectorAll('text')) {
      const box = text.getBBox();
      if (box.x < x - 1 || box.x + box.width > x + w + 1) {
        problems.push(`${describe(text)}: "${text.textContent}" renders ${Math.round(box.width)}px wide ` +
                      `in a ${Math.round(w)}px box`);
      }
    }
  }
  for (const card of document.querySelectorAll('g.ig-card')) {
    const [x, y, w, h] = card.dataset.box.split(' ').map(Number);
    for (const text of card.querySelectorAll('text')) {
      const box = text.getBBox();
      if (box.x < x || box.y < y || box.x + box.width > x + w || box.y + box.height > y + h) {
        problems.push(`${describe(text)}: "${text.textContent}" renders outside its card`);
      }
    }
  }
  const svg = document.querySelector('svg');
  const [, , width, height] = svg.getAttribute('viewBox').split(' ').map(Number);
  for (const text of svg.querySelectorAll('text')) {
    const box = text.getBBox();
    if (box.x < 0 || box.y < 0 || box.x + box.width > width || box.y + box.height > height) {
      problems.push(`${describe(text)}: "${text.textContent}" renders outside the image`);
    }
  }
  return problems;
})()
"""

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>infographic</title>
<style>@page {{ size: {width}px {height}px; margin: 0; }}
html, body {{ margin: 0; padding: 0; background: #ffffff; }} svg {{ display: block; }}</style>
</head><body>{svg}</body></html>
"""


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Content project root.")
    parser.add_argument("--config", default="guide.json", help="Guide settings file.")
    parser.add_argument("--spec", default=infographic.SPEC_PATH, help="Infographic specification.")
    parser.add_argument("--output-dir", default="output", help="Directory for the outputs.")
    parser.add_argument("--name", default="infographic", help="Base name of the output files.")
    parser.add_argument("--version", default=None, help="Version drawn on the image. Defaults to git describe.")
    parser.add_argument("--browser", default=None, help="Chrome or Edge executable.")
    parser.add_argument("--scale", type=float, default=2, help="PNG pixels per SVG unit. Defaults to 2.")
    return parser.parse_args()


def main() -> int:
    # Labels may hold characters the console encoding lacks; never fail on printing them.
    sys.stdout.reconfigure(errors="backslashreplace")
    args = arguments()
    root = Path(args.root).resolve()
    config_path = root / args.config
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    version = args.version or git_version(root)

    svg, report = infographic.build(root, config, version, date.today().isoformat(), args.spec)
    for warning in report.warnings:
        print(f"Warning: {warning}")
    if report.errors:
        print(f"The infographic specification has {len(report.errors)} problem(s):")
        for error in report.errors:
            print(f"  {error}")
        return 1

    output = root / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    svg_path = output / f"{args.name}.svg"
    svg_path.write_text(svg, encoding="utf-8", newline="\n")

    browser = find_browser(args.browser)
    if not browser:
        print("Chrome or Edge is required to check the infographic and export its PNG and PDF. "
              "Install one, or name it with --browser or CHROME_PATH.")
        return 1
    width, height = infographic.WIDTH, infographic.HEIGHT
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            page = Path(temporary) / "infographic.html"
            page.write_text(PAGE.format(width=width, height=height, svg=svg), encoding="utf-8")
            with HeadlessBrowser(browser) as session:
                session.open(page, width, height, args.scale)
                problems = session.evaluate(MEASURE)
                if problems:
                    print(f"The rendered infographic has {len(problems)} text problem(s):")
                    for problem in problems:
                        print(f"  {problem}")
                    return 1
                png = session.screenshot(width, height)
                pdf = session.pdf(width, height)
    except BrowserError as error:
        print(f"Exporting the infographic failed: {error}")
        return 1

    (output / f"{args.name}.png").write_bytes(png)
    (output / f"{args.name}.pdf").write_bytes(pdf)
    print(f"Built {svg_path} and its PNG and PDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
