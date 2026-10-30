import json, os, sys, tempfile, unittest, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.agents import Factory
from chessx_libs.agents.cli import main as cli


class TestFactory(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(); self.f = Factory(self.root)

    def test_create_build_run(self):
        mat = os.path.join(self.root, "notes.txt"); open(mat, "w").write("e4 e5")
        self.f.create(name="chess_bot", prompt="Study openings", sub_prompts=["Sicilian", "French"],
                      script="echo hi-$CHESSX_AGENT", code="print(6*7)", materials=[mat], links=["https://lichess.org"])
        self.assertEqual(self.f.list(), ["chess_bot"])
        a = self.f.build("chess_bot")
        self.assertEqual(len(a.children), 2)
        res = a.run()
        self.assertEqual(res["payload"]["script"]["stdout"].strip(), "hi-chess_bot")
        self.assertEqual(res["payload"]["code"]["stdout"].strip(), "42")
        self.assertEqual(res["sub"][0]["prompt"], "Sicilian")

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.f.create(name="x", type="nope")
        with self.assertRaises(ValueError):
            self.f.create(name="y", links=["ftp://x"])

    def test_cli(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli(["create", "bot", "--prompt", "p", "--sub", "s1", "--link", "https://x.io"], factory=self.f)
            cli(["gen-type", "translate chess books", "--name", "book translator"], factory=self.f)
            cli(["list"], factory=self.f)
        self.assertIn('"bot"', buf.getvalue())
        self.assertIn("book_translator", self.f.registry.names())


if __name__ == "__main__":
    unittest.main()
