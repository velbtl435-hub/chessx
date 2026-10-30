import importlib, os, sys, unittest, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestShim(unittest.TestCase):
    def test_warns_and_names_work(self):
        sys.modules.pop("chessx_libs.interface.pixelart", None)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            m = importlib.import_module("chessx_libs.interface.pixelart")
        self.assertTrue(any(issubclass(x.category, DeprecationWarning) and "chessx_libs.pixelart" in str(x.message) for x in w))
        for n in ["Color", "paint", "PIXEL_FROM", "PIXEL_TO", "PIXEL_TABLE", "SPRITES", "FONT", "render_sprite", "retro_text"]:
            self.assertTrue(hasattr(m, n), n)
        self.assertEqual(m.render_sprite("slime").split("\n")[0], "  ▓▓  ")
        self.assertIn("\033[", m.render_sprite("ghost", force_color=True))
        self.assertEqual(len(m.retro_text("OK").split("\n")), 5)
        self.assertEqual(m.retro_text("I").split("\n")[0], "███")

    def test_interface_package_no_warning(self):
        for k in [k for k in sys.modules if k.startswith("chessx_libs.interface")]:
            sys.modules.pop(k)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from chessx_libs.interface import render_sprite, retro_text, SPRITES, Color, Board  # noqa
        self.assertFalse([x for x in w if issubclass(x.category, DeprecationWarning)])
        self.assertIn("knight", SPRITES); self.assertTrue(retro_text("A"))


if __name__ == "__main__":
    unittest.main()
