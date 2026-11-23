"""Contacts: their kinds, their links and the icons drawn next to them."""
import html
import re

from .text import t, web_address


# Icons (Lucide, ISC licence: see THIRD-PARTY-NOTICES.md), drawn in the text colour
ICONS = {
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "email": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "address": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "github": '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>',
    "web": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    # more contact types (simple line drawings in the same manner)
    "whatsapp": '<path d="M3 21l1.65-3.8a9 9 0 1 1 3.4 2.9z"/><path d="M9.2 8.6c-.5 2.9 2.8 6.4 6 6l.8-1.4-1.9-1-1 .9c-.9-.3-1.9-1.3-2.2-2.2l.9-1-.9-1.9z"/>',
    "telegram": '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
    "x": '<path d="M4 4h4.5L20 20h-4.5z"/><path d="M20 4l-6.6 7.3M4 20l6.6-7.3"/>',
    "instagram": '<rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>',
    "facebook": '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>',
    "youtube": '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3z"/>',
    "gitlab": '<path d="m22 13.3-3.3-10a.4.4 0 0 0-.8 0l-2.3 6.7H8.4L6.1 3.3a.4.4 0 0 0-.8 0L2 13.3a.7.7 0 0 0 .3.8L12 21l9.7-6.9a.7.7 0 0 0 .3-.8z"/>',
    "stackoverflow": '<path d="M4 15v5h16v-5"/><path d="M8 17h8M8.4 13.3l7.8 1.6M9.6 9.3l7.2 3.3M11.9 5.4l6.1 5.1"/>',
    "behance": '<path d="M3 6v12M3 6h4.5a2.75 2.75 0 0 1 0 5.5H3M3 11.5h5a3.25 3.25 0 0 1 0 6.5H3"/><path d="M14 14.5h7a3.5 3.5 0 1 0-1.2 2.7M15.5 8.5h4"/>',
    "dribbble": '<circle cx="12" cy="12" r="10"/><path d="M19.1 5.1C15.2 9.1 10 10.4 2.3 10.9M21.8 12.8c-6.6-1.4-12.1 1-16.4 6.3M8.6 2.8c4.4 6 6 9.4 8 17.7"/>',
    "orcid": '<circle cx="12" cy="12" r="10"/><path d="M8 10.5V16M8 7.5h.01M11 8v8h2.5a4 4 0 0 0 0-8z"/>',
    "scholar": '<path d="M22 10 12 5 2 10l10 5z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/>',
    "researchgate": '<rect x="2" y="2" width="20" height="20" rx="3"/><path d="M6.5 16V8h2.5a2.2 2.2 0 0 1 0 4.4H6.5M9 12.4l2.2 3.6M18 9.3a2.8 2.8 0 1 0 .2 4.4V12h-1.6"/>',
    # general icons, to give a contact another one
    "mobile": '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>',
    "chat": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>',
    "chain": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "home": '<path d="m3 10 9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "briefcase": '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>',
    "star": '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
    "heart": '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 12 5a5.5 5.5 0 0 0-10 3.5c0 2.3 1.5 4 3 5.5l7 7z"/>',
}
# the kinds of contact, in the groups the editor shows them in, with their names (the editor's page receives them
# with the CV); the icon of each has the same name. "icon" in a contact chooses another one, "none" = no icon
CONTACT_GROUPS = [
    ("Basic", {"phone": "Phone", "email": "Email", "address": "Address", "web": "Website"}),
    ("Professional", {"linkedin": "LinkedIn", "github": "GitHub", "gitlab": "GitLab", "stackoverflow": "Stack Overflow",
                      "behance": "Behance", "dribbble": "Dribbble"}),
    ("Research", {"orcid": "ORCID", "scholar": "Google Scholar", "researchgate": "ResearchGate"}),
    ("Messaging and social", {"whatsapp": "WhatsApp", "telegram": "Telegram", "x": "X (Twitter)",
                              "instagram": "Instagram", "facebook": "Facebook", "youtube": "YouTube"}),
]
CONTACT_TYPES = [kind for _, kinds in CONTACT_GROUPS for kind in kinds]
# a handle written instead of a link (e.g. @janedoe) becomes this link
HANDLE_LINKS = {"github": "https://github.com/{}", "gitlab": "https://gitlab.com/{}", "x": "https://x.com/{}",
                "instagram": "https://www.instagram.com/{}", "telegram": "https://t.me/{}"}


def icon(kind):
    return f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">{ICONS.get(kind, ICONS["web"])}</svg>'


def contact_link(c):
    """The link of a contact. For GitHub, LinkedIn and websites it is the one written
    in "link" (the text is only the name shown); for email and phone it comes from the text."""
    text, kind = c.get("text", "").strip(), c.get("type")
    if c.get("link"):
        return web_address(c["link"])
    if kind == "email":
        return f"mailto:{text}"
    if kind == "phone":
        return "tel:" + re.sub(r"[^\d+]", "", text)
    if kind == "whatsapp" and re.sub(r"\D", "", text):
        return "https://wa.me/" + re.sub(r"\D", "", text)
    if kind == "orcid" and re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", text):
        return f"https://orcid.org/{text}"
    # a user name (@jane.doe, janedoe): no "/" and not "www."; otherwise it is the address of the page
    if kind in HANDLE_LINKS and re.fullmatch(r"@?[\w.-]+", text) and not text.lower().startswith("www."):
        return HANDLE_LINKS[kind].format(text.lstrip("@"))
    if kind not in ("address", "email", "phone") and re.fullmatch(r"\S+\.\S+", text):
        return web_address(text)
    return ""


def contact_text(c):
    text = t(c.get("text", "")).replace("/", "/<wbr>")
    link = contact_link(c)
    return f'<a href="{html.escape(link)}">{text}</a>' if link else text
