"""Where the CVs are kept (the workspace in use) and the folders of the project."""
from pathlib import Path


SRC = Path(__file__).resolve().parents[1]   # the src/ folder (this file is in src/cv_editor/)
ROOT = SRC.parent
STYLES_DIR = SRC / "styles"


class Workspace:
    """Where the CVs are kept, with their PDFs and generated pages, and what belongs to that place.

        cvs_dir    cvs/<person>/              the CVs
        pdf_dir    PDF/<person>/<language>/   the PDFs built from the terminal
        html_dir   html/<person>/             the generated pages (in the project folder: src/html/, not kept in git)

    Without a folder it is the project folder; with one (the editor's --data or --demo), that folder.
    One workspace is in use at a time: workspace() gives it, use_workspace() changes it."""

    def __init__(self, folder=None, demo=False):
        if folder is None:
            self.cvs_dir, self.pdf_dir, self.html_dir = ROOT / "cvs", ROOT / "PDF", SRC / "html"
        else:
            folder = Path(folder).resolve()
            self.cvs_dir, self.pdf_dir, self.html_dir = folder / "cvs", folder / "PDF", folder / "html"
        self.demo = demo                                # the editor's demo: an empty temporary folder
        self.translator_memory = {} if demo else None   # the demo keeps a translator key in memory, not in a file
        self.photo_src = {}                             # CV name -> {photo file name -> path used in the HTML}


_workspace = Workspace()


def workspace():
    """The workspace in use."""
    return _workspace


def use_workspace(new):
    """Keeps the CVs, the PDFs and the generated pages in another place from now on (--data, --demo, the tests)."""
    global _workspace
    _workspace = new
    return new


def short_path(path):
    """A path in a message: from the project folder when it is inside it, in full otherwise."""
    path = Path(path)
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
