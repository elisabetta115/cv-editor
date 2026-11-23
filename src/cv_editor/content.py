"""The content of a CV: reading it, the order of its sections, what is hidden."""
import copy
import sys

from .language import KNOWN_LANGUAGES, base_language, language_config


# ---------------------------------------------------------------------
#  Sections and their order
# ---------------------------------------------------------------------
# The fixed sections. Contacts and personal details sit in the header, unless they
# are placed in the sidebar of a style that shows one.
FIXED_SECTIONS = ["contacts", "details", "profile", "about_me", "experience", "education", "skills", "interests"]
# The CV has a sidebar, in every style, as soon as one section is placed in it; without one,
# every section is in the main column. These are suggested when the sidebar is switched on.
SIDEBAR_SUGGESTED = ["contacts", "details", "about_me", "skills"]
DEFAULT_AFTER = "skills"  # old files: extra sections without "after" go after the skills
EXTRA_PARTS = ["text", "entries", "list", "tags", "rows"]


def order_sections(cv, file):
    """The order of the CV sections: a list of
        {"kind": "builtin", "key": name, "hidden": bool, "side": bool}   fixed sections
        {"kind": "extra", "section": dict, "hidden": bool, "side": bool}  extra sections
    "side" = in the sidebar (the CV has a sidebar, in every style, when at least one section is in it).

    Files written by the editor list every section in [[sections]], fixed ones as
    {builtin = "experience"}, in the order chosen by the user; a fixed section taken out of the CV
    is {builtin = "interests", removed = true} and is not in the list. Older or hand-written files
    only list the extra sections, each placed after the section named in "after"."""
    def builtin(key, s=None):
        s = s or {}
        return {"kind": "builtin", "key": key, "hidden": bool(s.get("hidden")), "side": s.get("column") == "side"}

    def extra(s):
        return {"kind": "extra", "section": s, "hidden": bool(s.get("hidden")), "side": s.get("column") == "side"}

    sections = cv.get("sections", [])
    for s in sections:
        if "builtin" not in s:
            s.setdefault("title", "")
            if isinstance(s.get("list"), str):
                s["list"] = [s["list"]]
    if any("builtin" in s for s in sections):  # explicit order
        order, seen = [], set()
        for s in sections:
            if "builtin" not in s:
                order.append(extra(s))
            elif s["builtin"] in FIXED_SECTIONS and s["builtin"] not in seen:
                seen.add(s["builtin"])
                if not s.get("removed"):
                    order.append(builtin(s["builtin"], s))
        # fixed sections missing from the list (e.g. added in a newer version) are not lost:
        # each goes right after the fixed section that comes before it in FIXED_SECTIONS
        for i, k in enumerate(FIXED_SECTIONS):
            if k in seen:
                continue
            before = [j for j, x in enumerate(order) if x["kind"] == "builtin" and x["key"] in FIXED_SECTIONS[:i]]
            order.insert(before[-1] + 1 if before else 0, builtin(k))
            seen.add(k)
        return order

    names = {k: k for k in FIXED_SECTIONS}
    names.update({str(v).strip().lower(): k for k, v in cv["labels"].items() if k in FIXED_SECTIONS})
    order = [(k, None, builtin(k)) for k in FIXED_SECTIONS]  # (key, after, item)
    added = []
    for s in sections:
        after = str(s.get("after", DEFAULT_AFTER)).strip().lower()
        if after not in names:
            valid = ", ".join(FIXED_SECTIONS + [x["title"] for x in added])
            print(f"  ! {file}: section \"{s['title']}\": after = \"{s.get('after')}\" does not exist, "
                  f"putting it at the end.\n    Possible values: {valid}", file=sys.stderr)
        after = names.get(after, after)
        key = s["title"].strip().lower()
        names[key] = key
        added.append(s)
        # after the named section and after the extra sections already placed there
        spots = [j for j, (k, a, _) in enumerate(order) if after in (k, a)]
        order.insert(spots[-1] + 1 if spots else len(order), (key, after, extra(s)))
    return [x for _, _, x in order]


# ---------------------------------------------------------------------
#  Reading the content
# ---------------------------------------------------------------------
TABLES = ["cv_language", "labels", "person", "skills", "interests", "privacy", "signature"]
LISTS_OF_TABLES = ["details", "contacts", "experience", "education", "languages", "sections"]


