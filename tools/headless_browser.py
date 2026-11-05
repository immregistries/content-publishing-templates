"""Drive an installed Chrome or Edge in headless mode (standard library only).

Used to measure rendered text and export PNG and PDF files. The browser is
found from --browser, the CHROME_PATH environment variable, the PATH, or the
usual install locations on Windows, macOS, and Linux.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path


PATH_NAMES = ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
              "msedge", "microsoft-edge", "microsoft-edge-stable"]


def known_locations() -> list[Path]:
    program_files = [os.environ.get(name) for name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    windows = [
        Path(base) / product
        for base in program_files if base
        for product in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe")
    ]
    return windows + [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ]


def find_browser(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    for name in PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for path in known_locations():
        if path.is_file():
            return str(path)
    return None


class BrowserError(RuntimeError):
    pass


class _WebSocket:
    def __init__(self, url: str):
        parsed = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\n"
                   "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise BrowserError("DevTools connection closed during the handshake")
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise BrowserError("DevTools WebSocket connection failed")
        self.ident = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.ident += 1
        ident = self.ident
        payload = json.dumps({"id": ident, "method": method, "params": params or {}}).encode()
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", length)
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(bytes(header) + bytes(value ^ mask[i % 4] for i, value in enumerate(payload)))
        while True:
            message = self._receive()
            if message.get("id") == ident:
                if "error" in message:
                    raise BrowserError(f"{method} failed: {message['error'].get('message')}")
                return message.get("result", {})

    def _receive(self) -> dict:
        data = b""
        while True:
            first = self._read(2)
            length = first[1] & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if first[1] & 0x80 else None
            payload = self._read(length)
            if mask:
                payload = bytes(value ^ mask[i % 4] for i, value in enumerate(payload))
            opcode = first[0] & 0x0F
            if opcode in (0x1, 0x0):
                data += payload
                if first[0] & 0x80:
                    return json.loads(data)
            elif opcode == 0x8:
                raise BrowserError("DevTools connection closed")

    def _read(self, count: int) -> bytes:
        chunks = []
        while count:
            chunk = self.sock.recv(min(count, 1 << 20))
            if not chunk:
                raise BrowserError("DevTools connection closed")
            chunks.append(chunk)
            count -= len(chunk)
        return b"".join(chunks)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class HeadlessBrowser:
    """A headless browser with one page, used as a context manager."""

    def __init__(self, executable: str):
        self.executable = executable
        self.profile = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.process: subprocess.Popen | None = None
        self.page: _WebSocket | None = None

    def __enter__(self) -> "HeadlessBrowser":
        command = [self.executable, "--headless", "--disable-gpu", "--no-first-run",
                   "--no-default-browser-check", "--hide-scrollbars", "--mute-audio",
                   "--font-render-hinting=none", "--remote-allow-origins=*",
                   "--remote-debugging-port=0", f"--user-data-dir={self.profile.name}", "about:blank"]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            command.insert(1, "--no-sandbox")
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error:
            raise BrowserError(f"Could not start {self.executable}: {error}") from error
        port_file = Path(self.profile.name) / "DevToolsActivePort"
        deadline = time.time() + 30
        while not port_file.is_file() or not port_file.read_text().strip():
            if self.process.poll() is not None or time.time() > deadline:
                self.__exit__(None, None, None)
                raise BrowserError(f"{self.executable} did not start its DevTools endpoint")
            time.sleep(0.1)
        port = int(port_file.read_text().split()[0])
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10))
        page = next((target for target in targets if target.get("type") == "page"), None)
        if page is None:
            request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
            page = json.load(urllib.request.urlopen(request, timeout=10))
        self.page = _WebSocket(page["webSocketDebuggerUrl"])
        return self

    def __exit__(self, *exc) -> None:
        if self.page:
            self.page.close()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.profile.cleanup()

    def open(self, path: Path, width: int, height: int, scale: float = 1) -> None:
        self.page.call("Emulation.setDeviceMetricsOverride",
                       {"width": width, "height": height, "deviceScaleFactor": scale, "mobile": False})
        self.page.call("Page.navigate", {"url": path.resolve().as_uri()})
        deadline = time.time() + 30
        while self.evaluate("document.readyState") != "complete":
            if time.time() > deadline:
                raise BrowserError(f"Timed out loading {path}")
            time.sleep(0.05)
        self.evaluate("document.fonts.ready.then(() => true)", wait=True)

    def evaluate(self, expression: str, wait: bool = False):
        result = self.page.call("Runtime.evaluate",
                                {"expression": expression, "returnByValue": True, "awaitPromise": wait})
        if "exceptionDetails" in result:
            raise BrowserError(f"Script failed: {result['exceptionDetails'].get('text')}")
        return result.get("result", {}).get("value")

    def screenshot(self, width: int, height: int) -> bytes:
        """PNG of the top-left area, at the device scale given to open()."""
        result = self.page.call("Page.captureScreenshot", {
            "format": "png", "fromSurface": True,
            "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
        })
        return base64.b64decode(result["data"])

    def pdf(self, width: int, height: int) -> bytes:
        result = self.page.call("Page.printToPDF", {
            "printBackground": True, "preferCSSPageSize": True,
            "paperWidth": width / 96, "paperHeight": height / 96,
            "marginTop": 0, "marginBottom": 0, "marginLeft": 0, "marginRight": 0,
        })
        return base64.b64decode(result["data"])
