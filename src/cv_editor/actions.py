"""What the editor asks for (read, preview, save, PDF, new CV, photos, signature), without any web code."""
import json
import re
import secrets
import shutil
from urllib.parse import quote, unquote

from .contacts import CONTACT_GROUPS, ICONS
from .content import empty_cv, normalize, prepare
from .language import KNOWN_LANGUAGES, base_language, language_config, languages
from .pdf import find_chrome, print_pdf
from .photos import (
    can_zoom, find_photos, framed_photo, photo_frame, prepare_photos, signature_file, signature_src, write_photo,
    write_signature,
)
from .render import document, has_sidebar, render_page
from .schema import FIXED_SECTIONS, SIDEBAR_SUGGESTED
from .storage import (
    Profile, check_code, clean_cv, delete_language, free_name, get_profile, load, load_settings,
    profiles as all_profiles, remove_profile_files, save_language, save_settings,
)
from .styles import COLORS, STYLE_GROUPS, STYLES
from .workspace import ROOT, workspace


def list_profiles():
    return {"profiles": [{"name": x.name, "languages": list(languages(x))} for x in all_profiles()]}


def new_profile(r):
    first, last = str(r.get("first_name") or "").strip(), str(r.get("last_name") or "").strip()
    language = check_code(r.get("language") or "en")
    try:
        profile = Profile(free_name(f"{first} {last}"))
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
    langs = languages(source)
    wanted = r.get("languages") or list(langs)
    if not isinstance(wanted, list) or not wanted or any(code not in langs for code in wanted):
        raise RuntimeError("Choose at least one language of the CV to copy.")
    try:
        target = Profile(free_name(str(r.get("name") or "").strip() or source.name))
    except ValueError:
        raise RuntimeError("Write a name without special characters such as / \\ : * ? \" < > |.")
    try:
        target.dir.mkdir(parents=True)
        for code in wanted:
            shutil.copy2(source.dir / langs[code]["content"], target.dir / langs[code]["content"])
        if source.settings_file.is_file():
            shutil.copy2(source.settings_file, target.settings_file)
        if signature_file(source):
            shutil.copy2(signature_file(source), target.dir / signature_file(source).name)
        for f in find_photos(source) if r.get("photos", True) else []:
            target.photo_dir.mkdir(exist_ok=True)
            shutil.copy2(f, target.photo_dir / f.name)
    except Exception:
        remove_profile_files(target)  # no half-made copies
        raise
    return {"profile": target.name}


# ---------------------------------------------------------------------
#  Actions called by the editor
# ---------------------------------------------------------------------
def refresh_photos(profile):
    photos = find_photos(profile)
    paths = prepare_photos(profile, photos)
    workspace().photo_src[profile.name] = {f.name: src for f, src in paths.items()}
    base = "/html/" + quote(profile.name) + "/"
    return [{"name": f.name, "src": base + paths[f]} for f in photos]


def read_data(profile):
    langs = {}
    for code, conf in languages(profile).items():
        data = normalize(load(profile, conf["content"]), code)
        prepared = prepare(data, conf["content"], code)
        # section order: {"builtin", "hidden", "side"} for the fixed sections,
        # the index in "sections" for the extra ones
        order = [{"builtin": x["key"], "hidden": x["hidden"], "side": x["side"]} if x["kind"] == "builtin"
                 else next(i for i, s in enumerate(prepared["sections"]) if s is x["section"])
                 for x in prepared["order"]]
        langs[code] = {"name": conf["name"], "data": data, "order": order}
    return {"profile": profile.name, "languages": langs, "photos": refresh_photos(profile), "signature": signature_url(profile),
            "styles": [{"id": k, "name": v["name"], "group": v["group"], "color": v["color"], "side": v["side"],
                        "tags": v["tags"], "description": v["description"]} for k, v in STYLES.items()],
            "style_groups": STYLE_GROUPS,
            "fixed_sections": FIXED_SECTIONS,
            "sidebar_suggested": SIDEBAR_SUGGESTED,
            "colors": COLORS, "settings": load_settings(profile), "can_zoom": can_zoom(),
            "icons": {k: v for k, v in ICONS.items() if k != "link"},  # the icons a contact can have
            "contact_groups": CONTACT_GROUPS,                           # the kinds of contact, with their names
            "templates": templates()}


def templates():
    """The known languages, for a first CV and a new language: code, name and section titles."""
    return [{"code": k, "name": v["name"], "labels": v.get("labels")} for k, v in KNOWN_LANGUAGES.items()]


def example():
    """The example CV (.json), opened by "Try the example"."""
    return json.loads((ROOT / "examples" / "example-cv.json").read_text(encoding="utf-8"))


def view(r):
    """What the editor shows: CV, language, style, colour and photo (content not saved yet included)."""
    profile = get_profile(r.get("profile"))
    language, style = check_code(r.get("language")), r.get("style")
    if style not in STYLES:
        raise RuntimeError(f"Unknown style: {style!r}")
    prepared = prepare(clean_cv(r.get("data") or {}), language_config(language)["content"], language)
    if profile.name not in workspace().photo_src:
        refresh_photos(profile)
    photo = r.get("photo") or ""
    color = r.get("color") if r.get("color") in COLORS else None
    src = workspace().photo_src[profile.name].get(photo)
    frame = photo_frame(r.get("frame")) if src else None  # how the photo is framed (not saved yet included)
    signature = signature_src(profile)  # shown only when the content asks for it ([signature] show = true)
    return profile, language, style, prepared, framed_photo(profile, src, frame), photo, color, frame, signature


def preview(r):
    profile, language, style, prepared, src, _, color, frame, signature = view(r)
    base = "/html/" + quote(profile.name) + "/"
    return {"document": document(prepared, language, style, src, preview_base=base, color=color, frame=frame, signature=signature),
            "page": render_page(prepared, style, src, frame, signature), "sidebar": has_sidebar(prepared)}


def pdf_name(person, language):
    """The name of a downloaded PDF: CV_<first name>_<last name>_<LANGUAGE>.pdf, e.g. CV_Jane_Doe_EN.pdf
    (other versions in a language too: the person who receives it does not need to know)."""
    parts = ["CV", str(person.get("first_name") or ""), str(person.get("last_name") or ""), base_language(language).upper()]
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
        page.write_text(document(prepared, language, style, src, color=color, frame=frame, signature=signature), encoding="utf-8")
        print_pdf(find_chrome(), page, pdf)
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
    names = {f.name: f for f in find_photos(profile)}
    if r.get("name") not in names:
        raise RuntimeError("Photo not found.")
    names[r["name"]].unlink()
    return {"photos": refresh_photos(profile)}


def signature_url(profile):
    """The address of the signature for the editor, None when the CV has none."""
    src = signature_src(profile)
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
