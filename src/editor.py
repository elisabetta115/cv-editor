#!/usr/bin/env python3
"""
CV editor: opens in the browser.

    python3 editor.py              # open the editor
    python3 editor.py --install    # add "CV Editor" to the applications menu (Linux)

Edit the content on the left and see the CV update live on the right.
"Save" writes the cvs/<name>/content_<code>.toml files; "PDF" downloads the version on screen.
Every person has their own CV; CVs can be exported to and imported from a .json or a .zip file
(the .zip holds the same folders as cvs/).
The editor keeps running until you close the terminal window (or press Ctrl+C).
"""
import argparse
import base64
import binascii
import io
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import tempfile
import tomllib
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from datetime import date, datetime, time
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import generate_cv as cv
import translator

HERE = cv.HERE
ROOT = HERE.parent
PORT = 8765
TOKEN = secrets.token_urlsafe(24)
CODE_FILES = [HERE / "editor.py", HERE / "generate_cv.py", HERE / "translator.py"]
CODE_VERSION = [f.stat().st_mtime_ns for f in CODE_FILES]  # to notice when the code is updated while running
UPDATED_PAGE = """<!doctype html><meta charset="utf-8"><title>CV Editor</title>
<body style="font: 16px system-ui, sans-serif; margin: 15vh auto; max-width: 34em; line-height: 1.5">
<h1 style="font-size: 22px">The CV editor has been updated</h1>
<p>Close the small terminal window of the editor and open <b>CV Editor</b> again.</p></body>"""
LOCK = threading.Lock()            # one file operation at a time
EXPORT_FORMAT = "cv-editor"        # marks the example .json file (and those exported by older versions)
MAX_PHOTO_BYTES = 15_000_000


# Folders the browser may read (nothing else)
def static_folders():
    return {"/styles/": HERE / "styles", "/fonts/": HERE / "fonts", "/html/": cv.workspace().html_dir}


# ---------------------------------------------------------------------
#  Writing the .toml files
# ---------------------------------------------------------------------
FILE_ORDER = ["cv_language", "labels", "person", "details", "contacts", "experience", "education", "languages",
              "skills", "interests", "sections", "privacy"]
FILE_TITLES = {
    "cv_language": "LANGUAGE OF THIS CV", "labels": "SECTION TITLES AND LABELS",
    "person": "NAME, HEADLINE AND INTRODUCTION", "details": "PERSONAL DETAILS",
    "contacts": "CONTACTS  (type: " + " | ".join(cv.CONTACT_TYPES) + ";  icon: another icon, none = no icon)",
    "experience": "EXPERIENCE", "education": "EDUCATION", "languages": "LANGUAGES", "skills": "SKILLS",
    "interests": "INTERESTS  (an empty line = new paragraph)",
    "sections": "SECTIONS, in the order they appear in the CV  (builtin = a fixed section above; hidden = not shown;"
                "  removed = a fixed section taken out of the CV)",
    "privacy": "PRIVACY NOTE  (hidden = true: kept here, not shown in the CV; removed = true: deleted)",
}
FILE_HEADER = ["The easiest way to edit it is the editor:",
               "    python3 src/editor.py      (or \"CV Editor\" from the applications menu)",
               "You can still edit it by hand; in the text you can use **bold** and *italic*.",
               "hidden = true in a detail, contact, job, degree, language or row: kept here, not shown in the CV.",
               "digital_hidden, soft_hidden, list_hidden, tags_hidden, description_hidden: the lines of that list",
               "    kept here but not shown in the CV."]


def _key(k):
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k, ensure_ascii=False)


def _string(v):
    if "\n" in v:
        body = v.replace("\r", "").replace("\\", "\\\\").replace('"', '\\"')
        body = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", lambda m: f"\\u{ord(m.group()):04x}", body)
        return f'"""\n{body}\n"""'
    return json.dumps(v, ensure_ascii=False).replace("\x7f", "\\u007f")


def _value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return _string(v)
    if isinstance(v, list):
        items = [_value(x) for x in v]
        line = "[" + ", ".join(items) + "]"
        if len(line) <= 72 and "\n" not in line:
            return line
        return "[\n" + "".join(f"  {x},\n" for x in items) + "]"
    raise ValueError(f"Unsupported value: {v!r}")


def _list_of_tables(v):
    return isinstance(v, list) and v and all(isinstance(x, dict) for x in v)


def _table(lines, name, d, array=False):
    lines.append(f"[[{name}]]" if array else f"[{name}]")
    simple = [(k, v) for k, v in d.items() if not isinstance(v, dict) and not _list_of_tables(v)]
    width = max((len(_key(k)) for k, _ in simple), default=0)
    for k, v in simple:
        lines.append(f"{_key(k).ljust(width)} = {_value(v)}")
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append("")
            _table(lines, f"{name}.{_key(k)}", v)
        elif _list_of_tables(v):
            for x in v:
                lines.append("")
                _table(lines, f"{name}.{_key(k)}", x, array=True)


