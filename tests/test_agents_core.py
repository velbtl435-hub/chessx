import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.agents import Agent, Limits, AgentLimitError


class TestTree(unittest.TestCase):
    def test_recursive_spawn(self):
        def fib(agent, n):
            if n < 2:
                return n
            return agent.spawn("f%d" % (n - 1), kind="fib%d" % (n - 1), task=fib).run(n - 1) + \
                   agent.spawn("f%d" % (n - 2), kind="fib%d" % (n - 2), task=fib).run(n - 2)
        root = Agent("root", task=fib)
        self.assertEqual(root.run(10), 55)
        self.assertGreater(root.tree.total, 100)

    def test_depth_limit(self):
        def deep(a):
            return a.spawn("c", kind="k%d" % a.depth, task=deep).run()
        root = Agent("r", task=deep, limits=Limits(max_depth=5))
        with self.assertRaises(AgentLimitError):
            root.run()
        self.assertEqual(max(a.depth for a in root.walk()), 5)

    def test_budget_and_total(self):
        r = Agent("r", limits=Limits(budget=3, spawn_cost=1))
        for i in range(3):
            r.spawn("c%d" % i)
        with self.assertRaises(AgentLimitError):
            r.spawn("x")
        r2 = Agent("r", limits=Limits(max_total=2))
        r2.spawn("a"); r2.spawn("b")
        with self.assertRaises(AgentLimitError):
            r2.spawn("c")

    def test_cycle_detection(self):
        def same(a):
            return a.spawn("same", task=same).run()
        root = Agent("r", kind="loop", task=same, meta={"cycle_repeat": 10})
        with self.assertRaises(AgentLimitError) as cm:
            root.run()
        self.assertIn("cycle", str(cm.exception))

    def test_kill_switch(self):
        r = Agent("r"); c = r.spawn("c")
        r.kill()
        with self.assertRaises(AgentLimitError):
            c.spawn("x")
        self.assertEqual(c.state, "killed")

    def test_events_bubble(self):
        r = Agent("r"); seen = []
        r.listeners.append(lambda a, e, d: seen.append((a.name, e)))
        r.spawn("c").spawn("g").run()
        self.assertIn(("g", "done"), seen)


if __name__ == "__main__":
    unittest.main()
