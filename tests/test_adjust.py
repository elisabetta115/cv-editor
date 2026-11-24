"""The Adjust panel: a style fitted to a CV (text size, spacing, line spacing, long entries), saved with each style."""
import copy
import re
import unittest

from support import DataDirTestCase, chrome, example_content
from cv_editor.actions import page_count, preview, read_data
from cv_editor.build import generate
from cv_editor.content import prepare
from cv_editor.render import document
from cv_editor.storage import load_settings, save_settings
from cv_editor.styles import ADJUSTMENTS, adjust_css, adjust_values
from cv_editor.transfer import export_zip, import_zip
from cv_editor.workspace import SRC

TIGHT = {"text": 80, "spacing": 50, "lines": 85}
AIRY = {"text": 120, "spacing": 150, "lines": 115}


class ValuesTest(unittest.TestCase):
    def test_checked_rounded_and_kept_within_limits(self):
        self.assertEqual(adjust_values({"text": 90, "spacing": 80.4, "lines": 100, "split": True}),
                         {"text": 90, "spacing": 80, "split": True})
        self.assertEqual(adjust_values({"text": 10, "spacing": 999, "lines": 200}),
                         {"text": ADJUSTMENTS["text"][0], "spacing": ADJUSTMENTS["spacing"][1], "lines": ADJUSTMENTS["lines"][1]})
        for bad in (None, "x", [], {"text": "90"}, {"text": True}, {"split": "yes"}, {"split": 1}, {"other": 5}):
            self.assertEqual(adjust_values(bad), {}, bad)

    def test_css(self):
        self.assertEqual(adjust_css(None), "")
        self.assertEqual(adjust_css({"text": 100, "split": False}), "")
        self.assertEqual(adjust_css({"text": 90, "lines": 95}), ":root{--adj-text:0.9;--adj-lines:0.95;}")
        self.assertIn(".entry{break-inside:auto}", adjust_css({"split": True}))

    def test_as_designed_the_page_does_not_change(self):
        prepared = prepare(example_content(), "content_en.toml", "en")
        for style in ("modern", "swiss", "notebook"):
            designed = document(prepared, "en", style, None)
            self.assertEqual(document(prepared, "en", style, None, adjust={"text": 100, "split": False}), designed)
            self.assertIn("--adj-space:0.7;", document(prepared, "en", style, None, adjust={"spacing": 70}))


class StylesheetsTest(unittest.TestCase):
    """Every stylesheet lets the adjustments work: a new or changed style that forgets them is caught here."""

    def rules(self):
        for f in sorted((SRC / "styles").glob("*.css")):
            if f.name != "fonts.css":
                css = re.sub(r"/\*.*?\*/", "", f.read_text(encoding="utf-8"), flags=re.S)
                for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
                    yield f.name, [s.strip() for s in m.group(1).split(",")], m.group(2)

    def test_line_spacing(self):
        for name, selectors, body in self.rules():
            for v in re.findall(r"line-height:\s*([\d.]+)\s*(?:;|$)", body):
                self.assertLess(float(v), 1.2, f"{name}: {', '.join(selectors)} {{ line-height: {v} }}: "
                                               f"write it calc({v} * var(--adj-lines, 1)) (names and titles under 1.2 may stay)")

    def test_text_size(self):
        found = 0
        for name, selectors, body in self.rules():
            if "html" in selectors and "font-size" in body:
                found += 1
                self.assertIn("var(--adj-text, 1)", body, f"{name}: the font size of html must use var(--adj-text, 1)")
        self.assertGreater(found, 0)

    def test_spacing(self):
        spacing = re.compile(r"(\.cv-section(:[\w-]+(\([^)]*\))?)*|\.entry\s*\+\s*\.entry|\.section-body\s*>\s*\*\s*\+\s*\*)$")
        for name, selectors, body in self.rules():
            if not all(spacing.search(s) for s in selectors):
                continue
            for prop, value in re.findall(r"(margin-top|margin-bottom):\s*([^;]+)", body):
                if re.search(r"(^|\s)-?[\d.]*[1-9][\d.]*(mm|rem|em|px|pt)", value.replace("var(--adj-space, 1)", "")) \
                        and "var(--L)" not in value:
                    self.assertIn("var(--adj-space, 1)", value, f"{name}: {', '.join(selectors)} {{ {prop}: {value} }}")


class SavedTest(DataDirTestCase):
    def test_saved_with_each_style(self):
        profile = self.import_example()
        save_settings(profile, {"styles": {"swiss": {"color": "teal", "adjust": {"text": 90, "split": True}},
                                           "modern": {"adjust": {"spacing": 100}}}})
        styles = load_settings(profile)["styles"]
        self.assertEqual(styles["swiss"], {"color": "teal", "adjust": {"text": 90, "split": True}})
        self.assertNotIn("adjust", styles["modern"])   # 100 % is the style as designed: nothing is kept
        text = profile.settings_file.read_text()
        self.assertIn('[styles.swiss]\ncolor = "teal"\ntext = 90\nsplit = true\n', text)
        self.assertIn("[styles.modern]\ncolor", text)
        self.assertEqual(read_data(profile)["settings"]["styles"]["swiss"]["adjust"], {"text": 90, "split": True})

    def test_kept_by_export_and_import(self):
        profile = self.import_example()
        save_settings(profile, {"styles": {"zen": {"adjust": {"lines": 90, "spacing": 75}}}})
        copy_name = import_zip(export_zip([profile]), "copy")["profiles"][0]
        self.assertEqual(load_settings(profile.__class__(copy_name))["styles"]["zen"]["adjust"], {"spacing": 75, "lines": 90})

    def test_preview_and_command_line(self):
        profile = self.import_example()
        content = read_data(profile)["languages"]["en"]["data"]
        page = preview({"profile": profile.name, "language": "en", "style": "modern", "data": content,
                        "adjust": {"text": 85, "split": True}})["document"]
        self.assertIn("--adj-text:0.85;", page)
        save_settings(profile, {"styles": {"swiss": {"adjust": {"text": 90}}}})
        generate(profile, "en", ["swiss", "zen"], None, html_only=True, log=lambda *_: None)
        pages = {f.name.split("_")[4]: f.read_text() for f in profile.html_dir.glob("CV_*.html")}
        self.assertIn("--adj-text:0.9;", pages["Swiss"])
        self.assertNotIn("--adj-", pages["Zen"].split("</style>")[0].split("<style>")[-1])


@unittest.skipUnless(chrome(), "Chrome or Chromium is not installed")
class PagesTest(DataDirTestCase):
    def test_tighter_means_fewer_pages(self):
        """A long CV (about four pages, so that page breaks do not decide): as tight as possible, as designed,
        as airy as possible. Each is at least a page apart from the next."""
        profile = self.import_example()
        content = copy.deepcopy(read_data(profile)["languages"]["en"]["data"])
        content["experience"] = content["experience"] * 14
        ask = lambda adjust: page_count({"profile": profile.name, "language": "en", "style": "modern", "data": content,
                                         "adjust": adjust})["pages"]
        tight, designed, airy = ask(TIGHT), ask(None), ask(AIRY)
        self.assertLess(tight, designed)
        self.assertLess(designed, airy)


if __name__ == "__main__":
    unittest.main()