def write_toml(data, language):
    rule = "# " + "-" * 69
    name = (data.get("cv_language") or {}).get("name") or cv.language_config(language)["name"]
    header = [f"CURRICULUM — CONTENT IN {name.upper()}", ""] + FILE_HEADER
    lines = [rule] + [f"#  {r}" if r else "#" for r in header] + [rule]
    keys = [k for k in FILE_ORDER if k in data] + [k for k in data if k not in FILE_ORDER]
    simple = [k for k in keys if not isinstance(data[k], dict) and not _list_of_tables(data[k])]
    if simple:
        lines.append("")
        lines += [f"{_key(k)} = {_value(data[k])}" for k in simple]
    for k in keys:
        if k in simple:
            continue
        lines += ["", "", rule, f"#  {FILE_TITLES.get(k, k.upper())}", rule]
        if isinstance(data[k], dict):
            _table(lines, _key(k), data[k])
        else:
            for i, x in enumerate(data[k]):
                if i:
                    lines.append("")
                _table(lines, _key(k), x, array=True)
    return "\n".join(lines) + "\n"


def clean(v, in_list=False):
    """Trims spaces; inside list items drops empty fields and items left completely empty."""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        out = [clean(x, True) for x in v]
        return [x for x in out if x not in ("", [], {})]
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if x is None or k.startswith("_"):
                continue
            x = clean(x, in_list)
            if in_list and x in ("", [], {}):
                continue
            out[k] = x
        return out
    return v


def clean_cv(data):
    data = clean(data)
    if isinstance(data.get("sections"), list):  # extra sections left empty are not saved
        data["sections"] = [s for s in data["sections"] if isinstance(s, dict) and set(s) - {"after"}]
    for k in ("sections", "cv_language"):  # optional: not written when empty
        if k in data and not data[k]:
            del data[k]
    return data


def save_settings(profile, settings):
    """Writes settings.toml: the colour chosen for each style and the framing of each photo."""
    lines = ["# Styles of this CV: chosen in the editor (python3 src/editor.py).",
             "#   color   = " + " | ".join(cv.COLORS),
             "# Photos: how each one is framed, in every style.",
             "#   x, y    = 0-100 (0 = left / top edge of the photo, 100 = right / bottom edge)",
             f"#   zoom    = 1 (the whole photo) to {cv.MAX_ZOOM}",
             "#   shape   = " + " | ".join(cv.SHAPES) + "   (without it: the shape of each style)",
             ""]
    settings = settings if isinstance(settings, dict) else {}
    styles = settings.get("styles") if isinstance(settings.get("styles"), dict) else {}
    for style, conf in cv.STYLES.items():
        x = styles.get(style) if isinstance(styles.get(style), dict) else {}
        color = x.get("color") if x.get("color") in cv.COLORS else conf["color"]
        lines += [f"[styles.{style}]", f'color = "{color}"', ""]
    photos = settings.get("photos") if isinstance(settings.get("photos"), dict) else {}
    for name, value in sorted(photos.items()):
        frame = cv.photo_frame(value)
        if frame and isinstance(name, str) and cv.PHOTO_NAME.fullmatch(name):
            lines += [f"[photos.{_key(name)}]"]
            lines += [f"{k} = {frame[k]:g}" for k in ("x", "y", "zoom") if k in frame]
            lines += [f'shape = "{frame["shape"]}"'] if "shape" in frame else []
            lines += [""]
    profile.dir.mkdir(parents=True, exist_ok=True)
    profile.settings_file.write_text("\n".join(lines), encoding="utf-8")


def check_code(language):
    """A language (en) or another version in a language (en-ireland)."""
    if not isinstance(language, str) or not cv.VERSION_CODE.fullmatch(language):
        raise RuntimeError(f"Invalid language code: {language!r} (2 or 3 lowercase letters, e.g. es, fr, de).")
    return language


def save_language(profile, language, data):
    check_code(language)
    data = clean_cv(data)
    text = write_toml(data, language)
    if clean_cv(tomllib.loads(text)) != data:  # check: the file reads back identical
        raise RuntimeError("The file check failed: nothing was saved.")
    profile.dir.mkdir(parents=True, exist_ok=True)
    path = profile.dir / cv.language_config(language)["content"]
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


# ---------------------------------------------------------------------
#  CVs (one per person)
# ---------------------------------------------------------------------
def get_profile(name, must_exist=True):
    try:
        profile = cv.Profile(name)
    except ValueError as e:
        raise RuntimeError(str(e))
    if must_exist and not profile.exists():
        raise RuntimeError(f"There is no CV called \"{profile.name}\".")
    return profile


def free_name(name):
    """The name itself, or "Name (2)", "Name (3)"... if a CV with that name already exists."""
    base = cv.check_cv_name(name)
    candidate, n = base, 2
    while (cv.workspace().cvs_dir / candidate).exists():
        candidate = f"{base} ({n})"
        n += 1
    return candidate


def remove_profile_files(profile):
    """Deletes a CV: its folder in cvs/, its PDFs and its generated pages."""
    place = cv.workspace()
    for folder, parent in ((profile.dir, place.cvs_dir), (profile.pdf_dir, place.pdf_dir), (profile.html_dir, place.html_dir)):
        if folder.is_dir() and folder.resolve().parent == parent.resolve():
            shutil.rmtree(folder)


