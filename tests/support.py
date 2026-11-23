"""Shared helpers for the tests.

Importing this module points the editor at an empty temporary folder at once, so that no test can ever read or
change the CVs in cvs/. Every DataDirTestCase gets a new empty folder of its own.
"""
import atexit
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
EXAMPLE = REPO / "examples" / "example-cv.json"

sys.dont_write_bytecode = True       # no __pycache__ folders left in src/
sys.path.insert(0, str(SRC))

from cv_editor.content import normalize  # noqa: E402
from cv_editor.pdf import find_chrome  # noqa: E402
from cv_editor.workspace import Workspace, use_workspace, workspace  # noqa: E402
import editor                        # noqa: E402
import translator                    # noqa: E402

_first = tempfile.mkdtemp(prefix="cv-editor-tests-")
atexit.register(shutil.rmtree, _first, True)
use_workspace(Workspace(_first))   # never the real cvs/ folder


def chrome():
    """The path of Chrome or Chromium, None when it is not installed (the tests that need it are skipped)."""
    try:
        return find_chrome()
    except SystemExit:  # find_chrome() stops the program when there is none
        return None


def example():
    """The example CV file (.json), as the editor exports it."""
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def example_content(language="en"):
    """The content of one language of the example CV, normalised as the editor reads it."""
    return normalize(copy.deepcopy(example()["languages"][language]), language)


# A valid 1 × 1 pixel PNG image: a photo that every tool can read, without needing Pillow to make it.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201e5270ade"
    "0000000049454e44ae426082")


class DataDirTestCase(unittest.TestCase):
    """A test with its own empty data folder (cvs/, PDF/, html/). demo = True: the editor's demo."""
    demo = False

    def setUp(self):
        self.data_dir = Path(tempfile.mkdtemp(prefix="cv-editor-test-"))
        self.workspace = use_workspace(Workspace(self.data_dir, demo=self.demo))
        self.addCleanup(shutil.rmtree, self.data_dir, True)
        # a last check: the CVs of this test are in its own folder
        self.assertTrue(workspace().cvs_dir.resolve().is_relative_to(self.data_dir.resolve()))

    def import_example(self):
        """The example CV, imported as "Try the example" does. Returns its Profile."""
        names = editor.import_cv({"data": example(), "mode": "copy"})["profiles"]
        return editor.get_profile(names[0])
