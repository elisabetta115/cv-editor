"""Text in the CV: **bold**, *italic*, links, and the links of the contacts. Nothing unsafe reaches the page."""
import unittest

import support  # noqa: F401
from cv_editor.contacts import contact_link
from cv_editor.render import description
from cv_editor.text import paragraphs, rich, t, web_address


class TextTest(unittest.TestCase):
    def test_bold_italic_and_escaping(self):
        self.assertEqual(t("**bold** and *italic*"), "<strong>bold</strong> and <em>italic</em>")
        self.assertEqual(t("<script>alert(1)</script> & co"), "&lt;script&gt;alert(1)&lt;/script&gt; &amp; co")
        self.assertEqual(t("[my site](https://example.com)"), "[my site](https://example.com)")  # no links in t()

    def test_links(self):
        cases = {
            "[my site](https://example.com) and **[bold link](example.org)**":
                '<a class="text-link" href="https://example.com">my site</a> and '
                '<strong><a class="text-link" href="https://example.org">bold link</a></strong>',
            "see www.example.com.": 'see <a class="text-link" href="https://www.example.com">www.example.com</a>.',
            "go to https://example.com/a?b=1, then":
                'go to <a class="text-link" href="https://example.com/a?b=1">https://example.com/a?b=1</a>, then',
            "[mail](jane@example.com)": '<a class="text-link" href="mailto:jane@example.com">mail</a>',
            "[call](tel:+391234)": '<a class="text-link" href="tel:+391234">call</a>',
            "[a](https://x.com/(paren))": '<a class="text-link" href="https://x.com/(paren)">a</a>',
        }
        for text, expected in cases.items():
            self.assertEqual(rich(text), expected, text)

    def test_unsafe_links_stay_text(self):
        for text in ("[x](javascript:alert(1))", "[x](JaVaScRiPt:alert(1))", "[data](data:text/html,hi)"):
            self.assertEqual(rich(text), t(text), text)
            self.assertNotIn("<a", rich(text))
        quoted = rich('[a](https://x.com/a"onmouseover="alert(1))')
        self.assertNotIn('"onmouseover', quoted)

    def test_web_address(self):
        cases = {"https://a.com": "https://a.com", "example.com": "https://example.com", "mailto:a@b.c": "mailto:a@b.c",
                 "localhost:8080": "https://localhost:8080", "javascript:x": "", "JaVaScRiPt:x": "", "ftp://x": "", "": ""}
        for link, expected in cases.items():
            self.assertEqual(web_address(link), expected, link)

    def test_contact_links(self):
        cases = [
            ({"type": "email", "text": "a@b.com"}, "mailto:a@b.com"),
            ({"type": "phone", "text": "+39 (0)6 123-45"}, "tel:+390612345"),
            ({"type": "whatsapp", "text": "+39 333 1234"}, "https://wa.me/393331234"),
            ({"type": "orcid", "text": "0000-0002-1825-0097"}, "https://orcid.org/0000-0002-1825-0097"),
            ({"type": "github", "text": "@jane"}, "https://github.com/jane"),
            ({"type": "github", "text": "github.com/jane"}, "https://github.com/jane"),
            ({"type": "x", "text": "jane"}, "https://x.com/jane"),
            ({"type": "linkedin", "text": "Jane Doe", "link": "linkedin.com/in/jane"}, "https://linkedin.com/in/jane"),
            ({"type": "web", "text": "jane.dev"}, "https://jane.dev"),
            ({"type": "address", "text": "Via Roma 1, Roma"}, ""),
            ({"type": "web", "text": "x", "link": "javascript:alert(1)"}, ""),
        ]
        for contact, expected in cases:
            self.assertEqual(contact_link(contact), expected, contact)

    def test_paragraphs_and_descriptions(self):
        self.assertEqual(paragraphs("one\ntwo\n\n  three  "), "<p>one two</p><p>three</p>")
        self.assertEqual(description("single line"), '<ul class="desc"><li>single line</li></ul>')
        self.assertEqual(description(["a", "", "  ", "b"]), '<ul class="desc"><li>a</li><li>b</li></ul>')
        self.assertEqual(description([]), "")


if __name__ == "__main__":
    unittest.main()
