#!/usr/bin/env python3
"""
Builds CVs as PDF files from plain-text content files.

Every CV (one per person) is a folder in cvs/:

    cvs/<Name>/content_it.toml   ->  PDF/<Name>/Italiano/
    cvs/<Name>/content_en.toml   ->  PDF/<Name>/English/      (one file per language)
    cvs/<Name>/content_en-ireland.toml -> PDF/<Name>/English (Ireland)/   (another version in English)
    cvs/<Name>/settings.toml         enabled styles and colours
    cvs/<Name>/photos/               every photo here becomes a PDF version
    cvs/<Name>/signature.png         the signature, at the end of the CVs that ask for it ([signature] show = true)

For each language and each style (one stylesheet each in styles/: formal, modern,
swiss, terminal... 50 in all) it creates one version without a photo and one
version for EVERY photo (jpg, jpeg, png, webp, gif, avif, bmp). That is a lot of
PDFs: --style picks some styles only.

Besides the fixed sections (experience, education, skills...) you can add new
ones with the [[sections]] blocks of the .toml files. The easiest way to edit
everything, and to import/export a CV as a .json file, is the editor:
    python3 editor.py

Usage:
    python3 generate_cv.py                            # every CV, every version
    python3 generate_cv.py --cv "Jane Doe"            # one CV only
    python3 generate_cv.py --language it              # Italian only
    python3 generate_cv.py --style creative --photo photo2
    python3 generate_cv.py --style modern,swiss,zen      # some styles only (there are 50)
    python3 generate_cv.py --photo 0                  # only the versions without a photo
    python3 generate_cv.py --data /path/to/folder     # the CVs kept in another folder (as with the editor)

Requirements: Python 3.11+ and Google Chrome or Chromium.
If Chrome is not found, give its path in the CHROME variable:
    CHROME="/path/to/chrome" python3 generate_cv.py
"""
import argparse
import copy
import glob
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template
from urllib.parse import quote, unquote

try:
    import tomllib
except ImportError:
    sys.exit("Python 3.11 or newer is required (the tomllib module is missing).")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STYLES_DIR = HERE / "styles"


class Workspace:
    """Where the CVs are kept, with their PDFs and generated pages, and what belongs to that place.

        cvs_dir    cvs/<person>/              the CVs
        pdf_dir    PDF/<person>/<language>/   the PDFs built from the terminal
        html_dir   html/<person>/             the generated pages (in the project folder: src/html/, not kept in git)

    Without a folder it is the project folder; with one (the editor's --data or --demo), that folder.
    One workspace is in use at a time: workspace() gives it, use_workspace() changes it."""

    def __init__(self, folder=None, demo=False):
        if folder is None:
            self.cvs_dir, self.pdf_dir, self.html_dir = ROOT / "cvs", ROOT / "PDF", HERE / "html"
        else:
            folder = Path(folder).resolve()
            self.cvs_dir, self.pdf_dir, self.html_dir = folder / "cvs", folder / "PDF", folder / "html"
        self.demo = demo                                # the editor's demo: an empty temporary folder
        self.translator_memory = {} if demo else None   # the demo keeps a translator key in memory, not in a file
        self.photo_src = {}                             # CV name -> {photo file name -> path used in the HTML}


_workspace = Workspace()


def workspace():
    """The workspace in use."""
    return _workspace


def use_workspace(new):
    """Keeps the CVs, the PDFs and the generated pages in another place from now on (--data, --demo, the tests)."""
    global _workspace
    _workspace = new
    return new


def short_path(path):
    """A path in a message: from the project folder when it is inside it, in full otherwise."""
    path = Path(path)
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
CONVERT_FIRST_EXTENSIONS = {".heic", ".heif", ".tif", ".tiff", ".dng", ".raw", ".cr2", ".cr3", ".nef", ".arw"}
MAX_PHOTO_SIDE = 1000  # pixels: more than enough for print


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

