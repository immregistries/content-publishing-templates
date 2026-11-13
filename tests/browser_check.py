"""Headless browser smoke check for guide sign-in and posting (stdlib only)."""

import argparse
import base64
import hashlib
import http.server
import json
import os
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
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=10)
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
    return response.get("result", {}).get("result", {}).get("value")


def wait_for(ws, expression, timeout=12):
    end = time.time() + timeout
    while time.time() < end:
        if evaluate(ws, expression): return
        time.sleep(.2)
    raise RuntimeError("Timed out waiting for browser condition: " + expression)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--browser", required=True); parser.add_argument("--root", required=True)
    parser.add_argument("--screenshots", help="Folder to save screenshots of review flags for a visual check.")
    args = parser.parse_args()
    static = QuietServer(("127.0.0.1", 8765), lambda *values, **kw: Quiet(*values, directory=args.root, **kw))
    hub = mock_hub.serve(8766, ["http://127.0.0.1:8765"])
    for server in (static, hub): threading.Thread(target=server.serve_forever, daemon=True).start()
    profiles = []
    processes = []
    try:
        def open_profile(port, token, user, author):
            profile = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); profiles.append(profile)
            hub.state.tokens[token] = {"user": user, "isAuthor": author}
            command = [args.browser, "--headless", "--disable-gpu", "--no-sandbox", "--no-first-run", "--remote-allow-origins=*", "--remote-debugging-port=" + str(port), "--user-data-dir=" + profile.name, "about:blank"]
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); processes.append(process)
            endpoint = "http://127.0.0.1:%d/json/new?http://127.0.0.1:8765/output/guide/index.html" % port
            end = time.time() + 15
            while True:
                try:
                    request = urllib.request.Request(endpoint, method="PUT")
                    with urllib.request.urlopen(request) as response: target = json.load(response)
                    break
                except OSError:
                    if time.time() > end: raise
                    time.sleep(.2)
            ws = WebSocket(target["webSocketDebuggerUrl"])
            wait_for(ws, "location.hostname === '127.0.0.1' && location.port === '8765'")
            key = "content-guide-token:http://127.0.0.1:8766:example-core-document"
            value = json.dumps({"accessToken": token, "expiresAt": "2099-01-01T00:00:00.000Z", "user": user})
            evaluate(ws, "localStorage.setItem(%s, %s); location.reload()" % (json.dumps(key), json.dumps(value)))
            wait_for(ws, "document.body && document.body.innerText.includes('Signed in as %s')" % user["displayName"])
            return ws

        author = open_profile(9223, "ihg_browser_author", {"userId": 9, "displayName": "Test Author", "organization": "Example Organization"}, True)
        wait_for(author, "Array.from(document.querySelectorAll('.guide-comment-button')).some(b => !b.hidden)")
        # The fixture's Mermaid diagram is drawn before comments start, and can take a comment.
        wait_for(author, "document.querySelector('.guide-diagram pre.mermaid[data-processed] svg') !== null")
        wait_for(author, "document.querySelector('.guide-diagram.guide-block .guide-comment-button') !== null")
        result = author.send("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('.guide-comment-button')).find(b => !b.hidden).click()", "returnByValue": True})
        if result.get("result", {}).get("exceptionDetails"):
            raise RuntimeError("Comment button failed: " + json.dumps(result["result"]["exceptionDetails"]))
        wait_for(author, "document.querySelector('.guide-comment-form textarea') !== null")
        evaluate(author, "document.querySelector('.guide-comment-form textarea').value='Browser smoke comment'; document.querySelector('.guide-comment-form input[type=checkbox]').click(); document.querySelector('.guide-comment-form').requestSubmit()")
        wait_for(author, "document.querySelector('.guide-comment__text') && document.querySelector('.guide-comment__text').textContent.includes('Browser smoke comment')")
        evaluate(author, "Array.from(document.querySelectorAll('.guide-comment__tools button')).find(b => b.textContent==='Dispose').click()")
        wait_for(author, "document.querySelector('.guide-author-form') !== null")
        evaluate(author, "document.querySelector('.guide-author-form textarea').value='Browser disposition note'; document.querySelector('.guide-author-form').requestSubmit()")
        wait_for(author, "document.body.innerText.includes('Browser disposition note')")

        # Open forms must survive the periodic refresh, including their value,
        # focus, and selection. Use separate threads so both forms are open at once.
        evaluate(author, "Array.from(document.querySelectorAll('.guide-comment-button')).find(b => !b.hidden).click()")
        wait_for(author, "document.querySelector('.guide-comment-form textarea') !== null")
        evaluate(author, "document.querySelector('.guide-comment-form textarea').value='Second browser comment'; document.querySelector('.guide-comment-form').requestSubmit()")
        wait_for(author, "Array.from(document.querySelectorAll('.guide-comment__text')).some(n => n.textContent.includes('Second browser comment'))")
        evaluate(author, "var t=Array.from(document.querySelectorAll('.guide-comment')).find(n => n.querySelector('.guide-comment__text').textContent.includes('Browser smoke comment')); Array.from(t.querySelectorAll(':scope > .guide-comment__tools button')).find(b => b.textContent==='Change disposition').click()")
        wait_for(author, "document.querySelector('.guide-author-form textarea') !== null")
        evaluate(author, "var n=document.querySelector('.guide-author-form textarea'); n.value='Disposition draft through refreshes'; n.focus(); n.setSelectionRange(12,12)")
        evaluate(author, "var t=Array.from(document.querySelectorAll('.guide-comment')).find(n => n.querySelector('.guide-comment__text').textContent.includes('Second browser comment')); Array.from(t.querySelectorAll(':scope > .guide-comment__tools button')).find(b => b.textContent==='Reply').click()")
        wait_for(author, "document.querySelectorAll('.guide-comment-form textarea').length === 2")
        evaluate(author, "var n=Array.from(document.querySelectorAll('.guide-comment-form textarea')).find(n => !n.closest('.guide-author-form')); n.value='Reply draft through refreshes'; n.focus(); n.setSelectionRange(8,8)")
        time.sleep(65)
        if not evaluate(author, "var a=document.querySelector('.guide-author-form textarea'); var r=Array.from(document.querySelectorAll('.guide-comment-form textarea')).find(n => !n.closest('.guide-author-form')); a && r && a.value==='Disposition draft through refreshes' && r.value==='Reply draft through refreshes' && document.activeElement===r && r.selectionStart===8 && r.selectionEnd===8"):
            raise RuntimeError("Open comment forms lost text, focus, or selection during refresh.")
        evaluate(author, "var a=document.querySelector('.guide-author-form'); var r=Array.from(document.querySelectorAll('.guide-comment-form')).find(n => !n.classList.contains('guide-author-form')); a.requestSubmit(); r.requestSubmit()")
        wait_for(author, "document.body.innerText.includes('Disposition draft through refreshes')")
        wait_for(author, "document.body.innerText.includes('Reply draft through refreshes')")

        # A row of a row-anchored table takes its own comment, shown in a
        # full-width row beneath it, and has its own review flag button.
        wait_for(author, "document.querySelector('tr#fx-2.guide-block > td:last-child > .guide-comment-button') !== null")
        wait_for(author, "document.querySelector('tr#fx-2 > td:last-child > .guide-flag-button') !== null")
        evaluate(author, "document.querySelector('tr#fx-2 > td:last-child > .guide-comment-button').click()")
        wait_for(author, "document.querySelector('tr#fx-2 + tr.guide-row-extra .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('tr#fx-2 + tr.guide-row-extra .guide-comment-form'); f.querySelector('textarea').value='Row comment'; f.requestSubmit()")
        wait_for(author, "Array.from(document.querySelectorAll('tr#fx-2 + tr.guide-row-extra .guide-comment__text')).some(n => n.textContent.includes('Row comment'))")
        if not evaluate(author, "!document.querySelector('tr#fx-1 + tr.guide-row-extra') || getComputedStyle(document.querySelector('tr#fx-1 + tr.guide-row-extra')).display === 'none'"):
            raise RuntimeError("An empty comment row was shown under a row without comments.")

        # A response that is not the hub's JSON, as from a firewall in front of it,
        # is reported as such. The text stays in the form and survives a reload.
        evaluate(author, "document.querySelector('tr#fx-1 > td:last-child > .guide-comment-button').click()")
        wait_for(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form'); var n=f.querySelector('textarea'); n.value='Long draft TEST-FIREWALL-BLOCK'; n.dispatchEvent(new Event('input')); f.requestSubmit()")
        wait_for(author, "(document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-form-error')||{}).textContent.includes('stopped before it reached InteropHub (HTTP 403')")
        if not evaluate(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form textarea').value==='Long draft TEST-FIREWALL-BLOCK'"):
            raise RuntimeError("A blocked comment's text was not kept in the form.")
        evaluate(author, "location.reload()")
        wait_for(author, "document.body.innerText.includes('Row comment') && document.querySelector('tr#fx-1 > td:last-child > .guide-comment-button') !== null")
        evaluate(author, "document.querySelector('tr#fx-1 > td:last-child > .guide-comment-button').click()")
        wait_for(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-form-draft') !== null")
        if not evaluate(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form textarea').value==='Long draft TEST-FIREWALL-BLOCK'"):
            raise RuntimeError("An unsaved comment draft was not restored after a reload.")
        evaluate(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-form-draft button').click()")
        if not evaluate(author, "document.querySelector('tr#fx-1 + tr.guide-row-extra .guide-comment-form textarea').value==='' && !Object.keys(localStorage).some(k => k.startsWith('content-guide-draft:'))"):
            raise RuntimeError("Discarding a draft did not clear it.")

        # Review flags: an author flags an area from the flag button beside the
        # comment button. The area gets a purple marker and bar instead of a
        # highlight, the section link gets a dot, and the panel lists the flags.
        evaluate(author, "document.querySelector('p[data-anchor=\"review-item\"] > .guide-flag-button').click()")
        wait_for(author, "document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('p[data-anchor=\"review-item\"] > .guide-comment-form'); f.querySelector('textarea').value='Please check this area'; f.requestSubmit()")
        wait_for(author, "document.querySelector('.guide-flag-marker:not(.guide-flag-marker--row)') !== null")
        if not evaluate(author, "var m=document.querySelector('.guide-flag-marker:not(.guide-flag-marker--row)'); m.nextElementSibling.dataset.anchor==='review-item' && m.textContent.includes('Please check this area') && document.querySelectorAll('[data-anchor=\"review-item\"].guide-review-flagged').length===document.querySelectorAll('[data-anchor=\"review-item\"]').length && document.querySelectorAll('.guide-review-flagged--continued').length>=1 && document.querySelector('.guide-nav-flagged') !== null"):
            raise RuntimeError("A flagged area did not get its marker, bar, or section dot.")
        evaluate(author, "document.querySelector('tr#fx-2 > td:last-child > .guide-flag-button').click()")
        wait_for(author, "document.querySelector('tr#fx-2 + tr.guide-row-extra .guide-comment-form textarea') !== null")
        evaluate(author, "var f=document.querySelector('tr#fx-2 + tr.guide-row-extra .guide-comment-form'); f.querySelector('textarea').value='Row needs a decision'; f.requestSubmit()")
        wait_for(author, "document.querySelector('tr#fx-2.guide-review-flagged > td:first-child > .guide-flag-marker--row') !== null")
        wait_for(author, "(document.querySelector('.guide-review-flag-heading')||{}).textContent==='Review flags (2)'")
        if args.screenshots:
            import base64, os
            os.makedirs(args.screenshots, exist_ok=True)
            author.send("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            for name, selector in (("flag-area", ".guide-flag-marker:not(.guide-flag-marker--row)"), ("flag-row", "tr#fx-2")):
                evaluate(author, "document.querySelector(%s).scrollIntoView({block:'center'}); document.querySelector(%s).querySelector('.guide-flag-badge') && document.querySelector(%s).querySelector('.guide-flag-badge').click()" % ((json.dumps(selector),) * 3))
                time.sleep(.5)
                shot = author.send("Page.captureScreenshot", {"format": "png"})
                with open(os.path.join(args.screenshots, name + ".png"), "wb") as handle: handle.write(base64.b64decode(shot["result"]["data"]))
                evaluate(author, "document.querySelectorAll('.guide-flag-marker.is-open .guide-flag-badge').forEach(b => b.click())")

        reader = open_profile(9224, "ihg_browser_reader", {"userId": 10, "displayName": "Test Reader", "organization": "Example Organization"}, False)
        wait_for(reader, "document.body.innerText.includes('Disposition draft through refreshes')")
        if evaluate(reader, "Array.from(document.querySelectorAll('.guide-comment__tools button')).some(b => ['Dispose','Close','Delete','Re-attach'].includes(b.textContent))"):
            raise RuntimeError("Reader profile was shown author controls.")
        wait_for(reader, "document.querySelectorAll('.guide-flag-marker').length === 2")
        if evaluate(reader, "document.querySelector('.guide-flag-button') !== null || document.querySelector('.guide-flag-popover button') !== null || document.querySelector('.guide-review-flag-entry button') !== null"):
            raise RuntimeError("Reader profile was shown review flag controls.")

        # The author clears a flag from its marker.
        evaluate(author, "document.querySelector('tr#fx-2 .guide-flag-badge').click()")
        wait_for(author, "document.querySelector('tr#fx-2 .guide-flag-marker.is-open') !== null")
        evaluate(author, "Array.from(document.querySelectorAll('tr#fx-2 .guide-flag-popover button')).find(b => b.textContent==='Clear').click()")
        wait_for(author, "document.querySelector('tr#fx-2 .guide-flag-marker') === null && !document.querySelector('tr#fx-2').classList.contains('guide-review-flagged')")
        wait_for(author, "(document.querySelector('.guide-review-flag-heading')||{}).textContent==='Review flags (1)'")
        print("Two-profile browser comments, refresh-safe drafts, blocked-request drafts, review flags, author disposition, and reader visibility check passed.")
    finally:
        for process in processes: process.terminate()
        for process in processes:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
        for profile in profiles: profile.cleanup()
        static.shutdown(); hub.shutdown(); static.server_close(); hub.server_close()


if __name__ == "__main__": main()
