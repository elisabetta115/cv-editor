"""CVs on disk: one folder per person in cvs/, its content files and its settings."""
import re
import sys
import tomllib

from .photos import PHOTO_NAME, photo_frame
from .styles import COLORS, STYLES
from .workspace import workspace


# ---------------------------------------------------------------------
#  CVs: one folder per person in cvs/
# ---------------------------------------------------------------------
def check_cv_name(name):
    """A CV name is also a folder name: no slashes or other characters folders cannot have."""
    name = " ".join(str(name or "").split())
    if not name or name.startswith(".") or len(name) > 80 or re.search(r'[\\/:*?"<>|\x00-\x1f]', name):
        raise ValueError(f"Invalid CV name: {name!r}")
    return name


class Profile:
    """One person's CV: cvs/<name>/ with content_<code>.toml, settings.toml and photos/."""

    def __init__(self, name):
        self.name = check_cv_name(name)
        place = workspace()
        self.dir = place.cvs_dir / self.name
        self.settings_file = self.dir / "settings.toml"
        self.photo_dir = self.dir / "photos"
        self.html_dir = place.html_dir / self.name
        # smaller copies of the photos, used by the HTML pages (keeps the PDFs light)
        self.html_photo_dir = self.html_dir / "photos"
        self.pdf_dir = place.pdf_dir / self.name

    def exists(self):
        return self.dir.is_dir()


def profiles():
    """Every CV in cvs/, in alphabetical order."""
    cvs_dir = workspace().cvs_dir
    if not cvs_dir.is_dir():
        return []
    found = []
    for d in sorted(cvs_dir.iterdir(), key=lambda x: x.name.lower()):
        if d.is_dir() and not d.name.startswith("."):
            try:
                found.append(Profile(d.name))
            except ValueError:
                pass
    return found


def load_settings(profile):
    """settings.toml, written by the editor: the colour chosen for each style and the framing of each photo."""
    data = {}
    if profile.settings_file.exists():
        try:
            data = tomllib.loads(profile.settings_file.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            print(f"  ! settings.toml is not valid ({e}): using the default styles and colours.", file=sys.stderr)
    out = {}
    stored = data.get("styles") if isinstance(data.get("styles"), dict) else {}
    for style, conf in STYLES.items():
        x = stored.get(style) if isinstance(stored.get(style), dict) else {}
        color = x.get("color") if x.get("color") in COLORS else conf["color"]
        out[style] = {"color": color}
    photos = data.get("photos") if isinstance(data.get("photos"), dict) else {}
    frames = {name: frame for name, v in photos.items() if PHOTO_NAME.fullmatch(name) and (frame := photo_frame(v))}
    return {"styles": out, "photos": frames}


def load(profile, file):
    try:
        with open(profile.dir / file, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Error in {profile.name}/{file}: {e}\n(Check the quotes, brackets and commas on that line.)")
