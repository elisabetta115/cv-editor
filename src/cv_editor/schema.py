"""The structure of a CV's content (content_<code>.toml), in one place: the parts of the file and their order, the
fixed sections, what can be hidden, and which fields are never translated. The modules that read, write and
translate a CV take these from here; the kinds of contact are in contacts.py."""
from .contacts import CONTACT_TYPES

# The parts of a content file, in the order they are written: "table" is one table ([person]), "list" a list of
# tables ([[experience]]). The title heads the part in the file.
PARTS = {
    "cv_language": ("table", "LANGUAGE OF THIS CV"),
    "labels": ("table", "SECTION TITLES AND LABELS"),
    "person": ("table", "NAME, HEADLINE AND INTRODUCTION"),
    "details": ("list", "PERSONAL DETAILS"),
    "contacts": ("list", "CONTACTS  (type: " + " | ".join(CONTACT_TYPES) + ";  icon: another icon, none = no icon)"),
    "experience": ("list", "EXPERIENCE"),
    "education": ("list", "EDUCATION"),
    "languages": ("list", "LANGUAGES"),
    "skills": ("table", "SKILLS"),
    "interests": ("table", "INTERESTS  (an empty line = new paragraph)"),
    "sections": ("list", "SECTIONS, in the order they appear in the CV  (builtin = a fixed section above; "
                         "hidden = not shown;  removed = a fixed section taken out of the CV)"),
    "privacy": ("table", "PRIVACY NOTE  (hidden = true: kept here, not shown in the CV; removed = true: deleted)"),
    "signature": ("table", "SIGNATURE"),
}
FILE_ORDER = list(PARTS)
FILE_TITLES = {k: title for k, (_, title) in PARTS.items()}
TABLES = [k for k, (kind, _) in PARTS.items() if kind == "table"]
LISTS_OF_TABLES = [k for k, (kind, _) in PARTS.items() if kind == "list"]

PERSON = ["first_name", "last_name", "headline", "profile", "about_me"]   # the fields of [person]
SKILL_LISTS = ["digital", "soft"]                                         # the lists of [skills]
SECTION_LISTS = ["list", "tags"]                                          # the lists of words of an extra section

# The fixed sections. Contacts and personal details sit in the header, unless they
# are placed in the sidebar of a style that shows one.
FIXED_SECTIONS = ["contacts", "details", "profile", "about_me", "experience", "education", "skills", "interests"]
# The CV has a sidebar, in every style, as soon as one section is placed in it; without one,
# every section is in the main column. These are suggested when the sidebar is switched on.
SIDEBAR_SUGGESTED = ["contacts", "details", "about_me", "skills"]
DEFAULT_AFTER = "skills"  # old files: extra sections without "after" go after the skills

# lists whose items (a personal detail, a contact, a job...) can be hidden with hidden = true:
# they stay in the file and in the editor, but not in the CV
HIDEABLE = ["details", "contacts", "experience", "education", "languages"]
HIDEABLE_IN_SECTIONS = ["entries", "rows"]
# the lines of these lists (a skill, a tag, a bullet point...) can be hidden one by one: their text is written in
# "<list>_hidden", e.g. digital = ["Excel", "Figma"] with digital_hidden = ["Excel"]
HIDEABLE_LINES = SKILL_LISTS + SECTION_LISTS + ["description"]

# Translation. Fields that are names, addresses or technical stay as they are written (an official name, such as
# Sapienza Università di Roma, is always right; a translated one may not be), and so do whole parts of the CV.
NOT_TRANSLATED = {"first_name", "last_name", "organization", "link", "type", "id", "builtin", "hidden", "column",
                  "after", "copied_from"}
NOT_TRANSLATED_PARTS = {"contacts", "cv_language"}
# what the text of a field is, told to the translator (so that "Native" is translated as a language level)
FIELD_KINDS = {"role": "job title", "location": "place", "grade": "final grade", "thesis": "thesis title",
               "language": "language name", "level": "language level", "digital": "digital skill", "soft": "soft skill",
               "list": "list item", "tags": "tag", "profile": "profile text"}
PART_KINDS = {"labels": "section title", "privacy": "privacy note", "interests": "interests"}
