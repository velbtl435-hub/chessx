import os, sys, tempfile, unittest, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import tamagox
from chessx_libs.agents import Agent, Factory
from chessx_libs.agents.cli import main as cli


class TestTamagoX(unittest.TestCase):
    def test_off_by_default_noop(self):
        tamagox.enable(False)
        self.assertIsNone(tamagox.attach(Agent("a"), tamagox.Pet("p")))

    def test_activity_moves_stats_and_persists(self):
        d = tempfile.mkdtemp(); store = tamagox.PetStore(d); pet = tamagox.Pet("bot")
        tamagox.enable(True)
        try:
            a = Agent("bot"); tamagox.attach(a, pet, store)
            a.spawn("kid").run(); a.run()
        finally:
            tamagox.enable(False)
        self.assertGreater(pet.xp, 0); self.assertTrue(store.exists("bot"))
        def boom(ag): raise ValueError("x")
        b = Agent("b", task=boom); p2 = tamagox.Pet("b", mood=50); tamagox.attach(b, p2, force=True)
        with self.assertRaises(ValueError):
            b.run()
        self.assertLess(p2.mood, 50)

    def test_decay_care_status(self):
        p = tamagox.Pet("p", updated=1); p.tick(now=3600 * 20)
        self.assertEqual(p.status(), "hungry"); p.feed(); p.feed(); self.assertLess(p.hunger, 80)
        self.assertIn("Lv1", p.render())
        self.assertEqual(tamagox.act(p, "analyze_text", "e4 e5 e4")["top"][0], "e4")
        with self.assertRaises(KeyError):
            tamagox.act(p, "nope")

    def test_factory_pet_cli(self):
        f = Factory(tempfile.mkdtemp()); f.create(name="pbot", code="print(1)")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli(["run", "pbot", "--pet"], factory=f); cli(["pet", "pbot", "feed"], factory=f)
        self.assertIn("pbot Lv1", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
