"""The files that Windows and macOS users double-click to open the editor, in the project folder."""
import os
import re
import subprocess
import unittest

from support import REPO, SRC

WINDOWS = REPO / "Start CV Editor - Windows.bat"
MAC = REPO / "Start CV Editor - Mac.command"


class LaunchersTest(unittest.TestCase):
    def test_same_oldest_python_everywhere(self):
        """The launchers, the editor and the tests on GitHub agree on the oldest Python the editor supports."""
        for file in (WINDOWS, MAC, SRC / "editor.py"):
            self.assertIn("sys.version_info < (3, 11)", file.read_text(encoding="utf-8"), file.name)
        self.assertIn('python: "3.11"', (REPO / ".github/workflows/tests.yml").read_text(encoding="utf-8"))

    def test_windows_file(self):
        content = WINDOWS.read_bytes()
        content.decode("ascii")                                              # no accents: Windows reads it in its own code page
        self.assertEqual(content.count(b"\n"), content.count(b"\r\n"))      # Windows line endings (see .gitattributes)
        self.assertIn(rb"src\editor.py %*", content)
        # no ( ) blocks: a folder name with brackets, such as "cv-editor-main (1)", would break them
        self.assertNotRegex(content.decode(), r"(?m)^\s*(if|for)\b.*\($")

    def test_mac_file(self):
        content = MAC.read_bytes()
        content.decode("ascii")
        self.assertNotIn(b"\r", content)
        self.assertTrue(content.startswith(b"#!/bin/sh\n"))
        self.assertIn(b'src/editor.py "$@"', content)
        if os.name == "posix":                                               # the Finder runs it only if it is executable
            self.assertTrue(os.access(MAC, os.X_OK), "chmod +x the file (git keeps the permission)")

    def test_they_start_the_editor(self):
        """The launcher of this system finds Python and runs the editor (--help: it shows its options and ends)."""
        if os.name == "nt":
            command = [str(WINDOWS), "--help"]
        else:
            command = ["sh", str(MAC), "--help"]                            # sh: the same on Linux and macOS
        r = subprocess.run(command, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL, cwd=REPO.parent)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, re.compile(r"usage: editor\.py .*--demo", re.S))


if __name__ == "__main__":
    unittest.main()
