"""Headless browser check for guide comments and the annotations panel (stdlib only).

Serves a guide built in InteropHub comment mode (--root) against the in-memory
mock hub, seeded with comments, replies, a comment that cannot be placed, and
review flags (mock_hub.seed_demo). The fixture's change markers and front
section (Executive Summary, What changed, Scope) come from its source. It
checks, as an author and as a reader:

- the panel: closed by default with margin ticks, opening each tab from the
  strip, the lens deciding which markers the text shows, ?lens=, remembering
  the last tab, Esc and focus return, arrow keys on the tabs, resizing it by
  dragging or with the keyboard (limits, memory, reset), and the bottom sheet
  at narrow width;
- comments: posting, disposition, close, re-attach, and flag edits from the
  panel; replies and refresh-safe drafts; row comments; blocked requests; the
  Open/All and Mine filters; and a reader's view without author controls;
- version comment modes: a Release version (readers see this release and
  earlier; authors see the rest marked "From another version" and left out of
  the counts), a Closed version (no comments, flags, or controls), and a write
  refused because the version closed while it was being written;
- local-comments mode (--local-guide), and a signed-out reader.

--screenshots saves pictures of each tab, wide and narrow, for a visual check.
--quick skips the 65-second wait that proves open forms survive a refresh.
"""

import argparse
import base64
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request

import mock_hub


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # Headless Chromium routinely cancels speculative asset requests.
        pass


class WebSocket:
    def __init__(self, url):
        parsed = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nOrigin: http://localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response: response += self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]: raise RuntimeError("DevTools WebSocket connection failed")
        self.ident = 0

    def send(self, method, params=None):
        self.ident += 1; ident = self.ident
        payload = json.dumps({"id": ident, "method": method, "params": params or {}}).encode()
        mask = os.urandom(4); length = len(payload)
        header = bytearray([0x81, 0x80 | (length if length < 126 else 126)])
        if length >= 126: header += struct.pack("!H", length)
        self.sock.sendall(header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(payload)))
        while True:
            message = self.recv()
            if message.get("id") == ident: return message

    def recv(self):
        first = self._read(2); length = first[1] & 0x7F
        if length == 126: length = struct.unpack("!H", self._read(2))[0]
        elif length == 127: length = struct.unpack("!Q", self._read(8))[0]
        if first[1] & 0x80: mask = self._read(4)
        else: mask = None
        payload = self._read(length)
        if mask: payload = bytes(value ^ mask[i % 4] for i, value in enumerate(payload))
        return json.loads(payload)

    def _read(self, count):
        value = b""
        while len(value) < count: value += self.sock.recv(count - len(value))
        return value


def evaluate(ws, expression):
    response = ws.send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    result = response.get("result", {})
    if result.get("exceptionDetails"):
        raise RuntimeError("Browser script failed: " + expression[:200] + "\n" + json.dumps(result["exceptionDetails"])[:800])
    return result.get("result", {}).get("value")


def truth(expression):
    # A DOM node comes back by value as {}, which Python reads as false, so
    # conditions are made true or false in the page.
    return "Boolean(eval(%s))" % json.dumps(expression)


def wait_for(ws, expression, timeout=12):
    end = time.time() + timeout
    while time.time() < end:
        if evaluate(ws, truth(expression)): return
        time.sleep(.2)
    raise RuntimeError("Timed out waiting for browser condition: " + expression)


def check(ws, expression, message, detail=None):
    if not evaluate(ws, truth(expression)):
        raise RuntimeError(message + (" Found: " + str(evaluate(ws, detail)) if detail else ""))


def drag(ws, start, end, y=400):
    # The panel slides in when it opens; grab its edge once it has settled.
    wait_for(ws, "document.getAnimations().every(a => a.playState !== 'running')")
    ws.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": start, "y": y})
    ws.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": start, "y": y, "button": "left", "buttons": 1, "clickCount": 1})
    for x in range(start, end, 40 if end > start else -40):
        ws.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "left", "buttons": 1})
    ws.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": end, "y": y, "button": "left", "buttons": 1})
    ws.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": end, "y": y, "button": "left", "buttons": 0, "clickCount": 1})


