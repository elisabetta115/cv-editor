"""Printing the pages to PDF with Chrome or Chromium."""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile


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
    candidates = [  # macOS: in Applications, or in the Applications folder of the user
        f"{apps}/{app}.app/Contents/MacOS/{app}" for apps in ("/Applications", os.path.expanduser("~/Applications"))
        for app in ("Google Chrome", "Chromium", "Microsoft Edge", "Brave Browser")]
    folders = [os.environ[f] for f in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA") if os.environ.get(f)]
    candidates += [  # Windows: Chrome first, for everyone or for the user only; Edge is always there
        os.path.join(folder, *path) for path in (("Google", "Chrome", "Application", "chrome.exe"),
                                                 ("Microsoft", "Edge", "Application", "msedge.exe"),
                                                 ("BraveSoftware", "Brave-Browser", "Application", "brave.exe"))
        for folder in folders]
    candidates += sorted(glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-*/chrome-headless-shell")), reverse=True)
    candidates += sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-*/chrome")), reverse=True)
    for c in candidates:
        if os.path.exists(c):
            return c
    sys.exit("Chrome/Chromium not found. Install it or give its path with CHROME=... "
             "(alternatively use --html-only and print the HTML from the browser).")


def print_pdf(chrome, source, target):
    # ignore_cleanup_errors: on Windows, Chrome may still hold a file of its profile for a moment after it ends
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        subprocess.run([
            chrome, "--headless", "--no-sandbox", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            f"--user-data-dir={profile}", "--allow-file-access-from-files",
            "--no-pdf-header-footer", "--print-to-pdf-no-header", "--virtual-time-budget=10000",
            f"--print-to-pdf={target}", source.as_uri(),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)


def count_pages(pdf):
    return pages_in(pdf.read_bytes())


def pages_in(content):
    """The number of pages of a PDF made by Chrome (its bytes)."""
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", content))
