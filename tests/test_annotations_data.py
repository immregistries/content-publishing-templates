"""The data the annotations panel relies on: the mock hub's "mine" and cleared
flags, and the sample change-marker element (sample_change_markers.py)."""

import json
import re
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

import mock_hub
import sample_change_markers


ORIGIN = "http://127.0.0.1:8765"


class MockHubAnnotationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = mock_hub.serve(0, [ORIGIN])
        mock_hub.seed_demo(cls.server.state)
        cls.server.state.tokens["reader"] = {"user": mock_hub.READER, "isAuthor": False}
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def get(self, path):
        request = urllib.request.Request(self.base + path, headers={"Origin": ORIGIN, "Authorization": "Bearer reader"})
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    def test_mine_marks_the_callers_threads_and_replies(self):
        threads = self.get("/api/guide/example-core-document/comments")["comments"]
        by_text = {thread["text"][:20]: thread for thread in threads}
        own = next(thread for text, thread in by_text.items() if text.startswith("Does"))
        other = next(thread for text, thread in by_text.items() if text.startswith("Our program"))
        self.assertTrue(own["mine"])
        self.assertFalse(own["replies"][0]["mine"])
        self.assertFalse(other["mine"])
        self.assertTrue(other["replies"][0]["mine"])

    def test_cleared_flags_only_when_asked(self):
        active = self.get("/api/guide/example-core-document/review-flags")["reviewFlags"]
        every = self.get("/api/guide/example-core-document/review-flags?includeCleared=true")["reviewFlags"]
        self.assertTrue(all(flag["clearedAt"] is None for flag in active))
        self.assertGreater(len(every), len(active))
        self.assertTrue(any(flag["clearedAt"] for flag in every))


class MockHubLabelsTest(unittest.TestCase):
    """The mock follows the contract's label rules (5.3.1, 5.4.1, 7.5)."""
    SITE = "http://127.0.0.1:8765"

    def setUp(self):
        self.server = mock_hub.serve(0, [ORIGIN])
        mock_hub.seed_demo(self.server.state, self.SITE)
        self.server.state.tokens["reader"] = {"user": mock_hub.READER, "isAuthor": False}
        self.server.state.tokens["author"] = {"user": mock_hub.AUTHOR, "isAuthor": True}
        self.base = "http://127.0.0.1:%d" % self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()

    def call(self, path, token="reader", method="GET", body=None):
        headers = {"Origin": ORIGIN, "Authorization": "Bearer " + token}
        data = None
        if body is not None:
            data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.load(error)

    def page(self, name):
        return urllib.parse.quote(self.SITE + "/output/" + name + "/index.html?lens=comments#x", safe="")

    def comments(self, name, token="reader", extra=""):
        return self.call("/api/guide/example-core-document/comments?pageUrl=" + self.page(name) + extra, token)[1]

    def texts(self, result):
        return {thread["text"][:12]: thread.get("inScope") for thread in result["comments"]}

    def test_release_filters_readers_and_marks_for_authors(self):
        reader = self.comments("release")
        self.assertEqual({"label": "v0.2.0", "display": "current", "commentMode": "release"},
                         {k: reader["labelPolicy"][k] for k in ("label", "display", "commentMode")})
        self.assertNotIn("Our program ", self.texts(reader))
        self.assertTrue(all(self.texts(reader).values()))
        author = self.comments("release", "author")
        self.assertIs(False, self.texts(author)["Our program "])
        self.assertIs(True, self.texts(author)["Status shoul"])
        since = self.comments("release", extra="&since=2000-01-01T00:00:00.000Z")
        self.assertNotIn("Our program ", self.texts(since))

    def test_open_shows_everything_in_scope(self):
        for token in ("reader", "author"):
            result = self.comments("guide", token)
            self.assertEqual(("main", "open"), (result["labelPolicy"]["label"], result["labelPolicy"]["commentMode"]))
            self.assertIn("Our program ", self.texts(result))
            self.assertTrue(all(self.texts(result).values()))
            self.assertTrue(all(flag["inScope"] for flag in result["reviewFlags"]))

    def test_closed_shows_nothing_and_refuses_writes(self):
        for token in ("reader", "author"):
            result = self.comments("closed", token)
            self.assertEqual(([], [], "closed"), (result["comments"], result["reviewFlags"], result["labelPolicy"]["commentMode"]))
        closed = self.SITE + "/output/closed/index.html"
        top = {"anchor": "review-item", "blockIndex": 0, "text": "Hello", "pageUrl": closed}
        self.assertEqual((403, "comments_closed"), (lambda r: (r[0], r[1]["error"]))(self.call("/api/guide/example-core-document/comments", method="POST", body=top)))
        reply = {"parentCommentId": 1, "text": "Hello", "pageUrl": closed}
        self.assertEqual(403, self.call("/api/guide/example-core-document/comments", method="POST", body=reply)[0])
        flag = {"anchor": "review-item", "note": "Look", "pageUrl": closed}
        self.assertEqual(403, self.call("/api/guide/example-core-document/review-flags", "author", "POST", flag)[0])

    def test_writes_record_the_label(self):
        status, thread = self.call("/api/guide/example-core-document/comments", method="POST", body={
            "anchor": "review-item", "blockIndex": 0, "text": "Hello", "pageUrl": self.SITE + "/output/release/?a=1#b"})
        self.assertEqual((201, "v0.2.0"), (status, thread["madeOnLabel"]))
        status, thread = self.call("/api/guide/example-core-document/comments", method="POST", body={
            "parentCommentId": thread["id"], "text": "Reply", "pageUrl": self.SITE.upper().replace("HTTP", "http") + "/output/guide/"})
        self.assertEqual("main", thread["replies"][-1]["madeOnLabel"])
        status, thread = self.call("/api/guide/example-core-document/comments", method="POST", body={
            "anchor": "review-item", "blockIndex": 0, "text": "Old guide"})
        self.assertIsNone(thread["madeOnLabel"])
        self.assertEqual((400, "pageUrl"), (lambda r: (r[0], r[1].get("field")))(self.call(
            "/api/guide/example-core-document/comments", method="POST",
            body={"anchor": "review-item", "blockIndex": 0, "text": "Long", "pageUrl": "http://x/" + "a" * 2000})))

    def test_without_a_page_or_with_an_unknown_one(self):
        plain = self.call("/api/guide/example-core-document/comments")[1]
        self.assertNotIn("labelPolicy", plain)
        self.assertTrue(all("inScope" not in thread for thread in plain["comments"]))
        unknown = self.call("/api/guide/example-core-document/comments?pageUrl=" + urllib.parse.quote("https://elsewhere.example/", safe=""))[1]
        self.assertIsNone(unknown["labelPolicy"])
        self.assertEqual(len(plain["comments"]), len(unknown["comments"]))

    def test_labels_and_patch(self):
        reader = [row["label"] for row in self.call("/api/guide/example-core-document/labels")[1]["labels"]]
        author = self.call("/api/guide/example-core-document/labels", "author")[1]["labels"]
        self.assertEqual(["main", "v0.2.0"], reader)
        self.assertEqual(["main", "v0.2.0", "v0.1.0"], [row["label"] for row in author])
        self.assertTrue(all("openInScope" in row for row in author))
        path = "/api/guide/example-core-document/labels/"
        self.assertEqual(403, self.call(path + "main", "reader", "PATCH", {"display": "current"})[0])
        self.assertEqual((400, "invalid_request"), (lambda r: (r[0], r[1]["error"]))(self.call(path + "main", "author", "PATCH", {})))
        self.assertEqual((400, "display"), (lambda r: (r[0], r[1]["field"]))(self.call(path + "main", "author", "PATCH", {"display": "shown"})))
        self.assertEqual(404, self.call(path + "v9.9.9", "author", "PATCH", {"display": "listed"})[0])
        status, result = self.call(path + "main", "author", "PATCH", {"display": "CURRENT", "commentMode": "Release"})
        self.assertEqual((200, "current", "release", "v0.2.0", "listed"),
                         (status, result["display"], result["commentMode"], result["demoted"]["label"], result["demoted"]["display"]))