def press(ws, key, code=None, keycode=0, shift=False):
    for kind in ("keyDown", "keyUp"):
        ws.send("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code or key, "windowsVirtualKeyCode": keycode, "modifiers": 8 if shift else 0})


# Page helpers, defined once per page load. T(text) finds a top-level thread in
# the panel by its text; shown(selector) says whether any match is displayed.
HELPERS = """
window.T = function (text) {
  return Array.from(document.querySelectorAll('#guide-list-comments .guide-comment:not(.guide-reply)'))
    .find(function (n) { return n.querySelector(':scope > .guide-comment__text').textContent.includes(text); });
};
window.tool = function (node, label) {
  return Array.from(node.querySelectorAll(':scope > .guide-comment__tools button')).find(function (b) { return b.textContent === label; });
};
window.shown = function (selector) {
  return Array.from(document.querySelectorAll(selector)).some(function (n) { return getComputedStyle(n).display !== 'none'; });
};
window.count = function (lens) {
  return document.querySelector('.guide-lens-strip [data-guide-count=' + lens + ']').textContent;
};
window.strip = function (lens) { return document.querySelector('[data-guide-lens=' + lens + ']'); };
window.hubThread = function (text) {
  var request = new XMLHttpRequest();
  request.open('GET', 'http://127.0.0.1:8766/api/guide/example-core-document/comments', false);
  request.setRequestHeader('Authorization', 'Bearer ' + JSON.parse(localStorage.getItem('content-guide-token:http://127.0.0.1:8766:example-core-document')).accessToken);
  request.send();
  return JSON.parse(request.responseText).comments.find(function (c) { return c.text === text; });
};
window.lensIs = function (lens) { return document.body.classList.contains('guide-lens-' + lens); };
window.panelWidth = function () { return Math.round(document.getElementById('guide-annotations').getBoundingClientRect().width); };
window.mainLeft = function () { return Math.round(document.getElementById('guide-main').getBoundingClientRect().left); };
true
"""

STATIC = "http://127.0.0.1:8765/output/guide/"
RELEASE = "http://127.0.0.1:8765/output/release/"
CLOSED = "http://127.0.0.1:8765/output/closed/"
WIDE = (1400, 1000)
NARROW = (420, 860)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--browser", required=True); parser.add_argument("--root", required=True)
    parser.add_argument("--local-guide", help="A guide built in local-comments mode, to check that mode too.")
    parser.add_argument("--screenshots", help="Folder to save screenshots of the annotations panel for a visual check.")
    parser.add_argument("--quick", action="store_true", help="Skip the 65-second refresh check (for development only).")
    args = parser.parse_args()
    guide = os.path.join(args.root, "output", "guide", "index.html")
    # The same guide as two more versions (mock_hub.seed_demo): output/release/
    # is v0.2.0 in Release mode and output/closed/ is v0.1.0 in Closed mode.
    for version in ("release", "closed"):
        folder = os.path.join(args.root, "output", version); os.makedirs(folder, exist_ok=True)
        shutil.copyfile(guide, os.path.join(folder, "index.html"))
    if args.local_guide:
        shutil.copyfile(args.local_guide, os.path.join(args.root, "output", "guide", "local.html"))

    static = QuietServer(("127.0.0.1", 8765), lambda *values, **kw: Quiet(*values, directory=args.root, **kw))
    hub = mock_hub.serve(8766, ["http://127.0.0.1:8765"])
    mock_hub.seed_demo(hub.state, "http://127.0.0.1:8765")
    for server in (static, hub): threading.Thread(target=server.serve_forever, daemon=True).start()
    profiles = []
    processes = []
    if args.screenshots: os.makedirs(args.screenshots, exist_ok=True)

    def screenshot(ws, name, size=WIDE, scroll=None):
        if not args.screenshots: return
        ws.send("Emulation.setDeviceMetricsOverride", {"width": size[0], "height": size[1], "deviceScaleFactor": 1, "mobile": False})
        evaluate(ws, scroll or "window.scrollTo(0, 0); true")
        time.sleep(.6)
        shot = ws.send("Page.captureScreenshot", {"format": "png"})
        with open(os.path.join(args.screenshots, name + ".png"), "wb") as handle: handle.write(base64.b64decode(shot["result"]["data"]))

    def load(ws, url, ready):
        evaluate(ws, "location.href = %s; true" % json.dumps(url))
        time.sleep(.3)
        wait_for(ws, "document.readyState === 'complete' && document.body.className.includes('guide-lens-')", 20)
        evaluate(ws, HELPERS)
        if ready: wait_for(ws, ready, 15)

    try:
        def open_profile(token=None, user=None, author=False, page="index.html"):
            profile = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); profiles.append(profile)
            # Port 0 lets the browser choose a free port and write it to its own
            # profile, so a browser still closing from an earlier run is never reached.
            command = [args.browser, "--headless", "--disable-gpu", "--no-sandbox", "--no-first-run", "--remote-allow-origins=*", "--remote-debugging-port=0", "--user-data-dir=" + profile.name, "about:blank"]
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); processes.append(process)
            active = os.path.join(profile.name, "DevToolsActivePort")
            end = time.time() + 30
            while True:
                try:
                    with open(active, encoding="utf-8") as handle: port = int(handle.readline().strip())
                    request = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (port, STATIC + page), method="PUT")
                    with urllib.request.urlopen(request) as response: target = json.load(response)
                    break
                except (OSError, ValueError):
                    if time.time() > end: raise
                    time.sleep(.2)
            ws = WebSocket(target["webSocketDebuggerUrl"])
            ws.send("Emulation.setDeviceMetricsOverride", {"width": WIDE[0], "height": WIDE[1], "deviceScaleFactor": 1, "mobile": False})
            wait_for(ws, "location.hostname === '127.0.0.1' && location.port === '8765'", 30)
            if token:
                hub.state.tokens[token] = {"user": user, "isAuthor": author}
                key = "content-guide-token:http://127.0.0.1:8766:example-core-document"
                value = json.dumps({"accessToken": token, "expiresAt": "2099-01-01T00:00:00.000Z", "user": user})
                evaluate(ws, "localStorage.setItem(%s, %s); true" % (json.dumps(key), json.dumps(value)))
                load(ws, STATIC + page, "document.getElementById('guide-comments-status').textContent.includes('Signed in as %s')" % user["displayName"])
            else:
                load(ws, STATIC + page, None)
            return ws

        author = open_profile("ihg_browser_author", mock_hub.AUTHOR, True)
        wait_for(author, "T('Typo in') === undefined && T('position') !== undefined")

        # ---- The panel, closed by default ----
        check(author, "lensIs('none') && document.getElementById('guide-annotations').hidden && getComputedStyle(document.getElementById('guide-annotations')).display === 'none' && strip('comments').getAttribute('aria-expanded') === 'false'",
              "The annotations panel was not closed by default.")
        check(author, "count('comments') === '4' && count('review') === '3' && count('changes') === '5'",
              "Strip counts are wrong: " + str(evaluate(author, "[count('comments'), count('review'), count('changes')].join(',')")))
        check(author, "document.querySelectorAll('.guide-annotated').length >= 6 && getComputedStyle(document.querySelector('.guide-annotated'), '::before').content !== 'none'",
              "The closed panel did not leave margin ticks where annotations are.")
        check(author, "!shown('.guide-flag-marker') && !shown('.guide-change-marker') && !shown('.guide-comment-count')",
              "Markers showed in the text while the panel was closed.")
        check(author, "!document.querySelector('.guide-rail #guide-list-comments') && !document.querySelector('.guide-rail .guide-flag-card')",
              "The right rail still holds comments or review flags.")
        screenshot(author, "wide-1-closed-author")

        # ---- The front section (Executive Summary, What changed, Scope) ----
        check(author, "!Array.from(document.querySelectorAll('.aira-context-nav a')).some(a => ['#executive-summary', '#scope', '#guide-what-changed'].includes(a.getAttribute('href'))) && document.querySelectorAll('.aira-context-nav a').length === 1",
              "The front section has entries in the section bar.")
        check(author, "document.getElementById('guide-rail-title').textContent === 'Overview' && Array.from(document.querySelectorAll('#guide-subnav a')).map(a => a.textContent).join('|') === 'Executive Summary|What changed|Scope'",
              "The right rail did not list the front section while the reader was in it.",
              "document.getElementById('guide-rail-title').textContent")
        check(author, "var b=document.querySelector('.guide-status-banner'), s=document.getElementById('executive-summary'); b && b.compareDocumentPosition(s) & Node.DOCUMENT_POSITION_FOLLOWING && document.querySelector('.guide-title-link').getAttribute('href') === '#document-start'",
              "The status banner is not above the Executive Summary, or the title does not link to the top.")
        check(author, "var i=document.querySelector('.guide-scope-card--in').getBoundingClientRect(), o=document.querySelector('.guide-scope-card--out').getBoundingClientRect(), u=document.querySelector('.guide-scope-card--undecided').getBoundingClientRect(); Math.abs(i.top - o.top) < 2 && o.left > i.right && u.top >= Math.max(i.bottom, o.bottom) && u.width > i.width * 1.8",
              "In scope and Out of scope are not side by side with Not yet decided beneath.")
        check(author, "Array.from(document.querySelectorAll('#guide-what-changed .guide-what-changed__item')).map(n => n.querySelector('.guide-what-changed__level').textContent).join(',') === 'Feedback wanted,Feedback wanted,Changed,Changed,Changed' && document.querySelector('#guide-what-changed h2').textContent === 'What changed in v0.2.0'",
              "The What changed list is missing, mistitled, or not feedback first.")
        screenshot(author, "front-1-scope", scroll="document.getElementById('scope').scrollIntoView(); true")

        # ---- Each tab from the strip, and the lens it sets ----
        evaluate(author, "strip('comments').click(); true")
        check(author, "!document.getElementById('guide-annotations').hidden && lensIs('comments') && strip('comments').getAttribute('aria-expanded') === 'true' && document.activeElement.id === 'guide-tab-comments' && document.getElementById('guide-tab-comments').getAttribute('aria-selected') === 'true'",
              "The Comments strip button did not open the panel on its tab with focus on the tab.")
        check(author, "shown('.guide-comment-count') && !shown('.guide-flag-marker') && !shown('.guide-change-marker')",
              "The Comments lens did not show only comment counts.")
        check(author, "document.querySelector('.guide-annotation-group--unplaced') && document.querySelector('.guide-annotation-group--unplaced').textContent.includes('contradicts chapter 3') && Array.from(document.querySelectorAll('.guide-annotation-group__title')).map(n => n.textContent).join('|').startsWith('Executive Summary')",
              "Comments were not listed by section, then Not placed.")
        screenshot(author, "wide-2-comments-author")
        press(author, "Escape", "Escape", 27)
        check(author, "getComputedStyle(document.getElementById('guide-annotations')).display === 'none' && lensIs('none') && document.activeElement === strip('comments')",
              "Esc did not close the panel and return focus to the strip.")

        evaluate(author, "strip('review').click(); true")
        check(author, "lensIs('review') && shown('.guide-flag-marker') && shown('.guide-change-marker--feedback') && !shown('.guide-change-marker:not(.guide-change-marker--feedback)') && !shown('.guide-comment-count')",
              "The Review lens did not show flags and feedback-wanted markers only.")
        check(author, "document.querySelectorAll('#guide-list-review .guide-flag-card').length === 1 && document.querySelectorAll('#guide-list-review .guide-change-card--feedback').length === 2 && document.querySelector('#guide-list-review').textContent.includes('Flagged by Test Author')",
              "The Review tab did not list the flag (with who) and both feedback-wanted markers.")
        screenshot(author, "wide-3-review-author")
        press(author, "ArrowRight", "ArrowRight", 39)
        check(author, "lensIs('changes') && document.activeElement.id === 'guide-tab-changes'", "Arrow keys did not move between tabs.")
        check(author, "shown('.guide-change-marker') && document.querySelectorAll('.guide-change-marker').length === 5 && !shown('.guide-flag-marker') && document.querySelectorAll('#guide-list-changes .guide-change-card').length === 5",
              "The Changes lens did not show every change marker and only those.")
        check(author, "document.querySelector('section#detail').classList.contains('guide-changed') && document.querySelectorAll('[data-anchor=\"fixture-introduction\"].guide-changed').length === 1 && document.querySelector('tr#fx-2').classList.contains('guide-changed--feedback')",
              "Change markers did not cover their section, single block, and row.")
        screenshot(author, "wide-4-changes", scroll="document.getElementById('detail').scrollIntoView(); true")
        evaluate(author, "Array.from(document.querySelectorAll('#guide-list-changes .guide-where')).find(b => b.textContent.includes('FX-2')).click(); true")
        wait_for(author, "document.querySelector('tr#fx-2').classList.contains('guide-highlight')")

        # ---- Remembered state and ?lens= ----
        load(author, STATIC + "index.html", "T('position') !== undefined")
        check(author, "lensIs('changes') && !document.getElementById('guide-annotations').hidden", "The last tab and open state were not remembered.")
        load(author, STATIC + "index.html?lens=comments", "T('position') !== undefined")
        check(author, "lensIs('comments')", "?lens=comments did not override the remembered tab.")

        # ---- Resizing the panel ----
        # Drag its right edge; the reading column follows. The width stays
        # within its limits, is remembered, and resets on double-click or Home.
        check(author, "panelWidth() === 340 && mainLeft() === 340 && document.getElementById('guide-annotations-resize').getAttribute('aria-valuenow') === '340'",
              "The panel did not start at its default width.", "JSON.stringify([panelWidth(), mainLeft()])")
        drag(author, 339, 500)
        check(author, "Math.abs(panelWidth() - 500) <= 2 && Math.abs(mainLeft() - panelWidth()) <= 1 && !document.body.classList.contains('guide-resizing')",
              "Dragging the panel's edge did not resize it and move the reading column.", "JSON.stringify([panelWidth(), mainLeft()])")
        drag(author, 499, 1300)
        check(author, "panelWidth() === 640 && document.body.classList.contains('guide-rail-below') && getComputedStyle(document.querySelector('.guide-layout')).gridTemplateColumns.split(' ').length === 1",
              "The panel grew past its limit, or the rail did not move under the text.", "JSON.stringify([panelWidth(), document.body.className])")
        drag(author, 639, 100)
        check(author, "panelWidth() === 280 && !document.body.classList.contains('guide-rail-below')",
              "The panel shrank past its limit, or the rail stayed under the text with room beside it.", "JSON.stringify([panelWidth(), document.body.className])")
        evaluate(author, "document.getElementById('guide-annotations-resize').focus(); true")
        press(author, "ArrowRight", "ArrowRight", 39)
        press(author, "ArrowRight", "ArrowRight", 39, shift=True)
        check(author, "panelWidth() === 360 && document.getElementById('guide-annotations-resize').getAttribute('aria-valuenow') === '360'",
              "Arrow keys did not resize the panel.", "panelWidth()")
        load(author, STATIC + "index.html", "T('position') !== undefined")
        check(author, "panelWidth() === 360 && lensIs('comments')", "The panel's width was not remembered.", "panelWidth()")
        evaluate(author, "document.getElementById('guide-annotations-resize').dispatchEvent(new MouseEvent('dblclick', {bubbles: true})); true")
        check(author, "panelWidth() === 340", "Double-click did not reset the panel's width.", "panelWidth()")
        drag(author, 339, 520)
        screenshot(author, "wide-10-resized")
        evaluate(author, "var r=document.getElementById('guide-annotations-resize'); r.focus(); r.dispatchEvent(new KeyboardEvent('keydown', {key: 'Home', bubbles: true})); true")
        check(author, "panelWidth() === 340", "Home did not reset the panel's width.", "panelWidth()")

        # ---- Comments: post, dispose, and reply from the panel ----
        wait_for(author, "Array.from(document.querySelectorAll('.guide-comment-button')).some(b => !b.hidden)")
        wait_for(author, "document.querySelector('.guide-diagram pre.mermaid[data-processed] svg') !== null")
        wait_for(author, "document.querySelector('.guide-diagram.guide-block .guide-comment-button') !== null")
        evaluate(author, "Array.from(document.querySelectorAll('.guide-comment-button')).find(b => !b.hidden).click(); true")
        wait_for(author, "document.querySelector('#guide-content .guide-comment-form textarea') !== null")
        evaluate(author, "document.querySelector('.guide-comment-form textarea').value='Browser smoke comment'; document.querySelector('.guide-comment-form input[type=checkbox]').click(); document.querySelector('.guide-comment-form').requestSubmit(); true")
        wait_for(author, "T('Browser smoke comment') && !document.querySelector('#guide-content .guide-comment-form') && lensIs('comments')")
        evaluate(author, "tool(T('Browser smoke comment'), 'Dispose').click(); true")
        wait_for(author, "T('Browser smoke comment').querySelector('.guide-author-form') !== null")
        evaluate(author, "var f=T('Browser smoke comment').querySelector('.guide-author-form'); f.querySelector('textarea').value='Browser disposition note'; f.requestSubmit(); true")
        wait_for(author, "T('Browser smoke comment').textContent.includes('Browser disposition note')")

        # Open forms survive the periodic refresh, with their value, focus, and
        # selection. Use separate threads so both forms are open at once.
        evaluate(author, "Array.from(document.querySelectorAll('.guide-comment-button')).find(b => !b.hidden).click(); true")
        wait_for(author, "document.querySelector('#guide-content .guide-comment-form textarea') !== null")
        evaluate(author, "document.querySelector('#guide-content .guide-comment-form textarea').value='Second browser comment'; document.querySelector('#guide-content .guide-comment-form').requestSubmit(); true")
        wait_for(author, "T('Second browser comment') !== undefined")
        evaluate(author, "tool(T('Browser smoke comment'), 'Change disposition').click(); true")
        wait_for(author, "document.querySelector('.guide-author-form textarea') !== null")
        evaluate(author, "var n=document.querySelector('.guide-author-form textarea'); n.value='Disposition draft through refreshes'; n.focus(); n.setSelectionRange(12,12); true")
        evaluate(author, "tool(T('Second browser comment'), 'Reply').click(); true")
        wait_for(author, "document.querySelectorAll('#guide-list-comments .guide-comment-form textarea').length === 2")
        evaluate(author, "var n=Array.from(document.querySelectorAll('.guide-comment-form textarea')).find(n => !n.closest('.guide-author-form')); n.value='Reply draft through refreshes'; n.focus(); n.setSelectionRange(8,8); true")
        if not args.quick:
            time.sleep(65)
            check(author, "var a=document.querySelector('.guide-author-form textarea'); var r=Array.from(document.querySelectorAll('.guide-comment-form textarea')).find(n => !n.closest('.guide-author-form')); a && r && a.value==='Disposition draft through refreshes' && r.value==='Reply draft through refreshes' && document.activeElement===r && r.selectionStart===8 && r.selectionEnd===8",
                  "Open comment forms lost text, focus, or selection during refresh.")
        evaluate(author, "var a=document.querySelector('.guide-author-form'); var r=Array.from(document.querySelectorAll('.guide-comment-form')).find(n => !n.classList.contains('guide-author-form')); a.requestSubmit(); r.requestSubmit(); true")
        wait_for(author, "document.getElementById('guide-list-comments').textContent.includes('Disposition draft through refreshes')")
        wait_for(author, "document.getElementById('guide-list-comments').textContent.includes('Reply draft through refreshes')")

        # A row of a row-anchored table takes its own comment and flag. The form
        # opens in a full-width row beneath it; the thread is listed in the panel.
        wait_for(author, "document.querySelector('tr#fx-2.guide-block > td:last-child > .guide-comment-button') !== null")
        wait_for(author, "document.querySelector('tr#fx-2 > td:last-child > .guide-flag-button') !== null")
        evaluate(author, "document.querySelector('tr#fx-2 > td:last-child > .guide-comment-button').click(); true")
        wait_for(author, "document.querySelector('tr#fx-2 + tr.guide-row-extra .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('tr#fx-2 + tr.guide-row-extra .guide-comment-form'); f.querySelector('textarea').value='Row comment'; f.requestSubmit(); true")
        wait_for(author, "T('Row comment') && T('Row comment').closest('.guide-annotation-item').querySelector('.guide-where').textContent.includes('FX-2')")
        check(author, "document.querySelector('tr#fx-2 .guide-comment-count--row') !== null && !document.querySelector('tr#fx-2 + tr.guide-row-extra')",
              "A row comment did not get its count in the row, or left an empty row behind.")
        check(author, "!document.querySelector('tr#fx-1 + tr.guide-row-extra') || getComputedStyle(document.querySelector('tr#fx-1 + tr.guide-row-extra')).display === 'none'",
              "An empty comment row was shown under a row without comments.")

        # A response that is not the hub's JSON, as from a firewall in front of it,
        # is reported as such. The text stays in the form and survives a reload.
        evaluate(author, "document.querySelector('tr#fx-1 > td:last-child > .guide-comment-button').click(); true")
        wait_for(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form'); var n=f.querySelector('textarea'); n.value='Long draft TEST-FIREWALL-BLOCK'; n.dispatchEvent(new Event('input')); f.requestSubmit(); true")
        wait_for(author, "(document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-form-error')||{textContent:''}).textContent.includes('stopped before it reached InteropHub (HTTP 403')")
        check(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form textarea').value==='Long draft TEST-FIREWALL-BLOCK'",
              "A blocked comment's text was not kept in the form.")
        load(author, STATIC + "index.html", "T('Row comment') !== undefined && document.querySelector('tr#fx-1 > td:last-child > .guide-comment-button') !== null")
        evaluate(author, "document.querySelector('tr#fx-1 > td:last-child > .guide-comment-button').click(); true")
        wait_for(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-form-draft') !== null")
        check(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form textarea').value==='Long draft TEST-FIREWALL-BLOCK'",
              "An unsaved comment draft was not restored after a reload.")
        evaluate(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-form-draft button').click(); true")
        check(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form textarea').value==='' && !Object.keys(localStorage).some(k => k.startsWith('content-guide-draft:'))",
              "Discarding a draft did not clear it.")
        evaluate(author, "Array.from(document.querySelectorAll('tr#fx-1 + tr.guide-row-extra .guide-comment-form button')).find(b => b.textContent==='Cancel').click(); true")

        # ---- Review flags ----
        # An author flags an area from the flag button beside the comment button.
        # In the Review lens the area gets a purple marker and bar and the section
        # link a dot; the Review tab lists the flag.
        evaluate(author, "strip('review').click(); true")
        evaluate(author, "document.querySelector('p[data-anchor=\"review-item\"] > .guide-flag-button').click(); true")
        wait_for(author, "document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form'); f.querySelector('textarea').value='Please check this area'; f.requestSubmit(); true")
        wait_for(author, "Array.from(document.querySelectorAll('.guide-flag-marker')).some(m => m.nextElementSibling && m.nextElementSibling.dataset.anchor === 'review-item')")
        check(author, "var m=Array.from(document.querySelectorAll('.guide-flag-marker')).find(m => m.nextElementSibling && m.nextElementSibling.dataset.anchor === 'review-item'); m.textContent.includes('Please check this area') && document.querySelectorAll('[data-anchor=\"review-item\"].guide-review-flagged').length===document.querySelectorAll('[data-anchor=\"review-item\"]').length && document.querySelectorAll('.guide-review-flagged--continued').length>=1 && shown('.guide-nav-flagged') && getComputedStyle(document.querySelector('.guide-nav-flagged'), '::after').content !== 'none'",
              "A flagged area did not get its marker, bar, or section dot.")
        evaluate(author, "document.querySelector('tr#fx-2 > td:last-child > .guide-flag-button').click(); true")
        wait_for(author, "document.querySelector('tr#fx-2 + tr.guide-row-extra .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('tr#fx-2 + tr.guide-row-extra .guide-comment-form'); f.querySelector('textarea').value='Row needs a decision'; f.requestSubmit(); true")
        wait_for(author, "document.querySelector('tr#fx-2.guide-review-flagged > td:first-child > .guide-flag-marker--row') !== null")
        wait_for(author, "count('review') === '5' && document.querySelectorAll('#guide-list-review .guide-flag-card').length === 3")

        # Edit a flag from its card in the panel.
        evaluate(author, "var c=Array.from(document.querySelectorAll('#guide-list-review .guide-flag-card')).find(c => c.textContent.includes('Please check this area')); Array.from(c.querySelectorAll('.guide-comment__tools button')).find(b => b.textContent==='Edit').click(); true")
        wait_for(author, "document.querySelector('#guide-list-review .guide-flag-card .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('#guide-list-review .guide-flag-card .guide-comment-form'); f.querySelector('textarea').value='Edited from the panel'; f.requestSubmit(); true")
        wait_for(author, "Array.from(document.querySelectorAll('.guide-flag-marker')).some(m => m.textContent.includes('Edited from the panel')) && document.getElementById('guide-list-review').textContent.includes('Edited from the panel')")

        # Clear a flag from its marker in the text.
        evaluate(author, "document.querySelector('tr#fx-2 .guide-flag-badge').click(); true")
        wait_for(author, "document.querySelector('tr#fx-2 .guide-flag-marker.is-open') !== null")
        evaluate(author, "Array.from(document.querySelectorAll('tr#fx-2 .guide-flag-popover button')).find(b => b.textContent==='Clear').click(); true")
        wait_for(author, "document.querySelector('tr#fx-2 .guide-flag-marker') === null && !document.querySelector('tr#fx-2').classList.contains('guide-review-flagged')")
        wait_for(author, "count('review') === '4'")
        # All shows cleared flags too.
        evaluate(author, "document.querySelector('[data-guide-filter=review-state] [data-value=all]').click(); true")
        wait_for(author, "document.querySelectorAll('#guide-list-review .guide-flag-card--cleared').length === 2")
        check(author, "!document.querySelector('#guide-list-review .guide-flag-card--cleared button')", "A cleared flag offered controls.")
        evaluate(author, "document.querySelector('[data-guide-filter=review-state] [data-value=open]').click(); true")
        wait_for(author, "document.querySelectorAll('#guide-list-review .guide-flag-card--cleared').length === 0")

        # ---- Author controls in the Comments tab: close, re-attach, filters ----
        evaluate(author, "strip('comments').click(); true")
        open_before = evaluate(author, "count('comments')")
        evaluate(author, "tool(T('Second browser comment'), 'Close').click(); true")
        wait_for(author, "T('Second browser comment') === undefined && count('comments') === String(Number(%s) - 1)" % json.dumps(open_before))
        evaluate(author, "document.querySelector('[data-guide-filter=comments-state] [data-value=all]').click(); true")
        wait_for(author, "T('Second browser comment') && T('Second browser comment').classList.contains('guide-comment--closed') && T('Typo in') !== undefined")
        evaluate(author, "document.querySelector('[data-guide-filter=comments-state] [data-value=open]').click(); true")
        wait_for(author, "T('Typo in') === undefined")
        evaluate(author, "tool(T('contradicts chapter 3'), 'Re-attach').click(); true")
        wait_for(author, "T('contradicts chapter 3').querySelector('.guide-author-form select') !== null")
        evaluate(author, "T('contradicts chapter 3').querySelector('.guide-author-form').requestSubmit(); true")
        wait_for(author, "!document.querySelector('.guide-annotation-group--unplaced') && T('contradicts chapter 3') !== undefined")
        evaluate(author, "document.querySelector('[data-guide-filter=mine]').click(); true")
        check(author, "T('Browser smoke comment') && T('position') && T('Our program treats') === undefined",
              "Mine did not keep the author's own threads and the ones they replied to, or let others through.")
        evaluate(author, "document.querySelector('[data-guide-filter=mine]').click(); true")
        check(author, "T('Our program treats') !== undefined", "Turning Mine off did not show everyone's comments again.")

        # ---- A reader ----
        reader = open_profile("ihg_browser_reader", mock_hub.READER, False, "index.html?lens=comments")
        wait_for(reader, "document.getElementById('guide-list-comments').textContent.includes('Disposition draft through refreshes')")
        check(reader, "lensIs('comments') && !Array.from(document.querySelectorAll('#guide-annotations button')).some(b => ['Dispose','Close','Delete','Re-attach','Clear','Change disposition'].includes(b.textContent))",
              "The reader was shown author controls in the panel.")
        check(reader, "document.querySelector('.guide-flag-button') === null && document.querySelector('.guide-flag-popover button') === null && document.querySelector('#guide-list-review .guide-flag-card button') === null",
              "The reader was shown review flag controls.")
        check(reader, "document.querySelectorAll('.guide-flag-marker').length === 2", "The reader did not see the review flags.")
        screenshot(reader, "wide-5-comments-reader")
        evaluate(reader, "document.querySelector('[data-guide-filter=mine]').click(); true")
        check(reader, "T('position') && T('Our program treats') && T('Browser smoke comment') === undefined && T('position').querySelector('.guide-comment__mine')",
              "Mine did not use the hub's 'mine' for the reader.",
              "JSON.stringify([!!T('position'), !!T('Our program treats'), !T('Browser smoke comment'), !!(T('position') && T('position').querySelector('.guide-comment__mine')), Array.from(document.querySelectorAll('#guide-list-comments .guide-comment:not(.guide-reply) > .guide-comment__text')).map(n => n.textContent.slice(0, 30))])")
        evaluate(reader, "document.querySelector('[data-guide-filter=mine]').click(); true")
        evaluate(reader, "strip('review').click(); true")
        screenshot(reader, "wide-6-review-reader", scroll="document.getElementById('detail').scrollIntoView(); true")

        # ---- The bottom sheet at narrow width ----
        reader.send("Emulation.setDeviceMetricsOverride", {"width": NARROW[0], "height": NARROW[1], "deviceScaleFactor": 1, "mobile": False})
        time.sleep(.4)
        check(reader, "var r=document.getElementById('guide-annotations').getBoundingClientRect(); r.left === 0 && Math.round(r.width) === document.documentElement.clientWidth && Math.abs(r.bottom - innerHeight) < 2 && r.top > innerHeight * 0.2 && document.getElementById('guide-main').getBoundingClientRect().left === 0",
              "Below 900 px the panel did not become a bottom sheet over an unshifted page.",
              "JSON.stringify([document.getElementById('guide-annotations').getBoundingClientRect(), innerWidth, innerHeight, document.getElementById('guide-main').getBoundingClientRect().left])")
        check(reader, "var i=document.querySelector('.guide-scope-card--in').getBoundingClientRect(), o=document.querySelector('.guide-scope-card--out').getBoundingClientRect(); o.top >= i.bottom",
              "On a narrow screen the Scope cards did not stack.")
        check(reader, "getComputedStyle(document.getElementById('guide-annotations-resize')).display === 'none'",
              "The bottom sheet showed a resize handle.")
        screenshot(reader, "narrow-2-review", NARROW, "document.getElementById('detail').scrollIntoView(); true")
        evaluate(reader, "strip('comments').click(); true")
        screenshot(reader, "narrow-1-comments", NARROW)
        evaluate(reader, "strip('changes').click(); true")
        screenshot(reader, "narrow-3-changes", NARROW, "document.getElementById('detail').scrollIntoView(); true")
        press(reader, "Escape", "Escape", 27)
        check(reader, "getComputedStyle(document.getElementById('guide-annotations')).display === 'none' && document.activeElement === strip('changes')", "Esc did not close the bottom sheet.")
        screenshot(reader, "narrow-0-closed", NARROW)
        reader.send("Emulation.setDeviceMetricsOverride", {"width": WIDE[0], "height": WIDE[1], "deviceScaleFactor": 1, "mobile": False})

        # ---- Version comment modes (contract 5.3.1) ----
        # Release: readers see this release and earlier; authors see every
        # comment, with those from other versions marked and left out of counts.
        def set_mode(label, mode):
            with urllib.request.urlopen("http://127.0.0.1:8766/test/label?label=%s&mode=%s" % (label, mode)) as response: response.read()
        note = "document.getElementById('guide-label-note')"
        load(reader, RELEASE + "?lens=comments", "T('position') !== undefined")
        check(reader, "!%s.hidden && %s.textContent.includes('this release and earlier') && !%s.textContent.includes('other versions')" % (note, note, note),
              "A reader on a Release version was not told what the Comments tab shows.", note + ".textContent")
        check(reader, "T('Our program treats') === undefined && T('Browser smoke comment') === undefined && T('Status should') !== undefined && !document.querySelector('.guide-other-version')",
              "A reader on a Release version saw comments from another version.")
        check(reader, "Number(count('comments')) === document.querySelectorAll('#guide-list-comments .guide-comment:not(.guide-reply)').length",
              "A reader's count on a Release version did not match the list.", "count('comments')")
        evaluate(reader, "Array.from(document.querySelectorAll('.guide-comment-button')).find(b => !b.hidden).click(); true")
        wait_for(reader, "document.querySelector('#guide-content .guide-comment-form textarea') !== null")
        evaluate(reader, "var f=document.querySelector('#guide-content .guide-comment-form'); f.querySelector('textarea').value='Written on the release'; var c=f.querySelector('input[type=checkbox]'); if (c) c.click(); f.requestSubmit(); true")
        wait_for(reader, "T('Written on the release') !== undefined")
        check(reader, "hubThread('Written on the release').madeOnLabel === 'v0.2.0'", "A comment on the Release page was not recorded on its label.")
        screenshot(reader, "modes-1-release-reader")
        load(author, RELEASE + "?lens=comments", "T('position') !== undefined")
        check(author, "%s.textContent.includes('Comments from other versions are marked.')" % note,
              "An author on a Release version was not told that other versions are marked.", note + ".textContent")
        check(author, "T('Our program treats').classList.contains('guide-other-version') && T('Our program treats').textContent.includes('From another version (main)') && T('Browser smoke comment').textContent.includes('From another version (main)') && !T('position').classList.contains('guide-other-version') && T('Status should').textContent.includes('Written on v0.2.0') && T('Written on the release').textContent.includes('Written on v0.2.0')",
              "An author on a Release version did not see other versions' comments marked, or where comments were written.")
        check(author, "Number(count('comments')) === document.querySelectorAll('#guide-list-comments .guide-comment:not(.guide-reply):not(.guide-other-version)').length && document.querySelectorAll('#guide-list-comments .guide-other-version').length >= 2",
              "Comments from other versions were counted.", "[count('comments'), document.querySelectorAll('#guide-list-comments .guide-other-version').length]")
        evaluate(author, "strip('review').click(); true")
        check(author, "Array.from(document.querySelectorAll('#guide-list-review .guide-flag-card')).some(c => c.textContent.includes('Edited from the panel') && c.textContent.includes('From another version (main)')) && count('review') === String(document.querySelectorAll('#guide-list-review .guide-flag-card:not(.guide-other-version)').length + 2)",
              "A flag from another version was not marked, or was counted.", "count('review')")
        evaluate(author, "strip('comments').click(); true")
        screenshot(author, "modes-2-release-author")

        # Closed: no comments, flags, or controls, for authors and readers alike.
        load(author, CLOSED + "?lens=comments", "%s.textContent === 'Comments are closed on this version.'" % note)
        check(author, "count('comments') === '\u2013' && !document.querySelector('#guide-list-comments .guide-comment') && !shown('.guide-comment-button') && !shown('.guide-flag-button') && !document.querySelector('.guide-flag-marker') && document.querySelector('[data-guide-filter=comments-state]').parentElement.hidden",
              "A Closed version showed comments or comment controls to an author.")
        evaluate(author, "strip('review').click(); true")
        check(author, "!document.querySelector('#guide-list-review .guide-flag-card') && count('review') === '2'", "A Closed version showed review flags.", "count('review')")
        evaluate(author, "strip('comments').click(); true")
        screenshot(author, "modes-3-closed-author")
        load(reader, CLOSED + "?lens=comments", "%s.textContent === 'Comments are closed on this version.'" % note)
        check(reader, "!document.querySelector('#guide-list-comments .guide-comment') && !shown('.guide-comment-button')", "A Closed version showed comments to a reader.")

        # A mode changed while the page is open: the next refresh reads
        # everything again, so threads the new mode reveals or hides follow.
        load(reader, RELEASE + "?lens=comments", "T('position') !== undefined")
        check(reader, "T('Our program treats') === undefined", "A reader on a Release version saw another version's comment.")
        set_mode("v0.2.0", "open")
        evaluate(reader, "document.dispatchEvent(new Event('visibilitychange')); true")
        wait_for(reader, "T('Our program treats') !== undefined && %s.hidden" % note, 15)
        set_mode("v0.2.0", "release")
        evaluate(reader, "document.dispatchEvent(new Event('visibilitychange')); true")
        # Setting Release again moves v0.2.0's publication time to now (it has no
        # upload), so every earlier comment is in scope; only the line returns.
        wait_for(reader, "!%s.hidden && T('Our program treats') !== undefined" % note, 15)

        # A version closed while a comment was being written: the write is
        # refused, and the text stays in the form and in the browser.
        load(author, RELEASE, "T('position') !== undefined")
        evaluate(author, "document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-button').click(); true")
        wait_for(author, "document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form textarea') !== null")
        evaluate(author, "var n=document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form textarea'); n.value='Written as the version closed'; n.dispatchEvent(new Event('input')); true")
        set_mode("v0.2.0", "closed")
        evaluate(author, "document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form').requestSubmit(); true")
        wait_for(author, "(document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form .guide-form-error')||{textContent:''}).textContent.includes('Comments are closed on this version.')")
        check(author, "var f=document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form'); getComputedStyle(f).display !== 'none' && f.querySelector('textarea').value === 'Written as the version closed' && Object.keys(localStorage).some(k => k.startsWith('content-guide-draft:') && localStorage.getItem(k) === 'Written as the version closed') && !shown('.guide-comment-button') && %s.textContent === 'Comments are closed on this version.' && count('comments') === '\u2013' && !document.querySelector('#guide-list-comments .guide-comment') && count('review') === '2' && !document.querySelector('.guide-flag-marker')" % note,
              "A write refused because comments closed lost its text or left the comment controls showing.")
        screenshot(author, "modes-4-refused-closed", scroll="document.querySelector('p[data-anchor=\"review-item\"]').scrollIntoView({block:'center'}); true")
        set_mode("v0.2.0", "release")
        evaluate(author, "localStorage.clear(); true")

        # ---- Signed out, and local-comments mode ----
        visitor = open_profile()
        wait_for(visitor, "document.getElementById('guide-sign-in') !== null")
        check(visitor, "count('comments') === '–' && count('changes') === '5' && count('review') === '2'",
              "A signed-out reader's counts were wrong.")
        evaluate(visitor, "document.querySelector('.guide-comment-button').click(); true")
        wait_for(visitor, "lensIs('comments') && document.activeElement && document.activeElement.id === 'guide-sign-in'")
        screenshot(visitor, "wide-7-signed-out")
        if args.local_guide:
            load(visitor, STATIC + "local.html?lens=review", None)
            check(visitor, "lensIs('review') && document.querySelectorAll('#guide-list-review .guide-annotation-item').length === 2 && document.querySelectorAll('#guide-list-review .guide-change-card--feedback').length === 2 && document.querySelector('#guide-tabpanel-review .guide-filters').hidden",
                  "In local-comments mode the Review tab did not show only the source's feedback markers.")
            screenshot(visitor, "wide-8-local-review")
            evaluate(visitor, "document.querySelector('#guide-tab-comments').click(); true")
            check(visitor, "var d=document.getElementById('guide-comments-download'); d.closest('#guide-tabpanel-comments') && !d.closest('[hidden]') && document.querySelector('[data-guide-filter=comments-state]').hidden && !document.querySelector('.guide-rail #guide-comments-download')",
                  "In local-comments mode the load and download controls were not in the Comments tab.")
            evaluate(visitor, "var n=document.getElementById('guide-commenter'); n.value='Local Reader'; n.dispatchEvent(new Event('change')); document.querySelector('.guide-comment-button').click(); true")
            wait_for(visitor, "document.querySelector('#guide-content .guide-comment-form textarea') !== null")
            evaluate(visitor, "document.querySelector('#guide-content .guide-comment-form textarea').value='Local panel comment'; document.querySelector('#guide-content .guide-comment-form').requestSubmit(); true")
            wait_for(visitor, "T('Local panel comment') !== undefined && count('comments') === '1' && lensIs('comments')")
            evaluate(visitor, "document.querySelector('[data-guide-filter=mine]').click(); true")
            check(visitor, "T('Local panel comment') !== undefined", "Mine did not match the local commenter's name.")
            screenshot(visitor, "wide-9-local-comments")
        print("Front section (banner, summary, What changed, scope cards, rail) and annotations panel (tabs, lenses, ?lens=, memory, resizing, comment modes, Esc, bottom sheet, filters, author and reader views, local mode) and guide comments (refresh-safe drafts, blocked-request drafts, review flags, rows) check passed.")
    finally:
        for process in processes: process.terminate()
        for process in processes:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
        for profile in profiles: profile.cleanup()
        static.shutdown(); hub.shutdown(); static.server_close(); hub.server_close()


if __name__ == "__main__": main()
