"""Offline tests for chessx_libs.sounds (no playback: CHESSX_MUTE=1).
Run: python3 -m unittest discover -s chessx_libs/sounds/tests -t .
"""
import os, shutil, tempfile, unittest, wave
from unittest import mock

os.environ["CHESSX_MUTE"] = "1"
import numpy as np  # noqa: E402
import chessx_libs.sounds as S  # noqa: E402
from chessx_libs.sounds import dsp, chiptune, synthwave, cabinet, events  # noqa: E402

REQUIRED = ["move", "capture", "check", "castle", "promote", "game_end", "click", "error", "notify",
            "boot", "hdd", "fan", "floppy", "keyboard", "crt", "chiptune_theme", "synthwave_loop"]


class TestLegacy(unittest.TestCase):
    def test_sfx_api(self):
        self.assertTrue(S.synth("boot"))
        self.assertIn("boot", S.EFFECTS)
        self.assertEqual(S.play("boot"), "noop")  # muted
        with self.assertRaises(S.UnknownSound):
            S.play("does-not-exist")
        self.assertTrue(S.PROCEDURAL)


class TestDSP(unittest.TestCase):
    def test_notes_osc_adsr(self):
        self.assertAlmostEqual(dsp.note_freq("A4"), 440)
        self.assertAlmostEqual(dsp.note_freq("C5"), 523.25, places=1)
        self.assertEqual(dsp.note_freq("."), 0)
        for k in ("sine", "square", "pulse", "triangle", "saw", "noise"):
            x = dsp.osc(k, 440, 0.1, duty=0.25, seed=1)
            self.assertEqual(x.shape, (2205,))
            self.assertLessEqual(np.abs(x).max(), 1.0)
        p = dsp.osc("pulse", 100, 1.0, duty=0.25)
        self.assertAlmostEqual((p > 0).mean(), 0.25, places=2)
        e = dsp.adsr(1000, 0.01, 0.01, 0.5, 0.01)
        self.assertEqual(len(e), 1000)
        self.assertEqual(e[-1], 0)

    def test_filters_and_fallback(self):
        x = dsp.osc("noise", 0, 0.2, seed=3)
        lp = dsp.lowpass(x, 500)
        self.assertLess(np.abs(np.diff(lp)).mean(), np.abs(np.diff(x)).mean())
        with mock.patch.object(dsp, "scipy_signal", return_value=None):
            lp2 = dsp.lowpass(x, 500)
            self.assertEqual(lp2.shape, x.shape)
            self.assertLess(np.abs(np.diff(lp2)).mean(), np.abs(np.diff(x)).mean())
            self.assertEqual(dsp.bandpass(x, 300, 3000).shape, x.shape)


class TestSynths(unittest.TestCase):
    def test_chiptune(self):
        ev, n = chiptune.parse_pattern("C4 - . E4:047 x")
        self.assertEqual(n, 5)
        self.assertEqual(ev[0][2], 2)
        self.assertEqual(ev[1][3], [0, 4, 7])
        x = chiptune.render_pattern({"a": ("pulse25", "C4 - E4 G4")}, bpm=120)
        self.assertAlmostEqual(len(x) / dsp.RATE, 4 * 60 / 120 / 4, places=2)

    def test_durations(self):
        self.assertAlmostEqual(len(cabinet.hdd(1.5)) / dsp.RATE, 1.5, places=2)
        self.assertAlmostEqual(len(cabinet.crt(1.0)) / dsp.RATE, 1.0, places=2)
        self.assertAlmostEqual(len(synthwave.loop(bars=1, bpm=120)) / dsp.RATE, 2.0, places=2)


class TestEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_required_registered(self):
        names = S.list_events()
        for r in REQUIRED:
            self.assertIn(r, names)
        self.assertLessEqual({"cabinet", "chess", "music", "ui"}, set(S.categories()))

    def test_every_event_renders(self):
        for e in S.list_events():
            with self.subTest(event=e):
                x = S.render(e)
                self.assertEqual(x.ndim, 1)
                self.assertGreater(len(x), 0)
                self.assertTrue(np.isfinite(x).all())
                self.assertLessEqual(np.abs(x).max(), 1.0)
                self.assertGreater(np.abs(x).max(), 0.01)
                self.assertLess(len(x) / dsp.RATE, 10)

    def test_deterministic(self):
        for e in ("hdd", "keyboard", "floppy", "synthwave_loop", "chiptune_theme", "capture"):
            self.assertTrue(np.array_equal(S.render(e, seed=7), S.render(e, seed=7)), e)
        self.assertFalse(np.array_equal(S.render("keyboard", seed=1), S.render("keyboard", seed=2)))

    def test_wav_valid(self):
        p = S.save("crt", os.path.join(self.tmp, "c.wav"), rate=16000, seconds=0.5)
        with wave.open(p) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 16000))
            self.assertEqual(w.getnframes(), 8000)

    def test_register_and_play(self):
        S.register("beep", lambda rate=dsp.RATE, seed=0, **kw: dsp.osc("sine", 440, 0.1, rate) * 0.5)
        self.assertIn("beep", S.list_events("custom"))
        self.assertEqual(S.render("beep").shape, (2205,))
        with self.assertRaises(KeyError):
            S.render("nope")
        self.assertEqual(S.play("beep"), "noop")  # muted
        with mock.patch.dict(os.environ, {"CHESSX_MUTE": ""}), \
                mock.patch.object(events, "find_player", return_value="noop"):
            self.assertEqual(S.play("beep"), "noop")  # no player -> silent no-op
        with mock.patch.dict(os.environ, {"CHESSX_MUTE": ""}), \
                mock.patch.object(events.subprocess, "Popen") as po:
            self.assertEqual(events.play_file("/tmp/x.wav", player="aplay"), "aplay")
            po.assert_called_once()
            po.side_effect = OSError
            self.assertEqual(events.play_file("/tmp/x.wav", player="aplay"), "noop")

    def test_sonify(self):
        a, b = S.sonify(b"abc"), S.sonify(b"xyz")
        self.assertEqual(a.shape, b.shape)
        self.assertFalse(np.array_equal(a, b))

    def test_chess_reuses_media_table(self):
        from chessx_libs.media.gen.audio import CHESS_SOUNDS
        self.assertIs(events._chess_table(), CHESS_SOUNDS)
        self.assertTrue(np.array_equal(S.render("move"), S.render("chess.move")))


class TestUnknownSound(unittest.TestCase):
    CALL_SITES = ["result", "error", "boot", "success"]  # chessx.py, tamagox play_audio, menu entry 14 default

    def test_raises_keyerror_with_valid_list(self):
        for fn in (S.play, S.render, S.save):
            with self.subTest(fn=fn.__name__), self.assertRaises(KeyError) as cm:
                fn("nope-x")
            self.assertIsInstance(cm.exception, S.UnknownSound)
            msg = str(cm.exception)
            self.assertTrue(msg.startswith("unknown sound 'nope-x'; valid: "), msg)
            self.assertIn("capture", msg)
        self.assertIs(events.UnknownSound, S.UnknownSound)

    def test_raises_even_when_muted_or_disabled(self):
        with self.assertRaises(S.UnknownSound):
            S.play("nope", enabled=False)

    def test_legacy_sfx_path(self):
        from chessx_libs.sounds import sfx
        for fn in (sfx.play, sfx.synth):
            with self.assertRaises(S.UnknownSound) as cm:
                fn("nope")
            self.assertIn("boot", str(cm.exception))

    def test_known_names_never_raise(self):
        for name in self.CALL_SITES + sorted(S.EFFECTS):
            self.assertIn(name, S.list_events())
            self.assertEqual(S.play(name), "noop")  # muted
        with mock.patch.dict(os.environ, {"CHESSX_MUTE": ""}), \
                mock.patch.object(events, "find_player", return_value="noop"):
            self.assertEqual(S.play("boot"), "noop")  # no player -> still silent


if __name__ == "__main__":
    unittest.main()
