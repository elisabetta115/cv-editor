"""The editor's local web server: reachable only from this computer, with a secret token for every request.

Every request the editor makes is one line of ROUTES: its method and address, what answers it, and whether it waits
for the lock (requests that read or write the CV files take turns). The answers come from actions.py, transfer.py
and translator.py, which know nothing about the web.
"""
import json
import re
import secrets
import threading
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from mimetypes import guess_type
from typing import Callable
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import translator
from .actions import (
    add_photo, add_signature, delete_photo, delete_profile, delete_signature, duplicate_profile, example,
    list_profiles, make_pdf, new_profile, preview, read_data, save, templates,
)
from .storage import get_profile, profiles as all_profiles
from .transfer import export_zip, import_cv, import_zip
from .workspace import SRC, workspace


PORT = 8765
TOKEN = secrets.token_urlsafe(24)
CODE_FILES = [SRC / "editor.py", SRC / "generate_cv.py", *sorted((SRC / "cv_editor").glob("*.py"))]
CODE_VERSION = [f.stat().st_mtime_ns for f in CODE_FILES]  # to notice when the code is updated while running
UPDATED_PAGE = """<!doctype html><meta charset="utf-8"><title>CV Editor</title>
<body style="font: 16px system-ui, sans-serif; margin: 15vh auto; max-width: 34em; line-height: 1.5">
<h1 style="font-size: 22px">The CV editor has been updated</h1>
<p>Close the small terminal window of the editor and open <b>CV Editor</b> again.</p></body>"""
LOCK = threading.Lock()            # one file operation at a time
MAX_BODY = 80_000_000              # bytes: the largest request (a .zip of every CV with its photos)


# Folders the browser may read (nothing else)
def static_folders():
    return {"/styles/": SRC / "styles", "/fonts/": SRC / "fonts", "/html/": workspace().html_dir}


# ---------------------------------------------------------------------
#  Requests and answers
# ---------------------------------------------------------------------
@dataclass
class Request:
    """What the editor sent: the ?parameters of the address, the headers and the body."""
    query: dict
    headers: object
    body: bytes = b""

    def arg(self, name, default=""):
        """A ?parameter of the address (cv=Jane%20Doe -> "Jane Doe")."""
        return (self.query.get(name) or [default])[0]

    def header(self, name):
        return self.headers.get(name)

    def json(self):
        """The body as a JSON object."""
        data = json.loads(self.body or b"{}")
        if not isinstance(data, dict):
            raise RuntimeError("Invalid request.")
        return data


@dataclass
class File:
    """An answer that is a file (a .zip to download, a PDF to download or show) instead of JSON."""
    content: bytes
    content_type: str
    disposition: str   # the Content-Disposition header: attachment or inline, and the file name


@dataclass
class Route:
    answer: Callable   # Request -> a JSON object, or a File
    lock: bool = True  # False: it touches no CV file, so it does not wait for the others


def download(profile, ext):
    """Content-Disposition of an exported file: cv-<name>.json / .zip, or cvs.zip for every CV."""
    name = "cvs"
    if profile:
        name = "cv-" + (re.sub(r"[^\w-]+", "-", profile.name.lower()).strip("-") or "cv")
    return f'attachment; filename="{quote(name)}{ext}"'


def export(request):
    """?cv=<name>&photos=0|1: one CV as a .zip, or every CV when no name is given."""
    name = request.arg("cv")
    profiles = [get_profile(name)] if name else all_profiles()
    if not profiles:
        raise RuntimeError("There is no CV to export.")
    content = export_zip(profiles, request.arg("photos", "1") != "0")
    return File(content, "application/zip", download(profiles[0] if name else None, ".zip"))


def pdf(request):
    """The PDF of what the editor shows: downloaded, or shown in the Pages view ("inline": true)."""
    r = request.json()
    name, content = make_pdf(r)
    disposition = "inline" if r.get("inline") else "attachment"
    return File(content, "application/pdf", f"{disposition}; filename*=UTF-8''{quote(name)}")


def json_body(action):
    """A route whose answer is the action applied to the JSON object sent."""
    return lambda request: action(request.json())


