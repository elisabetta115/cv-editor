"""CVs on disk: writing the .toml files, reading them back, and creating, copying and deleting CVs."""
import tomllib
import unittest

from support import DataDirTestCase, example_content
from cv_editor.actions import delete_profile, duplicate_profile, list_profiles, new_profile, read_data, save
from cv_editor.content import empty_cv
from cv_editor.language import KNOWN_LANGUAGES, base_language, language_config, languages
from cv_editor.storage import check_code, clean_cv, get_profile, write_toml
from cv_editor.storage import check_cv_name, load, load_settings, profiles
from cv_editor.styles import STYLES
from cv_editor.workspace import workspace


class TomlTest(unittest.TestCase):
    def round_trip(self, data, language="en"):
        data = clean_cv(data)
        return clean_cv(tomllib.loads(write_toml(data, language))), data

    def test_example_reads_back_identical(self):
        back, data = self.round_trip(example_content())
        self.assertEqual(back, data)

    def test_difficult_text_reads_back_identical(self):
        data = example_content()
        data["person"]["profile"] = 'Quotes " and \\ backslashes, tabs\tand "triple """ quotes"'
        data["person"]["about_me"] = "Two lines\nand a \"quote\"\n\nand a new paragraph \\ with a backslash"
        data["person"]["headline"] = "Ünïcödé — 日本語 — emoji 🙂 — \x7f control"
        data["interests"] = {"text": "Line with control \x01 character\nsecond line"}
        data["labels"]["key with spaces"] = "a label whose name needs quotes"
        data["labels"]["ключ"] = "a key in another alphabet"
        back, data = self.round_trip(data)
        self.assertEqual(back, data)

    def test_header_names_the_language(self):
        self.assertIn("CONTENT IN ENGLISH", write_toml(example_content(), "en"))
        self.assertIn("CONTENT IN ITALIANO", write_toml(empty_cv("it"), "it"))

    def test_clean_drops_empty_items(self):
        data = {"experience": [{"role": "  Designer ", "dates": ""}, {"role": ""}], "sections": [{"after": "skills"}]}
        self.assertEqual(clean_cv(data), {"experience": [{"role": "Designer"}]})


class NamesTest(unittest.TestCase):
    def test_cv_names(self):
        for good in ("Jane Doe", "Jane Doe – Marketing", "Zoë O'Brien (2)", "a" * 80):
            self.assertEqual(check_cv_name(good), good)
        self.assertEqual(check_cv_name("  Jane   Doe "), "Jane Doe")
        self.assertEqual(check_cv_name("Jane\nDoe"), "Jane Doe")  # line breaks become spaces
        for bad in ("", "   ", ".hidden", "..", "a/b", "a\\b", "../cvs", "a:b", "a*b", 'a"b', "a<b>", "a|b", "a\x01b", "a" * 81):
            with self.assertRaises(ValueError, msg=bad):
                check_cv_name(bad)

    def test_language_codes(self):
        for good in ("en", "it", "fil", "en-ireland", "en-bigtech", "de-2025"):
            self.assertEqual(check_code(good), good)
        for bad in ("", "e", "EN", "english", "en_US", "en-", "en-Ireland", "../en", "en/x", None, 12):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                check_code(bad)

    def test_language_config(self):
        self.assertEqual(language_config("en")["content"], "content_en.toml")
        self.assertEqual(language_config("en-ireland")["name"], "English (Ireland)")
        self.assertEqual(base_language("en-ireland"), "en")


class ProfilesTest(DataDirTestCase):
    def test_new_cv(self):
        name = new_profile({"first_name": "Jane", "last_name": "Doe", "language": "it"})["profile"]
        self.assertEqual(name, "Jane Doe")
        profile = get_profile(name)
        self.assertEqual(list(languages(profile)), ["it"])
        data = load(profile, "content_it.toml")
        self.assertEqual(data["person"]["first_name"], "Jane")
        self.assertEqual(data["labels"]["experience"], KNOWN_LANGUAGES["it"]["labels"]["experience"])
        # a second CV with the same name gets another one
        self.assertEqual(new_profile({"first_name": "Jane", "last_name": "Doe"})["profile"], "Jane Doe (2)")
        self.assertEqual([x["name"] for x in list_profiles()["profiles"]], ["Jane Doe", "Jane Doe (2)"])

    def test_new_cv_rejects_bad_names(self):
        with self.assertRaises(RuntimeError):
            new_profile({"first_name": "../../etc", "last_name": "x"})
        self.assertEqual(profiles(), [])

    def test_missing_cv(self):
        with self.assertRaises(RuntimeError):
            get_profile("Nobody")

    def test_save_and_read_back(self):
        profile = self.import_example()
        data = read_data(profile)["languages"]["en"]["data"]
        data["person"]["headline"] = "Lead Designer"
        data["experience"].insert(0, {"role": "Lead Designer", "organization": "New Studio", "dates": "2025 – today",
                                      "description": ["Leads a team of five.", "Runs the design system."]})
        save({"profile": profile.name, "languages": {"en": data}})
        again = read_data(profile)["languages"]["en"]["data"]
        self.assertEqual(again["person"]["headline"], "Lead Designer")
        self.assertEqual(again["experience"][0]["organization"], "New Studio")
        self.assertEqual(clean_cv(again), clean_cv(data))

    def test_save_another_language_and_delete_it(self):
        profile = self.import_example()
        italian = read_data(profile)["languages"]["en"]["data"]
        italian["cv_language"] = {"name": "Italiano"}
        save({"profile": profile.name, "languages": {"en": read_data(profile)["languages"]["en"]["data"],
                                                             "it": italian}})
        self.assertEqual(list(languages(profile)), ["it", "en"])  # Italian and English first
        save({"profile": profile.name, "languages": {"en": italian}, "delete": ["it"]})
        self.assertEqual(list(languages(profile)), ["en"])

    def test_save_needs_a_language(self):
        profile = self.import_example()
        with self.assertRaises(RuntimeError):
            save({"profile": profile.name, "languages": {}})
        with self.assertRaises(RuntimeError):
            save({"profile": profile.name, "languages": {"EN": {}}})

    def test_settings(self):
        profile = self.import_example()
        save({"profile": profile.name, "languages": {"en": example_content()},
                     "settings": {"styles": {"modern": {"color": "burgundy"}, "swiss": {"color": "not a colour"}},
                                  "photos": {"me.jpg": {"x": 30, "y": 70, "zoom": 2, "shape": "circle"},
                                             "../evil.jpg": {"x": 1}}}})
        settings = load_settings(profile)
        self.assertEqual(settings["styles"]["modern"]["color"], "burgundy")
        self.assertEqual(settings["styles"]["swiss"]["color"], STYLES["swiss"]["color"])  # the style's own
        self.assertEqual(set(settings["styles"]), set(STYLES))
        self.assertEqual(settings["photos"], {"me.jpg": {"x": 30, "y": 70, "zoom": 2, "shape": "circle"}})

    def test_duplicate_and_delete(self):
        profile = self.import_example()
        copy = duplicate_profile({"profile": profile.name, "name": "Alex – Marketing"})["profile"]
        self.assertEqual(copy, "Alex – Marketing")
        self.assertEqual(load(get_profile(copy), "content_en.toml"), load(profile, "content_en.toml"))
        self.assertEqual(load_settings(get_profile(copy)), load_settings(profile))
        left = delete_profile({"profile": copy})["profiles"]
        self.assertEqual([x["name"] for x in left], [profile.name])
        self.assertFalse((workspace().cvs_dir / copy).exists())


if __name__ == "__main__":
    unittest.main()
