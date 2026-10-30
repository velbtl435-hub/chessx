import os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.agents import Workspace, sweep, Factory


class TestWorkspace(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_isolation_and_nesting(self):
        w = Workspace(self.root, "alpha"); c = w.child("beta"); i = w.child("gamma", mode="isolated")
        self.assertTrue(c.path.startswith(w.path)); self.assertFalse(i.path.startswith(w.path + os.sep))
        w.write("a/b.txt", "x"); self.assertEqual(w.read("a/b.txt"), "x")
        with self.assertRaises(PermissionError):
            w.write("../../escape", "x")
        self.assertEqual(w.env()["HOME"], w.path)

    def test_state_and_cleanup(self):
        w = Workspace(self.root, "s", cleanup="on_success"); w.save_state(k=1)
        self.assertEqual(w.state()["k"], 1)
        self.assertFalse(Workspace(self.root, "t", cleanup="on_success").finish(False))
        self.assertTrue(w.finish(True)); self.assertFalse(os.path.exists(w.path))
        old = Workspace(self.root, "old"); old.save_state()
        self.assertEqual(sorted(sweep(self.root, ttl=10, now=time.time() + 100)), ["old", "t"])
        self.assertEqual(sweep(self.root, ttl=10), [])

    def test_factory_runs_in_workspace(self):
        f = Factory(self.root)
        f.create(name="ws_bot", script="pwd; echo $HOME > home.txt", sub_prompts=["s"])
        res = f.run("ws_bot")
        self.assertIn(os.path.join("workspaces", "ws_bot", "files"), res["payload"]["script"]["stdout"])
        self.assertIn(os.path.join("ws_bot", "sub", "ws_bot_sub1"), res["sub"][0]["workspace"])
        self.assertEqual(Workspace(os.path.join(self.root, "workspaces"), "ws_bot").state()["last_success"], True)


if __name__ == "__main__":
    unittest.main()
