import io, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.pixelart import list_sprites, get_sprite, render_frame, animate, SPRITES


class TestPixelart(unittest.TestCase):
    def test_sprites_valid(self):
        self.assertGreaterEqual(len(list_sprites()), 5)
        for s in SPRITES.values():
            self.assertGreaterEqual(len(s.frames), 2, s.name)
            for f in s.frames:
                for row in f:
                    for ch in row:
                        self.assertTrue(ch == "." or ch in s.palette, (s.name, ch))

    def test_render(self):
        s = get_sprite("frog")
        mono = render_frame(s, 0, color=False)
        self.assertEqual(len(mono.split("\n")), (s.height + 1) // 2)
        self.assertNotEqual(mono, render_frame(s, 1, color=False))
        self.assertIn("\033[38;2;", render_frame("cat", 3))
        self.assertTrue(render_frame("bird", 0, False, offset=4).startswith("    "))
        with self.assertRaises(KeyError):
            get_sprite("dragon")

    def test_animate_headless(self):
        out = io.StringIO()
        n = animate("slime", frames=5, out=out, sleep=lambda _: None)
        self.assertEqual(n, 5); self.assertIn("\u2580", out.getvalue())


if __name__ == "__main__":
    unittest.main()