# ---------------------------------------------------------------------
#  Languages
# ---------------------------------------------------------------------
# Known languages: name, words used in the PDF file names and section titles
# already translated (used when the editor creates a CV in a new language).
# Every language of the CV is a content_<code>.toml file; a language that is not
# listed here takes its name from the [cv_language] table of its file and uses
# the English words.
KNOWN_LANGUAGES = {
    "it": {"name": "Italiano", "no_photo": "SenzaFoto", "photo_word": "Foto",
           "styles": {"formal": "Serio", "creative": "Creativo", "modern": "Moderno", "minimal": "Minimale",
                      "elegant": "Elegante", "classic": "Classico", "bold": "Audace", "compact": "Compatto",
                      "timeline": "Cronologia", "executive": "Executive"},
           "labels": {"profile": "Profilo", "about_me": "Su di me", "contacts": "Contatti",
                      "details": "Dati personali", 
                      "experience": "Esperienza", "education": "Istruzione", "skills": "Competenze",
                      "languages": "Lingue", "digital_skills": "Competenze digitali", "soft_skills": "Soft skill",
                      "interests": "Interessi", "grade": "Voto", "thesis": "Tesi"}},
    "en": {"name": "English", "no_photo": "NoPhoto", "photo_word": "Photo",
           "styles": {"formal": "Formal", "creative": "Creative", "modern": "Modern", "minimal": "Minimal",
                      "elegant": "Elegant", "classic": "Classic", "bold": "Bold", "compact": "Compact",
                      "timeline": "Timeline", "executive": "Executive"},
           "labels": {"profile": "Profile", "about_me": "About me", "contacts": "Contacts",
                      "details": "Personal details", 
                      "experience": "Experience", "education": "Education", "skills": "Skills",
                      "languages": "Languages", "digital_skills": "Digital skills", "soft_skills": "Soft skills",
                      "interests": "Interests", "grade": "Final score", "thesis": "Thesis"}},
    "es": {"name": "Español", "no_photo": "SinFoto", "photo_word": "Foto",
           "styles": {"formal": "Formal", "creative": "Creativo", "modern": "Moderno", "minimal": "Minimalista",
                      "elegant": "Elegante", "classic": "Clasico", "bold": "Audaz", "compact": "Compacto",
                      "timeline": "Cronologia", "executive": "Ejecutivo"},
           "labels": {"profile": "Perfil", "about_me": "Sobre mí", "contacts": "Contacto",
                      "details": "Datos personales", 
                      "experience": "Experiencia", "education": "Formación", "skills": "Competencias",
                      "languages": "Idiomas", "digital_skills": "Competencias digitales",
                      "soft_skills": "Habilidades blandas", "interests": "Intereses", "grade": "Nota", "thesis": "Tesis"}},
    "fr": {"name": "Français", "no_photo": "SansPhoto", "photo_word": "Photo",
           "styles": {"formal": "Classique", "creative": "Creatif", "modern": "Moderne", "minimal": "Minimaliste",
                      "elegant": "Elegant", "classic": "Traditionnel", "bold": "Audacieux", "compact": "Compact",
                      "timeline": "Chronologie", "executive": "Executif"},
           "labels": {"profile": "Profil", "about_me": "À propos", "contacts": "Contact",
                      "details": "Informations personnelles", 
                      "experience": "Expérience", "education": "Formation", "skills": "Compétences",
                      "languages": "Langues", "digital_skills": "Compétences numériques", "soft_skills": "Savoir-être",
                      "interests": "Centres d'intérêt", "grade": "Note", "thesis": "Mémoire"}},
    "de": {"name": "Deutsch", "no_photo": "OhneFoto", "photo_word": "Foto",
           "styles": {"formal": "Klassisch", "creative": "Kreativ", "modern": "Modern", "minimal": "Minimalistisch",
                      "elegant": "Elegant", "classic": "Traditionell", "bold": "Markant", "compact": "Kompakt",
                      "timeline": "Zeitleiste", "executive": "Executive"},
           "labels": {"profile": "Profil", "about_me": "Über mich", "contacts": "Kontakt",
                      "details": "Persönliche Daten", 
                      "experience": "Berufserfahrung", "education": "Ausbildung", "skills": "Kenntnisse",
                      "languages": "Sprachen", "digital_skills": "IT-Kenntnisse", "soft_skills": "Soft Skills",
                      "interests": "Interessen", "grade": "Note", "thesis": "Abschlussarbeit"}},
    "pt": {"name": "Português", "no_photo": "SemFoto", "photo_word": "Foto",
           "styles": {"formal": "Formal", "creative": "Criativo", "modern": "Moderno", "minimal": "Minimalista",
                      "elegant": "Elegante", "classic": "Classico", "bold": "Arrojado", "compact": "Compacto",
                      "timeline": "Cronologia", "executive": "Executivo"},
           "labels": {"profile": "Perfil", "about_me": "Sobre mim", "contacts": "Contatos",
                      "details": "Dados pessoais", 
                      "experience": "Experiência", "education": "Formação", "skills": "Competências",
                      "languages": "Idiomas", "digital_skills": "Competências digitais", "soft_skills": "Soft skills",
                      "interests": "Interesses", "grade": "Nota", "thesis": "Tese"}},
    "nl": {"name": "Nederlands", "no_photo": "ZonderFoto", "photo_word": "Foto",
           "styles": {"formal": "Formeel", "creative": "Creatief", "modern": "Modern", "minimal": "Minimalistisch",
                      "elegant": "Elegant", "classic": "Klassiek", "bold": "Opvallend", "compact": "Compact",
                      "timeline": "Tijdlijn", "executive": "Executive"},
           "labels": {"profile": "Profiel", "about_me": "Over mij", "contacts": "Contact",
                      "details": "Persoonlijke gegevens", 
                      "experience": "Werkervaring", "education": "Opleiding", "skills": "Vaardigheden",
                      "languages": "Talen", "digital_skills": "Digitale vaardigheden", "soft_skills": "Soft skills",
                      "interests": "Interesses", "grade": "Cijfer", "thesis": "Scriptie"}},
    "ca": {"name": "Català"},
    "ga": {"name": "Gaeilge"},
    "sv": {"name": "Svenska"},
    "da": {"name": "Dansk"},
    "nb": {"name": "Norsk"},
    "fi": {"name": "Suomi"},
}
LANGUAGE_CODE = re.compile(r"[a-z]{2,3}")
# A CV can also have more versions in the same language, each with its own content, e.g. one following
# the Irish rules: "en-ireland" (content_en-ireland.toml) is a version in English ("en").
VERSION_CODE = re.compile(r"[a-z]{2,3}(?:-[a-z0-9]{1,24})?")


def base_language(code):
    """The language of a version: "en-ireland" -> "en"."""
    return str(code).split("-")[0]


def language_config(code, meta=None):
    """Name, PDF folder and file-name words of a language (or of another version in a language)."""
    base, _, variant = str(code).partition("-")
    meta, known, english = meta or {}, KNOWN_LANGUAGES.get(base, {}), KNOWN_LANGUAGES["en"]
    default = (known.get("name") or base.upper()) + (f" ({variant.capitalize()})" if variant else "")
    name = str(meta.get("name") or default)
    folder = re.sub(r'[\\/:*?"<>|]+', "", str(meta.get("folder") or name)).strip() or code.upper()
    return {
        "name": name,
        "content": f"content_{code}.toml",
        "folder": folder,
        "styles": {**{k: re.sub(r"\W+", "", v["name"]) for k, v in STYLES.items()}, **english["styles"],
                   **known.get("styles", {}),
                   **(meta["styles"] if isinstance(meta.get("styles"), dict) else {})},
        "no_photo": meta.get("no_photo") or known.get("no_photo") or english["no_photo"],
        "photo_word": meta.get("photo_word") or known.get("photo_word") or english["photo_word"],
    }


def languages(profile):
    """The languages of a CV: one per content_<code>.toml file (Italian and English first, each
    language followed by its other versions)."""
    found = {}
    for f in profile.dir.glob("content_*.toml"):
        code = f.stem.removeprefix("content_")
        if not VERSION_CODE.fullmatch(code):
            continue
        try:
            meta = tomllib.loads(f.read_text(encoding="utf-8")).get("cv_language", {})
        except (tomllib.TOMLDecodeError, OSError):
            meta = {}
        found[code] = language_config(code, meta if isinstance(meta, dict) else {})
    bases = ["it", "en"] + sorted({base_language(k) for k in found} - {"it", "en"})
    order = sorted(found, key=lambda k: (bases.index(base_language(k)), k != base_language(k), k))
    return {k: found[k] for k in order}


