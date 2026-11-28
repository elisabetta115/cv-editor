#!/bin/sh
# CV Editor for macOS: double-click this file in the Finder to open the editor in your browser.
# Keep the Terminal window open while you use the editor: closing it closes the editor.
cd "$(dirname "$0")" || exit 1

# $1 is Python 3.11 or newer
usable() {
  case "$(command -v "$1")" in
    "") return 1 ;;
    # Apple's own python3 is older, and without the developer tools it opens a window asking to install them
    /usr/bin/python3) if [ "$(uname)" = Darwin ] && ! xcode-select -p >/dev/null 2>&1; then return 1; fi ;;
  esac
  "$1" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null
}

for python in python3.15 python3.14 python3.13 python3.12 python3.11 python3 \
              /opt/homebrew/bin/python3 /usr/local/bin/python3 \
              /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  if usable "$python"; then
    exec "$python" src/editor.py "$@"
  fi
done

echo "CV Editor needs Python 3.11 or newer, which is not on this Mac yet."
echo
echo "1. Install it from https://www.python.org/downloads/ (the page opens now)."
echo "2. Then double-click this file again."
open "https://www.python.org/downloads/" 2>/dev/null
exit 1
