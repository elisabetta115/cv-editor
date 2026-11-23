"""CVs on disk: one folder per person in cvs/, its content files and its settings."""
import json
import os
import re
import shutil
import sys
import tomllib

from .language import VERSION_CODE, language_config, languages
from .photos import MAX_ZOOM, PHOTO_NAME, SHAPES, photo_frame
from .schema import FILE_ORDER, FILE_TITLES, HIDEABLE_LINES
from .styles import COLORS, STYLES
from .workspace import workspace


# ---------------------------------------------------------------------
#  CVs: one folder per person in cvs/
# ---------------------------------------------------------------------
def check_cv_name(name):
    """A CV name is also a folder name: no slashes or other characters folders cannot have."""
    name = " ".join(str(name or "").split())
    if not name or name.startswith(".") or len(name) > 80 or re.search(r'[\\/:*?"<>|\x00-\x1f]', name):
        raise ValueError(f"Invalid CV name: {name!r}")
    return name


class Profile:
    """One person's CV: cvs/<name>/ with content_<code>.toml, settings.toml and photos/."""

    def __init__(self, name):
        self.name = check_cv_name(name)
        place = workspace()
        self.dir = place.cvs_dir / self.name
        self.settings_file = self.dir / "settings.toml"
        self.photo_dir = self.dir / "photos"
        self.html_dir = place.html_dir / self.name
        # smaller copies of the photos, used by the HTML pages (keeps the PDFs light)
        self.html_photo_dir = self.html_dir / "photos"
        self.pdf_dir = place.pdf_dir / self.name

    def exists(self):
        return self.dir.is_dir()


def profiles():
    """Every CV in cvs/, in alphabetical order."""
    cvs_dir = workspace().cvs_dir
    if not cvs_dir.is_dir():
        return []
    found = []
    for d in sorted(cvs_dir.iterdir(), key=lambda x: x.name.lower()):
        if d.is_dir() and not d.name.startswith("."):
            try:
                found.append(Profile(d.name))
            except ValueError:
                pass
    return found


def load_settings(profile):
    """settings.toml, written by the editor: the colour chosen for each style and the framing of each photo."""
    data = {}
    if profile.settings_file.exists():
        try:
            data = tomllib.loads(profile.settings_file.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            print(f"  ! settings.toml is not valid ({e}): using the default styles and colours.", file=sys.stderr)
    out = {}
    stored = data.get("styles") if isinstance(data.get("styles"), dict) else {}
    for style, conf in STYLES.items():
        x = stored.get(style) if isinstance(stored.get(style), dict) else {}
        color = x.get("color") if x.get("color") in COLORS else conf["color"]
        out[style] = {"color": color}
    photos = data.get("photos") if isinstance(data.get("photos"), dict) else {}
    frames = {name: frame for name, v in photos.items() if PHOTO_NAME.fullmatch(name) and (frame := photo_frame(v))}
    return {"styles": out, "photos": frames}


def load(profile, file):
    try:
        with open(profile.dir / file, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Error in {profile.name}/{file}: {e}\n(Check the quotes, brackets and commas on that line.)")


# ---------------------------------------------------------------------
#  Writing the .toml files
# ---------------------------------------------------------------------
# the parts of a content file, their order and titles: PARTS in schema.py
FILE_HEADER = ["The easiest way to edit it is the editor:",
               "    python3 src/editor.py      (or \"CV Editor\" from the applications menu)",
               "You can still edit it by hand; in the text you can use **bold** and *italic*.",
               "hidden = true in a detail, contact, job, degree, language or row: kept here, not shown in the CV.",
               ", ".join(f"{k}_hidden" for k in HIDEABLE_LINES) + ": the lines of that list",
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
    name = (data.get("cv_language") or {}).get("name") or language_config(language)["name"]
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
             "#   color   = " + " | ".join(COLORS),
             "# Photos: how each one is framed, in every style.",
             "#   x, y    = 0-100 (0 = left / top edge of the photo, 100 = right / bottom edge)",
             f"#   zoom    = 1 (the whole photo) to {MAX_ZOOM}",
             "#   shape   = " + " | ".join(SHAPES) + "   (without it: the shape of each style)",
             ""]
    settings = settings if isinstance(settings, dict) else {}
    styles = settings.get("styles") if isinstance(settings.get("styles"), dict) else {}
    for style, conf in STYLES.items():
        x = styles.get(style) if isinstance(styles.get(style), dict) else {}
        color = x.get("color") if x.get("color") in COLORS else conf["color"]
        lines += [f"[styles.{style}]", f'color = "{color}"', ""]
    photos = settings.get("photos") if isinstance(settings.get("photos"), dict) else {}
    for name, value in sorted(photos.items()):
        frame = photo_frame(value)
        if frame and isinstance(name, str) and PHOTO_NAME.fullmatch(name):
            lines += [f"[photos.{_key(name)}]"]
            lines += [f"{k} = {frame[k]:g}" for k in ("x", "y", "zoom") if k in frame]
            lines += [f'shape = "{frame["shape"]}"'] if "shape" in frame else []
            lines += [""]
    profile.dir.mkdir(parents=True, exist_ok=True)
    profile.settings_file.write_text("\n".join(lines), encoding="utf-8")


def check_code(language):
    """A language (en) or another version in a language (en-ireland)."""
    if not isinstance(language, str) or not VERSION_CODE.fullmatch(language):
        raise RuntimeError(f"Invalid language code: {language!r} (2 or 3 lowercase letters, e.g. es, fr, de).")
    return language


def save_language(profile, language, data):
    check_code(language)
    data = clean_cv(data)
    text = write_toml(data, language)
    if clean_cv(tomllib.loads(text)) != data:  # check: the file reads back identical
        raise RuntimeError("The file check failed: nothing was saved.")
    profile.dir.mkdir(parents=True, exist_ok=True)
    path = profile.dir / language_config(language)["content"]
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


# ---------------------------------------------------------------------
#  CVs (one per person)
# ---------------------------------------------------------------------
def get_profile(name, must_exist=True):
    try:
        profile = Profile(name)
    except ValueError as e:
        raise RuntimeError(str(e))
    if must_exist and not profile.exists():
        raise RuntimeError(f"There is no CV called \"{profile.name}\".")
    return profile


def free_name(name):
    """The name itself, or "Name (2)", "Name (3)"... if a CV with that name already exists."""
    base = check_cv_name(name)
    candidate, n = base, 2
    while (workspace().cvs_dir / candidate).exists():
        candidate = f"{base} ({n})"
        n += 1
    return candidate


def remove_profile_files(profile):
    """Deletes a CV: its folder in cvs/, its PDFs and its generated pages."""
    place = workspace()
    for folder, parent in ((profile.dir, place.cvs_dir), (profile.pdf_dir, place.pdf_dir), (profile.html_dir, place.html_dir)):
        if folder.is_dir() and folder.resolve().parent == parent.resolve():
            shutil.rmtree(folder)


def delete_language(profile, language):
    """Removes the content file of a language, its PDFs and its HTML pages."""
    conf = languages(profile).get(check_code(language))
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