def empty_cv(language, first_name="", last_name=""):
    known = cv.KNOWN_LANGUAGES.get(cv.base_language(language), {})
    labels = known.get("labels") or cv.KNOWN_LANGUAGES["en"]["labels"]
    return {"cv_language": {"name": cv.language_config(language)["name"]}, "labels": dict(labels),
            "person": {"first_name": first_name, "last_name": last_name, "headline": "", "profile": "", "about_me": ""},
            "details": [], "contacts": [], "experience": [], "education": [], "languages": [],
            "skills": {"digital": [], "soft": []}, "interests": {"text": ""}, "privacy": {"text": ""}}


def list_profiles():
    return {"profiles": [{"name": x.name, "languages": list(cv.languages(x))} for x in cv.profiles()]}


def new_profile(r):
    first, last = str(r.get("first_name") or "").strip(), str(r.get("last_name") or "").strip()
    language = check_code(r.get("language") or "en")
    try:
        profile = cv.Profile(free_name(f"{first} {last}"))
    except ValueError:
        raise RuntimeError("Write a first and last name without special characters such as / \\ : * ? \" < > |.")
    save_language(profile, language, empty_cv(language, first, last))
    save_settings(profile, {})
    return {"profile": profile.name}


def delete_profile(r):
    profile = get_profile(r.get("profile"))
    remove_profile_files(profile)  # the last one too: the editor then shows its welcome screen
    return list_profiles()


def duplicate_profile(r):
    """r = {"profile", "name", "languages": [codes] (empty: all), "photos": bool}: a copy of a CV, as saved,
    under a new name ("Name (2)"... if it is taken), to change without touching the original."""
    source = get_profile(r.get("profile"))
    langs = cv.languages(source)
    wanted = r.get("languages") or list(langs)
    if not isinstance(wanted, list) or not wanted or any(code not in langs for code in wanted):
        raise RuntimeError("Choose at least one language of the CV to copy.")
    try:
        target = cv.Profile(free_name(str(r.get("name") or "").strip() or source.name))
    except ValueError:
        raise RuntimeError("Write a name without special characters such as / \\ : * ? \" < > |.")
    try:
        target.dir.mkdir(parents=True)
        for code in wanted:
            shutil.copy2(source.dir / langs[code]["content"], target.dir / langs[code]["content"])
        if source.settings_file.is_file():
            shutil.copy2(source.settings_file, target.settings_file)
        if cv.signature_file(source):
            shutil.copy2(cv.signature_file(source), target.dir / cv.signature_file(source).name)
        for f in cv.find_photos(source) if r.get("photos", True) else []:
            target.photo_dir.mkdir(exist_ok=True)
            shutil.copy2(f, target.photo_dir / f.name)
    except Exception:
        remove_profile_files(target)  # no half-made copies
        raise
    return {"profile": target.name}


# ---------------------------------------------------------------------
#  The example CV (.json): read by "Try the example"
# ---------------------------------------------------------------------


def suggested_name(data):
    """The name of the CV in an exported file, or the person's name in its first language."""
    name = data.get("name") if isinstance(data.get("name"), str) else ""
    if not name.strip():
        for content in (data.get("languages") or {}).values():
            person = content.get("person") if isinstance(content, dict) else None
            if isinstance(person, dict):
                name = f"{person.get('first_name') or ''} {person.get('last_name') or ''}"
                if name.strip():
                    break
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name or "").strip(" .")
    return " ".join(name.split())[:80] or "Imported CV"


def write_photo(profile, name, content):
    name = Path(unquote(str(name or ""))).name
    ext = Path(name).suffix.lower()
    if ext in cv.CONVERT_FIRST_EXTENSIONS:
        raise RuntimeError(f"{name}: browsers cannot read this format. Save it as JPG or PNG first.")
    if ext not in cv.PHOTO_EXTENSIONS or name.startswith("."):
        raise RuntimeError(f"{name}: this does not look like a photo (JPG, PNG and WEBP work).")
    if len(content) > MAX_PHOTO_BYTES:
        raise RuntimeError(f"{name}: the photo is too large.")
    profile.photo_dir.mkdir(parents=True, exist_ok=True)
    target, n = profile.photo_dir / name, 2
    while target.exists():
        target = profile.photo_dir / f"{Path(name).stem}-{n}{ext}"
        n += 1
    target.write_bytes(content)
    return target.name


def from_export(data):
    """The CV in an exported .json file, checked and decoded (nothing is written yet)."""
    if not isinstance(data, dict) or data.get("format") != EXPORT_FORMAT:
        raise RuntimeError("This is not a CV file exported by the CV editor.")
    langs = data.get("languages")
    if not isinstance(langs, dict) or not langs or not all(isinstance(v, dict) for v in langs.values()):
        raise RuntimeError("The file contains no CV content.")
    for code in langs:
        check_code(code)
    photos = []
    for x in data.get("photos") or []:
        if not isinstance(x, dict):
            continue
        m = re.fullmatch(r"data:image/[\w.+-]+;base64,(.+)", str(x.get("data") or ""), re.S)
        try:
            content = base64.b64decode(m.group(1), validate=True) if m else b""
        except (binascii.Error, ValueError):
            content = b""
        if not content:
            raise RuntimeError(f"The photo {x.get('name')!r} in the file is damaged.")
        photos.append((x.get("name"), content))
    return {"name": suggested_name(data), "languages": langs, "settings": data.get("settings"), "photos": photos}