ROUTES = {
    # reading
    ("GET", "/api/cvs"): Route(lambda r: {**list_profiles(), "demo": workspace().demo}),
    ("GET", "/api/data"): Route(lambda r: read_data(get_profile(r.arg("cv")))),     # ?cv=<name>: everything of a CV
    ("GET", "/api/templates"): Route(lambda r: {"templates": templates()}),         # known languages, for a first CV
    ("GET", "/api/example"): Route(lambda r: example()),                            # the example CV, to try the editor
    ("GET", "/api/export-zip"): Route(export),
    ("GET", "/api/translator"): Route(lambda r: translator.status(), lock=False),   # which translators are ready
    # what the editor shows: no CV file is written
    ("POST", "/api/preview"): Route(json_body(preview), lock=False),
    ("POST", "/api/pdf"): Route(pdf, lock=False),
    # changes to the CVs
    ("POST", "/api/save"): Route(json_body(save)),
    ("POST", "/api/cvs/new"): Route(json_body(new_profile)),
    ("POST", "/api/cvs/delete"): Route(json_body(delete_profile)),
    ("POST", "/api/cvs/duplicate"): Route(json_body(duplicate_profile)),
    ("POST", "/api/import"): Route(json_body(import_cv)),                           # the example or a .json file
    ("POST", "/api/import-zip"): Route(lambda r: import_zip(r.body, r.header("X-Mode"))),  # X-Mode: check|replace|copy
    ("POST", "/api/photos"): Route(lambda r: add_photo(r.header("X-CV"), r.header("X-File-Name"), r.body)),
    ("POST", "/api/photos/delete"): Route(json_body(delete_photo)),
    ("POST", "/api/signature"): Route(lambda r: add_signature(r.header("X-CV"), r.header("X-File-Name"), r.body)),
    ("POST", "/api/signature/delete"): Route(json_body(delete_signature)),
    # translation: {data, from, to, engine} -> the content translated; {key, region} -> keeps the Azure key
    ("POST", "/api/translate"): Route(json_body(translator.translate_cv), lock=False),
    ("POST", "/api/translator"): Route(json_body(translator.set_key), lock=False),
}


# ---------------------------------------------------------------------
#  Local server (reachable only from this computer)
# ---------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _send(self, status, body, content_type, extra_headers=()):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra_headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status=200, extra_headers=()):
        self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", extra_headers)

    def _allowed(self, need_token=True):
        # no requests from other websites: local host and the editor's secret token
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return False
        return not need_token or secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def do_GET(self):
        url = urlparse(self.path)
        path = unquote(url.path)
        if path == "/api/ping":  # answered to anyone: tells a second editor that this one is already open
            return self._json({"editor": "curriculum"})
        if not self._allowed(need_token=False):
            return self._send(403, b"", "text/plain")
        if path == "/":
            return self._page()
        if path.startswith("/api/"):
            return self._api("GET", path, Request(parse_qs(url.query), self.headers))
        return self._static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._allowed():
            return self._send(403, b"", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._json({"error": "File too large."}, 413)
        return self._api("POST", path, Request({}, self.headers, self.rfile.read(length)))

    def _api(self, method, path, request):
        """A request of ROUTES: only with the token; an error becomes {"error": "..."} for the editor to show."""
        if not self._allowed():
            return self._send(403, b"", "text/plain")
        route = ROUTES.get((method, path))
        if not route:
            return self._send(404, b"", "text/plain")
        try:
            if route.lock:
                with LOCK:
                    answer = route.answer(request)
            else:
                answer = route.answer(request)
        except (Exception, SystemExit) as e:
            return self._json({"error": str(e)}, 500)
        if isinstance(answer, File):
            return self._send(200, answer.content, answer.content_type, [("Content-Disposition", answer.disposition)])
        return self._json(answer)

    def _page(self):
        """The editor's page, with the token its requests need (or a notice when the code changed meanwhile)."""
        if [f.stat().st_mtime_ns for f in CODE_FILES] != CODE_VERSION:
            return self._send(200, UPDATED_PAGE.encode(), "text/html; charset=utf-8")
        page = (SRC / "editor.html").read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
        return self._send(200, page.encode(), "text/html; charset=utf-8")

    def _static(self, path):
        """A file of the folders the browser may read: stylesheets, fonts, the generated pages and photos."""
        for prefix, folder in static_folders().items():
            if path.startswith(prefix):
                file = (folder / path[len(prefix):]).resolve()
                if file.is_file() and file.is_relative_to(folder.resolve()):
                    content_type = guess_type(file.name)[0] or "application/octet-stream"
                    return self._send(200, file.read_bytes(), content_type)
        self._send(404, b"", "text/plain")


def already_running(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2) as r:
            return json.load(r).get("editor") == "curriculum"
    except Exception:
        return False
