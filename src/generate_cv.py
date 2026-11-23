#!/usr/bin/env python3
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
import sys

from cv_editor.build import generate
from cv_editor.storage import profiles
from cv_editor.styles import STYLES
from cv_editor.workspace import Workspace, short_path, use_workspace, workspace


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
