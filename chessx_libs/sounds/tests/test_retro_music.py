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
        self.assertEqual(p["dpcm"][0], {"drum": "k"})
        self.assertEqual(p["noise"][4], {"drum": "s"})
        self.assertEqual(M.parse_cell("C#4:u5:@9:w0:v"), {"n": 61, "slide": 5, "vol": 1.0, "duty": 0.125, "vib": 0.01})
        self.assertEqual(M.parse_cell("---"), {"off": True})
        for bad in ("pattern A\npulse1 C4", "chip nes\npattern A\nbogus C4", "chip nes\npattern A\npulse1 C4:z"):
            with self.assertRaises(ValueError):
                M.parse_song(bad)

    def test_extra_channels_filled(self):
        for c, names in (("opl", ["opl7", "opl8", "opl9"]), ("snes", ["dsp7", "dsp8"]),
                         ("ps1", [f"spu{i}" for i in range(7, 25)])):
            s = M.compose(c, "title", 1, bars=2)
            for n in names:
                self.assertTrue(any(x is not None for x in s.patterns["A"][n]), (c, n))
        ps = {ch.name: ch for ch in M.layout("ps1")}
        self.assertNotEqual(ps["spu18"].detune, ps["spu19"].detune)
        self.assertNotEqual(ps["spu18"].pan, ps["spu19"].pan)
        s = M.compose("nes", "title", 1, bars=1)
        dp = s.patterns["A"]["dpcm"]
        self.assertTrue(any(x and x.get("drum") == "k" for x in dp))

    def test_per_chip_drums_differ(self):
        self.assertEqual(set(M.DRUM_KITS), set(CHIPS))
        self.assertEqual(M.DRUM_KITS["nes"]["k"]["voice"], "dpcm")
        self.assertTrue(M.DRUM_KITS["sn"]["k"]["periodic"])
        kicks = {c: M.render_song(M.parse_song(f"chip {c}\npattern A\n{M.layout(c)[[ch.kind for ch in M.layout(c)].index('drums')].name} k . . .\n"), crush=False)
                 for c in ("gb", "sid", "fm", "opl")}
        self.assertEqual(len({round(float(np.abs(x).mean()), 4) for x in kicks.values()}), 4)

    def test_sid_filter_sweep(self):
        s = M.compose("sid", "title", 1, bars=1)
        f = s.sid_filter
        self.assertNotEqual(f["from"], f["to"])
        self.assertEqual(f["voices"], ["voice2"])  # bass voice has its filter bit set
        self.assertNotIn("filter", {c.role: c.opts for c in s.channels}["bass"])
        x = M.render_song(s)
        self.assertLessEqual(float(np.abs(x).max()), 0.9)

    def test_sid_global_filter_routing(self):
        from chessx_libs.sounds.retro.sid import SID
        sid = SID()
        v = [{"wave": "tone", "shape": "saw", "f0": f, "dur": 0.2} for f in (220, 330, 440)]
        dry = sid.voices3([v[0]], [v[1]], [v[2]])
        lp = sid.voices3([v[0]], [v[1]], [v[2]], filter={"cutoff": 300, "res": 0.2, "route": (1, 1, 1)})
        part = sid.voices3([v[0]], [v[1]], [v[2]], filter={"cutoff": 300, "res": 0.2, "route": (1, 0, 0)})
        hf = lambda x: float(np.abs(np.diff(x)).mean())
        self.assertLess(hf(lp), hf(part))
        self.assertLess(hf(part), hf(dry) * 1.01)
        s = M.compose("sid", "title", 1, bars=1)
        a = M.render_song(s, crush=False)
        s.sid_filter = dict(s.sid_filter, voices=["voice1", "voice2", "voice3"])
        b = M.render_song(s, crush=False)
        self.assertFalse(np.array_equal(a, b))
        self.assertLessEqual(float(np.abs(b).max()), 0.9)

    def test_automation_compose_and_text(self):
        auto = {"cutoff": [(0, 300), (31, 6000)], "res": [(0, 0.2), (31, 0.8)],
                "echo_fb": [(0, 0.0), (16, 0.7)], "echo_mix": [(0, 0.1), (31, 0.6)]}
        for chip in ("nes", "sid", "snes"):
            s = M.compose(chip, "title", 3, bars=2, automation=auto)
            x = M.render_song(s)
            self.assertLessEqual(float(np.abs(x).max()), 0.9)
            self.assertTrue(np.isfinite(x).all())
            self.assertFalse(np.array_equal(x[:len(x) // 2], M.render_song(M.compose(chip, "title", 3, bars=2))[:len(x) // 2]))
        s = M.parse_song("chip gb\npattern A\nsquare1 C5:f300:q2:e0:m1 . . . E5 . .:f5000:e7:m6 . G5 . . .\n")
        a = M.song_automation(s)
        self.assertEqual(a["cutoff"], [(0.0, 300.0), (6.0, 5000.0)])
        self.assertAlmostEqual(a["echo_fb"][1][1], 0.7)
        self.assertEqual(set(s.patterns["A"]["square1"][6]), {"auto"})
        segs = M._channel_segments(s, s.channels[0], 1)
        self.assertEqual(sum(1 for g in segs if g["wave"] == "tone"), 3)  # automation-only row is a hold
        x = M.render_song(s)
        self.assertGreater(len(x), int(s.duration() * 44100))  # echo tail
        self.assertLessEqual(float(np.abs(x).max()), 0.9)
        with self.assertRaises(ValueError):
            M.parse_cell(".:a047")
        with self.assertRaises(ValueError):
            M.render_song(M.compose("nes", bars=1, automation={"wobble": [(0, 1)]}))

    def test_opl_rhythm_mode(self):
        from chessx_libs.sounds.retro.fm import opl_rhythm, opl_noise
        f = np.full(4410, 300.0)
        outs = {h: opl_rhythm(h, f, 44100, 1) for h in ("bd", "sd", "hh", "tom", "cym")}
        for h, x in outs.items():
            self.assertTrue(np.isfinite(x).all() and np.abs(x).max() <= 1.0, h)
        self.assertEqual(len({round(float(np.abs(np.diff(x)).mean()), 3) for x in outs.values()}), 5)
        self.assertTrue(np.array_equal(opl_noise(1000, 3), opl_noise(1000, 3)))
        with self.assertRaises(ValueError):
            opl_rhythm("cowbell", f, 44100)
        s = M.compose("opl", "title", 2, bars=2, rhythm=True)
        names = [c.name for c in s.channels]
        self.assertEqual(names[6:], ["bd", "sd", "hh", "tom", "cym"])
        segs = M._channel_segments(s, s.channels[6], 1)
        self.assertTrue(any(g.get("rhythm") == "bd" for g in segs))
        self.assertTrue(any(c and c.get("drum") in "tc" for p in s.patterns.values() for c in p["tom"] + p["cym"]))
        x = M.render_song(s)
        self.assertLessEqual(float(np.abs(x).max()), 0.9)
        self.assertFalse(np.array_equal(x, M.render_song(M.compose("opl", "title", 2, bars=2))))
        t = M.parse_song("chip opl\nrhythm on\npattern A\nbd k . k .\nhh h h h h\ncym c . . .\ntom . . t t\n")
        self.assertTrue(t.rhythm)
        self.assertLessEqual(float(np.abs(M.render_song(t)).max()), 0.9)
        with self.assertRaises(ValueError):
            M.parse_song("chip nes\nrhythm on\n")
        with self.assertRaises(ValueError):
            M.parse_song("chip opl\npattern A\nopl1 C4\nrhythm on\n")
        self.assertEqual(M.parse_cell("t"), {"drum": "t"})  # tom off rhythm mode falls back to the kit kick
        g = M.parse_song("chip gb\npattern A\nnoise c . . .\n")
        self.assertEqual(M._channel_segments(g, g.channels[3], 1)[0]["f0"], M.DRUM_KITS["gb"]["h"]["f0"])

    def test_seamless_loop_tail(self):
        x = np.arange(10.0)
        self.assertEqual(M.fold_tail(x, 4).tolist(), [0 + 4 + 8, 1 + 5 + 9, 2 + 6, 3 + 7])
        self.assertEqual(M.fold_tail(np.ones(2), 4).tolist(), [1, 1, 0, 0])
        self.assertEqual(M.fold_tail(np.ones((6, 2)), 4).shape, (4, 2))
        s = M.compose("snes", "title", 1, bars=2)  # S-DSP echo leaves a tail past the song
        n = int(round(s.duration() * 22050))
        plain, seam = M.render_song(s, rate=22050), M.render_song(s, rate=22050, seamless=True)
        self.assertGreater(len(plain), n)
        self.assertEqual(len(seam), n)
        self.assertLessEqual(float(np.abs(seam).max()), 0.9)
        # the tail is carried into the start: the head differs from the plain render's head
        self.assertFalse(np.allclose(seam[:2000] / np.abs(seam).max(), plain[:2000] / np.abs(plain).max()))
        st = M.render_song(s, rate=22050, stereo_out=True, seamless=True)
        self.assertEqual(st.shape, (n, 2))
        self.assertTrue(np.array_equal(seam, M.render_song(s, rate=22050, seamless=True)))
        from chessx_libs.sounds import events
        e = events.render("retro.ps1.music.title", rate=22050, seamless=True)
        self.assertEqual(len(e), int(round(M.compose("ps1", "title", 0, 2).duration() * 22050)))

    def test_loop_option(self):
        a = events.render("retro.gb.music.victory", seed=1)
        b = events.render("retro.gb.music.victory", seed=1, loops=2)
        c = events.render("retro.gb.music.victory", seed=1, loop=True)
        self.assertAlmostEqual(len(b) / len(a), 2, delta=0.05)
        self.assertTrue(np.array_equal(b, c))
        self.assertLessEqual(float(np.abs(b).max()), 0.9)

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
