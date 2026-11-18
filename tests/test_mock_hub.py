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
            try:
                raw = error.read(); return error.code, dict(error.headers), json.loads(raw) if raw else None
            finally:
                error.close()

    def code(self, verifier=VERIFIER):
        digest = hashlib.sha256(verifier.encode()).digest()
        value = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        query = urllib.parse.urlencode({"app_code": "topic-reference", "return_to": ORIGIN + "/guide/", "state": "state", "code_challenge": value, "code_challenge_method": "S256", "response_mode": "fragment", "requested_url": ORIGIN + "/guide/"})
        opener = urllib.request.build_opener(NoRedirect)
        try: opener.open(self.base + "/home?" + query)
        except urllib.error.HTTPError as error:
            try: location = error.headers["Location"]
            finally: error.close()
        return urllib.parse.parse_qs(urllib.parse.urlparse(location).fragment)["code"][0]

    def exchange(self, code=None, verifier=VERIFIER, return_to=ORIGIN + "/guide/", origin=ORIGIN):
        return self.request("/api/guide/token", "POST", {"code": code or self.code(verifier), "codeVerifier": verifier, "returnTo": return_to}, origin=origin)

    def token(self):
        status, _, body = self.exchange(); self.assertEqual(200, status); return body["accessToken"]

    def author_token(self):
        code = self.code_for("Test Author")
        status, _, body = self.exchange(code)
        self.assertEqual(200, status)
        return body["accessToken"]

    def code_for(self, name):
        digest = hashlib.sha256(VERIFIER.encode()).digest()
        value = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        query = urllib.parse.urlencode({"app_code": "topic-reference", "return_to": ORIGIN + "/guide/", "state": "state", "code_challenge": value, "code_challenge_method": "S256", "response_mode": "fragment", "requested_url": ORIGIN + "/guide/", "user": name})
        opener = urllib.request.build_opener(NoRedirect)
        try: opener.open(self.base + "/home?" + query)
        except urllib.error.HTTPError as error:
            try: location = error.headers["Location"]
            finally: error.close()
        return urllib.parse.parse_qs(urllib.parse.urlparse(location).fragment)["code"][0]

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

    def test_author_state_disposition_conflict_and_state_all(self):
        reader, author = self.token(), self.author_token()
        item = self.add(reader)
        status, _, body = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"dispositionCode": "PERSUASIVE"}, author)
        self.assertEqual((400, "changeNote"), (status, body["field"]))
        status, _, disposed = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"dispositionCode": "PERSUASIVE", "changeNote": "Updated wording.", "expectedUpdatedAt": item["updatedAt"]}, author)
        self.assertEqual((200, "DISPOSED", "Persuasive"), (status, disposed["state"], disposed["disposition"]["label"]))
        status, _, conflict = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"state": "CLOSED", "expectedUpdatedAt": item["updatedAt"]}, author)
        self.assertEqual((409, "conflict", disposed["updatedAt"]), (status, conflict["error"], conflict["current"]["updatedAt"]))
        status, _, closed = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"state": "CLOSED", "expectedUpdatedAt": disposed["updatedAt"]}, author)
        self.assertEqual((200, "CLOSED"), (status, closed["state"]))
        default_ids = [value["id"] for value in self.request("/api/guide/document/comments", token=reader)[2]["comments"]]
        self.assertNotIn(item["id"], default_ids)
        listed = self.request("/api/guide/document/comments?state=all", token=reader)[2]["comments"]
        self.assertEqual("CLOSED", listed[-1]["state"])
        status, _, reopened = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"state": "OPEN", "expectedUpdatedAt": closed["updatedAt"]}, author)
        self.assertEqual("DISPOSED", reopened["state"])
        status, _, cleared = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"dispositionCode": None, "expectedUpdatedAt": reopened["updatedAt"]}, author)
        self.assertEqual((200, "OPEN", None), (status, cleared["state"], cleared["changeNote"]))

    def test_author_delete_reply_and_tombstone(self):
        reader, author = self.token(), self.author_token()
        top = self.add(reader)
        top = self.request("/api/guide/document/comments", "POST", {"parentCommentId": top["id"], "text": "Reply"}, reader)[2]
        reply = top["replies"][0]
        self.assertEqual(204, self.request("/api/guide/comments/%s" % reply["id"], "DELETE", token=author)[0])
        changes = self.request("/api/guide/document/comments?since=2000-01-01T00:00:00.000Z", token=reader)[2]["comments"]
        changed = next(value for value in changes if value["id"] == top["id"])
        self.assertTrue(changed["replies"][0]["deleted"])

    def test_author_permissions_and_reattach(self):
        reader, author = self.token(), self.author_token()
        item = self.add(reader)
        status, _, body = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"anchor": "moved", "blockIndex": 2, "snippet": "Moved text", "expectedUpdatedAt": item["updatedAt"]}, reader)
        self.assertEqual((403, "forbidden"), (status, body["error"]))
        status, _, moved = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"anchor": "moved", "blockIndex": 2, "snippet": "Moved text", "expectedUpdatedAt": item["updatedAt"]}, author)
        self.assertEqual((200, "moved", 2, "Moved text"), (status, moved["anchor"], moved["blockIndex"], moved["snippet"]))
        status, _, body = self.request("/api/guide/comments/%s" % item["id"], "PATCH", {"state": "OPEN", "expectedUpdatedAt": moved["updatedAt"]}, author)
        self.assertEqual((409, "invalid_state"), (status, body["error"]))

    def test_review_flags_replace_and_clear_idempotently(self):
        reader, author = self.token(), self.author_token()
        status, _, flag = self.request("/api/guide/document/review-flags", "POST", {"anchor": "document-start", "note": "Review this."}, author)
        self.assertEqual(201, status)
        status, _, replacement = self.request("/api/guide/document/review-flags", "POST", {"anchor": "document-start", "note": "Review again."}, author)
        self.assertEqual((200, flag["id"], "Review again."), (status, replacement["id"], replacement["note"]))
        self.assertEqual("Review again.", self.request("/api/guide/document/comments", token=reader)[2]["reviewFlags"][-1]["note"])
        path = "/api/guide/document/review-flags/%s" % flag["id"]
        self.assertEqual(204, self.request(path, "DELETE", token=author)[0])
        self.assertEqual(204, self.request(path, "DELETE", token=author)[0])
        self.assertFalse(self.request("/api/guide/document/review-flags", token=reader)[2]["reviewFlags"])

    def test_hosted_versions_create_replace_list_and_permissions(self):
        author, reader = self.author_token(), self.token()
        def upload(document, label, token, value=b"<!DOCTYPE html><title>Guide</title>"):
            request = urllib.request.Request(
                f"{self.base}/api/guide/{document}/versions/{label}", data=value,
                headers={"Authorization": "Bearer " + token, "Content-Type": "text/html"}, method="POST")
            try:
                with urllib.request.urlopen(request) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                try:
                    return error.code, json.load(error)
                finally:
                    error.close()
        status, created = upload("document", "latest", author)
        self.assertEqual((201, "latest", len(b"<!DOCTYPE html><title>Guide</title>")),
                         (status, created["label"], created["sizeBytes"]))
        self.assertEqual(200, upload("document", "latest", author, b"<!doctype html>new")[0])
        self.assertEqual(403, upload("document", "main", reader)[0])
        self.assertEqual((409, "invalid_state"),
                         (lambda result: (result[0], result[1]["error"]))(upload("external", "main", author)))
        listed = self.request("/api/guide/document/versions", token=reader)[2]
        self.assertEqual(["latest"], [item["label"] for item in listed["versions"]])
        latest = listed["versions"][0]
        self.assertEqual((2, "Test Author", 1), (latest["historyCount"], latest["uploadedBy"], len(latest["earlier"])))
        self.assertIsInstance(created["uploadedBy"], str)


