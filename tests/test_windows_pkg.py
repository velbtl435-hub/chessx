"""TST-01: chessx_libs.windows text layout."""
import unittest
from chessx_libs.windows import Layout, Pane, TabBar
from chessx_libs.windows.layout import _w, _fit


class TestHelpers(unittest.TestCase):
    def test_width_and_fit(self):
        self.assertEqual(_w("abc"), 3)
        self.assertEqual(_w("日本"), 4)
        self.assertEqual(_fit("abc", 5), "abc  ")
        self.assertEqual(_fit("abcdef", 3), "abc")
        self.assertEqual(_fit("日本語", 5), "日本 ")  # wide char never split
        self.assertEqual(_fit("", 0), "")


class TestPane(unittest.TestCase):
    def test_write_and_view(self):
        p = Pane("t")
        p.write("a\nb\nc")
        p.write("")
        p.write(42)
        self.assertEqual(p.lines, ["a", "b", "c", "", "42"])
        self.assertEqual(p.view(2), ["", "42"])
        p.scroll = 2
        self.assertEqual(p.view(2), ["b", "c"])
        p.scroll = 99
        self.assertEqual(p.view(2), ["a", "b"])


class TestTabBar(unittest.TestCase):
    def test_open_dedup_cycle_close(self):
        tb = TabBar()
        self.assertEqual(tb.current().title, "untitled")
        tb.close(); tb.cycle()  # no-ops on empty
        a = tb.open("a", "x")
        tb.open("b")
        self.assertIs(tb.open("a"), a)
        self.assertEqual((len(tb.tabs), tb.active), (2, 0))
        tb.cycle(); self.assertEqual(tb.current().title, "b")
        tb.cycle(-3); self.assertEqual(tb.current().title, "a")
        tb.close(); self.assertEqual([t.title for t in tb.tabs], ["b"])
        tb.close(0); self.assertEqual((tb.tabs, tb.active), ([], 0))

    def test_close_last_active_clamps(self):
        tb = TabBar()
        for n in "abc":
            tb.open(n)
        tb.close()
        self.assertEqual(tb.active, 1)

    def test_close_left_of_active_keeps_focus(self):
        tb = TabBar()
        for n in "abc":
            tb.open(n)
        tb.cycle(-1)  # active = b
        tb.close(0)
        self.assertEqual(tb.current().title, "b")
        tb.close(-1)  # negative index closes last tab
        self.assertEqual([t.title for t in tb.tabs], ["b"])

    def test_render(self):
        tb = TabBar()
        tb.open("a"); tb.open("b")
        self.assertEqual(tb.render(12), " a │[b]│    ")
        self.assertEqual(len(tb.render(3)), 3)


class TestLayout(unittest.TestCase):
    def mk(self, **kw):
        L = Layout(width=60, height=16, side_w=10, term_h=3, **kw)
        L.left.write("file.py")
        L.right.write("  def f")
        L.editor.open("main.py", "print(1)")
        L.terminal.write("ls")
        return L

    def test_dimensions(self):
        out = self.mk().render().split("\n")
        self.assertEqual(len(out), 16)
        self.assertTrue(all(len(r) == 60 for r in out))
        self.assertTrue(out[0].startswith("┌") and out[0].endswith("┐"))

    def test_content_placement(self):
        out = self.mk().render()
        self.assertIn("EXPLORER", out)
        self.assertIn("[main.py]", out)
        self.assertIn("print(1)", out)
        self.assertIn("$ ls", out)
        self.assertIn("TERMINAL", out)
        row = out.split("\n")[2]
        self.assertTrue(row.startswith("file.py"))
        self.assertTrue(row.rstrip().endswith("def f"))  # mirrored: right-aligned

    def test_no_mirror_and_toggles(self):
        L = self.mk(mirror=False)
        row = L.render().split("\n")[2]
        self.assertIn("│  def f", row)
        L.toggle("left"); L.toggle("right")
        self.assertFalse(L.show_left or L.show_right)
        out = L.render().split("\n")
        self.assertNotIn("EXPLORER", out[1])
        self.assertTrue(out[2].startswith("print(1)"))
        L.toggle("left")
        self.assertTrue(L.show_left)

    def test_default_size_from_terminal(self):
        L = Layout()
        self.assertGreater(L.width, 0)
        self.assertGreater(L.height, 0)


if __name__ == "__main__":
    unittest.main()
