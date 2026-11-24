"""The CV as an HTML page: one page structure for every style."""
import html

from .contacts import ICONS, contact_text, icon
from .language import base_language
from .photos import SHAPES
from .styles import STYLES, adjust_css, color_css
from .text import paragraphs, rich, t, web_address
from .workspace import STYLES_DIR


def with_link(title_html, link):
    """A clickable title, with a small arrow showing that it is a link."""
    link = web_address(link) if link else ""
    if not link:
        return title_html
    arrow = f'<svg class="icon icon-link" viewBox="0 0 24 24" aria-hidden="true">{ICONS["link"]}</svg>'
    return f'<a class="title-link" href="{html.escape(link)}">{title_html}{arrow}</a>'


def description(d):
    """The description of an entry: every line is a bullet point, a single line too."""
    lines = [d] if isinstance(d, str) else [x for x in d or [] if str(x).strip()]
    lines = [x for x in lines if str(x).strip()]
    return '<ul class="desc">' + "".join(f"<li>{rich(x)}</li>" for x in lines) + "</ul>" if lines else ""


def extras(entry, labels):
    out = ""
    if entry.get("grade"):
        out += f'<p class="extra"><span>{t(labels["grade"])}:</span> {rich(entry["grade"])}</p>'
    if entry.get("thesis"):
        out += f'<p class="extra"><span>{t(labels["thesis"])}:</span> <em>{rich(entry["thesis"])}</em></p>'
    return out


# ---------------------------------------------------------------------
#  Rendering: one page structure for every style
# ---------------------------------------------------------------------
#  <div class="page STYLE has-sidebar|no-sidebar [side-right]">
#    <header class="cv-header"> photo, name, headline, contacts and details (when not in the sidebar)
#    <aside class="sidebar">    sections placed in the sidebar (only when the style shows one)
#    <main class="main-column"> the other sections
#    <footer class="privacy">
#  Every section: <section class="cv-section sec-KEY"><h2>title</h2><div class="section-body">...</div>
def entry_html(e, title_field, labels):
    org = "".join(f'<span class="{cls}">{t(e[k])}</span>'
                  for k, cls in (("organization", "org-name"), ("location", "location")) if e.get(k))
    org = f'<div class="org">{org}</div>' if org else ""
    dates = f'<span class="dates">{t(e["dates"])}</span>' if e.get("dates") else ""
    # with a link of its own the whole title is the link; otherwise it may hold links in its words
    title = with_link(t(e.get(title_field, "")), e["link"]) if e.get("link") else rich(e.get(title_field, ""))
    return (f'<article class="entry"><div class="entry-head"><h3 class="entry-title">{title}</h3>{dates}</div>'
            f'{org}{description(e.get("description"))}{extras(e, labels)}</article>')


def entries_html(items, title_field, labels):
    return '<div class="entries">' + "".join(entry_html(e, title_field, labels) for e in items) + "</div>" if items else ""


def tags_html(items):
    return '<ul class="tags">' + "".join(f"<li>{rich(x)}</li>" for x in items) + "</ul>" if items else ""


def bullets_html(items, cls="bullets"):
    return f'<ul class="{cls}">' + "".join(f"<li>{rich(x)}</li>" for x in items) + "</ul>" if items else ""


def contact_icon(c):
    """The icon of a contact: the one chosen for it ("none": no icon), otherwise the one of its type."""
    kind = c.get("icon") if c.get("icon") == "none" or c.get("icon") in ICONS else c.get("type")
    return "" if kind == "none" else f'<span class="icon-wrap">{icon(kind)}</span>'


def contacts_html(cv):
    return '<ul class="contacts">' + "".join(
        f'<li>{contact_icon(x)}<span class="contact-text">{contact_text(x)}</span></li>'
        for x in cv["contacts"]) + "</ul>"


def details_html(cv):
    return '<ul class="details">' + "".join(
        f"<li><strong>{t(d.get('label', ''))}:</strong> <span>{rich(d.get('value', ''))}</span></li>"
        for d in cv["details"]) + "</ul>"


def skills_html(cv, labels, in_side):
    groups = []
    if cv["languages"]:
        groups.append((labels["languages"], '<ul class="languages">' + "".join(
            f'<li><span class="lang">{t(x.get("language", ""))}</span><span class="level">{rich(x.get("level", ""))}</span></li>'
            for x in cv["languages"]) + "</ul>"))
    if cv["digital_skills"]:
        groups.append((labels["digital_skills"], tags_html(cv["digital_skills"])))
    if cv["soft_skills"]:
        groups.append((labels["soft_skills"], bullets_html(cv["soft_skills"], "bullets cols")))
    return "".join(f'<div class="skill-group"><h3>{t(title)}</h3><div class="group-body">{body}</div></div>'
                   for title, body in groups)


def builtin_body(cv, key, in_side):
    p, labels = cv["person"], cv["labels"]
    if key in ("profile", "about_me"):
        return paragraphs(p.get(key))
    if key == "experience":
        return entries_html(cv["experience"], "role", labels)
    if key == "education":
        return entries_html(cv["education"], "title", labels)
    if key == "skills":
        return skills_html(cv, labels, in_side)
    if key == "interests":
        return paragraphs(cv["interests_text"])
    if key == "contacts":
        return contacts_html(cv) if cv["contacts"] else ""
    if key == "details":
        return details_html(cv) if cv["details"] else ""
    return ""


