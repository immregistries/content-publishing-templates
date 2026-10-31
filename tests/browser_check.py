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

        reader = open_profile(9224, "ihg_browser_reader", {"userId": 10, "displayName": "Test Reader", "organization": "Example Organization"}, False)
        wait_for(reader, "document.body.innerText.includes('Browser disposition note')")
        if evaluate(reader, "Array.from(document.querySelectorAll('.guide-comment__tools button')).some(b => ['Dispose','Close','Delete','Re-attach'].includes(b.textContent))"):
            raise RuntimeError("Reader profile was shown author controls.")
        print("Two-profile browser comment post, author disposition, and reader visibility check passed.")
    finally:
        for process in processes: process.terminate()
        for process in processes:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
        for profile in profiles: profile.cleanup()
        static.shutdown(); hub.shutdown(); static.server_close(); hub.server_close()


if __name__ == "__main__": main()
