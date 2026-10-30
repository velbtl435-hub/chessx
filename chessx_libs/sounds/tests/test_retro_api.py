"""Offline tests for play_retro/list_retro/render_retro (CHESSX_MUTE, no playback)."""
import os, unittest
from unittest import mock

os.environ["CHESSX_MUTE"] = "1"
import numpy as np  # noqa: E402
import chessx_libs.sounds as S  # noqa: E402
from chessx_libs.sounds import retro_api  # noqa: E402


class TestRetroAPI(unittest.TestCase):
    def test_list_all_and_one(self):
        L = S.list_retro()
        self.assertEqual(set(L), {"nes", "gb", "sid", "ay", "sn", "fm", "opl", "snes", "ps1"})
        self.assertIn("coin", L["nes"]["sfx"])
        self.assertIn("music.battle", L["nes"]["music"])
        self.assertIn("music.demo", L["nes"]["music"])
        self.assertEqual(S.list_retro("sid"), L["sid"])
        self.assertEqual(set(L["sid"]), {"sfx", "music"})

    def test_unknown(self):
        with self.assertRaises(S.UnknownSound) as cm:
            S.list_retro("atari")
        self.assertIn("nes", str(cm.exception))
        with self.assertRaises(KeyError):
            S.play_retro("atari", "coin")
        with self.assertRaises(S.UnknownSound) as cm:
            S.play_retro("nes", "nope")
        self.assertIn("coin", str(cm.exception))
        with self.assertRaises(S.UnknownSound):
            S.render_retro("nes", "music.polka")

    def test_play_noop_and_render(self):
        self.assertEqual(S.play_retro("nes", "coin", seed=1), "noop")
        self.assertEqual(S.play_retro("gb", "music.victory", loops=2), "noop")
        a = S.render_retro("gb", "music.victory", seed=1)
        b = S.render_retro("gb", "music.victory", seed=1, loops=2)
        self.assertAlmostEqual(len(b) / len(a), 2, delta=0.05)
        self.assertLessEqual(float(np.abs(S.render_retro("fm", "laser")).max()), 0.9)

    def test_without_numpy(self):
        with mock.patch.object(retro_api, "_events", side_effect=S.MissingDependency("no numpy")):
            self.assertEqual(S.list_retro(), {})
            self.assertEqual(S.list_retro("nes"), {})
            with self.assertRaises(S.MissingDependency):
                S.play_retro("nes", "coin")
            with self.assertRaises(S.MissingDependency):
                S.render_retro("nes", "coin")


if __name__ == "__main__":
    unittest.main()