# ---------------------------------------------------------------------
#  Colours and styles
# ---------------------------------------------------------------------
# Colour palettes, shared by every style. Each style uses:
#   dark  = headings, name, coloured bands   mid = organisations, icons, details
#   light = decorations (dots, labels)        bg  = light background (creative style)
COLORS = {
    "navy":       {"name": "Navy",         "dark": "#1d3a5f", "mid": "#2e5c8a", "light": "#6fa8dc", "bg": "#eef2f7"},
    "azure":      {"name": "Azure",        "dark": "#0d497d", "mid": "#1677bd", "light": "#3ec3e2", "bg": "#edf1f5"},
    "indigo":     {"name": "Indigo",       "dark": "#2a2f7a", "mid": "#4650b8", "light": "#9aa3f0", "bg": "#eff0fb"},
    "plum":       {"name": "Plum",         "dark": "#3d2856", "mid": "#6a4a94", "light": "#b9a0dc", "bg": "#f2eff7"},
    "teal":       {"name": "Teal",         "dark": "#134e4a", "mid": "#0f766e", "light": "#2ec4b6", "bg": "#ecf5f4"},
    "emerald":    {"name": "Emerald",      "dark": "#064e3b", "mid": "#047857", "light": "#34d399", "bg": "#ecf8f3"},
    "forest":     {"name": "Forest green", "dark": "#24452c", "mid": "#3d7a4e", "light": "#8cc59a", "bg": "#eef4ef"},
    "olive":      {"name": "Olive",        "dark": "#3b4419", "mid": "#5e6b22", "light": "#b5c26a", "bg": "#f4f6ea"},
    "burgundy":   {"name": "Burgundy",     "dark": "#5e1a2a", "mid": "#962d43", "light": "#e28a9b", "bg": "#f7eef0"},
    "crimson":    {"name": "Crimson",      "dark": "#7a1820", "mid": "#b42332", "light": "#f08a8f", "bg": "#fbeeef"},
    "rose":       {"name": "Rose",         "dark": "#7a1f4b", "mid": "#b03a70", "light": "#f2a0c4", "bg": "#fbf0f5"},
    "terracotta": {"name": "Terracotta",   "dark": "#6b2e14", "mid": "#a8461d", "light": "#f0a47c", "bg": "#f8f0ea"},
    "mustard":    {"name": "Mustard",      "dark": "#5c4300", "mid": "#8a6500", "light": "#e8b931", "bg": "#fbf6e6"},
    "chocolate":  {"name": "Chocolate",    "dark": "#3f2416", "mid": "#7a4b30", "light": "#c99a78", "bg": "#f6f0eb"},
    "graphite":   {"name": "Graphite",     "dark": "#1f2933", "mid": "#4a5563", "light": "#9aa5b1", "bg": "#f0f2f4"},
    "gold":       {"name": "Black & gold", "dark": "#1b1b1b", "mid": "#86661a", "light": "#cfa64a", "bg": "#f7f4ec"},
}

# The styles: one stylesheet each in styles/ (besides base.css and fonts.css). Adding a style
# is adding a file: the comment at its top describes it, with these lines:
#   @name          the name shown in the editor
#   @group         classic | modern | creative | themed  (how the editor groups the styles)
#   @color         the palette it starts with
#   @side          right: the sidebar goes on the right (left otherwise)
#   @tags          words to find it with the editor's search, separated by commas
#   @print         rules for the printed page that need the palette colours: CSS variables do not
#   @print-sidebar work inside @page, so write $dark, $mid, $light or $bg ("-sidebar": only when
#                  the CV has a sidebar), e.g. @print @page{background:$bg}
# The other lines of the comment are the description shown in the editor.
STYLE_GROUPS = {"classic": "Classic & formal", "modern": "Clean & modern", "creative": "Bold & creative",
                "themed": "Themed"}
NOT_STYLES = {"base", "fonts"}


def load_styles():
    found = []
    for f in STYLES_DIR.glob("*.css"):
        if f.stem in NOT_STYLES or not re.fullmatch(r"[a-z][a-z0-9-]*", f.stem):
            continue
        m = re.match(r"\s*/\*(.*?)\*/", f.read_text(encoding="utf-8"), re.S)
        meta, text = {}, []
        for line in (m.group(1) if m else "").splitlines():
            line = line.strip()
            k = re.match(r"@([a-z-]+)\s+(.*)", line)
            if k:
                meta[k.group(1)] = k.group(2).strip()
            elif line and not line.startswith("="):
                text.append(line)
        conf = {"name": meta.get("name") or f.stem.title(),
                "group": meta.get("group") if meta.get("group") in STYLE_GROUPS else "modern",
                "color": meta.get("color") if meta.get("color") in COLORS else "navy",
                "side": "right" if meta.get("side") == "right" else "left",
                "tags": [x.strip() for x in meta.get("tags", "").split(",") if x.strip()],
                "description": " ".join(text),
                "print": meta.get("print", ""), "print_sidebar": meta.get("print-sidebar", "")}
        found.append((list(STYLE_GROUPS).index(conf["group"]), conf["name"].lower(), f.stem, conf))
    return {stem: conf for _, _, stem, conf in sorted(found)}


STYLES = load_styles()