def normalize(data, language="en"):
    """Gives the content the expected shape: tables are dicts, lists hold dicts, lists of
    words hold strings, missing section titles come from the language. Content written
    by hand or imported from someone else's file may be incomplete or malformed."""
    data = copy.deepcopy(data) if isinstance(data, dict) else {}
    for k in TABLES:
        if not isinstance(data.get(k), dict):
            data[k] = {}
    for k in LISTS_OF_TABLES:
        v = data.get(k)
        data[k] = [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []
    for k in ("digital", "soft"):
        v = data["skills"].get(k, [])
        data["skills"][k] = [str(x) for x in v if isinstance(x, (str, int, float))] if isinstance(v, list) else []
    for s in data["sections"]:
        if isinstance(s.get("entries"), list):
            s["entries"] = [e for e in s["entries"] if isinstance(e, dict)]
        elif "entries" in s:
            del s["entries"]
        if "list" in s and not isinstance(s["list"], (list, str)):
            del s["list"]
        if "tags" in s:
            s["tags"] = [str(x) for x in s["tags"] if isinstance(x, (str, int, float))] if isinstance(s["tags"], list) else []
        if "rows" in s:
            s["rows"] = [r for r in s["rows"] if isinstance(r, dict)] if isinstance(s["rows"], list) else []
        if "builtin" in s and s["builtin"] not in FIXED_SECTIONS:
            del s["builtin"]  # unknown fixed section: treat it as an (empty) extra section
    template = KNOWN_LANGUAGES.get(base_language(language), {}).get("labels") or KNOWN_LANGUAGES["en"]["labels"]
    data["labels"] = {**template, **{k: str(v) for k, v in data["labels"].items()}}
    return data


# lists whose items (a personal detail, a contact, a job...) can be hidden with hidden = true:
# they stay in the file and in the editor, but not in the CV
HIDEABLE = ["details", "contacts", "experience", "education", "languages"]
HIDEABLE_IN_SECTIONS = ["entries", "rows"]


def shown(items):
    return [x for x in items if not x.get("hidden")]


# the lines of a list (a skill, a bullet point, a tag...) can be hidden too: their text is written in
# "<list>_hidden", e.g. digital = ["Excel", "Figma"] with digital_hidden = ["Excel"]
def shown_lines(owner, key):
    hidden = owner.get(f"{key}_hidden")
    if not isinstance(hidden, list) or not hidden:
        return
    hide = {str(x).strip() for x in hidden}
    value = owner.get(key)
    if isinstance(value, str) and key != "description":  # a list of one line written as text
        value = [value]
    if isinstance(value, str):
        owner[key] = "" if value.strip() in hide else value
    elif isinstance(value, list):
        owner[key] = [x for x in value if str(x).strip() not in hide]


def prepare(data, file="content", language="en"):
    """A copy of the content read from the .toml file, ready to be rendered (hidden items left out)."""
    cv = normalize(data, language)
    for k in HIDEABLE:
        cv[k] = shown(cv[k])
    for s in cv["sections"]:
        for k in HIDEABLE_IN_SECTIONS:
            if isinstance(s.get(k), list):
                s[k] = shown(s[k])
    for k in ("digital", "soft"):
        shown_lines(cv["skills"], k)
    for s in cv["sections"]:
        for k in ("list", "tags"):
            shown_lines(s, k)
    for e in cv["experience"] + cv["education"] + [e for s in cv["sections"] for e in s.get("entries") or []]:
        shown_lines(e, "description")
    cv["digital_skills"] = cv["skills"]["digital"]
    cv["soft_skills"] = cv["skills"]["soft"]
    # hidden = true: the text is kept but not shown; removed = true: the note was deleted
    cv["privacy_text"] = "" if cv["privacy"].get("hidden") or cv["privacy"].get("removed") else cv["privacy"].get("text", "")
    cv["interests_text"] = cv["interests"].get("text", "")
    cv["signed"] = bool(cv["signature"].get("show"))  # the signature at the end of the CV (when there is one)
    cv["order"] = order_sections(cv, file)
    return cv


def empty_cv(language, first_name="", last_name=""):
    known = KNOWN_LANGUAGES.get(base_language(language), {})
    labels = known.get("labels") or KNOWN_LANGUAGES["en"]["labels"]
    return {"cv_language": {"name": language_config(language)["name"]}, "labels": dict(labels),
            "person": {"first_name": first_name, "last_name": last_name, "headline": "", "profile": "", "about_me": ""},
            "details": [], "contacts": [], "experience": [], "education": [], "languages": [],
            "skills": {"digital": [], "soft": []}, "interests": {"text": ""}, "privacy": {"text": ""}}
