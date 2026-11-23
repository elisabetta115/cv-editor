#!/usr/bin/env python3
"""Compare the printed CVs of two versions of the code, pixel by pixel.

    python3 tests/compare_pixels.py            # the files as they are now, against the last commit
    python3 tests/compare_pixels.py v1.0       # ... against another commit, branch or tag

The example CV is printed to PDF in every style (as it is, with a sidebar, with a photo) by both versions;
every page is compared. Use it after changing a stylesheet: tests/test_render.py notices that a page's HTML
changed, this shows whether the printed result changed, and where (the differences are saved as images).

Needs Chrome or Chromium, pdftoppm (Linux: sudo apt install poppler-utils) and Pillow (pip install pillow).
"""
import argparse
import copy
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201e5270ade"
    "0000000049454e44ae426082")


def render(tree, out):
    """Prints the example CV in every style with the code in tree/src; writes out/<version>-<style>.pdf."""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(tree / "src"))
    try:  # the code in modules (src/cv_editor/)
        from cv_editor import content, pdf, render, styles
        cv = SimpleNamespace(normalize=content.normalize, prepare=content.prepare, FIXED_SECTIONS=content.FIXED_SECTIONS,
                             SIDEBAR_SUGGESTED=content.SIDEBAR_SUGGESTED, STYLES=styles.STYLES,
                             document=render.document, find_chrome=pdf.find_chrome, print_pdf=pdf.print_pdf)
    except ImportError:  # older versions: everything was in src/generate_cv.py
        import generate_cv as cv
    data = cv.normalize(json.loads((tree / "examples" / "example-cv.json").read_text(encoding="utf-8"))["languages"]["en"], "en")
    side = copy.deepcopy(data)
    extras = [s for s in side.get("sections", []) if "builtin" not in s]
    order = []
    for key in cv.FIXED_SECTIONS:
        order.append({"builtin": key, **({"column": "side"} if key in cv.SIDEBAR_SUGGESTED else {})})
        order += [s for s in extras if s.get("after") == key]
    side["sections"] = order + [s for s in extras if s not in order]
    out.mkdir(parents=True, exist_ok=True)
    (out / "photo.png").write_bytes(TINY_PNG)
    pages = []
    for version, content, photo in (("plain", data, None), ("sidebar", side, None), ("photo", data, "photo.png")):
        prepared = cv.prepare(copy.deepcopy(content), "content_en.toml", "en")
        for style in cv.STYLES:
            page = out / f"{version}-{style}.html"
            page.write_text(cv.document(prepared, "en", style, photo), encoding="utf-8")
            pages.append(page)
    chrome = cv.find_chrome()
    if not chrome:
        sys.exit("Chrome or Chromium is needed.")
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda page: cv.print_pdf(chrome, page, page.with_suffix(".pdf")), pages))


def pages_of(pdf):
    """The pages of a PDF as images."""
    from PIL import Image
    folder = Path(tempfile.mkdtemp(dir=pdf.parent))
    subprocess.run(["pdftoppm", "-png", "-r", "100", str(pdf), str(folder / "p")], check=True)
    images = [Image.open(f).convert("RGB") for f in sorted(folder.glob("p*.png"))]
    shutil.rmtree(folder)
    return images


def compare(old, new, diffs):
    """{name: what differs} for every PDF of the two folders; images of the differences in diffs/."""
    from PIL import Image, ImageChops
    found = {}
    for pdf in sorted(new.glob("*.pdf")):
        a, b = pages_of(old / pdf.name), pages_of(pdf)
        if len(a) != len(b):
            found[pdf.stem] = f"{len(a)} pages before, {len(b)} now"
            continue
        changed = [i + 1 for i, (x, y) in enumerate(zip(a, b)) if x.size != y.size or ImageChops.difference(x, y).getbbox()]
        if changed:
            found[pdf.stem] = "page " + ", ".join(map(str, changed))
            for i in changed:
                x, y = a[i - 1], b[i - 1].resize(a[i - 1].size)
                mask = ImageChops.difference(x, y).convert("L").point(lambda v: 255 if v else 0)
                marked = Image.composite(Image.new("RGB", y.size, (230, 0, 60)), y, mask)
                side_by_side = Image.new("RGB", (x.width * 2 + 10, x.height), "white")
                side_by_side.paste(x, (0, 0))
                side_by_side.paste(marked, (x.width + 10, 0))
                side_by_side.save(diffs / f"{pdf.stem}-page{i}.png")
    return found


def main():
    ap = argparse.ArgumentParser(description="Compare the printed CVs of the code now with another version.")
    ap.add_argument("revision", nargs="?", default="HEAD", help="commit, branch or tag to compare with (default: HEAD)")
    ap.add_argument("--render", nargs=2, metavar=("TREE", "OUT"), help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.render:
        return render(Path(args.render[0]), Path(args.render[1]))
    for tool in ("pdftoppm",):
        if not shutil.which(tool):
            sys.exit(f"{tool} is needed (Linux: sudo apt install poppler-utils).")
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.exit("Pillow is needed: pip install pillow")

    work = Path(tempfile.mkdtemp(prefix="cv-editor-pixels-"))
    old_tree = work / "old-code"
    old_tree.mkdir()
    archive = subprocess.run(["git", "-C", str(REPO), "archive", args.revision], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:
        try:
            t.extractall(old_tree, filter="data")
        except TypeError:  # Python 3.11 before 3.11.4
            t.extractall(old_tree)
    print(f"Printing the example CV in every style, with {args.revision} and with the files now…")
    for tree, out in ((old_tree, work / "before"), (REPO, work / "now")):
        subprocess.run([sys.executable, "-B", __file__, "--render", str(tree), str(out)], check=True)
    diffs = work / "differences"
    diffs.mkdir()
    found = compare(work / "before", work / "now", diffs)
    total = len(list((work / "now").glob("*.pdf")))
    if not found:
        print(f"Identical: all {total} CVs print exactly as with {args.revision}.")
        shutil.rmtree(work)
        return
    print(f"{len(found)} of {total} CVs print differently from {args.revision}:")
    for name, what in found.items():
        print(f"  {name}: {what}")
    print(f"Before / now, with the differences in red: {diffs}")
    sys.exit(1)


if __name__ == "__main__":
    main()
