"""The editor's local server: what the editor asks it, and what it refuses (other websites, missing token,
files outside the folders it may show)."""
import http.client
import io
import json
import threading
import unittest
import zipfile
from http.server import ThreadingHTTPServer
from urllib.parse import quote

from support import DataDirTestCase, chrome, cv, editor, example


class ServerTestCase(DataDirTestCase):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), editor.Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, token=True, host=None, headers=None):
        """(status, headers, body bytes); a dict body is sent as JSON."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        self.addCleanup(connection.close)
        h = {"Host": host or f"127.0.0.1:{self.port}", **(headers or {})}
        if token:
            h["X-Token"] = editor.TOKEN
        if isinstance(body, dict):
            body, h["Content-Type"] = json.dumps(body).encode(), "application/json"
        connection.request(method, path, body=body, headers=h)
        r = connection.getresponse()
        return r.status, dict(r.getheaders()), r.read()

    def api(self, path, body=None, **kw):
        """The JSON answer of a request that must succeed."""
        status, _, data = self.request("POST" if body is not None else "GET", path, body, **kw)
        self.assertEqual(status, 200, data[:300])
        return json.loads(data)


class SecurityTest(ServerTestCase):
    def test_ping_needs_nothing(self):
        self.assertEqual(self.api("/api/ping", token=False), {"editor": "curriculum"})

    def test_the_page_carries_the_token(self):
        status, headers, page = self.request("GET", "/", token=False)
        self.assertEqual(status, 200)
        self.assertIn(editor.TOKEN.encode(), page)
        self.assertNotIn(b"__TOKEN__", page)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_other_websites_are_refused(self):
        for host in ("evil.example", f"evil.example:{self.port}", "127.0.0.1", f"127.0.0.1.evil.example:{self.port}"):
            self.assertEqual(self.request("GET", "/", host=host)[0], 403, host)
            self.assertEqual(self.request("GET", "/api/cvs", host=host)[0], 403, host)
            self.assertEqual(self.request("POST", "/api/cvs/new", {"first_name": "A", "last_name": "B"}, host=host)[0], 403)
        self.assertEqual(self.request("GET", "/", host=f"localhost:{self.port}")[0], 200)

    def test_the_token_is_needed(self):
        self.assertEqual(self.request("GET", "/api/cvs", token=False)[0], 403)
        self.assertEqual(self.request("GET", "/api/cvs", headers={"X-Token": "wrong"}, token=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/cvs/new", {"first_name": "A", "last_name": "B"}, token=False)[0], 403)
        self.assertEqual(cv.profiles(), [])

    def test_only_the_allowed_folders_are_shown(self):
        self.assertEqual(self.request("GET", "/styles/base.css")[0], 200)
        self.assertEqual(self.request("GET", "/fonts/inter-400-normal.woff2")[0], 200)
        for path in ("/styles/../editor.py", "/styles/%2e%2e/editor.py", "/fonts/../../README.md",
                     "/html/../../src/editor.py", "/src/editor.py", "/editor.html", "/cvs/"):
            self.assertEqual(self.request("GET", path)[0], 404, path)

    def test_unknown_requests(self):
        self.assertEqual(self.request("GET", "/api/nothing")[0], 404)
        self.assertEqual(self.request("POST", "/api/nothing", {})[0], 404)
        status, _, body = self.request("POST", "/api/save", b"[1, 2]")
        self.assertEqual(status, 500)
        self.assertIn("error", json.loads(body))


class EditorRequestsTest(ServerTestCase):
    def test_a_session(self):
        """What the editor does: try the example, read it, preview it, change and save it, export and import it."""
        self.assertEqual(self.api("/api/cvs"), {"profiles": [], "demo": False})
        name = self.api("/api/import", {"data": self.api("/api/example"), "mode": "copy"})["profiles"][0]
        self.assertEqual(name, "Alex Morgan")
        data = self.api("/api/data?cv=" + quote(name))
        self.assertEqual(len(data["styles"]), len(cv.STYLES))
        content = data["languages"]["en"]["data"]

        view = {"profile": name, "language": "en", "style": "modern", "color": "burgundy", "photo": None, "data": content}
        preview = self.api("/api/preview", view)
        self.assertIn("Alex", preview["document"])
        self.assertIn("/styles/modern.css", preview["document"])
        self.assertIn(cv.COLORS["burgundy"]["dark"], preview["document"])
        self.assertFalse(preview["sidebar"])

        content["person"]["headline"] = "Changed by the test"
        self.assertEqual(self.api("/api/save", {"profile": name, "languages": {"en": content}}), {"saved": True})
        again = self.api("/api/data?cv=" + quote(name))["languages"]["en"]["data"]
        self.assertEqual(again["person"]["headline"], "Changed by the test")

        status, headers, body = self.request("GET", "/api/export-zip?cv=" + quote(name))
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/zip")
        self.assertIn('filename="cv-alex-morgan.zip"', headers["Content-Disposition"])
        self.assertIn("cvs/Alex Morgan/content_en.toml", zipfile.ZipFile(io.BytesIO(body)).namelist())
        self.assertEqual(self.api("/api/import-zip", body, headers={"X-Mode": "check"}),
                         {"cvs": [{"name": "Alex Morgan", "exists": True}]})
        self.assertEqual(self.api("/api/import-zip", body, headers={"X-Mode": "copy"}), {"profiles": ["Alex Morgan (2)"]})

    def test_new_duplicate_delete(self):
        self.assertEqual(self.api("/api/cvs/new", {"first_name": "Jane", "last_name": "Doe", "language": "en"}),
                         {"profile": "Jane Doe"})
        self.assertEqual(self.api("/api/cvs/duplicate", {"profile": "Jane Doe", "name": "Jane – Sales"}),
                         {"profile": "Jane – Sales"})
        self.assertEqual(self.api("/api/cvs/delete", {"profile": "Jane Doe"}),
                         {"profiles": [{"name": "Jane – Sales", "languages": ["en"]}]})

    def test_errors_are_reported(self):
        status, _, body = self.request("POST", "/api/preview", {"profile": "Nobody", "language": "en", "style": "modern"})
        self.assertEqual(status, 500)
        self.assertIn("Nobody", json.loads(body)["error"])

    def test_the_example_is_the_example_file(self):
        self.assertEqual(self.api("/api/example"), example())


@unittest.skipUnless(chrome(), "Chrome or Chromium is not installed")
class PdfTest(ServerTestCase):
    def test_pdf_of_the_view(self):
        name = editor.import_cv({"data": example(), "mode": "copy"})["profiles"][0]
        content = editor.read_data(editor.get_profile(name))["languages"]["en"]["data"]
        status, headers, pdf = self.request("POST", "/api/pdf", {"profile": name, "language": "en", "style": "formal",
                                                                 "data": content, "inline": True})
        self.assertEqual(status, 200, pdf[:300])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertIn("CV_Alex_Morgan_EN.pdf", headers["Content-Disposition"])
        self.assertTrue(headers["Content-Disposition"].startswith("inline"))


if __name__ == "__main__":
    unittest.main()