class SampleChangeMarkersTest(unittest.TestCase):
    GUIDE = (
        '<html><body><script>// a script element with the ID guide-change-markers, '
        'quoted: <script type="application/json" id="guide-change-markers"> as text\n</script>'
        '<script type="application/json" id="guide-data">{"id": "x", "title": "T", "version": "v1.2.0"}</script>'
        '</body></html>'
    )

    def test_inject_is_idempotent_and_leaves_scripts_alone(self):
        markers = sample_change_markers.fixture_markers("v1.2.0")
        once = sample_change_markers.inject(self.GUIDE, markers)
        twice = sample_change_markers.inject(once, markers)
        self.assertEqual(once, twice)
        self.assertIn("as text\n</script>", twice)
        found = re.findall(r'<script type="application/json" id="guide-change-markers">(.*?)</script>', twice)
        self.assertEqual([json.loads(text) for text in found if text.startswith("[")], [markers])
        self.assertLess(twice.index("guide-change-markers\">["), twice.index('id="guide-data"'))

    def test_markers_follow_the_contract(self):
        version = sample_change_markers.guide_version(self.GUIDE)
        self.assertEqual(version, "v1.2.0")
        for marker in sample_change_markers.fixture_markers(version):
            self.assertLessEqual(set(marker), {"anchor", "blockIndex", "version", "level", "note"})
            self.assertIn(marker["level"], ("changed", "feedback"))
            self.assertTrue(0 < len(marker["note"]) <= 300)

    def test_closing_tags_in_notes_are_escaped(self):
        result = sample_change_markers.inject(self.GUIDE, [{"anchor": "a", "version": "v1", "level": "changed", "note": "see </script> here"}])
        self.assertNotIn("see </script>", result)


if __name__ == "__main__":
    unittest.main()
