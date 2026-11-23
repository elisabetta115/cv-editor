"""The structure of a CV (schema.py) and the kinds of contact (contacts.py) agree with each other and with the code
that uses them: a new part, section or kind of contact added in one place is not forgotten in another."""
import unittest

import support
from cv_editor.contacts import CONTACT_GROUPS, CONTACT_TYPES, HANDLE_LINKS, ICONS
from cv_editor.content import empty_cv, normalize
from cv_editor.language import KNOWN_LANGUAGES
from cv_editor.schema import (
    DEFAULT_AFTER, FIELD_KINDS, FILE_ORDER, FILE_TITLES, FIXED_SECTIONS, HIDEABLE, HIDEABLE_IN_SECTIONS, HIDEABLE_LINES,
    LISTS_OF_TABLES, NOT_TRANSLATED_PARTS, PART_KINDS, PARTS, PERSON, SECTION_LISTS, SIDEBAR_SUGGESTED, SKILL_LISTS,
    TABLES,
)
from cv_editor.storage import clean_cv, write_toml


class SchemaTest(unittest.TestCase):
    def test_parts(self):
        self.assertEqual(FILE_ORDER, list(PARTS))
        self.assertEqual(sorted(TABLES + LISTS_OF_TABLES), sorted(PARTS))
        self.assertTrue(all(kind in ("table", "list") and title for kind, title in PARTS.values()))
        for names in (HIDEABLE, NOT_TRANSLATED_PARTS, PART_KINDS):
            self.assertLessEqual(set(names), set(PARTS), names)
        self.assertLessEqual(set(HIDEABLE), set(LISTS_OF_TABLES))

    def test_sections(self):
        self.assertLessEqual(set(SIDEBAR_SUGGESTED), set(FIXED_SECTIONS))
        self.assertIn(DEFAULT_AFTER, FIXED_SECTIONS)
        self.assertEqual(HIDEABLE_LINES, SKILL_LISTS + SECTION_LISTS + ["description"])
        self.assertEqual(HIDEABLE_IN_SECTIONS, ["entries", "rows"])
        for key in SKILL_LISTS + SECTION_LISTS:
            self.assertIn(key, FIELD_KINDS)

    def test_a_file_follows_the_order_of_the_parts(self):
        data = normalize(support.example()["languages"]["en"], "en")
        data["signature"] = {"show": True}
        data = clean_cv(data)
        text = write_toml(data, "en")
        titles = [line[3:] for line in text.splitlines() if line.startswith("#  ") and line[3:] in FILE_TITLES.values()]
        # a part with content gets a block with its title; an empty one is a line (languages = []) without
        with_block = [k for k in FILE_ORDER if k in data and (isinstance(data[k], dict) or (
            isinstance(data[k], list) and data[k] and all(isinstance(x, dict) for x in data[k])))]
        self.assertEqual(titles, [FILE_TITLES[k] for k in with_block])
        self.assertIn("signature", with_block)
        self.assertIn(", ".join(f"{k}_hidden" for k in HIDEABLE_LINES), text)

    def test_empty_cv(self):
        cv = empty_cv("it", "Jane", "Doe")
        self.assertEqual(list(cv["person"]), PERSON)
        self.assertEqual((cv["person"]["first_name"], cv["person"]["last_name"]), ("Jane", "Doe"))
        self.assertEqual(list(cv["skills"]), SKILL_LISTS)
        self.assertEqual([k for k in cv if k in LISTS_OF_TABLES], [k for k in LISTS_OF_TABLES if k != "sections"])
        self.assertEqual(cv["labels"], KNOWN_LANGUAGES["it"]["labels"])


class ContactKindsTest(unittest.TestCase):
    def test_every_kind_has_a_name_and_an_icon(self):
        self.assertEqual(CONTACT_TYPES, [k for _, kinds in CONTACT_GROUPS for k in kinds])
        self.assertEqual(len(CONTACT_TYPES), len(set(CONTACT_TYPES)))
        for kind in CONTACT_TYPES:
            self.assertIn(kind, ICONS, f"{kind} has no icon")
        self.assertTrue(all(name.strip() for _, kinds in CONTACT_GROUPS for name in kinds.values()))
        self.assertLessEqual(set(HANDLE_LINKS), set(CONTACT_TYPES))

    def test_the_page_has_no_copy_of_them(self):
        """The editor's page receives the kinds of contact with the CV, instead of keeping its own list."""
        page = "".join(f.read_text(encoding="utf-8") for f in [support.SRC / "editor.html", *(support.SRC / "web").rglob("*.js")])
        self.assertNotRegex(page, r'"Stack Overflow"|stackoverflow: "')
        self.assertIn("setContactKinds(r.contact_groups)", page)


if __name__ == "__main__":
    unittest.main()
