"""Photos and the signature: finding them, framing them, the smaller copies used by the pages."""
import glob
import re
import shutil
import sys
from urllib.parse import quote, unquote


PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
CONVERT_FIRST_EXTENSIONS = {".heic", ".heif", ".tif", ".tiff", ".dng", ".raw", ".cr2", ".cr3", ".nef", ".arw"}
MAX_PHOTO_SIDE = 1000  # pixels: more than enough for print


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