class MockTokenEndpointTest(unittest.TestCase):
    """GET /api/token and the help field follow InteropHub's contract (2, 2.1, 3.7)."""

    @classmethod
    def setUpClass(cls):
        cls.server = mock_hub.serve(0)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port
        tokens = cls.server.state.tokens
        tokens["ihp_author"] = {"user": {"userId": 3, "displayName": "Pat Author", "organization": "Example"},
                                "isAuthor": True, "label": "laptop agent"}
        tokens["ihp_reader"] = {"user": {"userId": 4, "displayName": "Lee Reader"}, "isAuthor": False,
                                "scopes": ["topics:read", "comments"]}
        tokens["ihg_guide"] = {"user": {"userId": 4, "displayName": "Lee Reader"}, "isAuthor": False}

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def call(self, method="GET", token=None, path="/api/token"):
        headers = {"Authorization": "Bearer " + token} if token else {}
        request = urllib.request.Request(self.base + path, headers=headers, method=method,
                                         data=b"{}" if method in ("POST", "PATCH") else None)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, dict(response.headers), json.loads(response.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, dict(error.headers), json.loads(error.read())

    def test_a_personal_token_describes_itself(self):
        status, headers, body = self.call(token="ihp_author")
        self.assertEqual((200, "no-store"), (status, headers["Cache-Control"]))
        self.assertEqual({"user", "kind", "label", "scopes", "expiresAt", "expiresInDays", "guides", "help"}, set(body))
        self.assertEqual({"userId": 3, "displayName": "Pat Author"}, body["user"])
        self.assertEqual(("personal", "laptop agent", ["comments", "topics:write"], 90),
                         (body["kind"], body["label"], body["scopes"], body["expiresInDays"]))
        self.assertEqual(["document", "external-document"], [guide["documentKey"] for guide in body["guides"]])
        self.assertEqual(["HUB", "EXTERNAL"], [guide["hosting"] for guide in body["guides"]])
        self.assertTrue(all(guide["active"] and guide["canPublish"] for guide in body["guides"]))
        self.assertEqual(self.base + "/help/topic-reference-authors#if-you-are-an-agent", body["help"])
        self.assertNotIn("ihp_author", json.dumps(body))

    def test_a_reader_and_a_guide_token(self):
        reader = self.call(token="ihp_reader")[2]
        self.assertEqual(([], ["comments", "topics:read"]), (reader["guides"], reader["scopes"]))
        guide = self.call(token="ihg_guide")[2]
        self.assertEqual(("guide", ["comments"], 30), (guide["kind"], guide["scopes"], guide["expiresInDays"]))

    def test_errors_carry_help(self):
        for token in (None, "ihp_unknown"):
            status, headers, body = self.call(token=token)
            self.assertEqual((401, "invalid_token"), (status, body["error"]))
            self.assertIn('error="invalid_token"', headers["WWW-Authenticate"])
            self.assertEqual(self.base + "/help/topic-reference-authors#troubleshooting-invalid_token", body["help"])
        status, headers, body = self.call("POST", "ihp_author")
        self.assertEqual((405, "invalid_request", "GET"), (status, body["error"], headers["Allow"]))
        self.assertTrue(body["help"].endswith("#troubleshooting-invalid_request"))
        status, headers, body = self.call("PATCH", "ihp_reader", "/api/guide/document/labels/latest")
        self.assertEqual((403, "insufficient_scope", "topics:write"), (status, body["error"], body["requiredScope"]))
        self.assertIn('scope="topics:write"', headers["WWW-Authenticate"])
        self.assertTrue(body["help"].endswith("#troubleshooting-insufficient_scope"))
        status, _, body = self.call(token="ihp_author", path="/api/guide/document/nothing-here")
        self.assertEqual((404, self.base + "/help/topic-reference-authors#troubleshooting-not_found"), (status, body["help"]))


if __name__ == "__main__":
    unittest.main()
