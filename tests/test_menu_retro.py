"""Menu entry 29 (retro sounds): offline, play_retro mocked."""
import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.menu import registry as r
from chessx_libs import sounds

LIST = {"nes": {"sfx": ["coin", "jump"], "music": ["music.battle"]}, "gb": {"sfx": ["hit"], "music": []}}


def fake_list(chip=None):
    if chip is None:
        return LIST
    if chip not in LIST:
        raise sounds.UnknownSound("unknown retro chip %r; valid chips: %s" % (chip, sorted(LIST)))
    return LIST[chip]


def asker(*a):
    it = iter(a)
    return lambda p: next(it, "")


class TestRetroEntry(unittest.TestCase):
    def setUp(self):
        self.p1 = mock.patch.object(sounds, "list_retro", side_effect=fake_list)
        self.play = mock.patch.object(sounds, "play_retro", return_value="noop").start()
        self.p1.start()

    def tearDown(self):
        mock.patch.stopall()

    def test_registered(self):
        self.assertEqual([e.key for e in r.ENTRIES if e.label == "menu_retro"], ["29"])

    def test_sfx(self):
        out = r._retro(None, asker("nes", "sfx", "jump"))
        self.play.assert_called_once_with("nes", "jump")
        self.assertIn("played nes jump", out)

    def test_music_defaults(self):
        r._retro(None, asker("nes", "music", ""))
        self.play.assert_called_once_with("nes", "music.battle")

    def test_unknown_chip_message(self):
        out = r._retro(None, asker("c64"))
        self.assertIn("valid chips", out)
        self.play.assert_not_called()

    def test_unknown_sound_message(self):
        self.play.side_effect = sounds.UnknownSound("unknown retro sound 'zap'; valid: coin, jump")
        self.assertIn("valid: coin", r._retro(None, asker("nes", "sfx", "zap")))

    def test_bad_kind(self):
        self.assertIn("sfx or music", r._retro(None, asker("nes", "drums")))

    def test_missing_numpy(self):
        self.play.side_effect = sounds.MissingDependency("numpy")
        self.assertEqual(r._retro(None, asker("nes", "sfx", "coin")), "needs numpy")

    def test_empty_listing_means_no_numpy(self):
        with mock.patch.object(sounds, "list_retro", return_value={}):
            self.assertEqual(r._retro(None, asker()), "needs numpy")


if __name__ == "__main__":
    unittest.main()
