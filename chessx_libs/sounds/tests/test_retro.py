"""Offline tests for chessx_libs.sounds.retro (section 27). No playback."""
import os, tempfile, unittest, wave

os.environ["CHESSX_MUTE"] = "1"
import numpy as np  # noqa: E402
from chessx_libs.sounds import events  # noqa: E402
from chessx_libs.sounds.retro import CHIPS, RECIPES, render_sfx, bitcrush, srcrush, stereo, write_wav_stereo, chip  # noqa: E402
from chessx_libs.sounds.retro import nes, psg, sid, fm  # noqa: E402

REQUIRED_SFX = {"coin", "jump", "hit", "powerup", "1up", "select", "game_over", "laser", "explosion",
                "level_complete", "chess_move", "chess_capture", "chess_check", "chess_mate"}


class TestRetro(unittest.TestCase):
    def test_chips_and_recipes(self):
        self.assertEqual(set(CHIPS), {"nes", "gb", "sid", "ay", "sn", "fm", "opl", "snes", "ps1"})
        self.assertTrue(REQUIRED_SFX <= set(RECIPES))
        self.assertEqual({c.era for c in CHIPS.values()}, {"8bit", "16bit", "32bit"})

    def test_all_events_render_no_clip(self):
        names = events.list_events("retro")
        self.assertEqual(len(names), len(CHIPS) * len(RECIPES))
        for n in names:
            x = events.render(n, seed=1)
            self.assertGreater(len(x), 100, n)
            self.assertLessEqual(float(np.abs(x).max()), 0.9, n)
            self.assertTrue(np.isfinite(x).all(), n)

    def test_deterministic(self):
        for c in CHIPS:
            a, b = render_sfx(c, "explosion", seed=7), render_sfx(c, "explosion", seed=7)
            self.assertTrue(np.array_equal(a, b), c)

    def test_unknown(self):
        with self.assertRaises(KeyError):
            chip("atari")
        with self.assertRaises(KeyError):
            render_sfx("nes", "nope")

    def test_lfsr_periods(self):
        for short, period in ((False, 32767), (True, 93)):
            s = np.asarray(nes.lfsr(2 * period + 10, short=short))
            self.assertTrue(np.array_equal(s[:period], s[period:2 * period]), short)

    def test_quantization(self):
        f = nes.quantize_pulse(np.array([440.0]))[0]
        self.assertAlmostEqual(f, 440, delta=2)
        self.assertNotEqual(f, 440.0)
        q = psg.AY8910().quant(np.array([5000.0]))[0]
        self.assertAlmostEqual(1773400 / (16 * q), round(1773400 / (16 * q)), places=6)

    def test_crush(self):
        x = np.sin(np.linspace(0, 20, 2000))
        self.assertLessEqual(len(np.unique(bitcrush(x, 4))), 16)
        self.assertEqual(len(srcrush(x, 11025, 22050)), len(x))

    def test_fm_algorithms_and_svf(self):
        for a in range(8):
            y = fm.fm_voice(np.full(500, 220.0), 22050, (1, 2, 1, 1), (1, 1, 1, 1), (1, 1, 1, 1), a, 0.5)
            self.assertTrue(np.isfinite(y).all())
        y = sid.svf(np.random.default_rng(0).standard_normal(2000), 500, 0.9)
        self.assertTrue(np.isfinite(y).all())

    def test_stereo_wav(self):
        st = stereo(render_sfx("ps1", "coin"), pan=0.3, width=0.5)
        self.assertEqual(st.shape[1], 2)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.wav")
            write_wav_stereo(p, st)
            with wave.open(p) as w:
                self.assertEqual(w.getnchannels(), 2)
                self.assertGreater(w.getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
