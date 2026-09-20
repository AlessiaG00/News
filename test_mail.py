import logging
import unittest

from mail import build_email_html


class BuildEmailHtmlTest(unittest.TestCase):

    def test_articolo_con_sommario_non_crasha(self):
        """Il caso che prima dava KeyError: 'summary'."""
        html = build_email_html([{
            "fonte": "OpenAI",
            "titolo": "Introducing the Australian Youth Safety Blueprint",
            "link": "https://openai.com/index/australian-youth-safety-blueprint/",
            "sommario": "OpenAI introduces the Blueprint.",
            "pubblicato": "18/09/2026",
        }])
        self.assertIn("Introducing the Australian Youth Safety Blueprint", html)
        self.assertIn("OpenAI introduces the Blueprint.", html)
        self.assertIn("18/09/2026", html)
        self.assertIn('href="https://openai.com/index/australian-youth-safety-blueprint/"', html)

    def test_solo_titolo(self):
        html = build_email_html([{"fonte": "BBC", "titolo": "Solo titolo"}])
        self.assertIn("Solo titolo", html)

    def test_autore_e_data_insieme(self):
        html = build_email_html([{
            "fonte": "NYT", "titolo": "T", "autore": "Mario Rossi", "pubblicato": "19/09/2026",
        }])
        self.assertIn("Mario Rossi &middot; 19/09/2026", html)

    def test_caratteri_speciali_escapati(self):
        html = build_email_html([{
            "fonte": "X", "titolo": "A & B <script>", "sommario": "<b>ciao</b>",
        }])
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>ciao</b>", html)
        self.assertIn("A &amp; B &lt;script&gt;", html)

    def test_link_non_valido_non_diventa_href(self):
        html = build_email_html([{
            "fonte": "X", "titolo": "T", "link": "javascript:alert(1)",
        }])
        self.assertNotIn("javascript:", html)

    def test_senza_titolo_e_senza_fonte(self):
        html = build_email_html([{"fonte": "Guardian"}, {"titolo": "Senza fonte"}])
        self.assertIn("(senza titolo)", html)
        self.assertIn("Sconosciuta", html)

    def test_lista_vuota_restituisce_html_valido(self):
        html = build_email_html([])
        self.assertIn("<html>", html)
        self.assertIn("Rassegna stampa", html)

    def test_articolo_rotto_non_blocca_gli_altri(self):
        class Rotto:
            def __str__(self):
                raise ValueError("boom")

        logging.disable(logging.CRITICAL)        # evita il traceback atteso nell'output
        self.addCleanup(logging.disable, logging.NOTSET)

        html = build_email_html([
            {"fonte": "Rotto", "titolo": "X", "sommario": Rotto()},
            {"fonte": "BBC", "titolo": "Articolo sano"},
        ])
        self.assertIn("Articolo sano", html)
        self.assertNotIn(">Rotto<", html)   # la sezione senza articoli validi sparisce


if __name__ == "__main__":
    unittest.main()