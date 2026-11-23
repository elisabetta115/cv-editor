"""Text in the CV as HTML: **bold**, *italic*, links, and only safe addresses."""
import html
import re


# ---------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------
# links written in the text: [words to show](address), or an address written as it is (https://…, www.…)
MARKDOWN_LINK = re.compile(r"\[([^\[\]\n]+)\]\(\s*((?:[^\s()]|\([^\s()]*\))+)\s*\)")
TEXT_LINK = re.compile(MARKDOWN_LINK.pattern + r"|(?<![\w@/.\-])((?:https?://|www\.)[^\s<>\[\]()*\"']+)", re.IGNORECASE)
EMAIL = re.compile(r"[^@\s/:]+@[^@\s/]+\.[^@\s/]+")


def t(text, links=False):
    """HTML-safe text, with **bold** and *italic*. links: [words](address) and the addresses written as
    they are (https://…, www.…) become links too; an address that is not safe (javascript:…) stays text."""
    text, found = str(text), []
    if links:
        def keep(m):
            if m.group(1) is not None:  # [words](address)
                words, address, after = t(m.group(1)), m.group(2), ""
            else:  # an address in the sentence: the full stop or comma after it is not part of it
                address = m.group(3).rstrip(".,;:!?")
                words, after = html.escape(address, quote=False), m.group(3)[len(address):]
            url = f"mailto:{address}" if EMAIL.fullmatch(address) else web_address(address)
            if not url:
                return m.group(0)
            found.append(f'<a class="text-link" href="{html.escape(url)}">{words}</a>')
            return f"{len(found) - 1}{after}"
        text = TEXT_LINK.sub(keep, text.replace("", "").replace("", ""))
    s = html.escape(text, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    if found:
        s = re.sub("(\\d+)", lambda m: found[int(m.group(1))], s)
    return s


def rich(text):
    """Text of the CV that can hold links (descriptions, free text, lists, tags, tables...)."""
    return t(text, links=True)


def web_address(link):
    """A safe link: web, email and phone addresses only ("" for javascript:, data: and the like)."""
    link = str(link).strip()
    if re.match(r"(https?|mailto|tel):", link, re.IGNORECASE):
        return link
    if re.match(r"[a-z][a-z0-9+.-]*:(?!\d)", link, re.IGNORECASE):  # another scheme (but not host:port)
        return ""
    return f"https://{link}" if link else ""


def paragraphs(text):
    """Free text: an empty line separates paragraphs, single line breaks become spaces."""
    blocks = re.split(r"\n\s*\n", (text or "").strip())
    return "".join(f"<p>{rich(' '.join(b.split()))}</p>" for b in blocks if b.strip())
