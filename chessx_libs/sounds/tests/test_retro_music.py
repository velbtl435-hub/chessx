"""Offline tests for chessx_libs.sounds.retro.music (tracker + procedural composition). No playback."""
import os, unittest

os.environ["CHESSX_MUTE"] = "1"
import numpy as np  # noqa: E402
from chessx_libs.sounds import events  # noqa: E402
from chessx_libs.sounds.retro import CHIPS, music as M  # noqa: E402

EXPECTED_CHANNELS = {"nes": 5, "gb": 4, "sid": 3, "ay": 4, "sn": 4, "fm": 6, "opl": 9, "snes": 8, "ps1": 24}


class TestRetroMusic(unittest.TestCase):
    def test_layouts(self):
        self.assertEqual(set(M.LAYOUTS), set(CHIPS))
        for c, n in EXPECTED_CHANNELS.items():
            self.assertEqual(len(M.layout(c)), n, c)

    def test_all_music_events_render(self):
        names = [n for n in events.list_events("retro") if ".music." in n]
        self.assertEqual(len(names), len(CHIPS) * len(M.STYLES) + 1)
        for n in names:
            x = events.render(n, seed=2)
            self.assertGreater(len(x), 22050, n)
            self.assertLessEqual(float(np.abs(x).max()), 0.9, n)
            self.assertTrue(np.isfinite(x).all(), n)

    def test_deterministic_and_seeded(self):
        a = M.render_music("nes", "title", seed=5)
        self.assertTrue(np.array_equal(a, M.render_music("nes", "title", seed=5)))
        s5, s6 = M.compose("fm", "battle", 5), M.compose("fm", "battle", 6)
        self.assertNotEqual(s5.patterns, s6.patterns)

    def test_compose_structure(self):
        s = M.compose("snes", "victory", seed=1, bars=4)
        self.assertEqual(s.order, ["A", "B"])
        self.assertEqual(s.rows(), 64)
        self.assertAlmostEqual(s.row_dur, s.speed * 2.5 / s.bpm)
        for p in s.patterns.values():
            self.assertEqual({len(v) for v in p.values()}, {32})
        with self.assertRaises(KeyError):
            M.compose("nes", "polka")

    def test_loops_length(self):
        s = M.parse_song(M.DEMO)
        one, two = M.render_song(s, crush=False), M.render_song(s, loops=2, crush=False)
        self.assertAlmostEqual(len(two) / len(one), 2, delta=0.05)

    def test_text_format(self):
        s = M.parse_song(M.DEMO)
        self.assertEqual((s.chip, s.bpm, s.speed, s.order, s.loop), ("nes", 150, 6, ["A", "A"], True))
        p = s.patterns["A"]
        self.assertEqual(p["pulse1"][0], {"n": 76})
        self.assertIsNone(p["pulse1"][1])
        self.assertEqual(p["pulse2"][0]["arp"], [0, 4, 7])
        self.assertEqual(p["noise"][0], {"drum": "k"})
        self.assertEqual(M.parse_cell("C#4:u5:@9:w0:v"), {"n": 61, "slide": 5, "vol": 1.0, "duty": 0.125, "vib": 0.01})
        self.assertEqual(M.parse_cell("---"), {"off": True})
        for bad in ("pattern A\npulse1 C4", "chip nes\npattern A\nbogus C4", "chip nes\npattern A\npulse1 C4:z"):
            with self.assertRaises(ValueError):
                M.parse_song(bad)

    def test_stereo_and_sid_ring_sync(self):
        st = M.render_song(M.compose("ps1", "title", 3, bars=1), stereo_out=True)
        self.assertEqual(st.shape[1], 2)
        self.assertLessEqual(float(np.abs(st).max()), 0.9)
        s = M.compose("sid", "battle", 1, bars=1)
        opts = {c.role: c.opts for c in s.channels}
        self.assertIn("ring", opts["lead"])
        self.assertIn("sync", opts["bass"])


if __name__ == "__main__":
    unittest.main()
