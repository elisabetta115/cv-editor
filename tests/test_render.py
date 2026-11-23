"""The HTML of the CV pages must not change by accident.

The example CV is rendered in every style, in several versions (plain, with a sidebar, with a photo, with
everything), and in every colour; each page is compared with its fingerprint in reference/render.json.

When a change to the pages is intended (a style was changed, a new option was added...), update the
fingerprints and review what changed with git diff:

    CV_UPDATE_REFERENCES=1 python3 -m unittest tests/test_render.py
"""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from support import example_content
from cv_editor.content import prepare
from cv_editor.photos import photo_frame
from cv_editor.render import document
from cv_editor.schema import FIXED_SECTIONS, SIDEBAR_SUGGESTED
from cv_editor.styles import COLORS, STYLES
from cv_editor.workspace import STYLES_DIR

REFERENCE = Path(__file__).parent / "reference" / "render.json"
PREVIEW_BASE = "/html/Alex%20Morgan/"
PHOTO = "photos/alex.jpg"
SIGNATURE = "signature-1.png"


def with_sidebar(data):
    """The suggested sections (contacts, details, about me, skills) in the sidebar, in the usual order."""
    data = copy.deepcopy(data)
    extras = [s for s in data.get("sections", []) if "builtin" not in s]
    order = []
    for key in FIXED_SECTIONS:
        order.append({"builtin": key, **({"column": "side"} if key in SIDEBAR_SUGGESTED else {})})
        order += [s for s in extras if s.get("after") == key]
    order += [s for s in extras if s not in order]
    data["sections"] = order
    return data


def with_everything(data):
    """The sidebar, more kinds of contacts and sections, hidden items, links and the signature."""
    data = with_sidebar(data)
    data["contacts"] += [{"type": "github", "text": "@alexmorgan"}, {"type": "whatsapp", "text": "+00 123 456 789"},
                         {"type": "web", "text": "Portfolio", "link": "https://example.com/portfolio", "icon": "star"}]
    data["details"] += [{"label": "Blood group", "value": "hidden-detail", "hidden": True}]
    data["experience"][-1]["hidden"] = True
    data["experience"][0]["link"] = "https://example.com/studio"
    data["sections"] += [
        {"title": "Volunteering", "text": "Mentor at a **local** coding club.\n\nSee [the club](https://example.org)."},
        {"title": "Certificates", "list": ["UX certificate", "Scrum *foundation*"]},
        {"title": "Tools", "tags": ["Figma", "Miro", "Notion"], "column": "side"},
        {"title": "Facts", "rows": [{"label": "Driving licence", "value": "B"}, {"label": "Secret", "value": "hidden-row", "hidden": True}]},
    ]
    data["signature"] = {"show": True}
    return data


def versions():
    """name -> (content, photo, frame, signature)"""
    plain = example_content()
    frame = photo_frame({"x": 40, "y": 30, "zoom": 1.5, "shape": "circle"})
    return {
        "plain": (plain, None, None, None),
        "sidebar": (with_sidebar(plain), None, None, None),
        "photo": (plain, PHOTO, frame, None),
        "everything": (with_everything(plain), PHOTO, frame, SIGNATURE),
    }


def render_all():
    """page name -> HTML of every page checked."""
    pages = {}
    for name, (data, photo, frame, signature) in versions().items():
        prepared = prepare(copy.deepcopy(data), "content_en.toml", "en")
        for style in STYLES:
            pages[f"{name}/{style}"] = document(prepared, "en", style, photo, preview_base=PREVIEW_BASE,
                                                   frame=frame, signature=signature)
        if name == "everything":
            # the page printed to PDF: stylesheets from the folder on this computer, written as STYLES/
            for style in STYLES:
                page = document(prepared, "en", style, photo, frame=frame, signature=signature)
                pages[f"print/{style}"] = page.replace(STYLES_DIR.as_uri() + "/", "STYLES/")
    prepared = prepare(example_content(), "content_en.toml", "en")
    for color in COLORS:
        pages[f"color/modern/{color}"] = document(prepared, "en", "modern", None, preview_base=PREVIEW_BASE, color=color)
    return pages


def fingerprint(page):
    return hashlib.sha256(page.encode("utf-8")).hexdigest()


class RenderTest(unittest.TestCase):
    def test_pages_unchanged(self):
        pages = render_all()
        actual = {k: fingerprint(v) for k, v in sorted(pages.items())}
        if os.environ.get("CV_UPDATE_REFERENCES"):
            REFERENCE.parent.mkdir(exist_ok=True)
            REFERENCE.write_text(json.dumps(actual, indent=1) + "\n", encoding="utf-8")
            self.skipTest(f"fingerprints of {len(actual)} pages written to {REFERENCE}")
        self.assertTrue(REFERENCE.is_file(), "No fingerprints yet: run with CV_UPDATE_REFERENCES=1 first.")
        expected = json.loads(REFERENCE.read_text(encoding="utf-8"))
        changed = sorted(k for k in actual if expected.get(k) != actual[k])
        missing = sorted(set(expected) - set(actual))
        if changed or missing:
            folder = Path(tempfile.mkdtemp(prefix="cv-editor-pages-"))
            for k in changed:
                (folder / (k.replace("/", "__") + ".html")).write_text(pages[k], encoding="utf-8")
            self.fail(f"{len(changed)} of {len(actual)} pages changed, {len(missing)} missing.\n"
                      f"Changed: {', '.join(changed[:12])}{' …' if len(changed) > 12 else ''}\n"
                      f"Missing: {', '.join(missing[:12])}\n"
                      f"The new pages are in {folder}\n"
                      "If the change is intended: CV_UPDATE_REFERENCES=1 python3 -m unittest tests/test_render.py")

    def test_every_version_is_different(self):
        """The versions really test different things (a sidebar, a photo, the signature...)."""
        pages = render_all()
        for style in ("formal", "modern"):
            self.assertIn('class="page formal no-sidebar"' if style == "formal" else 'class="page modern no-sidebar"',
                          pages[f"plain/{style}"])
            self.assertIn("has-sidebar", pages[f"sidebar/{style}"])
            self.assertIn(PHOTO, pages[f"photo/{style}"])
            self.assertIn("shape-circle", pages[f"photo/{style}"])
            self.assertIn(SIGNATURE, pages[f"everything/{style}"])
            self.assertIn('contenteditable="true"', pages[f"print/{style}"])
        everything = pages["everything/formal"]
        self.assertIn("Volunteering", everything)
        self.assertIn("Demo Company", pages["plain/formal"])       # the last job, shown...
        for hidden in ("hidden-detail", "hidden-row", "Demo Company"):  # ...and a detail, a row and that job hidden
            self.assertNotIn(hidden, everything)
        self.assertEqual(len({fingerprint(pages[f"color/modern/{c}"]) for c in COLORS}), len(COLORS))


if __name__ == "__main__":
    unittest.main()