def import_cv(r):
    """r = {"data": <exported .json file>, "mode": "check" | "replace" | "copy"}"""
    return import_cvs([from_export(r.get("data"))], r.get("mode"))


def import_zip(body, mode):
    """A .zip file: the cvs folder (or one CV's folder) zipped, as "Export .zip" makes it."""
    return import_cvs(read_zip(body), mode)


def import_cvs(found, mode):
    """Adds the CVs read from an imported file.
    mode "check": only says which ones already exist; "replace": those are overwritten; "copy": kept, the
    imported one gets another name. Every CV is written under a new name first, and the old one is replaced
    only when all of them were written: a failed import leaves the CVs as they were."""
    if mode == "check":
        return {"cvs": [{"name": x["name"], "exists": (cv.workspace().cvs_dir / x["name"]).exists()} for x in found]}
    written = []
    try:
        for x in found:
            written.append((x["name"], write_new_cv(x)))
    except Exception:
        for _, profile in written:
            remove_profile_files(profile)  # all or nothing
        raise
    names = []
    for name, profile in written:
        if mode == "replace" and profile.name != name and name not in names:
            old = cv.Profile(name)
            remove_profile_files(old)
            profile.dir.rename(old.dir)
            profile = old
        names.append(profile.name)
    return {"profiles": names}


def write_new_cv(x):
    """Writes an imported CV in a new folder (its own name, or "Name (2)"...). Content is normalised and rewritten."""
    profile = cv.Profile(free_name(x["name"]))
    try:
        for code, content in x["languages"].items():
            content = cv.normalize(content, code)
            content["cv_language"] = {"name": cv.language_config(code, content["cv_language"])["name"]}
            save_language(profile, code, content)
        save_settings(profile, x["settings"])
        for photo_name, content in x["photos"]:
            write_photo(profile, photo_name, content)
        if x.get("signature"):
            write_signature(profile, *x["signature"])
    except Exception:
        remove_profile_files(profile)  # no half-imported CVs
        raise
    return profile


# ---------------------------------------------------------------------
#  Export and import (.zip): the same folders as cvs/
# ---------------------------------------------------------------------
MAX_ZIP_FILES = 5000
MAX_ZIP_BYTES = 200_000_000         # unzipped
MAX_CONTENT_BYTES = 5_000_000       # one content_<code>.toml or settings.toml
CONTENT_FILE = re.compile(r"content_([a-z]{2,3}(?:-[a-z0-9]{1,24})?)\.toml")
SIGNATURE_FILE = re.compile(r"signature\.(png|jpe?g|webp|gif|avif|bmp)", re.IGNORECASE)


def export_zip(profiles, with_photos=True):
    """The CVs as a .zip laid out like the cvs folder: cvs/<name>/content_<code>.toml, settings.toml, photos/."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as z:
        for profile in profiles:
            folder = f"cvs/{profile.name}/"
            files = [profile.dir / conf["content"] for conf in cv.languages(profile).values()]
            for f in files + [profile.settings_file, cv.signature_file(profile)]:
                if f and f.is_file():
                    z.write(f, folder + f.name)
            for f in cv.find_photos(profile) if with_photos else []:  # the originals: photos are already compressed
                z.write(f, folder + "photos/" + f.name, zipfile.ZIP_STORED)
    return buffer.getvalue()


def zip_path(info):
    """A file's path in a .zip as a tuple of names. Zips made on Windows may not say that names are UTF-8."""
    name = info.filename
    if not info.flag_bits & 0x800:
        try:
            name = name.encode("cp437").decode("utf-8")
        except UnicodeError:
            pass
    return tuple(p for p in name.replace("\\", "/").split("/") if p not in ("", "."))


def plain(v):
    """TOML dates and times as text, like everything else in the editor."""
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [plain(x) for x in v]
    return v.isoformat() if isinstance(v, (date, time)) else v


