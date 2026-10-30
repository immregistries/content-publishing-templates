import base64
import hashlib
import json
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

import mock_hub


ORIGIN = "http://127.0.0.1:8765"
VERIFIER = "A" * 64


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class MockHubTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = mock_hub.serve(0, [ORIGIN])
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def request(self, path, method="GET", body=None, token=None, origin=ORIGIN):
        headers = {}
        if origin is not None: headers["Origin"] = origin
        if token: headers["Authorization"] = "Bearer " + token
        data = None
        if body is not None: data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(req)
            raw = response.read(); return response.status, dict(response.headers), json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raw = error.read(); return error.code, dict(error.headers), json.loads(raw) if raw else None

    def code(self, verifier=VERIFIER):
        digest = hashlib.sha256(verifier.encode()).digest()
        value = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        query = urllib.parse.urlencode({"app_code": "topic-reference", "return_to": ORIGIN + "/guide/", "state": "state", "code_challenge": value, "code_challenge_method": "S256", "response_mode": "fragment", "requested_url": ORIGIN + "/guide/"})
        opener = urllib.request.build_opener(NoRedirect)
        try: opener.open(self.base + "/home?" + query)
        except urllib.error.HTTPError as error: location = error.headers["Location"]
        return urllib.parse.parse_qs(urllib.parse.urlparse(location).fragment)["code"][0]

    def exchange(self, code=None, verifier=VERIFIER, return_to=ORIGIN + "/guide/", origin=ORIGIN):
        return self.request("/api/guide/token", "POST", {"code": code or self.code(verifier), "codeVerifier": verifier, "returnTo": return_to}, origin=origin)

    def token(self):
        status, _, body = self.exchange(); self.assertEqual(200, status); return body["accessToken"]

    def test_pkce_success_and_failures(self):
        status, _, body = self.exchange(); self.assertEqual(200, status); self.assertTrue(body["accessToken"].startswith("ihg_"))
        for body in (
            {"code": "missing", "codeVerifier": VERIFIER, "returnTo": ORIGIN + "/guide/"},
            {"code": self.code(), "codeVerifier": "B" * 64, "returnTo": ORIGIN + "/guide/"},
            {"code": self.code(), "codeVerifier": VERIFIER, "returnTo": ORIGIN + "/wrong/"},
        ):
            status, _, result = self.request("/api/guide/token", "POST", body)
            self.assertEqual((400, "invalid_request", "Sign-in code is invalid or expired."), (status, result["error"], result["message"]))
        reused = self.code(); self.assertEqual(200, self.exchange(reused)[0]); self.assertEqual(400, self.exchange(reused)[0])
        refused = self.code()
        status, headers, result = self.exchange(refused, origin="https://not-allowed.example")
        self.assertEqual((403, "forbidden"), (status, result["error"]))
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(200, self.exchange(refused)[0])

    def test_cors_allowed_and_refused(self):
        status, headers, _ = self.request("/api/guide/document", token=self.token())
        self.assertEqual(200, status); self.assertEqual(ORIGIN, headers["Access-Control-Allow-Origin"])
        status, headers, body = self.request("/api/guide/document", token=self.token(), origin="https://not-allowed.example")
        self.assertEqual(403, status); self.assertNotIn("Access-Control-Allow-Origin", headers); self.assertEqual("forbidden", body["error"])
        status, headers, _ = self.request("/api/guide/document", "OPTIONS")
        self.assertEqual(204, status); self.assertEqual("GET, POST, PATCH, DELETE", headers["Access-Control-Allow-Methods"])

    def add(self, token, text="A comment"):
        status, _, body = self.request("/api/guide/document/comments", "POST", {"anchor": "document-start", "blockIndex": 0, "snippet": "Fixture", "text": text}, token)
        self.assertEqual(201, status); return body

    def test_since_tombstone(self):
        token = self.token(); item = self.add(token)
        _, _, listing = self.request("/api/guide/document/comments", token=token); since = listing["serverTime"]
        self.request("/test/delete?id=%s" % item["id"], origin=None)
        _, _, changes = self.request("/api/guide/document/comments?since=" + urllib.parse.quote(since), token=token)
        self.assertTrue(any(value["id"] == item["id"] and value["deleted"] for value in changes["comments"]))

    def test_edit_window_and_reply_to_reply(self):
        token = self.token(); top = self.add(token)
        status, _, top = self.request("/api/guide/document/comments", "POST", {"parentCommentId": top["id"], "text": "Reply"}, token)
        self.assertEqual(201, status); reply_id = top["replies"][0]["id"]
        status, _, body = self.request("/api/guide/document/comments", "POST", {"parentCommentId": reply_id, "text": "Nested"}, token)
        self.assertEqual((400, "parentCommentId"), (status, body["field"]))
        self.request("/test/expire?id=%s" % top["id"], origin=None)
        status, _, body = self.request("/api/guide/comments/%s" % top["id"], "PATCH", {"text": "Too late"}, token)
        self.assertEqual((403, "edit_window_closed"), (status, body["error"]))


if __name__ == "__main__":
    unittest.main()
