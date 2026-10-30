import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.i18n import STRINGS
from chessx_libs.mathx import dispatch


class TestMathI18n(unittest.TestCase):
    def test_keys_all_langs(self):
        for lang in ("en", "pt", "ja"):
            for k in ("math_professor", "math_draw_prompt", "math_check_prompt",
                      "math_calc_prompt", "math_system_prompt", "math_error"):
                self.assertIn(k, STRINGS[lang])

    def test_error_localized(self):
        self.assertTrue(dispatch("math (", "pt").startswith("erro matemático"))
        self.assertTrue(dispatch("math (", "ja").startswith("数学エラー"))
        self.assertTrue(dispatch("math (", "en").startswith("math error"))


if __name__ == "__main__":
    unittest.main()