def read_zip(body):
    """The CVs in a .zip file: every folder holding content_<code>.toml files is one CV, named after the
    folder; its settings.toml and photos/ come with it. Only read, nothing is written: the paths in the
    .zip are never used to write files."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(body))
        infos = archive.infolist()
    except (zipfile.BadZipFile, OSError, ValueError):
        raise RuntimeError("This is not a valid .zip file.")
    if len(infos) > MAX_ZIP_FILES or sum(i.file_size for i in infos) > MAX_ZIP_BYTES:
        raise RuntimeError("The .zip file is too large.")
    files = {}
    for info in infos:
        parts = zip_path(info)
        # no folders, hidden files or the extra files macOS adds
        if parts and not info.is_dir() and not any(p.startswith(".") or p == "__MACOSX" for p in parts):
            files[parts] = info

    def read(parts, limit, what):
        info = files[parts]
        if info.file_size > limit:
            raise RuntimeError(f"{'/'.join(parts)}: the {what} is too large.")
        try:
            with archive.open(info) as f:
                return f.read(limit)
        except Exception:
            raise RuntimeError(f"{'/'.join(parts)} cannot be read: the .zip file is damaged or protected by a password.")

    def read_toml(parts):
        try:
            return plain(tomllib.loads(read(parts, MAX_CONTENT_BYTES, "file").decode("utf-8-sig")))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
            raise RuntimeError(f"{'/'.join(parts)} is not a valid content file: {e}")

    folders = sorted({p[:-1] for p in files if CONTENT_FILE.fullmatch(p[-1])})
    if not folders:
        raise RuntimeError("There is no CV in this .zip file: it should contain the folder of a CV, "
                           "with its content_en.toml (or another language) files.")
    found = []
    for folder in folders:
        langs = {CONTENT_FILE.fullmatch(p[-1]).group(1): read_toml(p) for p in files
                 if p[:-1] == folder and CONTENT_FILE.fullmatch(p[-1])}
        settings = {}
        if folder + ("settings.toml",) in files:
            try:
                settings = read_toml(folder + ("settings.toml",))
            except RuntimeError:
                pass  # not valid: the default colours
        photos = [(p[-1], read(p, MAX_PHOTO_BYTES, "photo")) for p in sorted(files)
                  if p[:-1] == folder + ("photos",) and Path(p[-1]).suffix.lower() in cv.PHOTO_EXTENSIONS]
        name = suggested_name({"name": folder[-1] if folder else "", "languages": langs})
        signature = next(((p[-1], read(p, MAX_PHOTO_BYTES, "signature")) for p in sorted(files)
                          if p[:-1] == folder and SIGNATURE_FILE.fullmatch(p[-1])), None)
        found.append({"name": name, "languages": langs, "settings": settings, "photos": photos, "signature": signature})
    return found


# ---------------------------------------------------------------------
#  Actions called by the editor
# ---------------------------------------------------------------------
def refresh_photos(profile):
    photos = cv.find_photos(profile)
    paths = cv.prepare_photos(profile, photos)
    cv.workspace().photo_src[profile.name] = {f.name: src for f, src in paths.items()}
    base = "/html/" + quote(profile.name) + "/"
    return [{"name": f.name, "src": base + paths[f]} for f in photos]


def delete_language(profile, language):
    """Removes the content file of a language, its PDFs and its HTML pages."""
    conf = cv.languages(profile).get(check_code(language))
    if not conf:
        return
    (profile.dir / conf["content"]).unlink(missing_ok=True)
    folder = profile.pdf_dir / conf["folder"]
    for pdf in folder.glob("CV_*.pdf"):
        pdf.unlink()
    try:
        folder.rmdir()  # only if it is now empty
    except OSError:
        pass
    for page in profile.html_dir.glob(f"CV_*_{language.upper()}_*.html"):
        page.unlink()


def read_data(profile):
    langs = {}
    for code, conf in cv.languages(profile).items():
        data = cv.normalize(cv.load(profile, conf["content"]), code)
        prepared = cv.prepare(data, conf["content"], code)
        # section order: {"builtin", "hidden", "side"} for the fixed sections,
        # the index in "sections" for the extra ones
        order = [{"builtin": x["key"], "hidden": x["hidden"], "side": x["side"]} if x["kind"] == "builtin"
                 else next(i for i, s in enumerate(prepared["sections"]) if s is x["section"])
                 for x in prepared["order"]]
        langs[code] = {"name": conf["name"], "data": data, "order": order}
    return {"profile": profile.name, "languages": langs, "photos": refresh_photos(profile), "signature": signature_url(profile),
            "styles": [{"id": k, "name": v["name"], "group": v["group"], "color": v["color"], "side": v["side"],
                        "tags": v["tags"], "description": v["description"]} for k, v in cv.STYLES.items()],
            "style_groups": cv.STYLE_GROUPS,
            "fixed_sections": cv.FIXED_SECTIONS,
            "sidebar_suggested": cv.SIDEBAR_SUGGESTED,
            "colors": cv.COLORS, "settings": cv.load_settings(profile), "can_zoom": cv.can_zoom(),
            "icons": {k: v for k, v in cv.ICONS.items() if k != "link"},  # the icons a contact can have
            "templates": [{"code": k, "name": v["name"], "labels": v.get("labels")}
                          for k, v in cv.KNOWN_LANGUAGES.items()]}


def view(r):
    """What the editor shows: CV, language, style, colour and photo (content not saved yet included)."""
    profile = get_profile(r.get("profile"))
    language, style = check_code(r.get("language")), r.get("style")
    if style not in cv.STYLES:
        raise RuntimeError(f"Unknown style: {style!r}")
    prepared = cv.prepare(clean_cv(r.get("data") or {}), cv.language_config(language)["content"], language)
    if profile.name not in cv.workspace().photo_src:
        refresh_photos(profile)
    photo = r.get("photo") or ""
    color = r.get("color") if r.get("color") in cv.COLORS else None
    src = cv.workspace().photo_src[profile.name].get(photo)
    frame = cv.photo_frame(r.get("frame")) if src else None  # how the photo is framed (not saved yet included)
    signature = cv.signature_src(profile)  # shown only when the content asks for it ([signature] show = true)
    return profile, language, style, prepared, cv.framed_photo(profile, src, frame), photo, color, frame, signature


def preview(r):
    profile, language, style, prepared, src, _, color, frame, signature = view(r)
    base = "/html/" + quote(profile.name) + "/"
    return {"document": cv.document(prepared, language, style, src, preview_base=base, color=color, frame=frame, signature=signature),
            "page": cv.render_page(prepared, style, src, frame, signature), "sidebar": cv.has_sidebar(prepared)}


def pdf_name(person, language):
    """The name of a downloaded PDF: CV_<first name>_<last name>_<LANGUAGE>.pdf, e.g. CV_Jane_Doe_EN.pdf
    (other versions in a language too: the person who receives it does not need to know)."""
    parts = ["CV", str(person.get("first_name") or ""), str(person.get("last_name") or ""), cv.base_language(language).upper()]
    name = "_".join(x for x in (re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", p).strip() for p in parts) if x)
    return re.sub(r"\s+", "_", name) + ".pdf"


def make_pdf(r):
    """The PDF of exactly what the editor shows. Returns (file name, PDF bytes)."""
    profile, language, style, prepared, src, _, color, frame, signature = view(r)
    name = pdf_name(prepared["person"], language)
    profile.html_dir.mkdir(parents=True, exist_ok=True)
    tag = secrets.token_hex(6)
    page, pdf = profile.html_dir / f"_view_{tag}.html", profile.html_dir / f"_view_{tag}.pdf"
    try:
        page.write_text(cv.document(prepared, language, style, src, color=color, frame=frame, signature=signature), encoding="utf-8")
        cv.print_pdf(cv.find_chrome(), page, pdf)
        return name, pdf.read_bytes()
    finally:
        page.unlink(missing_ok=True)
        pdf.unlink(missing_ok=True)


def save(r):
    """r = {"profile": name, "languages": {code: content}, "delete": [codes], "settings": {...}}"""
    profile = get_profile(r.get("profile"))
    to_save = r.get("languages") or {}
    if not to_save:
        raise RuntimeError("The CV must have at least one language.")
    for language in to_save:
        check_code(language)
    for language in r.get("delete") or []:
        if language not in to_save:
            delete_language(profile, language)
    for language, data in to_save.items():
        save_language(profile, language, data)
    if "settings" in r:
        save_settings(profile, r["settings"])
    return {"saved": True}


def add_photo(profile_name, name, content):
    profile = get_profile(unquote(profile_name or ""))
    saved = write_photo(profile, name, content)
    return {"photos": refresh_photos(profile), "name": saved}


def delete_photo(r):
    profile = get_profile(r.get("profile"))
    names = {f.name: f for f in cv.find_photos(profile)}
    if r.get("name") not in names:
        raise RuntimeError("Photo not found.")
    names[r["name"]].unlink()
    return {"photos": refresh_photos(profile)}


# ---------------------------------------------------------------------
#  The signature: cvs/<name>/signature.png
# ---------------------------------------------------------------------
SIGNATURE_MAX_SIZE = (1200, 600)   # pixels: more than enough for a signature 5 cm wide


def pdf_to_png(content):
    """The first page of a PDF as a PNG, with Poppler, MuPDF or Ghostscript (whichever is installed)."""
    tools = [("pdftoppm", lambda src, out: ["-png", "-r", "300", "-f", "1", "-l", "1", "-singlefile", src, out[:-4]]),
             ("mutool", lambda src, out: ["draw", "-q", "-r", "300", "-o", out, src, "1"]),
             ("gs", lambda src, out: ["-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=png16m", "-r300",
                                      "-dFirstPage=1", "-dLastPage=1", f"-sOutputFile={out}", src])]
    found = [(shutil.which(tool), args) for tool, args in tools if shutil.which(tool)]
    if not found:
        raise RuntimeError("To use a PDF the editor needs Poppler (on Linux: sudo apt install poppler-utils). "
                           "Or save the signature as PNG or JPG: a photo or a scan of it works.")
    with tempfile.TemporaryDirectory() as folder:
        src, out = str(Path(folder) / "signature.pdf"), str(Path(folder) / "page.png")
        Path(src).write_bytes(content)
        for exe, args in found:
            try:
                subprocess.run([exe, *args(src, out)], check=True, timeout=60,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return Path(out).read_bytes()
            except (subprocess.SubprocessError, OSError):
                continue
    raise RuntimeError("This PDF cannot be read. Save the signature as PNG or JPG instead.")


def cut_out_signature(content):
    """The signature cut out of the photo, scan or page it is on (needs Pillow): the paper becomes transparent,
    the ink stays, and the image is cropped around it. Returns PNG bytes."""
    from PIL import Image, ImageChops, ImageFilter, ImageOps
    try:
        with Image.open(io.BytesIO(content)) as im:
            im.load()
            im = ImageOps.exif_transpose(im)
            transparent = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
            rgba = im.convert("RGBA")
    except Exception:
        raise RuntimeError("This file cannot be read as an image: save the signature as PNG or JPG.")
    alpha = rgba.getchannel("A")
    if not (transparent and alpha.getextrema()[0] < 250):  # on paper: the ink is what is darker than the paper around it
        gray = rgba.convert("L")
        # the paper: the brightest around each point (shadows and uneven light in a photo are paper too)
        small = gray.resize((max(1, gray.width // 16), max(1, gray.height // 16)), Image.BILINEAR).filter(ImageFilter.MaxFilter(5))
        paper = small.resize(gray.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))
        ink = ImageChops.subtract(paper, gray)
        alpha = ink.point(lambda v: 0 if v < 28 else 255 if v > 90 else (v - 28) * 255 // 62)
        rgba.putalpha(alpha)
    box = alpha.point(lambda v: 255 if v > 40 else 0).getbbox()
    if not box:
        raise RuntimeError("No signature found in this file: it looks empty.")
    pad = max(6, (box[2] - box[0]) // 30)
    rgba = rgba.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(rgba.width, box[2] + pad), min(rgba.height, box[3] + pad)))
    rgba.thumbnail(SIGNATURE_MAX_SIZE, Image.LANCZOS)
    out = io.BytesIO()
    rgba.save(out, "PNG", optimize=True)
    return out.getvalue()


def write_signature(profile, name, content):
    """Saves the signature of a CV (in place of the one it had): an image (PNG, JPG...) or a PDF (its first page).
    With Pillow it is cut out of its background; without it, an image is kept as it is."""
    ext = Path(unquote(str(name or ""))).suffix.lower()
    if ext not in cv.PHOTO_EXTENSIONS | {".pdf"}:
        raise RuntimeError("Choose an image (PNG, JPG) or a PDF of your signature.")
    if len(content) > MAX_PHOTO_BYTES:
        raise RuntimeError("The file is too large.")
    if ext == ".pdf":
        if not cv.can_zoom():
            raise RuntimeError("To use a PDF the editor needs Pillow (pip install pillow). Or save the signature as PNG or JPG.")
        content, ext = pdf_to_png(content), ".png"
    if cv.can_zoom():
        content, ext = cut_out_signature(content), ".png"
    profile.dir.mkdir(parents=True, exist_ok=True)
    for old in profile.dir.glob("signature.*"):
        old.unlink()
    (profile.dir / f"signature{ext}").write_bytes(content)


def signature_url(profile):
    """The address of the signature for the editor, None when the CV has none."""
    src = cv.signature_src(profile)
    return "/html/" + quote(profile.name) + "/" + src if src else None


def add_signature(profile_name, name, content):
    profile = get_profile(unquote(profile_name or ""))
    write_signature(profile, name, content)
    return {"signature": signature_url(profile)}


def delete_signature(r):
    profile = get_profile(r.get("profile"))
    for f in list(profile.dir.glob("signature.*")) + list(profile.html_dir.glob("signature-*")):
        f.unlink(missing_ok=True)
    return {"signature": None}


ACTIONS = {
    "/api/preview": preview,
    "/api/save": save,
    "/api/photos/delete": delete_photo,
    "/api/signature/delete": delete_signature,
    "/api/cvs/new": new_profile,
    "/api/cvs/delete": delete_profile,
    "/api/cvs/duplicate": duplicate_profile,
    "/api/import": import_cv,
    "/api/translate": translator.translate_cv,   # {data, from, to, engine}: the content translated (local AI or Azure)
    "/api/translator": translator.set_key,       # {key, region}: checks and keeps the key (empty: removes it)
}
NO_WAIT = {"/api/preview", "/api/translate", "/api/translator"}  # no CV files touched: no need to wait for the lock


# ---------------------------------------------------------------------
#  Local server (reachable only from this computer)
# ---------------------------------------------------------------------
def download(profile, ext):
    """Content-Disposition of an exported file: cv-<name>.json / .zip, or cvs.zip for every CV."""
    name = "cvs"
    if profile:
        name = "cv-" + (re.sub(r"[^\w-]+", "-", profile.name.lower()).strip("-") or "cv")
    return "Content-Disposition", f'attachment; filename="{quote(name)}{ext}"'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _send(self, status, body, content_type, extra_headers=()):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra_headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status=200, extra_headers=()):
        self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", extra_headers)

    def _allowed(self, need_token=True):
        # no requests from other websites: local host and the editor's secret token
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return False
        return not need_token or secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def do_GET(self):
        url = urlparse(self.path)
        path, query = unquote(url.path), parse_qs(url.query)
        if path == "/api/ping":
            return self._json({"editor": "curriculum"})
        if not self._allowed(need_token=False):
            return self._send(403, b"", "text/plain")
        if path == "/":
            if [f.stat().st_mtime_ns for f in CODE_FILES] != CODE_VERSION:
                return self._send(200, UPDATED_PAGE.encode(), "text/html; charset=utf-8")
            page = (HERE / "editor.html").read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
            return self._send(200, page.encode(), "text/html; charset=utf-8")
        if path.startswith("/api/"):
            if not self._allowed():
                return self._send(403, b"", "text/plain")
            name = (query.get("cv") or [""])[0]
            try:
                if path == "/api/translator":  # which translators are ready (asks Ollama: no need to wait for the lock)
                    return self._json(translator.status())
                with LOCK:
                    if path == "/api/cvs":
                        return self._json({**list_profiles(), "demo": cv.workspace().demo})
                    if path == "/api/templates":  # known languages, for a first CV
                        return self._json({"templates": [{"code": k, "name": v["name"], "labels": v.get("labels")}
                                                         for k, v in cv.KNOWN_LANGUAGES.items()]})
                    if path == "/api/example":  # the example CV, to try the editor
                        return self._json(json.loads((ROOT / "examples" / "example-cv.json").read_text(encoding="utf-8")))
                    if path == "/api/data":
                        return self._json(read_data(get_profile(name)))
                    photos = (query.get("photos") or ["1"])[0] != "0"
                    if path == "/api/export-zip":  # one CV, or every CV when no name is given
                        profiles = [get_profile(name)] if name else cv.profiles()
                        if not profiles:
                            raise RuntimeError("There is no CV to export.")
                        return self._send(200, export_zip(profiles, photos), "application/zip",
                                          [download(profiles[0] if name else None, ".zip")])
            except (Exception, SystemExit) as e:
                return self._json({"error": str(e)}, 500)
            return self._send(404, b"", "text/plain")
        for prefix, folder in static_folders().items():
            if path.startswith(prefix):
                file = (folder / path[len(prefix):]).resolve()
                if file.is_file() and file.is_relative_to(folder.resolve()):
                    content_type = guess_type(file.name)[0] or "application/octet-stream"
                    return self._send(200, file.read_bytes(), content_type)
        self._send(404, b"", "text/plain")

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._allowed():
            return self._send(403, b"", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        if length > 80_000_000:
            return self._json({"error": "File too large."}, 413)
        body = self.rfile.read(length)
        try:
            if path == "/api/photos":
                with LOCK:
                    return self._json(add_photo(self.headers.get("X-CV"), self.headers.get("X-File-Name"), body))
            if path == "/api/signature":  # the body is the signature: an image or a PDF
                with LOCK:
                    return self._json(add_signature(self.headers.get("X-CV"), self.headers.get("X-File-Name"), body))
            if path == "/api/import-zip":  # the body is the .zip file, X-Mode: check | replace | copy
                with LOCK:
                    return self._json(import_zip(body, self.headers.get("X-Mode")))
            if path == "/api/pdf":  # the PDF of what the editor shows
                request = json.loads(body or b"{}")
                name, pdf = make_pdf(request if isinstance(request, dict) else {})
                disposition = "inline" if request.get("inline") else "attachment"
                return self._send(200, pdf, "application/pdf",
                                  [("Content-Disposition", f"{disposition}; filename*=UTF-8''{quote(name)}")])
            action = ACTIONS.get(path)
            if not action:
                return self._send(404, b"", "text/plain")
            request = json.loads(body or b"{}")
            if not isinstance(request, dict):
                raise RuntimeError("Invalid request.")
            if path in NO_WAIT:
                return self._json(action(request))
            with LOCK:
                return self._json(action(request))
        except (Exception, SystemExit) as e:
            return self._json({"error": str(e)}, 500)


def already_running(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2) as r:
            return json.load(r).get("editor") == "curriculum"
    except Exception:
        return False


def install():
    """Adds "CV Editor" to the applications menu (Linux)."""
    folder = Path.home() / ".local/share/applications"
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / "cv-editor.desktop"
    file.write_text(f"""[Desktop Entry]
