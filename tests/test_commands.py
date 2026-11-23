"""The two commands (python3 src/editor.py, python3 src/generate_cv.py) and building the pages from the terminal."""
import subprocess
import sys
import unittest

from support import SRC, DataDirTestCase, cv


def run(script, *args):
    return subprocess.run([sys.executable, "-B", str(SRC / script), *args], capture_output=True, text=True, timeout=120)


class CommandsTest(unittest.TestCase):
    def test_editor_command(self):
        r = run("editor.py", "--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for option in ("--install", "--port", "--no-browser", "--data", "--demo"):
            self.assertIn(option, r.stdout)

    def test_generate_command(self):
        r = run("generate_cv.py", "--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for option in ("--cv", "--language", "--style", "--photo", "--html-only", "--data"):
            self.assertIn(option, r.stdout)


class GenerateTest(DataDirTestCase):
    def test_pages_in_another_data_folder(self):
        """The CVs kept in another folder (the editor's --data): the pages are built there."""
        profile = self.import_example()
        messages = []
        cv.generate(profile, "en", ["formal"], None, html_only=True, log=messages.append)
        self.assertEqual([f.name for f in profile.html_dir.glob("CV_*.html")], ["CV_Alex_Morgan_EN_Formal_NoPhoto.html"])
        self.assertTrue(profile.html_dir.is_relative_to(self.data_dir.resolve()))
        self.assertIn(str(profile.html_dir / "CV_Alex_Morgan_EN_Formal_NoPhoto.html"), "\n".join(messages))

    def test_the_command_with_data(self):
        """python3 src/generate_cv.py --data FOLDER builds the pages of the CVs in that folder, and only there."""
        self.import_example()
        r = run("generate_cv.py", "--data", str(self.data_dir), "--style", "swiss,zen", "--html-only")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Alex Morgan:", r.stdout)
        pages = sorted(f.name for f in (self.data_dir / "html" / "Alex Morgan").glob("CV_*.html"))
        self.assertEqual(pages, ["CV_Alex_Morgan_EN_Swiss_NoPhoto.html", "CV_Alex_Morgan_EN_Zen_NoPhoto.html"])

    def test_the_command_without_cvs(self):
        r = run("generate_cv.py", "--data", str(self.data_dir), "--html-only")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No CV found in", r.stderr)


class WorkspaceTest(unittest.TestCase):
    def test_project_folder(self):
        place = cv.Workspace()
        self.assertEqual(place.cvs_dir, cv.ROOT / "cvs")
        self.assertEqual(place.pdf_dir, cv.ROOT / "PDF")
        self.assertEqual(place.html_dir, cv.HERE / "html")
        self.assertFalse(place.demo)
        self.assertIsNone(place.translator_memory)

    def test_messages_show_short_paths(self):
        self.assertEqual(cv.short_path(cv.ROOT / "PDF" / "Jane Doe"), cv.Path("PDF", "Jane Doe"))
        self.assertEqual(cv.short_path("/somewhere/else/cvs"), cv.Path("/somewhere/else/cvs"))


if __name__ == "__main__":
    unittest.main()
