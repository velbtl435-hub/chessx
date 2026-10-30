"""TST-01: chessx_libs.chess_ai intent classifier."""
import unittest
from chessx_libs.chess_ai import classify, Intent, INTENTS


class TestIntent(unittest.TestCase):
    def c(self, t):
        i = classify(t)
        return i.name, i.args

    def test_empty(self):
        for t in ("", "   ", None):
            i = classify(t)
            self.assertEqual((i.name, i.confidence, i.args), ("empty", 1.0, {}))

    def test_convert_forms(self):
        self.assertEqual(self.c("convert hex to binary"), ("convert", {"src": 16, "dst": 2}))
        self.assertEqual(self.c("convert ff from hex to bin"), ("convert", {"value": "ff", "src": 16, "dst": 2}))
        self.assertEqual(self.c("CVT dec -> hexadecimal 255"), ("convert", {"src": 10, "dst": 16, "value": "255"}))
        self.assertEqual(self.c("conv octal into decimal"), ("convert", {"src": 8, "dst": 10}))
        self.assertEqual(classify("convert hex to bin").confidence, 0.95)

    def test_convert_loose_fallback(self):
        i = classify("please turn binary to hex now")
        self.assertEqual((i.name, i.confidence, i.args), ("convert", 0.7, {"src": 2, "dst": 16}))
        self.assertEqual(self.c("hex binary")[0], "search")  # no 'to'/'convert'
        self.assertEqual(self.c("convert to hex")[0], "search")  # only one base

    def test_open(self):
        self.assertEqual(self.c("open 3"), ("open", {"index": 3}))
        self.assertEqual(self.c("abre #12"), ("open", {"index": 12}))
        self.assertEqual(self.c("o7"), ("open", {"index": 7}))
        self.assertEqual(self.c("open")[0], "search")

    def test_save_lang_refresh(self):
        self.assertEqual(self.c("save"), ("save", {}))
        self.assertEqual(self.c("export csv"), ("save", {"fmt": "csv"}))
        self.assertEqual(self.c("lang PT"), ("lang", {"lang": "pt"}))
        self.assertEqual(self.c("idioma jp"), ("lang", {"lang": "ja"}))
        self.assertEqual(self.c("lang fr")[0], "search")
        self.assertEqual(self.c("refresh"), ("refresh", {}))
        self.assertEqual(self.c("auto 30"), ("refresh", {"seconds": 30}))

    def test_simple_commands(self):
        for t, n in (("stats", "stats"), ("estatísticas", "stats"), ("?", "help"), ("ajuda", "help"),
                     ("q", "quit"), ("sair", "quit"), ("strings /bin/ls", "reverse")):
            self.assertEqual(classify(t).name, n, t)
        self.assertEqual(self.c("hexdump a.bin"), ("reverse", {"path": "a.bin"}))

    def test_search_fallback(self):
        i = classify("  best chess openings ")
        self.assertEqual((i.name, i.confidence, i.args), ("search", 0.5, {"query": "best chess openings"}))

    def test_intents_list(self):
        self.assertEqual(INTENTS[-1], "search")
        self.assertEqual(len(INTENTS), len(set(INTENTS)))
        self.assertIn("convert", INTENTS)
        self.assertIsInstance(classify("x"), Intent)


if __name__ == "__main__":
    unittest.main()
