"""The two commands (python3 src/editor.py, python3 src/generate_cv.py) and building the pages from the terminal."""
import subprocess
import sys
import unittest

from support import SRC, DataDirTestCase, cv


class CommandsTest(unittest.TestCase):
    def run_help(self, script):
        r = subprocess.run([sys.executable, "-B", str(SRC / script), "--help"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_editor_command(self):
        out = self.run_help("editor.py")
        for option in ("--install", "--port", "--no-browser", "--data", "--demo"):
            self.assertIn(option, out)

    def test_generate_command(self):
        out = self.run_help("generate_cv.py")
        for option in ("--cv", "--language", "--style", "--photo", "--html-only"):
            self.assertIn(option, out)


class GenerateTest(DataDirTestCase):
    @unittest.expectedFailure
    def test_pages_in_another_data_folder(self):
        """Known bug, to fix: generate() writes its messages with paths relative to the project folder, so it stops
        when the CVs are kept in another folder (as with the editor's --data). Remove expectedFailure once fixed."""
        profile = self.import_example()
        cv.generate(profile, "en", ["formal"], None, html_only=True, log=lambda *_: None)
        self.assertEqual([f.name for f in profile.html_dir.glob("CV_*.html")], ["CV_Alex_Morgan_EN_Formal_NoPhoto.html"])


if __name__ == "__main__":
    unittest.main()