Type=Application
Name=CV Editor
Comment=Edit CVs and build the PDFs
Exec={sys.executable} "{Path(__file__).resolve()}"
Path={HERE}
Terminal=true
Icon=x-office-document
Categories=Office;
""", encoding="utf-8")
    file.chmod(0o755)
    print(f'Done: look for "CV Editor" among your applications ({file}).')


def main():
    ap = argparse.ArgumentParser(description="CV editor (opens in the browser).")
    ap.add_argument("--install", action="store_true", help='add "CV Editor" to the applications menu')
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--data", metavar="FOLDER", help="keep the CVs and PDFs in this folder instead of the project folder")
    ap.add_argument("--demo", action="store_true",
                    help="try the editor as a new user: an empty temporary folder, deleted when the editor closes")
    args = ap.parse_args()
    if args.install:
        return install()
    demo_dir = None
    if args.demo:
        demo_dir = tempfile.mkdtemp(prefix="cv-editor-demo-")
        cv.use_workspace(cv.Workspace(demo_dir, demo=True))  # a translator key added in the demo is forgotten with it
        if args.port == PORT:
            args.port = PORT + 1  # next to a normal editor that may be open
    elif args.data:
        cv.use_workspace(cv.Workspace(args.data))

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        if already_running(args.port):
            print("The editor is already open: showing it in the browser.")
            webbrowser.open(f"http://127.0.0.1:{args.port}/")
            return
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # port taken by something else: use another one
    # closing the terminal window ends the editor cleanly (the demo folder is deleted)
    for sig in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), lambda *_: sys.exit(0))
    address = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"CV editor running at {address}" + ("  (DEMO: empty, nothing is kept)" if cv.workspace().demo else ""))
    print("To close it, close this window (or press Ctrl+C).")
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [address]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEditor closed.")
    finally:
        if demo_dir:
            shutil.rmtree(demo_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
