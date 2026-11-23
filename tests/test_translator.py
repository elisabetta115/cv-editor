"""Automatic translation: what is translated, what stays as written, and links kept through the translation.
No translator is called: a fake one stands in for the local AI and for Azure."""
import os
import unittest
from unittest import mock

from support import DataDirTestCase, example_content, translator
from cv_editor.language import KNOWN_LANGUAGES


def fake_engine(lines, kinds, r):
    """Translates every line by writing it in capitals, keeping the addresses of links as they are."""
    def upper(line):
        html, addresses = translator._to_html(line)
        return translator._from_html(html.upper().replace("<A ID=", "<a id=").replace("</A>", "</a>")
                                     .replace("<B>", "<b>").replace("</B>", "</b>").replace("<I>", "<i>").replace("</I>", "</i>"),
                                     addresses)
    return {line: upper(line) for line in lines}, sum(map(len, lines))


class LinesTest(unittest.TestCase):
    def test_html_round_trip(self):
        line = "Led the **redesign** of the [mobile app](https://example.com/app) for *2 million* people."
        html, addresses = translator._to_html(line)
        self.assertEqual(addresses, ["https://example.com/app"])
        self.assertNotIn("https://", html)  # the address is not sent to the translator
        self.assertEqual(translator._from_html(html, addresses), line)

    def test_a_lost_link_is_noticed(self):
        html, addresses = translator._to_html("See [my site](https://example.com).")
        self.assertIsNone(translator._from_html("See my site.", addresses))

    def test_addresses_stay_as_written(self):
        line = "See [my site](https://example.com) and [the shop](https://shop.example.com)."
        changed = "Vedi [il mio sito](https://esempio.com) e [il negozio](https://negozio.esempio.com)."
        self.assertEqual(translator._keep_links(line, changed),
                         "Vedi [il mio sito](https://example.com) e [il negozio](https://shop.example.com).")
        self.assertIsNone(translator._keep_links(line, "Vedi il mio sito."))

    def test_paragraphs(self):
        self.assertEqual(translator._paragraphs("one\ntwo\n\n three "), ["one two", "three"])


class TranslateCvTest(unittest.TestCase):
    def translate(self, data, source="en", target="it"):
        with mock.patch.dict(translator.ENGINES, {"fake": fake_engine}):
            return translator.translate_cv({"data": data, "from": source, "to": target, "engine": "fake"})

    def test_what_changes_and_what_stays(self):
        data = example_content()
        out = self.translate(data)["data"]
        person = out["person"]
        self.assertEqual((person["first_name"], person["last_name"]), ("Alex", "Morgan"))      # names stay
        self.assertEqual(person["headline"], "PRODUCT DESIGNER")                               # text is translated
        self.assertEqual(out["contacts"], data["contacts"])                                    # contacts stay
        self.assertEqual(out["experience"][0]["organization"], data["experience"][0]["organization"])
        self.assertEqual(out["experience"][0]["role"], data["experience"][0]["role"].upper())
        # the words of a link are translated, its address stays exactly as written
        self.assertEqual(out["experience"][0]["description"][0],
                         "LED THE REDESIGN OF THE [MOBILE APP](https://example.com/app) USED BY 2 MILLION PEOPLE.")
        # section titles known for Italian come from the editor, not from the translator
        self.assertEqual(out["labels"]["experience"], KNOWN_LANGUAGES["it"]["labels"]["experience"])

    def test_paragraphs_are_kept(self):
        data = example_content()
        data["person"]["about_me"] = "First paragraph,\nsame paragraph.\n\nSecond paragraph."
        about = self.translate(data)["data"]["person"]["about_me"]
        self.assertEqual(about, "FIRST PARAGRAPH, SAME PARAGRAPH.\n\nSECOND PARAGRAPH.")

    def test_other_versions_and_bad_codes(self):
        self.assertEqual(self.translate(example_content(), "en-bigtech", "it-roma")["data"]["person"]["first_name"], "Alex")
        for source, target in (("EN", "it"), ("en", "../it"), (None, "it")):
            with self.assertRaises(RuntimeError):
                self.translate(example_content(), source, target)

    def test_unknown_translator(self):
        with self.assertRaises(RuntimeError):
            translator.translate_cv({"data": {}, "from": "en", "to": "it", "engine": "nope"})


class KeyTest(DataDirTestCase):
    """Where the Microsoft Translator key is kept: a file in the user's settings, or only in memory in the demo."""

    def setUp(self):
        super().setUp()
        patches = [mock.patch.object(translator, "CONFIG_FILE", self.data_dir / "config" / "translator.json"),
                   mock.patch.dict("os.environ", {}, clear=False)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("AZURE_TRANSLATOR_KEY", None)

    def test_key_in_a_file(self):
        translator.CONFIG_FILE.parent.mkdir()
        translator.CONFIG_FILE.write_text('{"key": "' + "k" * 32 + '", "region": "westeurope"}')
        self.assertEqual(translator.credentials(), ("k" * 32, "westeurope"))
        translator.set_key({"key": ""})                       # an empty key removes it
        self.assertFalse(translator.CONFIG_FILE.exists())
        self.assertEqual(translator.credentials(), ("", ""))


class DemoKeyTest(DataDirTestCase):
    demo = True

    def test_the_demo_keeps_the_key_in_memory(self):
        with mock.patch.object(translator, "CONFIG_FILE", self.data_dir / "config" / "translator.json"), \
                mock.patch.dict("os.environ", {}, clear=False):
            os.environ.pop("AZURE_TRANSLATOR_KEY", None)
            self.workspace.translator_memory.update({"key": "d" * 32, "region": "northeurope"})
            self.assertEqual(translator.credentials(), ("d" * 32, "northeurope"))
            translator.set_key({"key": ""})
            self.assertEqual(self.workspace.translator_memory, {})
            self.assertFalse(translator.CONFIG_FILE.parent.exists())   # nothing written


if __name__ == "__main__":
    unittest.main()
