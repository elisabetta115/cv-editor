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
    return pages_in(pdf.read_bytes())


def pages_in(content):
    """The number of pages of a PDF made by Chrome (its bytes)."""
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", content))
