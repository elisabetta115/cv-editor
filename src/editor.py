#!/usr/bin/env python3
"""
CV editor: opens in the browser.

    python3 editor.py              # open the editor
    python3 editor.py --install    # add "CV Editor" to the applications menu (Linux)

On Windows and macOS, double-clicking "Start CV Editor - Windows.bat" or "Start CV Editor - Mac.command" in the
project folder runs this file.

Edit the content on the left and see the CV update live on the right.
"Save" writes the cvs/<name>/content_<code>.toml files; "PDF" downloads the version on screen.
Every person has their own CV; CVs can be exported to and imported from a .json or a .zip file
(the .zip holds the same folders as cvs/).
The editor keeps running until you close the terminal window (or press Ctrl+C).
"""
import argparse
import shutil
import signal
import sys
import tempfile
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(f"CV Editor needs Python 3.11 or newer (this is {sys.version.split()[0]}): https://www.python.org/downloads/")

from cv_editor.server import PORT, Handler, already_running
from cv_editor.workspace import SRC, Workspace, use_workspace, workspace


def install():
    """Adds "CV Editor" to the applications menu (Linux)."""
    if sys.platform in ("win32", "darwin"):
        launcher = "Start CV Editor - Windows.bat" if sys.platform == "win32" else "Start CV Editor - Mac.command"
        print(f'On this computer, double-click "{launcher}" in the project folder ({SRC.parent}) to open the editor.\n'
              "To keep it at hand, make a shortcut to that file: see the README, under Install.")
        return
    folder = Path.home() / ".local/share/applications"
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / "cv-editor.desktop"
    file.write_text(f"""[Desktop Entry]
Type=Application
Name=CV Editor
Comment=Edit CVs and build the PDFs
Exec={sys.executable} "{Path(__file__).resolve()}"
Path={SRC}
Terminal=true
Icon=x-office-document
Categories=Office;
""", encoding="utf-8")
    file.chmod(0o755)
    print(f'Done: look for "CV Editor" among your applications ({file}).')


def main():
    ap = argparse.ArgumentParser(description="CV editor (opens in the browser).")
    ap.add_argument("--install", action="store_true", help='add "CV Editor" to the applications menu')
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--data", metavar="FOLDER", help="keep the CVs and PDFs in this folder instead of the project folder")
    ap.add_argument("--demo", action="store_true",
                    help="try the editor as a new user: an empty temporary folder, deleted when the editor closes")
    args = ap.parse_args()
    if args.install:
        return install()
    demo_dir = None
    if args.demo:
        demo_dir = tempfile.mkdtemp(prefix="cv-editor-demo-")
        use_workspace(Workspace(demo_dir, demo=True))  # a translator key added in the demo is forgotten with it
        if args.port == PORT:
            args.port = PORT + 1  # next to a normal editor that may be open
    elif args.data:
        use_workspace(Workspace(args.data))

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        if already_running(args.port):
            print("The editor is already open: showing it in the browser.")
            webbrowser.open(f"http://127.0.0.1:{args.port}/")
            return
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # port taken by something else: use another one
    # closing the terminal window ends the editor cleanly (the demo folder is deleted)
    for sig in ("SIGTERM", "SIGHUP", "SIGBREAK"):  # SIGBREAK: Windows
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), lambda *_: sys.exit(0))
    address = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"CV editor running at {address}" + ("  (DEMO: empty, nothing is kept)" if workspace().demo else ""))
    print("To close it, close this window (or press Ctrl+C).")
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [address]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEditor closed.")
    finally:
        if demo_dir:
            shutil.rmtree(demo_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