def extra_body(s, labels):
    """An extra section: free text, entries, bullet list, tags and a table, in any combination."""
    out = paragraphs(s.get("text", ""))
    out += entries_html(s.get("entries") or [], "title", labels)
    out += bullets_html(s.get("list") or [])
    out += tags_html(s.get("tags") or [])
    if s.get("rows"):
        out += '<dl class="rows">' + "".join(
            f"<dt>{t(r.get('label', ''))}</dt><dd>{rich(r.get('value', ''))}</dd>" for r in s["rows"]) + "</dl>"
    return out


def section_html(key, title, body):
    return (f'<section class="cv-section sec-{key}"><h2>{t(title)}</h2>'
            f'<div class="section-body">{body}</div></section>')


def has_sidebar(cv):
    """True when at least one visible section with some content is placed in the sidebar."""
    return any(item["side"] and not item["hidden"] and
               (builtin_body(cv, item["key"], True) if item["kind"] == "builtin" else extra_body(item["section"], cv["labels"]))
               for item in cv["order"])


def render_page(cv, style, photo, frame=None, signature=None):
    """The CV (just the page body) in the chosen style, with the sidebar if a section is placed in it.
    frame: how the photo is framed (photo_frame), None = as the style frames it.
    signature: the path of the signature image, shown at the end when the CV asks for it."""
    conf = STYLES[style]
    show_side = has_sidebar(cv)
    p, labels = cv["person"], cv["labels"]
    side, main, header_extra = [], [], {"contacts": "", "details": ""}
    for item in cv["order"]:
        if item["hidden"]:
            continue
        in_side = show_side and item["side"]
        if item["kind"] == "builtin":
            key = item["key"]
            body = builtin_body(cv, key, in_side)
            if not body:
                continue
            if key in header_extra and not in_side:  # contacts and details live in the header
                header_extra[key] = body
                continue
            if key == "details" and in_side:  # a short list: no title needed
                side.append(f'<section class="cv-section sec-details">{body}</section>')
                continue
            title = labels[key]
            (side if in_side else main).append(section_html(key, title, body))
        else:
            s = item["section"]
            body = extra_body(s, labels)
            if body:
                (side if in_side else main).append(section_html("extra", s.get("title", ""), body))

    frame = frame or {}
    position = f' style="object-position: {frame["x"]:g}% {frame["y"]:g}%"' if "x" in frame else ""
    img = f'<img src="{html.escape(photo)}" alt=""{position}>' if photo else ""
    shape = f' shape-{frame["shape"]}' if frame.get("shape") in SHAPES else ""
    headline = f'<p class="headline">{rich(p["headline"])}</p>' if p.get("headline") else ""
    classes = f'page {style} {"has-sidebar" if show_side else "no-sidebar"}' + (" side-right" if conf["side"] == "right" else "")
    aside = ""
    if show_side:
        aside = (f'\n  <aside class="sidebar">' + (f'<div class="sidebar-photo{shape}">{img}</div>' if img else "")
                 + "".join(side) + "</aside>")
    # the privacy note, and the signature under it, on the right
    sign = f'<div class="signature"><img src="{html.escape(signature)}" alt=""></div>' if signature and cv.get("signed") else ""
    privacy = ""
    if sign:
        text = f'<p class="privacy-text">{rich(cv["privacy_text"])}</p>' if cv["privacy_text"] else ""
        privacy = f'\n  <footer class="privacy signed{"" if text else " signature-only"}">{text}{sign}</footer>'
    elif cv["privacy_text"]:
        privacy = f'\n  <footer class="privacy">{rich(cv["privacy_text"])}</footer>'
    return f"""<div class="{classes}">
  <header class="cv-header">
    {f'<div class="header-photo{shape}">{img}</div>' if img else ""}
    <div class="identity">
      <h1 class="name"><span class="first-name">{t(p.get("first_name", ""))}</span> <span class="last-name">{t(p.get("last_name", ""))}</span></h1>
      {headline}{header_extra["contacts"]}{header_extra["details"]}
    </div>
  </header>{aside}
  <main class="main-column">{"".join(main)}</main>{privacy}
</div>"""


def document(cv, language, style, photo, preview_base=None, color=None, frame=None, signature=None, adjust=None):
    """The complete HTML page, saved in html/<person>/. With preview_base it is meant
    for the editor: relative paths start from that address and links open in a new tab.
    adjust: the style fitted to this CV (the Adjust panel), None = as designed."""
    p = cv["person"]
    color = color or STYLES[style]["color"]
    base = f'<base href="{html.escape(preview_base)}" target="_blank">\n' if preview_base else ""
    # the stylesheets: from the editor's server in the preview, from this folder when printing
    styles = "/styles/" if preview_base else STYLES_DIR.as_uri() + "/"
    body = "<body>" if preview_base else '<body contenteditable="true" spellcheck="false">'
    return f"""<!doctype html>
<html lang="{base_language(language)}">
<head>
<meta charset="utf-8">
{base}<title>CV {html.escape(p.get("first_name", ""))} {html.escape(p.get("last_name", ""))}</title>
<link rel="stylesheet" href="{styles}fonts.css">
<link rel="stylesheet" href="{styles}base.css">
<link rel="stylesheet" href="{styles}{style}.css">
<style>{color_css(style, color, has_sidebar(cv))}{adjust_css(adjust)}</style>
</head>
{body}
{render_page(cv, style, photo, frame, signature)}
</body>
</html>
"""
