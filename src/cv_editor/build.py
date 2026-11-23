"""Building every version of a CV (language, style, photo) from the terminal."""
import re

from .content import prepare
from .language import languages
from .pdf import count_pages, find_chrome, print_pdf
from .photos import find_photos, framed_photo, photo_label, pick_photos, prepare_photos, signature_src
from .render import document
from .storage import load, load_settings
from .styles import STYLES
from .workspace import short_path


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
