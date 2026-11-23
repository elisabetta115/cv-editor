"""Exporting and importing CVs: the example .json file and .zip files, including damaged or hostile ones."""
import base64
import io
import unittest
import zipfile

from support import TINY_PNG, DataDirTestCase, cv, editor, example


def zip_of(files):
    """A .zip made of {path: bytes or text}."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buffer.getvalue()


CONTENT = '[cv_language]\nname = "English"\n\n[person]\nfirst_name = "Zip"\nlast_name = "Test"\n'


class JsonImportTest(DataDirTestCase):
    def test_example(self):
        profile = self.import_example()
        self.assertEqual(profile.name, "Alex Morgan")
        data = editor.read_data(profile)
        self.assertEqual(list(data["languages"]), ["en"])
        self.assertEqual(data["languages"]["en"]["data"]["person"]["last_name"], "Morgan")
        self.assertEqual(cv.load_settings(profile)["styles"]["formal"]["color"], "navy")

    def test_check_copy_and_replace(self):
        self.import_example()
        self.assertEqual(editor.import_cv({"data": example(), "mode": "check"}),
                         {"cvs": [{"name": "Alex Morgan", "exists": True}]})
        self.assertEqual(editor.import_cv({"data": example(), "mode": "copy"})["profiles"], ["Alex Morgan (2)"])
        changed = example()
        changed["languages"]["en"]["person"]["headline"] = "Replaced"
        self.assertEqual(editor.import_cv({"data": changed, "mode": "replace"})["profiles"], ["Alex Morgan"])
        self.assertEqual(cv.load(editor.get_profile("Alex Morgan"), "content_en.toml")["person"]["headline"], "Replaced")
        self.assertEqual(len(cv.profiles()), 2)

    def test_with_a_photo(self):
        data = example()
        data["photos"] = [{"name": "me.png", "data": "data:image/png;base64," + base64.b64encode(TINY_PNG).decode()}]
        profile = editor.get_profile(editor.import_cv({"data": data, "mode": "copy"})["profiles"][0])
        self.assertEqual([f.name for f in cv.find_photos(profile)], ["me.png"])

    def test_bad_files(self):
        damaged_photo = example()
        damaged_photo["photos"] = [{"name": "me.png", "data": "data:image/png;base64,@@@"}]
        bad_language = example()
        bad_language["languages"] = {"../en": bad_language["languages"]["en"]}
        for data in ({}, {"format": "something else"}, {"format": "cv-editor", "languages": {}}, damaged_photo, bad_language):
            with self.assertRaises(RuntimeError):
                editor.import_cv({"data": data, "mode": "copy"})
        self.assertEqual(cv.profiles(), [])  # nothing half-imported


class ZipTest(DataDirTestCase):
    def test_export_and_import_again(self):
        profile = self.import_example()
        editor.add_photo(profile.name, "me.png", TINY_PNG)
        editor.save({"profile": profile.name, "languages": {"en": editor.read_data(profile)["languages"]["en"]["data"]},
                     "settings": {"styles": {"modern": {"color": "burgundy"}}}})
        body = editor.export_zip([profile])
        names = sorted(zipfile.ZipFile(io.BytesIO(body)).namelist())
        self.assertEqual(names, ["cvs/Alex Morgan/content_en.toml", "cvs/Alex Morgan/photos/me.png",
                                 "cvs/Alex Morgan/settings.toml"])
        self.assertEqual(editor.import_zip(body, "check"), {"cvs": [{"name": "Alex Morgan", "exists": True}]})
        copy = editor.get_profile(editor.import_zip(body, "copy")["profiles"][0])
        self.assertEqual(copy.name, "Alex Morgan (2)")
        self.assertEqual(cv.load(copy, "content_en.toml"), cv.load(profile, "content_en.toml"))
        self.assertEqual(cv.load_settings(copy)["styles"]["modern"]["color"], "burgundy")
        self.assertEqual([f.read_bytes() for f in cv.find_photos(copy)], [TINY_PNG])

    def test_without_photos(self):
        profile = self.import_example()
        editor.add_photo(profile.name, "me.png", TINY_PNG)
        names = zipfile.ZipFile(io.BytesIO(editor.export_zip([profile], with_photos=False))).namelist()
        self.assertFalse(any("photos/" in n for n in names))

    def test_a_zip_made_by_hand(self):
        """A CV folder zipped by hand, with the extra files macOS adds."""
        body = zip_of({"Zip Test/content_en.toml": CONTENT, "Zip Test/photos/a.png": TINY_PNG,
                       "__MACOSX/Zip Test/._content_en.toml": "junk", "Zip Test/.DS_Store": "junk"})
        profile = editor.get_profile(editor.import_zip(body, "copy")["profiles"][0])
        self.assertEqual(profile.name, "Zip Test")
        self.assertEqual(cv.load(profile, "content_en.toml")["person"]["first_name"], "Zip")
        self.assertEqual([f.name for f in cv.find_photos(profile)], ["a.png"])

    def test_paths_never_leave_the_cvs_folder(self):
        body = zip_of({"../../outside/content_en.toml": CONTENT, "/absolute/content_en.toml": CONTENT,
                       "x/../../content_en.toml": CONTENT})
        try:
            names = editor.import_zip(body, "copy")["profiles"]
        except RuntimeError:
            names = []
        for name in names:
            self.assertTrue((cv.workspace().cvs_dir / name).resolve().is_relative_to(cv.workspace().cvs_dir.resolve()))
        written = {p.relative_to(self.data_dir).parts[0] for p in self.data_dir.rglob("*") if p.is_file()}
        self.assertLessEqual(written, {"cvs", "html"})
        self.assertFalse((self.data_dir.parent / "outside").exists())

    def test_bad_zips(self):
        too_big = zip_of({"A/content_en.toml": "x" * (editor.MAX_CONTENT_BYTES + 1)})
        too_many = zip_of({f"A/{i}.txt": "" for i in range(editor.MAX_ZIP_FILES + 1)})
        not_toml = zip_of({"A/content_en.toml": "this is [not toml"})
        no_cv = zip_of({"notes.txt": "hello"})
        for body in (b"not a zip", too_big, too_many, not_toml, no_cv):
            with self.assertRaises(RuntimeError):
                editor.import_zip(body, "copy")
        self.assertEqual(cv.profiles(), [])

    def test_a_failed_import_changes_nothing(self):
        """Two CVs in one .zip, the second one broken: the first is not kept, the existing one is untouched."""
        profile = self.import_example()
        before = profile.dir.joinpath("content_en.toml").read_bytes()
        body = zip_of({"cvs/Alex Morgan/content_en.toml": CONTENT, "cvs/Broken/content_en.toml": CONTENT,
                       "cvs/Broken/photos/big.png": b"x" * (editor.MAX_PHOTO_BYTES + 1)})
        with self.assertRaises(RuntimeError):
            editor.import_zip(body, "replace")
        self.assertEqual([p.name for p in cv.profiles()], ["Alex Morgan"])
        self.assertEqual(profile.dir.joinpath("content_en.toml").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
