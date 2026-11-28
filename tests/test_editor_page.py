"""The editor's page in a real browser (headless Chrome or Chromium): it loads without JavaScript errors and
shows the CV, or the welcome screen when there is no CV yet."""
import re
import subprocess
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from support import DataDirTestCase, chrome
from cv_editor.contacts import CONTACT_GROUPS
from cv_editor.server import Handler

CHROME = chrome()


@unittest.skipUnless(CHROME, "Chrome or Chromium is not installed")
class EditorPageTest(DataDirTestCase):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def open_editor(self):
        """(the page as the browser shows it once its scripts have run, the errors in the browser's console)"""
        url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
            r = subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-first-run",
                                "--no-default-browser-check", f"--user-data-dir={profile}", "--enable-logging=stderr",
                                "--v=0", "--virtual-time-budget=15000", "--dump-dom", url],
                               capture_output=True, text=True, timeout=120)
        console = [line for line in r.stderr.splitlines() if ":CONSOLE" in line]
        errors = [line for line in console if "Uncaught" in line or "Error" in line]
        # what is shown, without the text of the scripts (which mention "Welcome", section names...)
        return re.sub(r"<script\b.*?</script>", "", r.stdout, flags=re.S), errors

    def test_with_a_cv(self):
        self.import_example()
        page, errors = self.open_editor()
        self.assertEqual(errors, [])
        self.assertRegex(page, r'id="style-name"[^>]*>Formal<')                 # the design bar is filled in
        sections = re.findall(r'class="nav-name"[^>]*>([^<]*)<', page)          # the list of sections
        for section in ("Header", "Contacts", "Experience", "Education", "Skills"):
            self.assertIn(section, sections)
        self.assertRegex(page, r'srcdoc="[^"]*Morgan')                          # the CV is in the preview
        # the kinds of contact come from the server (contacts.py): the menu of a contact shows them all
        groups = re.findall(r'<optgroup label="([^"]+)"', page)
        self.assertEqual(groups[:len(CONTACT_GROUPS)], [g for g, _ in CONTACT_GROUPS])
        self.assertIn('<option value="stackoverflow">Stack Overflow</option>', page)
        self.assertRegex(page, r'(?s)id="btn-adjust"[^>]*>.*?<span class="label">Adjust</span>')              # the Adjust button, and its panel
        self.assertIn('id="adjust-panel"', page)
        self.assertNotIn("<h1>Welcome to CV Editor</h1>", page)

    def test_without_cvs(self):
        page, errors = self.open_editor()
        self.assertEqual(errors, [])
        self.assertIn("<h1>Welcome to CV Editor</h1>", page)
        self.assertNotRegex(page, r'class="nav-name"')


if __name__ == "__main__":
    unittest.main()
