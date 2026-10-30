"""Small in-memory comments API used by the guide validation suite."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


class State:
    def __init__(self, origins):
        self.origins = set(origins)
        self.codes, self.tokens, self.comments = {}, {}, {}
        self.next_id = 1
        self.can_view, self.active = True, True
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "GuideMock/1"

    @property
    def state(self):
        return self.server.state

    def log_message(self, *args):
        pass

    def cors(self):
        origin = self.headers.get("Origin")
        if origin and origin in self.state.origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Expose-Headers", "WWW-Authenticate")
            return True
        return not origin

    def json(self, status, value, extra=None):
        origin = self.headers.get("Origin")
        if origin and origin not in self.state.origins and status < 400:
            status = 403
            value = {"error": "forbidden", "message": "This origin is not allowed."}
        payload = json.dumps(value).encode()
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for key, val in (extra or {}).items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(payload)

    def empty(self, status=204):
        self.send_response(status); self.cors(); self.end_headers()

    def error(self, status, code, message, field=None):
        body = {"error": code, "message": message}
        if field: body["field"] = field
        extra = {"WWW-Authenticate": 'Bearer realm="interophub", error="invalid_token"'} if status == 401 else None
        self.json(status, body, extra)

    def body(self):
        try:
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except (ValueError, json.JSONDecodeError):
            return None

    def refuse_origin(self):
        origin = self.headers.get("Origin")
        if origin and origin not in self.state.origins:
            self.error(403, "forbidden", "This origin is not allowed.")
            return True
        return False

    def user(self):
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        record = self.state.tokens.get(token)
        if not record or record.get("revoked"):
            self.error(401, "invalid_token", "The access token is invalid or expired.")
            return None
        return record["user"]

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if origin not in self.state.origins:
            self.empty(403); return
        self.send_response(204); self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "600"); self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/home":
            q = parse_qs(parsed.query)
            required = all(q.get(k) for k in ("return_to", "state", "code_challenge"))
            if not required or q.get("code_challenge_method") != ["S256"] or q.get("response_mode") != ["fragment"] or urlparse(q["return_to"][0]).fragment:
                self.error(400, "invalid_request", "The sign-in request is invalid."); return
            code = secrets.token_urlsafe(24)
            user_name = q.get("user", ["Test Reader"])[0]
            self.state.codes[code] = {"challenge": q["code_challenge"][0], "returnTo": q["return_to"][0], "user": {"userId": 1 if user_name == "Test Reader" else 2, "displayName": user_name, "organization": "Example Organization"}}
            location = q["return_to"][0] + "#" + urlencode({"code": code, "state": q["state"][0]})
            self.send_response(302); self.send_header("Location", location); self.end_headers(); return
        if parsed.path.startswith("/test/"):
            self.test_control(parsed); return
        if self.refuse_origin(): return
        user = self.user()
        if not user: return
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "guide"]:
            self.json(200, {"documentKey": parts[2], "title": "Fixture guide", "isActive": self.state.active, "topic": {} if self.state.can_view else None, "permissions": {"canView": self.state.can_view, "canComment": self.state.can_view and self.state.active, "isAuthor": False}, "user": user, "dispositions": [], "editWindowDays": 14, "serverTime": now()}); return
        if len(parts) == 4 and parts[:2] == ["api", "guide"] and parts[3] == "comments":
            if not self.state.can_view: self.error(403, "forbidden", "This account cannot view comments."); return
            since = parse_qs(parsed.query).get("since", [None])[0]
            values = []
            for item in self.state.comments.values():
                if since and item["updatedAt"] >= since: values.append(self.thread(item, user, tombstones=True))
                elif not since and not item.get("deleted") and item.get("state") not in ("CLOSED", "WITHDRAWN"): values.append(self.thread(item, user))
            self.json(200, {"serverTime": now(), "comments": values, "reviewFlags": []}); return
        self.error(404, "not_found", "Not found.")

    def do_POST(self):
        parsed = urlparse(self.path); payload = self.body() or {}
        if parsed.path == "/api/guide/token":
            if self.refuse_origin(): return
            record = self.state.codes.get(payload.get("code"))
            valid = record and not record.get("used") and payload.get("returnTo") == record["returnTo"] and challenge(payload.get("codeVerifier", "")) == record["challenge"]
            if not valid: self.error(400, "invalid_request", "Sign-in code is invalid or expired."); return
            record["used"] = True; token = "ihg_" + secrets.token_urlsafe(32)[:43]
            expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            self.state.tokens[token] = {"user": record["user"]}
            self.json(200, {"accessToken": token, "tokenType": "Bearer", "expiresAt": expires, "scopes": ["comments"], "user": record["user"]}); return
        if self.refuse_origin(): return
        user = self.user()
        if not user: return
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "guide"] and parts[3] == "comments":
            if not self.state.active: self.error(409, "document_inactive", "This document is not accepting comments."); return
            text = str(payload.get("text", "")).strip()
            if not text or len(text) > 4000: self.error(400, "invalid_field", "Comment text must be between 1 and 4,000 characters.", "text"); return
            parent_id = payload.get("parentCommentId")
            if parent_id:
                parent = self.state.comments.get(parent_id)
                if not parent:
                    for top in self.state.comments.values():
                        if any(reply["id"] == parent_id for reply in top["replies"]): self.error(400, "invalid_field", "Replies cannot have replies.", "parentCommentId"); return
                    self.error(404, "not_found", "Comment not found."); return
                if parent["state"] in ("CLOSED", "WITHDRAWN") or parent.get("deleted"): self.error(409, "invalid_state", "This thread cannot receive replies."); return
                item = self.new_item(text, user, parent_id); parent["replies"].append(item); parent["updatedAt"] = item["updatedAt"]; self.json(201, self.thread(parent, user)); return
            anchor = payload.get("anchor")
            if not anchor or not isinstance(payload.get("blockIndex"), int): self.error(400, "invalid_field", "An anchor and block index are required.", "anchor"); return
            item = self.new_item(text, user); item.update({"documentKey": parts[2], "anchor": anchor, "blockIndex": payload["blockIndex"], "snippet": payload.get("snippet"), "state": "OPEN", "replies": []})
            self.state.comments[item["id"]] = item; self.json(201, self.thread(item, user)); return
        if len(parts) == 5 and parts[:3] == ["api", "guide", "comments"] and parts[4] == "withdraw":
            found, top = self.find(int(parts[3]));
            if not found: self.error(404, "not_found", "Comment not found."); return
            if found["author"]["userId"] != user["userId"] or self.expired(found): self.error(403, "edit_window_closed", "The edit window has closed."); return
            found["text"] = None; found["updatedAt"] = now()
            if found is top: found["state"] = "WITHDRAWN"
            else: found["withdrawn"] = True; top["updatedAt"] = found["updatedAt"]
            self.json(200, self.thread(top, user)); return
        self.error(404, "not_found", "Not found.")

    def do_PATCH(self):
        if self.refuse_origin(): return
        user = self.user()
        if not user: return
        parts = urlparse(self.path).path.strip("/").split("/"); payload = self.body() or {}
        if len(parts) != 4 or parts[:3] != ["api", "guide", "comments"]: self.error(404, "not_found", "Not found."); return
        found, top = self.find(int(parts[3]))
        if not found: self.error(404, "not_found", "Comment not found."); return
        if set(payload) - {"text", "expectedUpdatedAt"}: self.error(400, "invalid_field", "This field cannot be changed here.", next(iter(set(payload) - {"text", "expectedUpdatedAt"}))); return
        if found["author"]["userId"] != user["userId"]: self.error(403, "forbidden", "Only the commenter can edit this text."); return
        if self.expired(found): self.error(403, "edit_window_closed", "The edit window has closed."); return
        text = str(payload.get("text", "")).strip()
        if not text: self.error(400, "invalid_field", "Comment text is required.", "text"); return
        found["text"], found["editedAt"], found["updatedAt"] = text, now(), now(); top["updatedAt"] = found["updatedAt"]
        self.json(200, self.thread(top, user))

    def do_DELETE(self):
        if self.refuse_origin(): return
        if self.path == "/api/guide/token":
            auth = self.headers.get("Authorization", ""); token = auth[7:] if auth.startswith("Bearer ") else ""
            if token not in self.state.tokens or self.state.tokens[token].get("revoked"): self.error(401, "invalid_token", "The access token is invalid or expired."); return
            self.state.tokens[token]["revoked"] = True; self.empty(); return
        self.error(404, "not_found", "Not found.")

    def new_item(self, text, user, parent=None):
        identifier = self.state.next_id; self.state.next_id += 1; stamp = now()
        return {"id": identifier, "parentId": parent, "text": text, "author": user, "createdAt": stamp, "editedAt": None, "editableUntil": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(timespec="milliseconds").replace("+00:00", "Z"), "updatedAt": stamp, "withdrawn": False, "deleted": False}

    def expired(self, item):
        return datetime.fromisoformat(item["editableUntil"].replace("Z", "+00:00")) < datetime.now(timezone.utc)

    def find(self, identifier):
        for top in self.state.comments.values():
            if top["id"] == identifier: return top, top
            for reply in top["replies"]:
                if reply["id"] == identifier: return reply, top
        return None, None

    def thread(self, item, user, tombstones=False):
        if item.get("deleted") and tombstones: return {"id": item["id"], "deleted": True, "updatedAt": item["updatedAt"]}
        result = dict(item); own = item["author"]["userId"] == user["userId"] and not self.expired(item) and item["state"] in ("OPEN", "DISPOSED"); result["permissions"] = {"canEdit": own, "canWithdraw": own, "canReply": item["state"] in ("OPEN", "DISPOSED")}
        result["replies"] = []
        for reply in item["replies"]:
            if reply.get("deleted") and not tombstones: continue
            copy = dict(reply); own_reply = reply["author"]["userId"] == user["userId"] and not self.expired(reply) and not reply.get("withdrawn") and item["state"] in ("OPEN", "DISPOSED"); copy["permissions"] = {"canEdit": own_reply, "canWithdraw": own_reply}; result["replies"].append(copy)
        return result

    def test_control(self, parsed):
        q = parse_qs(parsed.query); action = parsed.path.rsplit("/", 1)[-1]
        if action == "revoke":
            token = q.get("token", [""])[0]
            if token in self.state.tokens: self.state.tokens[token]["revoked"] = True
        elif action in ("delete", "close"):
            item, top = self.find(int(q.get("id", ["0"])[0]))
            if item:
                if action == "delete": item["deleted"] = True
                else: top["state"] = "CLOSED"
                top["updatedAt"] = now()
        elif action == "expire":
            item, _ = self.find(int(q.get("id", ["0"])[0]))
            if item: item["editableUntil"] = "2000-01-01T00:00:00.000Z"
        elif action == "can-view": self.state.can_view = q.get("value", ["true"])[0] == "true"
        self.json(200, {"ok": True})


def serve(port=0, origins=None):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.state = State(origins or ["http://127.0.0.1:8765"])
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--allow-origin", action="append", default=[])
    args = parser.parse_args()
    server = serve(args.port, args.allow_origin or None)
    print(f"Mock comments service listening on http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()
