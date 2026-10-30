import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sympy as sp
from chessx_libs.mathx import interpret, render, dispatch

x, y, k, n = sp.symbols("x y k n")


def I(t):
    return interpret(t)[1]


class TestAsciiInterpreter(unittest.TestCase):
    def test_fraction(self):
        self.assertEqual(I(" x + 1\n -----\n   2"), (x + 1) / 2)

    def test_superscript(self):
        self.assertEqual(I(" 2\nx  + 3x"), x ** 2 + 3 * x)

    def test_sqrt_ascii(self):
        self.assertEqual(I("  ____\n\\/ x+1"), sp.sqrt(x + 1))

    def test_sqrt_unicode(self):
        self.assertEqual(I(" __\n√2x"), sp.sqrt(2 * x))

    def test_matrix(self):
        self.assertEqual(I("[1  2]\n[3  4]"), sp.Matrix([[1, 2], [3, 4]]))

    def test_matrix_unicode(self):
        self.assertEqual(I("⎡x  1⎤\n⎣0  y⎦"), sp.Matrix([[x, 1], [0, y]]))

    def test_integral_unicode(self):
        self.assertEqual(I("2\n∫ x^2 dx\n0").doit(), sp.Rational(8, 3))

    def test_integral_ascii(self):
        self.assertEqual(I("/2\n| x dx\n/0").doit(), 2)

    def test_sum(self):
        self.assertEqual(I(" n\n Σ  k^2\nk=1"), sp.Sum(k ** 2, (k, 1, n)))

    def test_subscripts(self):
        self.assertEqual(str(I("a  + a\n 1    2")), "a_1 + a_2")

    def test_mixed_fraction_and_power(self):
        self.assertEqual(I("  1       2\n --- + x\n  2"), x ** 2 + sp.Rational(1, 2))

    def test_equation(self):
        e = I("  x^2 - 1\n --------- = 0\n   x + 3")
        self.assertIsInstance(e, sp.Eq)
        self.assertEqual(set(sp.solve(e, x)), {-1, 1})

    def test_nested_fraction(self):
        self.assertEqual(I("  1\n ---\n  x\n-----\n  2"), 1 / (2 * x))   # longest bar is the main one

    def test_roundtrip_render(self):
        e = (x ** 2 - 1) / (x + 3)
        self.assertEqual(sp.simplify(I(render(e)) - e), 0)

    def test_draw_command_multiline(self):
        out = dispatch("draw", read_block=lambda: ["  x^2 - 1", "---------- = 0", "   x + 3"])
        self.assertIn("x = [-1, 1]", out)

    def test_render_command(self):
        self.assertIn("-", dispatch("render (x+1)/2"))


if __name__ == "__main__":
    unittest.main()
