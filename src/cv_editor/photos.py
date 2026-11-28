"""Photos and the signature: finding them, framing them, the smaller copies used by the pages."""
import glob
import io
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
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


MAX_PHOTO_BYTES = 15_000_000


def write_photo(profile, name, content):
    name = Path(unquote(str(name or ""))).name
    ext = Path(name).suffix.lower()
    if ext in CONVERT_FIRST_EXTENSIONS:
        raise RuntimeError(f"{name}: browsers cannot read this format. Save it as JPG or PNG first.")
    if ext not in PHOTO_EXTENSIONS or name.startswith("."):
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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
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
    if ext not in PHOTO_EXTENSIONS | {".pdf"}:
        raise RuntimeError("Choose an image (PNG, JPG) or a PDF of your signature.")
    if len(content) > MAX_PHOTO_BYTES:
        raise RuntimeError("The file is too large.")
    if ext == ".pdf":
        if not can_zoom():
            raise RuntimeError("To use a PDF the editor needs Pillow (pip install pillow). Or save the signature as PNG or JPG.")
        content, ext = pdf_to_png(content), ".png"
    if can_zoom():
        content, ext = cut_out_signature(content), ".png"
    profile.dir.mkdir(parents=True, exist_ok=True)
    for old in profile.dir.glob("signature.*"):
        old.unlink()
    (profile.dir / f"signature{ext}").write_bytes(content)