# Icons (Lucide, ISC licence: see THIRD-PARTY-NOTICES.md), drawn in the text colour
ICONS = {
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "email": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "address": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "github": '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>',
    "web": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    # more contact types (simple line drawings in the same manner)
    "whatsapp": '<path d="M3 21l1.65-3.8a9 9 0 1 1 3.4 2.9z"/><path d="M9.2 8.6c-.5 2.9 2.8 6.4 6 6l.8-1.4-1.9-1-1 .9c-.9-.3-1.9-1.3-2.2-2.2l.9-1-.9-1.9z"/>',
    "telegram": '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
    "x": '<path d="M4 4h4.5L20 20h-4.5z"/><path d="M20 4l-6.6 7.3M4 20l6.6-7.3"/>',
    "instagram": '<rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>',
    "facebook": '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>',
    "youtube": '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3z"/>',
    "gitlab": '<path d="m22 13.3-3.3-10a.4.4 0 0 0-.8 0l-2.3 6.7H8.4L6.1 3.3a.4.4 0 0 0-.8 0L2 13.3a.7.7 0 0 0 .3.8L12 21l9.7-6.9a.7.7 0 0 0 .3-.8z"/>',
    "stackoverflow": '<path d="M4 15v5h16v-5"/><path d="M8 17h8M8.4 13.3l7.8 1.6M9.6 9.3l7.2 3.3M11.9 5.4l6.1 5.1"/>',
    "behance": '<path d="M3 6v12M3 6h4.5a2.75 2.75 0 0 1 0 5.5H3M3 11.5h5a3.25 3.25 0 0 1 0 6.5H3"/><path d="M14 14.5h7a3.5 3.5 0 1 0-1.2 2.7M15.5 8.5h4"/>',
    "dribbble": '<circle cx="12" cy="12" r="10"/><path d="M19.1 5.1C15.2 9.1 10 10.4 2.3 10.9M21.8 12.8c-6.6-1.4-12.1 1-16.4 6.3M8.6 2.8c4.4 6 6 9.4 8 17.7"/>',
    "orcid": '<circle cx="12" cy="12" r="10"/><path d="M8 10.5V16M8 7.5h.01M11 8v8h2.5a4 4 0 0 0 0-8z"/>',
    "scholar": '<path d="M22 10 12 5 2 10l10 5z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/>',
    "researchgate": '<rect x="2" y="2" width="20" height="20" rx="3"/><path d="M6.5 16V8h2.5a2.2 2.2 0 0 1 0 4.4H6.5M9 12.4l2.2 3.6M18 9.3a2.8 2.8 0 1 0 .2 4.4V12h-1.6"/>',
    # general icons, to give a contact another one
    "mobile": '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>',
    "chat": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>',
    "chain": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "home": '<path d="m3 10 9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "briefcase": '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>',
    "star": '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
    "heart": '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 12 5a5.5 5.5 0 0 0-10 3.5c0 2.3 1.5 4 3 5.5l7 7z"/>',
}
# the contact types (their icon has the same name); "icon" in a contact chooses another one, "none" = no icon
CONTACT_TYPES = ["phone", "email", "address", "web", "linkedin", "github", "gitlab", "stackoverflow", "behance", "dribbble",
                 "orcid", "scholar", "researchgate", "whatsapp", "telegram", "x", "instagram", "facebook", "youtube"]
# a handle written instead of a link (e.g. @janedoe) becomes this link
HANDLE_LINKS = {"github": "https://github.com/{}", "gitlab": "https://gitlab.com/{}", "x": "https://x.com/{}",
                "instagram": "https://www.instagram.com/{}", "telegram": "https://t.me/{}"}


# ---------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------
# links written in the text: [words to show](address), or an address written as it is (https://…, www.…)
MARKDOWN_LINK = re.compile(r"\[([^\[\]\n]+)\]\(\s*((?:[^\s()]|\([^\s()]*\))+)\s*\)")
TEXT_LINK = re.compile(MARKDOWN_LINK.pattern + r"|(?<![\w@/.\-])((?:https?://|www\.)[^\s<>\[\]()*\"']+)", re.IGNORECASE)
EMAIL = re.compile(r"[^@\s/:]+@[^@\s/]+\.[^@\s/]+")


