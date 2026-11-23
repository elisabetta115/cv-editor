"""Exporting and importing CVs: the example .json file and .zip files (read safely, written all or nothing)."""
import base64
import binascii
import io
import re
import tomllib
import zipfile
from datetime import date, time
from pathlib import Path

from .content import normalize
from .language import language_config, languages
from .photos import MAX_PHOTO_BYTES, PHOTO_EXTENSIONS, find_photos, signature_file, write_photo, write_signature
from .storage import Profile, check_code, free_name, remove_profile_files, save_language, save_settings
from .workspace import workspace


EXPORT_FORMAT = "cv-editor"        # marks the example .json file (and those exported by older versions)


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
        return {"cvs": [{"name": x["name"], "exists": (workspace().cvs_dir / x["name"]).exists()} for x in found]}
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
            old = Profile(name)
            remove_profile_files(old)
            profile.dir.rename(old.dir)
            profile = old
        names.append(profile.name)
    return {"profiles": names}


def write_new_cv(x):
    """Writes an imported CV in a new folder (its own name, or "Name (2)"...). Content is normalised and rewritten."""
    profile = Profile(free_name(x["name"]))
    try:
        for code, content in x["languages"].items():
            content = normalize(content, code)
            content["cv_language"] = {"name": language_config(code, content["cv_language"])["name"]}
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
            files = [profile.dir / conf["content"] for conf in languages(profile).values()]
            for f in files + [profile.settings_file, signature_file(profile)]:
                if f and f.is_file():
                    z.write(f, folder + f.name)
            for f in find_photos(profile) if with_photos else []:  # the originals: photos are already compressed
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
                  if p[:-1] == folder + ("photos",) and Path(p[-1]).suffix.lower() in PHOTO_EXTENSIONS]
        name = suggested_name({"name": folder[-1] if folder else "", "languages": langs})
        signature = next(((p[-1], read(p, MAX_PHOTO_BYTES, "signature")) for p in sorted(files)
                          if p[:-1] == folder and SIGNATURE_FILE.fullmatch(p[-1])), None)
        found.append({"name": name, "languages": langs, "settings": settings, "photos": photos, "signature": signature})
    return found
