"""The styles (one stylesheet each in src/styles/) and the colour palettes."""
import re
from string import Template

from .workspace import STYLES_DIR


# ---------------------------------------------------------------------
#  Colours and styles
# ---------------------------------------------------------------------
# Colour palettes, shared by every style. Each style uses:
#   dark  = headings, name, coloured bands   mid = organisations, icons, details
#   light = decorations (dots, labels)        bg  = light background (creative style)
COLORS = {
    "navy":       {"name": "Navy",         "dark": "#1d3a5f", "mid": "#2e5c8a", "light": "#6fa8dc", "bg": "#eef2f7"},
    "azure":      {"name": "Azure",        "dark": "#0d497d", "mid": "#1677bd", "light": "#3ec3e2", "bg": "#edf1f5"},
    "indigo":     {"name": "Indigo",       "dark": "#2a2f7a", "mid": "#4650b8", "light": "#9aa3f0", "bg": "#eff0fb"},
    "plum":       {"name": "Plum",         "dark": "#3d2856", "mid": "#6a4a94", "light": "#b9a0dc", "bg": "#f2eff7"},
    "teal":       {"name": "Teal",         "dark": "#134e4a", "mid": "#0f766e", "light": "#2ec4b6", "bg": "#ecf5f4"},
    "emerald":    {"name": "Emerald",      "dark": "#064e3b", "mid": "#047857", "light": "#34d399", "bg": "#ecf8f3"},
    "forest":     {"name": "Forest green", "dark": "#24452c", "mid": "#3d7a4e", "light": "#8cc59a", "bg": "#eef4ef"},
    "olive":      {"name": "Olive",        "dark": "#3b4419", "mid": "#5e6b22", "light": "#b5c26a", "bg": "#f4f6ea"},
    "burgundy":   {"name": "Burgundy",     "dark": "#5e1a2a", "mid": "#962d43", "light": "#e28a9b", "bg": "#f7eef0"},
    "crimson":    {"name": "Crimson",      "dark": "#7a1820", "mid": "#b42332", "light": "#f08a8f", "bg": "#fbeeef"},
    "rose":       {"name": "Rose",         "dark": "#7a1f4b", "mid": "#b03a70", "light": "#f2a0c4", "bg": "#fbf0f5"},
    "terracotta": {"name": "Terracotta",   "dark": "#6b2e14", "mid": "#a8461d", "light": "#f0a47c", "bg": "#f8f0ea"},
    "mustard":    {"name": "Mustard",      "dark": "#5c4300", "mid": "#8a6500", "light": "#e8b931", "bg": "#fbf6e6"},
    "chocolate":  {"name": "Chocolate",    "dark": "#3f2416", "mid": "#7a4b30", "light": "#c99a78", "bg": "#f6f0eb"},
    "graphite":   {"name": "Graphite",     "dark": "#1f2933", "mid": "#4a5563", "light": "#9aa5b1", "bg": "#f0f2f4"},
    "gold":       {"name": "Black & gold", "dark": "#1b1b1b", "mid": "#86661a", "light": "#cfa64a", "bg": "#f7f4ec"},
}

# The styles: one stylesheet each in styles/ (besides base.css and fonts.css). Adding a style
# is adding a file: the comment at its top describes it, with these lines:
#   @name          the name shown in the editor
#   @group         classic | modern | creative | themed  (how the editor groups the styles)
#   @color         the palette it starts with
#   @side          right: the sidebar goes on the right (left otherwise)
#   @tags          words to find it with the editor's search, separated by commas
#   @print         rules for the printed page that need the palette colours: CSS variables do not
#   @print-sidebar work inside @page, so write $dark, $mid, $light or $bg ("-sidebar": only when
#                  the CV has a sidebar), e.g. @print @page{background:$bg}
# The other lines of the comment are the description shown in the editor.
STYLE_GROUPS = {"classic": "Classic & formal", "modern": "Clean & modern", "creative": "Bold & creative",
                "themed": "Themed"}
NOT_STYLES = {"base", "fonts"}


def load_styles():
    found = []
    for f in STYLES_DIR.glob("*.css"):
        if f.stem in NOT_STYLES or not re.fullmatch(r"[a-z][a-z0-9-]*", f.stem):
            continue
        m = re.match(r"\s*/\*(.*?)\*/", f.read_text(encoding="utf-8"), re.S)
        meta, text = {}, []
        for line in (m.group(1) if m else "").splitlines():
            line = line.strip()
            k = re.match(r"@([a-z-]+)\s+(.*)", line)
            if k:
                meta[k.group(1)] = k.group(2).strip()
            elif line and not line.startswith("="):
                text.append(line)
        conf = {"name": meta.get("name") or f.stem.title(),
                "group": meta.get("group") if meta.get("group") in STYLE_GROUPS else "modern",
                "color": meta.get("color") if meta.get("color") in COLORS else "navy",
                "side": "right" if meta.get("side") == "right" else "left",
                "tags": [x.strip() for x in meta.get("tags", "").split(",") if x.strip()],
                "description": " ".join(text),
                "print": meta.get("print", ""), "print_sidebar": meta.get("print-sidebar", "")}
        found.append((list(STYLE_GROUPS).index(conf["group"]), conf["name"].lower(), f.stem, conf))
    return {stem: conf for _, _, stem, conf in sorted(found)}


STYLES = load_styles()


# The Adjust panel: a style fitted to a CV, in % of the style's own design (100 = as designed), and whether a long
# entry may continue on the next page. Each style keeps its own (settings.toml, [styles.<id>]). The stylesheets
# multiply what they set by these: calc(6mm * var(--adj-space, 1)).
ADJUSTMENTS = {                          # name: (smallest, largest, CSS variable)
    "text": (80, 120, "--adj-text"),     # text size
    "spacing": (50, 150, "--adj-space"), # space between sections and between entries
    "lines": (85, 115, "--adj-lines"),   # line spacing of the text (names and headings keep theirs)
}


def adjust_values(value):
    """The adjustments of a style, checked and rounded: only those that differ from the style's design."""
    value = value if isinstance(value, dict) else {}
    out = {}
    for name, (low, high, _) in ADJUSTMENTS.items():
        v = value.get(name)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            v = round(min(high, max(low, v)))
            if v != 100:
                out[name] = v
    if value.get("split") is True:
        out["split"] = True
    return out


def adjust_css(adjust):
    """The CSS of the adjustments; nothing at all for a style as designed."""
    adjust = adjust_values(adjust)
    css = "".join(f"{var}:{adjust[name] / 100:g};" for name, (_, _, var) in ADJUSTMENTS.items() if name in adjust)
    css = f":root{{{css}}}" if css else ""
    if adjust.get("split"):  # a long entry may continue on the next page: its bullet points stay whole
        css += ".entry{break-inside:auto}.entry-head,.entry .org{break-after:avoid}"
    return css


def color_css(style, color, show_side=False):
    """The colour variables of the chosen palette, and rules for the printed page."""
    conf = STYLES[style]
    palette = COLORS.get(color) or COLORS[conf["color"]]
    colors = {k: v for k, v in palette.items() if k != "name"}
    css = ":root{" + "".join(f"--p-{k}:{v};" for k, v in colors.items()) + "}"
    css += Template(conf["print"]).safe_substitute(colors)
    if show_side:
        css += Template(conf["print_sidebar"]).safe_substitute(colors)
    return css
