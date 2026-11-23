"""Languages: the known ones (names, section titles, words in file names) and language codes."""
import re
import tomllib

from .styles import STYLES


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