def t(text, links=False):
    """HTML-safe text, with **bold** and *italic*. links: [words](address) and the addresses written as
    they are (https://…, www.…) become links too; an address that is not safe (javascript:…) stays text."""
    text, found = str(text), []
    if links:
        def keep(m):
            if m.group(1) is not None:  # [words](address)
                words, address, after = t(m.group(1)), m.group(2), ""
            else:  # an address in the sentence: the full stop or comma after it is not part of it
                address = m.group(3).rstrip(".,;:!?")
                words, after = html.escape(address, quote=False), m.group(3)[len(address):]
            url = f"mailto:{address}" if EMAIL.fullmatch(address) else web_address(address)
            if not url:
                return m.group(0)
            found.append(f'<a class="text-link" href="{html.escape(url)}">{words}</a>')
            return f"{len(found) - 1}{after}"
        text = TEXT_LINK.sub(keep, text.replace("", "").replace("", ""))
    s = html.escape(text, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    if found:
        s = re.sub("(\\d+)", lambda m: found[int(m.group(1))], s)
    return s


def rich(text):
    """Text of the CV that can hold links (descriptions, free text, lists, tags, tables...)."""
    return t(text, links=True)


def icon(kind):
    return f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">{ICONS.get(kind, ICONS["web"])}</svg>'


def web_address(link):
    """A safe link: web, email and phone addresses only ("" for javascript:, data: and the like)."""
    link = str(link).strip()
    if re.match(r"(https?|mailto|tel):", link, re.IGNORECASE):
        return link
    if re.match(r"[a-z][a-z0-9+.-]*:(?!\d)", link, re.IGNORECASE):  # another scheme (but not host:port)
        return ""
    return f"https://{link}" if link else ""


def contact_link(c):
    """The link of a contact. For GitHub, LinkedIn and websites it is the one written
    in "link" (the text is only the name shown); for email and phone it comes from the text."""
    text, kind = c.get("text", "").strip(), c.get("type")
    if c.get("link"):
        return web_address(c["link"])
    if kind == "email":
        return f"mailto:{text}"
    if kind == "phone":
        return "tel:" + re.sub(r"[^\d+]", "", text)
    if kind == "whatsapp" and re.sub(r"\D", "", text):
        return "https://wa.me/" + re.sub(r"\D", "", text)
    if kind == "orcid" and re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", text):
        return f"https://orcid.org/{text}"
    # a user name (@jane.doe, janedoe): no "/" and not "www."; otherwise it is the address of the page
    if kind in HANDLE_LINKS and re.fullmatch(r"@?[\w.-]+", text) and not text.lower().startswith("www."):
        return HANDLE_LINKS[kind].format(text.lstrip("@"))
    if kind not in ("address", "email", "phone") and re.fullmatch(r"\S+\.\S+", text):
        return web_address(text)
    return ""


def contact_text(c):
    text = t(c.get("text", "")).replace("/", "/<wbr>")
    link = contact_link(c)
    return f'<a href="{html.escape(link)}">{text}</a>' if link else text


def with_link(title_html, link):
    """A clickable title, with a small arrow showing that it is a link."""
    link = web_address(link) if link else ""
    if not link:
        return title_html
    arrow = f'<svg class="icon icon-link" viewBox="0 0 24 24" aria-hidden="true">{ICONS["link"]}</svg>'
    return f'<a class="title-link" href="{html.escape(link)}">{title_html}{arrow}</a>'


def description(d):
    """The description of an entry: every line is a bullet point, a single line too."""
    lines = [d] if isinstance(d, str) else [x for x in d or [] if str(x).strip()]
    lines = [x for x in lines if str(x).strip()]
    return '<ul class="desc">' + "".join(f"<li>{rich(x)}</li>" for x in lines) + "</ul>" if lines else ""


def extras(entry, labels):
    out = ""
    if entry.get("grade"):
        out += f'<p class="extra"><span>{t(labels["grade"])}:</span> {rich(entry["grade"])}</p>'
    if entry.get("thesis"):
        out += f'<p class="extra"><span>{t(labels["thesis"])}:</span> <em>{rich(entry["thesis"])}</em></p>'
    return out


def paragraphs(text):
    """Free text: an empty line separates paragraphs, single line breaks become spaces."""
    blocks = re.split(r"\n\s*\n", (text or "").strip())
    return "".join(f"<p>{rich(' '.join(b.split()))}</p>" for b in blocks if b.strip())


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
#  Rendering: one page structure for every style
# ---------------------------------------------------------------------
#  <div class="page STYLE has-sidebar|no-sidebar [side-right]">
#    <header class="cv-header"> photo, name, headline, contacts and details (when not in the sidebar)
#    <aside class="sidebar">    sections placed in the sidebar (only when the style shows one)
#    <main class="main-column"> the other sections
#    <footer class="privacy">
#  Every section: <section class="cv-section sec-KEY"><h2>title</h2><div class="section-body">...</div>
def entry_html(e, title_field, labels):
    org = "".join(f'<span class="{cls}">{t(e[k])}</span>'
                  for k, cls in (("organization", "org-name"), ("location", "location")) if e.get(k))
    org = f'<div class="org">{org}</div>' if org else ""
    dates = f'<span class="dates">{t(e["dates"])}</span>' if e.get("dates") else ""
    # with a link of its own the whole title is the link; otherwise it may hold links in its words
    title = with_link(t(e.get(title_field, "")), e["link"]) if e.get("link") else rich(e.get(title_field, ""))
    return (f'<article class="entry"><div class="entry-head"><h3 class="entry-title">{title}</h3>{dates}</div>'
            f'{org}{description(e.get("description"))}{extras(e, labels)}</article>')


def entries_html(items, title_field, labels):
    return '<div class="entries">' + "".join(entry_html(e, title_field, labels) for e in items) + "</div>" if items else ""


def tags_html(items):
    return '<ul class="tags">' + "".join(f"<li>{rich(x)}</li>" for x in items) + "</ul>" if items else ""


def bullets_html(items, cls="bullets"):
    return f'<ul class="{cls}">' + "".join(f"<li>{rich(x)}</li>" for x in items) + "</ul>" if items else ""


def contact_icon(c):
    """The icon of a contact: the one chosen for it ("none": no icon), otherwise the one of its type."""
    kind = c.get("icon") if c.get("icon") == "none" or c.get("icon") in ICONS else c.get("type")
    return "" if kind == "none" else f'<span class="icon-wrap">{icon(kind)}</span>'


def contacts_html(cv):
    return '<ul class="contacts">' + "".join(
        f'<li>{contact_icon(x)}<span class="contact-text">{contact_text(x)}</span></li>'
        for x in cv["contacts"]) + "</ul>"


def details_html(cv):
    return '<ul class="details">' + "".join(
        f"<li><strong>{t(d.get('label', ''))}:</strong> <span>{rich(d.get('value', ''))}</span></li>"
        for d in cv["details"]) + "</ul>"


def skills_html(cv, labels, in_side):
    groups = []
    if cv["languages"]:
        groups.append((labels["languages"], '<ul class="languages">' + "".join(
            f'<li><span class="lang">{t(x.get("language", ""))}</span><span class="level">{rich(x.get("level", ""))}</span></li>'
            for x in cv["languages"]) + "</ul>"))
    if cv["digital_skills"]:
        groups.append((labels["digital_skills"], tags_html(cv["digital_skills"])))
    if cv["soft_skills"]:
        groups.append((labels["soft_skills"], bullets_html(cv["soft_skills"], "bullets cols")))
    return "".join(f'<div class="skill-group"><h3>{t(title)}</h3><div class="group-body">{body}</div></div>'
                   for title, body in groups)


def builtin_body(cv, key, in_side):
    p, labels = cv["person"], cv["labels"]
    if key in ("profile", "about_me"):
        return paragraphs(p.get(key))
    if key == "experience":
        return entries_html(cv["experience"], "role", labels)
    if key == "education":
        return entries_html(cv["education"], "title", labels)
    if key == "skills":
        return skills_html(cv, labels, in_side)
    if key == "interests":
        return paragraphs(cv["interests_text"])
    if key == "contacts":
        return contacts_html(cv) if cv["contacts"] else ""
    if key == "details":
        return details_html(cv) if cv["details"] else ""
    return ""


def extra_body(s, labels):
    """An extra section: free text, entries, bullet list, tags and a table, in any combination."""
    out = paragraphs(s.get("text", ""))
    out += entries_html(s.get("entries") or [], "title", labels)
    out += bullets_html(s.get("list") or [])
    out += tags_html(s.get("tags") or [])
    if s.get("rows"):
        out += '<dl class="rows">' + "".join(
            f"<dt>{t(r.get('label', ''))}</dt><dd>{rich(r.get('value', ''))}</dd>" for r in s["rows"]) + "</dl>"
    return out


def section_html(key, title, body):
    return (f'<section class="cv-section sec-{key}"><h2>{t(title)}</h2>'
            f'<div class="section-body">{body}</div></section>')


def has_sidebar(cv):
    """True when at least one visible section with some content is placed in the sidebar."""
    return any(item["side"] and not item["hidden"] and
               (builtin_body(cv, item["key"], True) if item["kind"] == "builtin" else extra_body(item["section"], cv["labels"]))
               for item in cv["order"])


def render_page(cv, style, photo, frame=None, signature=None):
    """The CV (just the page body) in the chosen style, with the sidebar if a section is placed in it.
    frame: how the photo is framed (photo_frame), None = as the style frames it.
    signature: the path of the signature image, shown at the end when the CV asks for it."""
    conf = STYLES[style]
    show_side = has_sidebar(cv)
    p, labels = cv["person"], cv["labels"]
    side, main, header_extra = [], [], {"contacts": "", "details": ""}
    for item in cv["order"]:
        if item["hidden"]:
            continue
        in_side = show_side and item["side"]
        if item["kind"] == "builtin":
            key = item["key"]
            body = builtin_body(cv, key, in_side)
            if not body:
                continue
            if key in header_extra and not in_side:  # contacts and details live in the header
                header_extra[key] = body
                continue
            if key == "details" and in_side:  # a short list: no title needed
                side.append(f'<section class="cv-section sec-details">{body}</section>')
                continue
            title = labels[key]
            (side if in_side else main).append(section_html(key, title, body))
        else:
            s = item["section"]
            body = extra_body(s, labels)
            if body:
                (side if in_side else main).append(section_html("extra", s.get("title", ""), body))

    frame = frame or {}
    position = f' style="object-position: {frame["x"]:g}% {frame["y"]:g}%"' if "x" in frame else ""
    img = f'<img src="{html.escape(photo)}" alt=""{position}>' if photo else ""
    shape = f' shape-{frame["shape"]}' if frame.get("shape") in SHAPES else ""
    headline = f'<p class="headline">{rich(p["headline"])}</p>' if p.get("headline") else ""
    classes = f'page {style} {"has-sidebar" if show_side else "no-sidebar"}' + (" side-right" if conf["side"] == "right" else "")
    aside = ""
    if show_side:
        aside = (f'\n  <aside class="sidebar">' + (f'<div class="sidebar-photo{shape}">{img}</div>' if img else "")
                 + "".join(side) + "</aside>")
    # the privacy note, and the signature under it, on the right
    sign = f'<div class="signature"><img src="{html.escape(signature)}" alt=""></div>' if signature and cv.get("signed") else ""
    privacy = ""
    if sign:
        text = f'<p class="privacy-text">{rich(cv["privacy_text"])}</p>' if cv["privacy_text"] else ""
        privacy = f'\n  <footer class="privacy signed{"" if text else " signature-only"}">{text}{sign}</footer>'
    elif cv["privacy_text"]:
        privacy = f'\n  <footer class="privacy">{rich(cv["privacy_text"])}</footer>'
    return f"""<div class="{classes}">
  <header class="cv-header">
    {f'<div class="header-photo{shape}">{img}</div>' if img else ""}
    <div class="identity">
      <h1 class="name"><span class="first-name">{t(p.get("first_name", ""))}</span> <span class="last-name">{t(p.get("last_name", ""))}</span></h1>
      {headline}{header_extra["contacts"]}{header_extra["details"]}
    </div>
  </header>{aside}
  <main class="main-column">{"".join(main)}</main>{privacy}
</div>"""


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


# ---------------------------------------------------------------------
#  Framing of a photo: which part of it the styles show
# ---------------------------------------------------------------------
# x, y: 0-100, like CSS object-position (0 = the left / top edge of the photo, 100 = the right / bottom edge);
# zoom: 1 (the whole photo, cut only by the shape of the frame) to MAX_ZOOM. shape: one of SHAPES instead of
# the shape the style gives the photo (base.css, .shape-*). Each part is optional: what is missing comes
# from the style. The same framing is used in every style.
MAX_ZOOM = 4
SHAPES = ("rect", "rounded", "square", "circle")
PHOTO_NAME = re.compile(r"[^/\\\x00-\x1f]{1,200}")


def photo_frame(value):
    """A framing {"x", "y", "zoom", "shape"} (each part optional), checked and rounded; None when there is
    none: the photo as the style frames it."""
    if not isinstance(value, dict):
        return None
    out = {}
    if any(k in value for k in ("x", "y", "zoom")):
        try:
            x, y = (min(100.0, max(0.0, float(value.get(k, 50)))) for k in ("x", "y"))
            zoom = min(float(MAX_ZOOM), max(1.0, float(value.get("zoom", 1))))
            out = {"x": round(x, 1), "y": round(y, 1), "zoom": round(zoom, 2)}
        except (TypeError, ValueError):
            pass
    if value.get("shape") in SHAPES:
        out["shape"] = value["shape"]
    return out or None


def framed_photo(profile, src, frame):
    """The photo to put in the page for this framing. Zoomed in, it is a copy cut around the chosen point
    (html/<person>/photos/, needs Pillow): the page cannot enlarge the photo itself, some styles give it
    their shape (round, hexagon...). Without Pillow, or not zoomed, the photo as it is."""
    if not src or not frame or frame.get("zoom", 1) <= 1:
        return src
    source = profile.html_dir / unquote(src)
    name = f"{source.stem}.cut-{frame['x']:g}-{frame['y']:g}-{frame['zoom']:g}.jpg"
    target = source.with_name(name)
    if not target.exists():
        try:
            from PIL import Image
            with Image.open(source) as im:
                im = im.convert("RGB")
                w, h = im.width / frame["zoom"], im.height / frame["zoom"]
                left, top = (im.width - w) * frame["x"] / 100, (im.height - h) * frame["y"] / 100
                im.crop((round(left), round(top), round(left + w), round(top + h))).save(target, "JPEG", quality=92)
        except Exception:  # no Pillow, or the photo cannot be read: the whole photo
            return src
        for old in source.parent.glob(f"{glob.escape(source.stem)}.cut-*.jpg"):  # earlier framings of this photo
            if old != target:
                old.unlink(missing_ok=True)
    return "photos/" + quote(name)


# ---------------------------------------------------------------------
#  The signature: cvs/<person>/signature.png, at the end of the CVs that ask for it
# ---------------------------------------------------------------------
def signature_file(profile):
    """The signature of a CV (signature.png, or another image format), None when there is none."""
    if not profile.dir.is_dir():
        return None
    return next((f for f in sorted(profile.dir.glob("signature.*"))
                 if f.is_file() and f.suffix.lower() in PHOTO_EXTENSIONS), None)


def signature_src(profile):
    """The path of the signature for the HTML pages: a copy in html/<person>/ named after when it was changed
    (a new signature is never an old one kept by the browser). None when there is no signature."""
    f = signature_file(profile)
    if not f:
        return None
    profile.html_dir.mkdir(parents=True, exist_ok=True)
    name = f"signature-{f.stat().st_mtime_ns}{f.suffix.lower()}"
    target = profile.html_dir / name
    if not target.exists():
        shutil.copy2(f, target)
    for old in profile.html_dir.glob("signature-*"):
        if old != target:
            old.unlink(missing_ok=True)
    return quote(name)


def can_zoom():
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def color_css(style, color, show_side=False):
    """The colour variables of the chosen palette, and rules for the printed page."""
    conf = STYLES[style]
    palette = COLORS.get(color) or COLORS[conf["color"]]
    colors = {k: v for k, v in palette.items() if k != "name"}
    css = ":root{" + "".join(f"--p-{k}:{v};" for k, v in colors.items()) + "}"
    css += Template(conf["print"]).safe_substitute(colors)
    if show_side:
        css += Template(conf["print_sidebar"]).safe_substitute(colors)
    return css


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


def document(cv, language, style, photo, preview_base=None, color=None, frame=None, signature=None):
    """The complete HTML page, saved in html/<person>/. With preview_base it is meant
    for the editor: relative paths start from that address and links open in a new tab."""
    p = cv["person"]
    color = color or STYLES[style]["color"]
    base = f'<base href="{html.escape(preview_base)}" target="_blank">\n' if preview_base else ""
    # the stylesheets: from the editor's server in the preview, from this folder when printing
    styles = "/styles/" if preview_base else STYLES_DIR.as_uri() + "/"
    body = "<body>" if preview_base else '<body contenteditable="true" spellcheck="false">'
    return f"""<!doctype html>
<html lang="{base_language(language)}">
<head>
<meta charset="utf-8">
{base}<title>CV {html.escape(p.get("first_name", ""))} {html.escape(p.get("last_name", ""))}</title>
<link rel="stylesheet" href="{styles}fonts.css">
<link rel="stylesheet" href="{styles}base.css">
<link rel="stylesheet" href="{styles}{style}.css">
<style>{color_css(style, color, has_sidebar(cv))}</style>
</head>
{body}
{render_page(cv, style, photo, frame, signature)}
</body>
</html>
"""


# ---------------------------------------------------------------------
#  Photos: every photo in the photos/ folder
# ---------------------------------------------------------------------
def find_photos(profile):
    """The photos in the CV's photos/ folder, in alphabetical order."""
    if not profile.photo_dir.is_dir():
        return []
    photos, to_convert = [], []
    for f in sorted(profile.photo_dir.iterdir(), key=lambda x: x.name.lower()):
        if not f.is_file() or f.name.startswith("."):
            continue
        if f.suffix.lower() in PHOTO_EXTENSIONS:
            photos.append(f)
        elif f.suffix.lower() in CONVERT_FIRST_EXTENSIONS:
            to_convert.append(f.name)
    for name in to_convert:
        print(f"  ! {name}: browsers cannot read this format, save it as JPG or PNG.")
    return photos


def photo_label(f, conf):
    """Part of the PDF name: "photo2.jpg" -> Foto2 / Photo2, "Summer sea.png" -> Summer_sea."""
    m = re.fullmatch(r"(?:foto|photo)[\s_-]*(\d+)", f.stem, re.IGNORECASE)
    if m:
        return f"{conf['photo_word']}{m.group(1)}"
    name = re.sub(r"[^\w-]+", "_", f.stem).strip("_") or "Photo"
    return name[0].upper() + name[1:]


def prepare_photos(profile, photos):
    """Copies the photos to html/<person>/photos/, shrunk and rotated upright when needed.

    Returns, for each photo, the path to use in the HTML."""
    out_dir = profile.html_photo_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = None

    paths, used = {}, set()
    for f in photos:
        target = None
        if Image:
            try:
                with Image.open(f) as im:
                    rotated = im.getexif().get(0x0112, 1) not in (1, None)
                    if max(im.size) > MAX_PHOTO_SIDE or rotated:
                        im = ImageOps.exif_transpose(im)
                        im.thumbnail((MAX_PHOTO_SIDE, MAX_PHOTO_SIDE), Image.LANCZOS)
                        if im.mode not in ("RGB", "L"):
                            background = Image.new("RGB", im.size, "white")
                            background.paste(im, mask=im.convert("RGBA").getchannel("A"))
                            im = background
                        target = out_dir / f"{f.stem}{f.suffix.lower()}.jpg"
                        im.save(target, "JPEG", quality=90, optimize=True, progressive=True)
            except Exception as e:
                print(f"  ! {f.name}: could not shrink it ({e}), using the original.")
        elif f.stat().st_size > 1_500_000:
            print(f"  ! {f.name} is large ({f.stat().st_size // 1_000_000} MB): the PDFs will be heavy. "
                  "Install Pillow (pip install pillow) to shrink it automatically.")
        if target is None:
            target = out_dir / f.name
            shutil.copy2(f, target)
        used.add(target.name)
        paths[f] = "photos/" + quote(target.name)

    for old in out_dir.iterdir():
        if old.is_file() and old.name not in used:
            old.unlink()
    return paths


def pick_photos(profile, photos, wanted):
    """--photo: 0 = no photo, otherwise the file name (with or without extension)."""
    if wanted is None:
        return [None] + photos
    w = wanted.strip().lower()
    if w in ("0", "no", "none"):
        return [None]
    names = {w, f"photo{w}", f"foto{w}"} if w.isdigit() else {w}
    found = [f for f in photos if f.name.lower() in names or f.stem.lower() in names]
    if not found:
        available = ", ".join(f.name for f in photos) or "(the folder is empty)"
        sys.exit(f"No photo called \"{wanted}\" in {profile.photo_dir}.\nAvailable photos: {available}")
    return found


# ---------------------------------------------------------------------
#  Printing to PDF with Chrome / Chromium
# ---------------------------------------------------------------------
def find_chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "microsoft-edge", "brave-browser", "chrome"):
        if shutil.which(name):
            return shutil.which(name)
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    candidates += sorted(glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-*/chrome-headless-shell")), reverse=True)
    candidates += sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-*/chrome")), reverse=True)
    for c in candidates:
        if os.path.exists(c):
            return c
    sys.exit("Chrome/Chromium not found. Install it or give its path with CHROME=... "
             "(alternatively use --html-only and print the HTML from the browser).")


def print_pdf(chrome, source, target):
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([
            chrome, "--headless", "--no-sandbox", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            f"--user-data-dir={profile}", "--allow-file-access-from-files",
            "--no-pdf-header-footer", "--print-to-pdf-no-header", "--virtual-time-budget=10000",
            f"--print-to-pdf={target}", source.as_uri(),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)


def count_pages(pdf):
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", pdf.read_bytes()))


def load(profile, file):
    try:
        with open(profile.dir / file, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Error in {profile.name}/{file}: {e}\n(Check the quotes, brackets and commas on that line.)")


def generate(profile, language=None, style=None, photo=None, html_only=False, log=print):
    """Creates the HTML pages and the PDFs of one CV. Returns the list of PDFs created and
    the list of PDFs left over from versions that no longer exist (e.g. deleted photos)."""
    profile.html_dir.mkdir(parents=True, exist_ok=True)
    all_photos = find_photos(profile)
    photo_versions = pick_photos(profile, all_photos, photo)
    photo_src = prepare_photos(profile, all_photos)
    if not all_photos:
        log(f"  (no photos in {short_path(profile.photo_dir)}: creating only the versions without a photo)")
    chrome = None if html_only else find_chrome()
    all_settings = load_settings(profile)
    settings, frames = all_settings["styles"], all_settings["photos"]
    signature = signature_src(profile)
    generated, created = [], []

    for code, conf in languages(profile).items():
        if language and code != language:
            continue
        cv = prepare(load(profile, conf["content"]), f"{profile.name}/{conf['content']}", code)
        p = cv["person"]
        folder = profile.pdf_dir / conf["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        for style_id in STYLES:
            if style and style_id not in style:
                continue
            color = settings[style_id]["color"]
            for f in photo_versions:
                version = photo_label(f, conf) if f else conf["no_photo"]
                name = f"CV_{p.get('first_name', '')}_{p.get('last_name', '')}_{code.upper()}_{conf['styles'][style_id]}_{version}"
                name = re.sub(r"\s+", "_", re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", name))  # a valid file name
                if name in generated:  # e.g. photo2.jpg and photo2.png in the same folder
                    name += "_" + f.suffix.lstrip(".").lower()
                generated.append(name)
                source = profile.html_dir / f"{name}.html"
                frame = frames.get(f.name) if f else None
                src = framed_photo(profile, photo_src.get(f), frame)
                source.write_text(document(cv, code, style_id, src, color=color, frame=frame, signature=signature),
                                  encoding="utf-8")
                if not chrome:
                    log(f"  ✓ {short_path(source)}")
                    continue
                pdf = folder / f"{name}.pdf"
                print_pdf(chrome, source, pdf)
                pages = count_pages(pdf)
                created.append({"pdf": pdf, "pages": pages, "language": code, "style": style_id,
                                "photo": f.name if f else None})
                log(f"  ✓ {short_path(pdf)}  ({pages} p.)")

    stale = []
    if not (language or style or photo) and chrome:
        stale = [f for conf in languages(profile).values()
                 for f in sorted((profile.pdf_dir / conf["folder"]).glob("CV_*.pdf")) if f.stem not in generated]
    return created, stale


def main():
    ap = argparse.ArgumentParser(description="Build the CVs as PDF files.")
    ap.add_argument("--cv", metavar="NAME", help="only this CV (the name of its folder in cvs/)")
    ap.add_argument("--language", metavar="CODE", help="only this language (e.g. it, en)")
    ap.add_argument("--style", metavar="NAMES", help="only these styles, separated by commas (e.g. modern,swiss)")
    ap.add_argument("--photo", metavar="NAME",
                    help="only the photo with this file name (e.g. photo2 or sea.jpg); 0 = no photo")
    ap.add_argument("--html-only", action="store_true", help="create only the HTML pages (no PDFs)")
    ap.add_argument("--data", metavar="FOLDER",
                    help="the CVs are in this folder instead of the project folder (as with the editor's --data)")
    args = ap.parse_args()
    if args.data:
        use_workspace(Workspace(args.data))
    if args.style:
        args.style = [x.strip().lower() for x in args.style.split(",") if x.strip()]
        unknown = [x for x in args.style if x not in STYLES]
        if unknown:
            sys.exit(f"Unknown style: {', '.join(unknown)}. Available: {', '.join(STYLES)}")
    available = profiles()
    if args.cv:
        available = [x for x in available if x.name.lower() == args.cv.strip().lower()]
        if not available:
            sys.exit(f"No CV called \"{args.cv}\" in {short_path(workspace().cvs_dir)}. Available: "
                     + (", ".join(x.name for x in profiles()) or "none"))
    if not available:
        sys.exit(f"No CV found in {short_path(workspace().cvs_dir)}: create one with the editor (python3 editor.py).")
    for profile in available:
        print(f"{profile.name}:")
        _, stale = generate(profile, args.language, args.style, args.photo, args.html_only)
        # Warn about PDFs left over from photos or styles that no longer exist (they are not deleted)
        if stale:
            print("  These PDFs no longer match any photo or style (you can delete them):")
            for f in stale:
                print(f"    - {short_path(f)}")


if __name__ == "__main__":
    main()
