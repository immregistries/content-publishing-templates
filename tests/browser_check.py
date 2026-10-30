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

import mock_hub


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
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
    static = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), lambda *values, **kw: Quiet(*values, directory=args.root, **kw))
    hub = mock_hub.serve(8766, ["http://127.0.0.1:8765"])
    for server in (static, hub): threading.Thread(target=server.serve_forever, daemon=True).start()
    profile = tempfile.TemporaryDirectory()
    command = [args.browser, "--headless", "--disable-gpu", "--disable-gpu-sandbox", "--disable-software-rasterizer", "--no-sandbox", "--no-first-run", "--dump-dom", "--virtual-time-budget=5000", "--user-data-dir=" + profile.name, "http://127.0.0.1:8765/output/guide/index.html?interophub=signin"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
        if result.returncode or "Signed in as Test Reader" not in result.stdout:
            raise RuntimeError("The headless browser did not complete the guide sign-in round trip. " + result.stderr[-1000:] + result.stdout[-1000:])
        # Exercise one write against the same service after the browser round trip.
        user = {"userId": 99, "displayName": "Browser Check", "organization": "Example Organization"}
        hub.state.tokens["ihg_browser_check"] = {"user": user}
        import urllib.request
        request = urllib.request.Request("http://127.0.0.1:8766/api/guide/example-core-document/comments", data=json.dumps({"anchor": "document-start", "blockIndex": 0, "snippet": "Fixture", "text": "Browser smoke comment"}).encode(), headers={"Origin": "http://127.0.0.1:8765", "Authorization": "Bearer ihg_browser_check", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request) as response:
            if response.status != 201: raise RuntimeError("The browser smoke comment was not accepted.")
        print("Headless browser sign-in and comment post passed.")
    finally:
        static.shutdown(); hub.shutdown(); static.server_close(); hub.server_close(); profile.cleanup()


if __name__ == "__main__": main()
