import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.agents import Registry, Generator


class TestTypes(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "types.json")
        self.reg = Registry(self.path); self.gen = Generator(self.reg)

    def test_from_description_infers_caps_and_parent(self):
        t = self.gen.from_description("Pesquisa a web e traduz resultados")
        self.assertIn("search", t.capabilities); self.assertIn("i18n", t.capabilities)
        self.assertTrue(t.parent)
        self.assertIn(t.name, Registry(self.path).names())  # persisted

    def test_derive_and_resolve(self):
        self.gen.derive("researcher", "deep researcher", add_caps=["audit"])
        r = self.reg.resolve("deep_researcher")
        self.assertEqual(set(r["capabilities"]), {"search", "audit"})
        self.assertIn("research", r["prompt"])

    def test_combine_template_usage(self):
        c = self.gen.combine("researcher", "translator")
        self.assertEqual(set(c.capabilities), {"search", "i18n"})
        t = self.gen.from_template({"name": "{x}_bot", "description": "about {x}"}, x="chess")
        self.assertEqual(t.name, "chess_bot")
        made = self.gen.from_usage(["search chess", "find openings", "web news", "translate"], min_count=3)
        self.assertEqual([m.name for m in made], ["auto_search"])

    def test_unique_names(self):
        a = self.gen.from_description("x agent"); b = self.gen.from_description("x agent")
        self.assertNotEqual(a.name, b.name)


if __name__ == "__main__":
    unittest.main()
